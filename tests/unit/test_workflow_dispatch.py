"""Safety tests for explicit Phase IV workflow dispatch."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from verification_core.workflow_dispatch import (
    GitHubWorkflowDispatcher,
    GitHubWorkflowDispatchError,
    WorkflowInputRule,
)

AUTH_FIXTURE = "example-auth-value"
REPO = "acme/service"
WORKFLOW = "manual-verification.yml"
SCHEMA = {
    WORKFLOW: {
        "pr_number": WorkflowInputRule(required=True, max_length=8, pattern=r"[1-9][0-9]*"),
        "dry_run": WorkflowInputRule(allowed_values=("true", "false")),
    }
}
Handler = Callable[[httpx.Request], httpx.Response]


def make_dispatcher(
    handler: Handler,
    *,
    enabled: bool = True,
    input_schemas: dict[str, dict[str, WorkflowInputRule]] | None = None,
) -> tuple[GitHubWorkflowDispatcher, httpx.Client]:
    raw = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    return GitHubWorkflowDispatcher(
        AUTH_FIXTURE,
        allowed_workflows=(WORKFLOW,),
        input_schemas=SCHEMA if input_schemas is None else input_schemas,
        enabled=enabled,
        http_client=raw,
    ), raw


def test_dispatch_posts_only_allowlisted_workflow_and_schema_valid_inputs() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    dispatcher, raw = make_dispatcher(handler)
    dispatcher.dispatch(
        repository=REPO,
        workflow=WORKFLOW,
        ref="phase-4-staging",
        inputs={"pr_number": "6", "dry_run": "true"},
    )
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path == f"/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
    assert request.headers["Authorization"] == f"Bearer {AUTH_FIXTURE}"
    assert json.loads(request.content) == {
        "ref": "phase-4-staging",
        "inputs": {"pr_number": "6", "dry_run": "true"},
    }
    dispatcher.close()
    raw.close()


def test_dispatch_is_disabled_by_default_and_never_sends_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    dispatcher, raw = make_dispatcher(handler, enabled=False)
    with pytest.raises(GitHubWorkflowDispatchError, match="disabled"):
        dispatcher.dispatch(repository=REPO, workflow=WORKFLOW, ref="main")
    assert seen == []
    dispatcher.close()
    raw.close()


@pytest.mark.parametrize(
    "workflow",
    ["other.yml", "../manual-verification.yml", "manual-verification.yaml"],
)
def test_dispatch_rejects_non_allowlisted_workflow(workflow: str) -> None:
    dispatcher, raw = make_dispatcher(lambda _request: httpx.Response(204))
    with pytest.raises(GitHubWorkflowDispatchError, match="allowlist"):
        dispatcher.dispatch(repository=REPO, workflow=workflow, ref="main")
    dispatcher.close()
    raw.close()


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "../main",
        "/main",
        "main..oops",
        "feature//test",
        "main\\\\evil",
        "refs/heads/../main",
    ],
)
def test_dispatch_rejects_unsafe_refs(ref: str) -> None:
    dispatcher, raw = make_dispatcher(lambda _request: httpx.Response(204))
    with pytest.raises(ValueError, match="safe"):
        dispatcher.dispatch(repository=REPO, workflow=WORKFLOW, ref=ref, inputs={"pr_number": "6"})
    dispatcher.close()
    raw.close()


@pytest.mark.parametrize(
    "inputs",
    [
        {"GITHUB_TOKEN": "no", "pr_number": "6"},
        {"private_key": "no", "pr_number": "6"},
        {"bad key": "no", "pr_number": "6"},
        {"pr_number": 6},
        {"pr_number": "a" * 9},
        {"pr_number": "0"},
        {"pr_number": "6", "dry_run": "yes"},
        {"pr_number": "6", "unexpected": "no"},
        {f"input_{i}": "x" for i in range(11)},
    ],
)
def test_dispatch_rejects_unsafe_or_unconfigured_inputs(inputs: dict[str, Any]) -> None:
    dispatcher, raw = make_dispatcher(lambda _request: httpx.Response(204))
    with pytest.raises(ValueError):
        dispatcher.dispatch(
            repository=REPO,
            workflow=WORKFLOW,
            ref="main",
            inputs=inputs,
        )
    dispatcher.close()
    raw.close()


def test_dispatch_requires_schema_required_inputs_before_network() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    dispatcher, raw = make_dispatcher(handler)
    with pytest.raises(ValueError, match="required"):
        dispatcher.dispatch(repository=REPO, workflow=WORKFLOW, ref="main")
    assert seen == []
    dispatcher.close()
    raw.close()


def test_dispatch_rejects_invalid_repository_before_network() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    dispatcher, raw = make_dispatcher(handler)
    with pytest.raises(ValueError, match="owner/name"):
        dispatcher.dispatch(
            repository="../service",
            workflow=WORKFLOW,
            ref="main",
            inputs={"pr_number": "6"},
        )
    assert seen == []
    dispatcher.close()
    raw.close()


def test_dispatch_sanitizes_github_api_failure() -> None:
    dispatcher, raw = make_dispatcher(
        lambda _request: httpx.Response(403, json={"message": "sensitive body"})
    )
    with pytest.raises(GitHubWorkflowDispatchError, match="rejected") as error:
        dispatcher.dispatch(
            repository=REPO,
            workflow=WORKFLOW,
            ref="main",
            inputs={"pr_number": "6"},
        )
    assert "sensitive body" not in str(error.value)
    dispatcher.close()
    raw.close()


@pytest.mark.parametrize(
    "schemas",
    [
        {},
        {WORKFLOW: {"token": WorkflowInputRule()}},
        {WORKFLOW: {"not-a-rule": "anything"}},
    ],
)
def test_dispatch_configuration_rejects_missing_or_unsafe_schema(schemas: Any) -> None:
    raw = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(204)),
    )
    with pytest.raises(ValueError):
        GitHubWorkflowDispatcher(
            AUTH_FIXTURE,
            allowed_workflows=(WORKFLOW,),
            input_schemas=schemas,
            http_client=raw,
        )
    raw.close()


def test_workflow_input_rule_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="max_length"):
        WorkflowInputRule(max_length=0)
    with pytest.raises(ValueError, match="regular expression"):
        WorkflowInputRule(pattern="[")
    with pytest.raises(ValueError, match="allowed_values"):
        WorkflowInputRule(allowed_values=("ok", "a\nb"))
