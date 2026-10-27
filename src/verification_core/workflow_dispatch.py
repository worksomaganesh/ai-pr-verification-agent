"""Explicitly opt-in GitHub Actions workflow dispatch for Phase IV.

The caller must supply a token scoped with actions:write and explicit enablement.
Targets and their accepted inputs are constrained by operator-owned configuration.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class WorkflowInputRule:
    """Operator-owned constraint for one named workflow_dispatch input."""

    required: bool = False
    max_length: int = _MAX_INPUT_VALUE
    pattern: str | None = None
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.required) is not bool:
            raise ValueError("required must be a boolean")
        if type(self.max_length) is not int or not 1 <= self.max_length <= _MAX_INPUT_VALUE:
            raise ValueError("max_length must be between 1 and 1024")
        if self.pattern is not None:
            if not isinstance(self.pattern, str) or not self.pattern:
                raise ValueError("pattern must be a non-empty regular expression")
            try:
                re.compile(self.pattern)
            except re.error:
                raise ValueError("pattern must be a valid regular expression") from None
        if not isinstance(self.allowed_values, tuple):
            raise ValueError("allowed_values must be a tuple")
        if any(
            not isinstance(value, str)
            or len(value) > self.max_length
            or any(ord(char) < 32 and char not in "\t" for char in value)
            for value in self.allowed_values
        ):
            raise ValueError("allowed_values must contain bounded, printable strings")
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("allowed_values must not contain duplicates")


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
    repository. Every allowlisted workflow must also have an explicit input schema;
    an empty schema deliberately means that workflow accepts no inputs. This class
    does not mint broader credentials automatically.
    """

    def __init__(
        self,
        installation_token: str,
        *,
        allowed_workflows: tuple[str, ...],
        input_schemas: Mapping[str, Mapping[str, WorkflowInputRule]],
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
        if not isinstance(input_schemas, Mapping) or set(input_schemas) != set(allowed_workflows):
            raise ValueError("input_schemas must define exactly every allowlisted workflow")

        normalized_schemas: dict[str, dict[str, WorkflowInputRule]] = {}
        for workflow, schema in input_schemas.items():
            if not isinstance(schema, Mapping) or len(schema) > _MAX_INPUTS:
                raise ValueError("each workflow schema must define at most 10 inputs")
            normalized_schema: dict[str, WorkflowInputRule] = {}
            for name, rule in schema.items():
                if (
                    not isinstance(name, str)
                    or not _INPUT_NAME_RE.fullmatch(name)
                    or _SECRETISH_INPUT_RE.search(name)
                ):
                    raise ValueError("schema input names must be safe and must not carry credentials")
                if not isinstance(rule, WorkflowInputRule):
                    raise ValueError("each schema entry must use WorkflowInputRule")
                normalized_schema[name] = rule
            normalized_schemas[workflow] = normalized_schema

        self._authorization = f"Bearer {installation_token}"
        self._allowed_workflows = frozenset(allowed_workflows)
        self._input_schemas = normalized_schemas
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
        schema = self._input_schemas[workflow]
        if inputs is None:
            supplied: Mapping[str, str] = {}
        elif not isinstance(inputs, Mapping):
            raise ValueError("inputs must be a mapping of string values")
        else:
            supplied = inputs
            if len(supplied) > _MAX_INPUTS:
                raise ValueError("inputs exceed the configured count limit")

        normalized: dict[str, str] = {}
        for key, value in supplied.items():
            if (
                not isinstance(key, str)
                or not _INPUT_NAME_RE.fullmatch(key)
                or _SECRETISH_INPUT_RE.search(key)
            ):
                raise ValueError("input names must be safe and must not carry credentials")
            if key not in schema:
                raise ValueError("input name is not configured for this workflow")
            rule = schema[key]
            if not isinstance(value, str) or len(value) > rule.max_length:
                raise ValueError("input value violates the configured workflow schema")
            if any(ord(char) < 32 and char not in "\t" for char in value):
                raise ValueError("input values must not contain control characters")
            if rule.pattern is not None and re.fullmatch(rule.pattern, value) is None:
                raise ValueError("input value violates the configured workflow schema")
            if rule.allowed_values and value not in rule.allowed_values:
                raise ValueError("input value violates the configured workflow schema")
            normalized[key] = value

        missing = [name for name, rule in schema.items() if rule.required and name not in normalized]
        if missing:
            raise ValueError("required workflow inputs are missing")

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
