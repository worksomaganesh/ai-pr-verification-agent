"""Explicitly opt-in GitHub Actions workflow dispatch for Phase IV.

The caller must supply a token scoped with actions:write and explicit enablement.
Targets are constrained to an operator-owned workflow allowlist.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import httpx

from verification_core.github_app import GitHubAPIError, _make_http_client

_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9_.-]+\.ya?ml$")
_INPUT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SECRETISH_INPUT_RE = re.compile(
    r"(secret|token|password|private.?key|credential|api.?key|authorization)",
    re.IGNORECASE,
)
_MAX_INPUTS = 10
_MAX_INPUT_VALUE = 1024


class GitHubWorkflowDispatchError(GitHubAPIError):
    """Sanitized error for a rejected or failed workflow dispatch."""


def _valid_repository(repository: str) -> bool:
    if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
        return False
    owner, name = repository.split("/", maxsplit=1)
    return owner not in {".", ".."} and name not in {".", ".."}


def _valid_ref(ref: str) -> bool:
    if not isinstance(ref, str) or not _REF_RE.fullmatch(ref):
        return False
    if ref.startswith(("/", ".")) or ref.endswith(("/", ".", ".lock")):
        return False
    if (
        "//" in ref
        or ".." in ref
        or "@{" in ref
        or any(char in ref for char in ("\\", "~", "^", ":", "?", "*", "[", " "))
    ):
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".") for part in ref.split("/")
    )


class GitHubWorkflowDispatcher:
    """Dispatch an allowlisted workflow only after explicit opt-in.

    The caller supplies a token expected to have actions:write scoped to the intended
    repository. This class does not mint broader credentials automatically.
    """

    def __init__(
        self,
        installation_token: str,
        *,
        allowed_workflows: tuple[str, ...],
        enabled: bool = False,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not isinstance(installation_token, str) or not installation_token.strip():
            raise ValueError("installation_token must not be empty")
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        if not isinstance(allowed_workflows, tuple) or not allowed_workflows:
            raise ValueError("allowed_workflows must be a non-empty tuple")
        if any(
            not isinstance(workflow, str) or not _WORKFLOW_RE.fullmatch(workflow)
            for workflow in allowed_workflows
        ):
            raise ValueError("allowed workflow names must be YAML filenames")
        if len(set(allowed_workflows)) != len(allowed_workflows):
            raise ValueError("allowed_workflows must not contain duplicates")
        self._authorization = f"Bearer {installation_token}"
        self._allowed_workflows = frozenset(allowed_workflows)
        self._enabled = enabled
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None

    def dispatch(
        self,
        *,
        repository: str,
        workflow: str,
        ref: str,
        inputs: Mapping[str, str] | None = None,
    ) -> None:
        """Request one dispatch; reject unsafe/unconfigured requests before network I/O."""
        if not self._enabled:
            raise GitHubWorkflowDispatchError(
                "Workflow dispatch is disabled; explicit operator opt-in is required."
            )
        if not _valid_repository(repository):
            raise ValueError("repository must match owner/name")
        if not isinstance(workflow, str) or workflow not in self._allowed_workflows:
            raise GitHubWorkflowDispatchError("Workflow is not in the configured allowlist.")
        if not _valid_ref(ref):
            raise ValueError("ref must be a safe branch or tag reference")
        if inputs is None:
            normalized: dict[str, str] = {}
        elif not isinstance(inputs, Mapping):
            raise ValueError("inputs must be a mapping of string values")
        else:
            if len(inputs) > _MAX_INPUTS:
                raise ValueError("inputs exceed the configured count limit")
            normalized = {}
            for key, value in inputs.items():
                if (
                    not isinstance(key, str)
                    or not _INPUT_NAME_RE.fullmatch(key)
                    or _SECRETISH_INPUT_RE.search(key)
                ):
                    raise ValueError("input names must be safe and must not carry credentials")
                if not isinstance(value, str) or len(value) > _MAX_INPUT_VALUE:
                    raise ValueError(
                        "input values must be strings within the configured size limit"
                    )
                if any(ord(char) < 32 and char not in "\t" for char in value):
                    raise ValueError("input values must not contain control characters")
                normalized[key] = value

        path = f"/repos/{repository}/actions/workflows/{workflow}/dispatches"
        try:
            with self._client.stream(
                "POST",
                path,
                json={"ref": ref, "inputs": normalized},
                headers={"Authorization": self._authorization},
                follow_redirects=False,
            ) as response:
                if response.status_code != 204:
                    raise GitHubWorkflowDispatchError(
                        "GitHub rejected the workflow dispatch request.",
                        status_code=response.status_code,
                    )
        except GitHubAPIError:
            raise
        except httpx.TimeoutException:
            raise GitHubWorkflowDispatchError("GitHub workflow dispatch timed out.") from None
        except httpx.HTTPError:
            raise GitHubWorkflowDispatchError(
                "GitHub workflow dispatch transport failed."
            ) from None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
