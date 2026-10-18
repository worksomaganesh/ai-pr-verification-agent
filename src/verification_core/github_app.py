"""GitHub App authentication, read-only REST context access, and Check Run publishing.

The control plane uses short-lived installation tokens. This module never executes
repository code and never follows redirects from the GitHub API host.
"""

from __future__ import annotations

import ast
import base64
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from verification_core.github_context import (
    MAX_FILES_API_PAGES,
    GitHubContextError,
    GitHubReadClient,
)
from verification_core.planning import InventoryEntry
from verification_core.policy import MAX_POLICY_BYTES, validate_test_selector
from verification_core.security import scrub_secrets

GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MAX_JSON_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_POLICY_RESPONSE_BYTES = 512 * 1024
_MAX_TEST_SOURCE_BYTES = 256 * 1024
_MAX_TREE_RESPONSE_BYTES = 12 * 1024 * 1024
_MAX_TEST_FILES = 50


class GitHubAPIError(RuntimeError):
    """Sanitized error from a GitHub API request."""

    def __init__(
        self, message: str, *, status_code: int | None = None, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class GitHubRateLimitError(GitHubAPIError):
    """GitHub rate limit or secondary rate limit requires delayed retry."""


class GitHubResponseTooLarge(GitHubAPIError):
    """GitHub response exceeded the configured streaming size bound."""


@dataclass(frozen=True, slots=True)
class InstallationToken:
    """Short-lived token returned by GitHub for one App installation."""

    token: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.token or not self.token.strip():
            raise ValueError("installation token must not be empty")
        if self.expires_at.tzinfo is None:
            raise ValueError("token expiry must be timezone-aware")


def _make_http_client(timeout_seconds: float = 8.0) -> httpx.Client:
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise ValueError("timeout_seconds must be between 0 and 60")
    return httpx.Client(
        base_url=GITHUB_API_URL,
        timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0)),
        follow_redirects=False,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "ai-pr-verification-agent/0.1",
        },
    )


def _read_limited(response: httpx.Response, maximum_bytes: int) -> bytes:
    length = response.headers.get("Content-Length")
    if length is not None:
        try:
            if int(length) > maximum_bytes:
                raise GitHubResponseTooLarge("GitHub API response exceeded the size limit.")
        except ValueError:
            raise GitHubAPIError("GitHub API returned an invalid Content-Length header.") from None

    body = bytearray()
    for chunk in response.iter_bytes():
        if len(body) + len(chunk) > maximum_bytes:
            raise GitHubResponseTooLarge("GitHub API response exceeded the size limit.")
        body.extend(chunk)
    return bytes(body)


def _request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    params: Mapping[str, str | int] | None = None,
    json_body: Mapping[str, object] | None = None,
    authorization: str,
    max_bytes: int = _MAX_JSON_RESPONSE_BYTES,
) -> object:
    if not path.startswith("/") or path.startswith("//") or ".." in PurePosixPath(path).parts:
        raise GitHubAPIError("Refusing an unsafe GitHub API path.")
    headers = {"Authorization": authorization}
    try:
        with client.stream(
            method, path, params=params, json=json_body, headers=headers
        ) as response:
            if response.status_code in (403, 429):
                retry_after = response.headers.get("Retry-After")
                remaining = response.headers.get("X-RateLimit-Remaining")
                if response.status_code == 429 or retry_after is not None or remaining == "0":
                    parsed_retry = (
                        int(retry_after) if retry_after and retry_after.isdigit() else None
                    )
                    raise GitHubRateLimitError(
                        "GitHub API rate limit reached.",
                        status_code=response.status_code,
                        retry_after=parsed_retry,
                    )
            if response.status_code < 200 or response.status_code >= 300:
                message = (
                    "GitHub API authentication failed."
                    if response.status_code in (401, 403)
                    else "GitHub API request failed."
                )
                raise GitHubAPIError(message, status_code=response.status_code)
            raw = _read_limited(response, max_bytes)
    except GitHubAPIError:
        raise
    except httpx.TimeoutException:
        raise GitHubAPIError("GitHub API request timed out.") from None
    except httpx.HTTPError:
        raise GitHubAPIError("GitHub API transport failed.") from None

    try:
        return json.loads(raw)
    except ValueError:
        raise GitHubAPIError("GitHub API returned malformed JSON.") from None


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise GitHubAPIError(f"GitHub API field {field} was malformed.")
    return value


def _repository_path(path: str) -> str:
    if (
        not isinstance(path, str)
        or not path
        or len(path) > 1000
        or path.startswith("-")
        or "\\" in path
        or any(ord(char) < 32 or ord(char) == 127 for char in path)
        or PurePosixPath(path).is_absolute()
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise GitHubAPIError("Refusing an unsafe repository file path.")
    return path


class GitHubAppAuthenticator:
    """Mint App JWTs and exchange them for short-lived installation access tokens."""

    def __init__(
        self,
        app_id: int,
        private_key_pem: str,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if type(app_id) is not int or app_id < 1:
            raise ValueError("app_id must be a positive integer")
        if not isinstance(private_key_pem, str) or "PRIVATE KEY" not in private_key_pem:
            raise ValueError("private_key_pem must contain a PEM private key")
        self._app_id = app_id
        self._private_key_pem = private_key_pem
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None

    def create_app_jwt(self, *, now: int | None = None) -> str:
        """Create a short-lived RS256 JWT for GitHub App authentication."""
        current = int(time.time()) if now is None else now
        if type(current) is not int or current < 1:
            raise ValueError("now must be a positive Unix timestamp")
        try:
            token = jwt.encode(
                {"iat": current - 30, "exp": current + 540, "iss": self._app_id},
                self._private_key_pem,
                algorithm="RS256",
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            raise GitHubAPIError("GitHub App private key could not sign an App JWT.") from None
        if not isinstance(token, str):
            raise GitHubAPIError("GitHub App JWT encoder returned an invalid token.")
        return token

    def create_installation_token(self, installation_id: int) -> InstallationToken:
        """Exchange an App JWT for one installation token; never log or persist the token."""
        if type(installation_id) is not int or installation_id < 1:
            raise ValueError("installation_id must be a positive integer")
        payload = _request_json(
            self._client,
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            json_body={
                "permissions": {
                    "contents": "read",
                    "pull_requests": "read",
                    "checks": "write",
                }
            },
            authorization=f"Bearer {self.create_app_jwt()}",
        )
        data = _mapping(payload, "installation token response")
        token = data.get("token")
        expiry = data.get("expires_at")
        if not isinstance(token, str) or not token or not isinstance(expiry, str):
            raise GitHubAPIError("GitHub returned an invalid installation-token response.")
        try:
            expires_at = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError:
            raise GitHubAPIError("GitHub returned an invalid token expiry.") from None
        return InstallationToken(token=token, expires_at=expires_at)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class GitHubRESTClient(GitHubReadClient):
    """Installation-token client for the minimum read-only planning API surface."""

    def __init__(
        self,
        installation_token: str,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not isinstance(installation_token, str) or not installation_token.strip():
            raise ValueError("installation_token must not be empty")
        self._authorization = f"Bearer {installation_token}"
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None

    @staticmethod
    def _repo(repository: str) -> str:
        if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
            raise GitHubAPIError("Repository must match owner/name.")
        return quote(repository, safe="/")

    def _get(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        max_bytes: int = _MAX_JSON_RESPONSE_BYTES,
    ) -> object:
        return _request_json(
            self._client,
            "GET",
            path,
            params=params,
            authorization=self._authorization,
            max_bytes=max_bytes,
        )

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]:
        if type(pr_number) is not int or pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        result = self._get(f"/repos/{self._repo(repository)}/pulls/{pr_number}")
        return _mapping(result, "pull request")

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        safe_path = _repository_path(path)
        if not isinstance(ref, str) or not _SHA_RE.fullmatch(ref):
            raise GitHubAPIError("Content ref must be an exact 40-character commit SHA.")
        try:
            result = self._get(
                f"/repos/{self._repo(repository)}/contents/{quote(safe_path, safe='/')}",
                params={"ref": ref},
                max_bytes=_MAX_POLICY_RESPONSE_BYTES + 4096,
            )
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                return None
            raise
        data = _mapping(result, "content response")
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise GitHubAPIError("GitHub content response was not a base64 encoded file.")
        encoded = data.get("content")
        if (
            not isinstance(encoded, str)
            or len(encoded) > ((_MAX_POLICY_RESPONSE_BYTES + 2) // 3) * 4 + 4096
        ):
            raise GitHubResponseTooLarge("GitHub file content exceeded the configured size limit.")
        try:
            raw = base64.b64decode("".join(encoded.split()), validate=True)
            text = raw.decode("utf-8")
        except ValueError:
            raise GitHubAPIError("GitHub file content was not valid base64 UTF-8.") from None
        max_content = (
            MAX_POLICY_BYTES if safe_path == ".verification-policy.yml" else _MAX_TEST_SOURCE_BYTES
        )
        if len(raw) > max_content:
            raise GitHubResponseTooLarge("GitHub file content exceeded the configured size limit.")
        return text

    def list_pull_request_files(
        self, repository: str, pr_number: int, *, page: int, per_page: int
    ) -> Sequence[Mapping[str, Any]]:
        if type(pr_number) is not int or pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        if type(page) is not int or not 1 <= page <= MAX_FILES_API_PAGES:
            raise ValueError("page is outside the configured pagination limit")
        if type(per_page) is not int or not 1 <= per_page <= 100:
            raise ValueError("per_page must be between 1 and 100")
        result = self._get(
            f"/repos/{self._repo(repository)}/pulls/{pr_number}/files",
            params={"page": page, "per_page": per_page},
        )
        if not isinstance(result, list):
            raise GitHubAPIError("GitHub changed-file response was not a list.")
        records: list[Mapping[str, Any]] = []
        for item in result:
            records.append(_mapping(item, "changed file"))
        return tuple(records)

    def list_test_inventory(self, repository: str, head_sha: str) -> tuple[InventoryEntry, ...]:
        """Parse bounded test-file ASTs at the PR head; never import or execute PR code."""
        if not _SHA_RE.fullmatch(head_sha):
            raise GitHubAPIError("Test inventory ref must be an exact commit SHA.")
        commit_payload = _mapping(
            self._get(f"/repos/{self._repo(repository)}/git/commits/{head_sha}"),
            "git commit",
        )
        tree_record = _mapping(commit_payload.get("tree"), "git commit tree")
        tree_sha = tree_record.get("sha")
        if not isinstance(tree_sha, str) or not _SHA_RE.fullmatch(tree_sha):
            raise GitHubAPIError("GitHub commit response did not contain a valid tree SHA.")
        result = self._get(
            f"/repos/{self._repo(repository)}/git/trees/{tree_sha}",
            params={"recursive": 1},
            max_bytes=_MAX_TREE_RESPONSE_BYTES,
        )
        tree_payload = _mapping(result, "git tree")
        if tree_payload.get("truncated") is not False:
            raise GitHubAPIError("Git tree response was truncated; test inventory is incomplete.")
        tree = tree_payload.get("tree")
        if not isinstance(tree, list):
            raise GitHubAPIError("Git tree response did not contain a file list.")
        paths: list[str] = []
        for item in tree:
            entry = _mapping(item, "tree entry")
            path_value = entry.get("path")
            if not isinstance(path_value, str):
                continue
            pure = PurePosixPath(path_value)
            if (
                pure.suffix == ".py"
                and path_value.startswith("tests/")
                and (pure.name.startswith("test_") or pure.name.endswith("_test.py"))
            ):
                paths.append(path_value)
        paths.sort()
        if len(paths) > _MAX_TEST_FILES:
            raise GitHubAPIError(
                "Test inventory exceeded the configured file limit; inventory is incomplete."
            )

        entries: list[InventoryEntry] = []
        for path in paths:
            source = self.get_file_content(repository, path, head_sha)
            if source is None:
                continue
            if len(source.encode("utf-8")) > _MAX_TEST_SOURCE_BYTES:
                continue
            try:
                module = ast.parse(source, filename=path)
            except SyntaxError:
                continue
            for node in module.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        selector = f"{path}::{node.name}"
                        try:
                            entries.append(
                                InventoryEntry(selector=validate_test_selector(selector), path=path)
                            )
                        except ValueError:
                            continue
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith("Test"):
                        continue
                    for member in node.body:
                        if isinstance(
                            member, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ) and member.name.startswith("test_"):
                            selector = f"{path}::{node.name}::{member.name}"
                            try:
                                entries.append(
                                    InventoryEntry(selector=validate_test_selector(selector), path=path)
                                )
                            except ValueError:
                                continue
        unique = {entry.selector: entry for entry in entries}
        return tuple(unique[key] for key in sorted(unique))

    def publish_check_run(
        self,
        *,
        repository: str,
        head_sha: str,
        name: str,
        conclusion: str,
        title: str,
        summary: str,
        external_id: str,
        details_url: str | None = None,
    ) -> int:
        """Idempotently create/update the named check for one SHA using an external ID."""
        if not _SHA_RE.fullmatch(head_sha):
            raise ValueError("head_sha must be a lowercase 40-character SHA")
        if conclusion not in {
            "success", "neutral", "action_required", "failure", "cancelled", "timed_out", "skipped"
        }:
            raise ValueError("unsupported GitHub Check Run conclusion")
        safe_title = scrub_secrets(title)[:255]
        safe_summary = scrub_secrets(summary)[:60_000]
        safe_external_id = scrub_secrets(external_id)[:255]
        check_path = f"/repos/{self._repo(repository)}/commits/{head_sha}/check-runs"
        existing = self._get(
            check_path,
            params={"check_name": name, "per_page": 100},
        )
        data = _mapping(existing, "check run listing")
        runs = data.get("check_runs")
        if not isinstance(runs, list):
            raise GitHubAPIError("GitHub Check Run listing was malformed.")
        check_id: int | None = None
        for value in runs:
            item = _mapping(value, "check run")
            if item.get("external_id") == safe_external_id and type(item.get("id")) is int:
                check_id = item["id"]
                break

        body: dict[str, object] = {
            "name": name,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "external_id": safe_external_id,
            "output": {"title": safe_title, "summary": safe_summary},
        }
        if details_url is not None:
            body["details_url"] = details_url
        path = f"/repos/{self._repo(repository)}/check-runs"
        if check_id is None:
            result = _request_json(
                self._client,
                "POST",
                path,
                json_body=body,
                authorization=self._authorization,
            )
        else:
            result = _request_json(
                self._client,
                "PATCH",
                f"{path}/{check_id}",
                json_body=body,
                authorization=self._authorization,
            )
        response = _mapping(result, "check run response")
        identifier = response.get("id")
        if type(identifier) is not int or identifier < 1:
            raise GitHubAPIError("GitHub returned an invalid Check Run identifier.")
        return identifier

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
