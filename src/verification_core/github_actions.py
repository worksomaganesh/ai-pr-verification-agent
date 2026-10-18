"""Authenticated GitHub Actions metadata and bounded artifact downloads for Phase III."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx

from verification_core.github_app import (
    GitHubAPIError,
    GitHubResponseTooLarge,
    _make_http_client,
    _mapping,
    _read_limited,
    _request_json,
)

MAX_ACTIONS_API_PAGES = 10
_MAX_PAGE_SIZE = 100
_MAX_ACTIONS_ITEMS = MAX_ACTIONS_API_PAGES * _MAX_PAGE_SIZE
MAX_ARTIFACT_ARCHIVE_BYTES = 20 * 1024 * 1024
_ALLOWED_DOWNLOAD_SUFFIXES = (".blob.core.windows.net", ".githubusercontent.com")
_ALLOWED_DOWNLOAD_HOSTS = {
    "blob.core.windows.net",
    "pipelines.actions.githubusercontent.com",
}


class GitHubActionsAPIError(GitHubAPIError):
    """Sanitized error for GitHub Actions run, job, or artifact access."""


def _positive_id(value: int, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _repository(repository: str) -> str:
    if not isinstance(repository, str):
        raise GitHubActionsAPIError("Repository must match owner/name.")
    pieces = repository.split("/")
    if (
        len(pieces) != 2
        or not all(pieces)
        or any(part in {".", ".."} for part in pieces)
        or any(char in repository for char in "\\?#")
        or any(ord(char) < 32 or ord(char) == 127 for char in repository)
    ):
        raise GitHubActionsAPIError("Repository must match owner/name.")
    return repository


def _artifact_redirect_is_allowed(url: str) -> bool:
    """Allow HTTPS signed-URL hosts used for artifact blobs; never forward App auth."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or not parsed.path.startswith("/")
    ):
        return False
    host = hostname.lower()
    return host in _ALLOWED_DOWNLOAD_HOSTS or any(
        host.endswith(suffix) for suffix in _ALLOWED_DOWNLOAD_SUFFIXES
    )


class GitHubActionsClient:
    """Read run/job/artifact metadata from GitHub and download bounded artifact ZIPs.

    All metadata requests use the installation token. A signed artifact download URL is
    followed at most once and only when its HTTPS hostname is on a narrow storage allowlist.
    The installation token is never forwarded to that external host.
    """

    def __init__(
        self,
        installation_token: str,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
        max_archive_bytes: int = MAX_ARTIFACT_ARCHIVE_BYTES,
    ) -> None:
        if not isinstance(installation_token, str) or not installation_token.strip():
            raise ValueError("installation_token must not be empty")
        if (
            type(max_archive_bytes) is not int
            or not 1 <= max_archive_bytes <= MAX_ARTIFACT_ARCHIVE_BYTES
        ):
            raise ValueError("max_archive_bytes must be within the configured artifact limit")
        self._authorization = f"Bearer {installation_token}"
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None
        self._max_archive_bytes = max_archive_bytes

    @staticmethod
    def _repo(repository: str) -> str:
        return _repository(repository)

    def _get(
        self, path: str, *, params: Mapping[str, str | int] | None = None
    ) -> Mapping[str, object]:
        value = _request_json(
            self._client,
            "GET",
            path,
            params=params,
            authorization=self._authorization,
        )
        return _mapping(value, "GitHub Actions response")

    def get_workflow_run(self, repository: str, run_id: int) -> Mapping[str, object]:
        """Retrieve a single run from GitHub's Actions API, not from a webhook payload."""
        repo = self._repo(repository)
        _positive_id(run_id, "run_id")
        result = self._get(f"/repos/{repo}/actions/runs/{run_id}")
        if result.get("id") != run_id:
            raise GitHubActionsAPIError(
                "GitHub Actions run response did not match the requested ID."
            )
        return result

    def _list_paginated(
        self,
        *,
        repository: str,
        run_id: int,
        resource: str,
        collection_key: str,
    ) -> tuple[Mapping[str, object], ...]:
        repo = self._repo(repository)
        _positive_id(run_id, "run_id")
        if resource not in {"jobs", "artifacts"}:
            raise ValueError("unsupported Actions resource")
        collected: list[Mapping[str, object]] = []
        seen_ids: set[int] = set()
        expected_total: int | None = None
        for page in range(1, MAX_ACTIONS_API_PAGES + 1):
            result = self._get(
                f"/repos/{repo}/actions/runs/{run_id}/{resource}",
                params={"per_page": _MAX_PAGE_SIZE, "page": page},
            )
            total = result.get("total_count")
            if type(total) is not int or total < 0:
                raise GitHubActionsAPIError("GitHub Actions response had an invalid total_count.")
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise GitHubActionsAPIError("GitHub Actions pagination changed during retrieval.")
            raw_items = result.get(collection_key)
            if not isinstance(raw_items, list):
                raise GitHubActionsAPIError(
                    f"GitHub Actions response field {collection_key!r} was malformed."
                )
            if len(raw_items) > _MAX_PAGE_SIZE:
                raise GitHubActionsAPIError("GitHub Actions returned more items than requested.")
            for item in raw_items:
                record = _mapping(item, f"Actions {resource} item")
                identifier = record.get("id")
                if type(identifier) is not int or identifier < 1:
                    raise GitHubActionsAPIError(
                        f"GitHub Actions {resource} item has an invalid identifier."
                    )
                if identifier in seen_ids:
                    raise GitHubActionsAPIError(
                        f"GitHub Actions {resource} pagination returned duplicate identifiers."
                    )
                seen_ids.add(identifier)
                collected.append(record)
            if len(collected) > _MAX_ACTIONS_ITEMS:
                raise GitHubActionsAPIError(
                    "GitHub Actions result exceeds the configured item limit."
                )
            if len(collected) >= expected_total:
                if len(collected) != expected_total:
                    raise GitHubActionsAPIError(
                        "GitHub Actions pagination returned duplicate or excess items."
                    )
                return tuple(collected)
            if not raw_items and len(collected) < expected_total:
                raise GitHubActionsAPIError(
                    "GitHub Actions pagination ended before all items were retrieved."
                )
        raise GitHubActionsAPIError(
            "GitHub Actions pagination limit reached; result is incomplete."
        )

    def list_workflow_run_jobs(
        self, repository: str, run_id: int
    ) -> tuple[Mapping[str, object], ...]:
        """Retrieve every job record for a run, rejecting silently truncated pagination."""
        return self._list_paginated(
            repository=repository,
            run_id=run_id,
            resource="jobs",
            collection_key="jobs",
        )

    def list_workflow_run_artifacts(
        self, repository: str, run_id: int
    ) -> tuple[Mapping[str, object], ...]:
        """Retrieve every artifact metadata record and bind each one to the requested run."""
        artifacts = self._list_paginated(
            repository=repository,
            run_id=run_id,
            resource="artifacts",
            collection_key="artifacts",
        )
        for artifact in artifacts:
            workflow_run = artifact.get("workflow_run")
            run = _mapping(workflow_run, "artifact workflow_run")
            if run.get("id") != run_id:
                raise GitHubActionsAPIError(
                    "Artifact metadata was not bound to the requested workflow run."
                )
        return artifacts

    def download_workflow_artifact(self, repository: str, artifact_id: int) -> bytes:
        """Download one ZIP artifact with host validation and streaming byte limits."""
        repo = self._repo(repository)
        _positive_id(artifact_id, "artifact_id")
        path = f"/repos/{repo}/actions/artifacts/{artifact_id}/zip"
        try:
            with self._client.stream(
                "GET",
                path,
                headers={"Authorization": self._authorization},
                follow_redirects=False,
            ) as response:
                if response.status_code == 200:
                    return _read_limited(response, self._max_archive_bytes)
                if response.status_code not in {301, 302, 303, 307, 308}:
                    if response.status_code in {403, 429}:
                        raise GitHubActionsAPIError(
                            "GitHub rejected the Actions artifact download.",
                            status_code=response.status_code,
                        )
                    raise GitHubActionsAPIError(
                        "GitHub Actions artifact download failed.",
                        status_code=response.status_code,
                    )
                location = response.headers.get("Location")
                if not location or not _artifact_redirect_is_allowed(location):
                    raise GitHubActionsAPIError(
                        "GitHub returned an artifact redirect to a disallowed host."
                    )
            # The external signed URL is a bearer capability in its own right. Do not copy
            # the GitHub installation Authorization header to it and do not follow redirects.
            with self._client.stream("GET", location, follow_redirects=False) as download:
                if download.status_code != 200:
                    raise GitHubActionsAPIError("The signed artifact download failed.")
                return _read_limited(download, self._max_archive_bytes)
        except GitHubAPIError:
            raise
        except httpx.TimeoutException:
            raise GitHubActionsAPIError("GitHub Actions artifact download timed out.") from None
        except httpx.HTTPError:
            raise GitHubActionsAPIError("GitHub Actions artifact transport failed.") from None
        except GitHubResponseTooLarge:
            raise

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
