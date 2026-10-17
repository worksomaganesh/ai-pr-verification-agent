"""Tests for exact-SHA, fail-closed read-only GitHub context assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, cast

import pytest

from verification_core.github_context import (
    GitHubContextError,
    PullRequestContext,
    assemble_pull_request_context,
)
from verification_core.planning import DiffLimits
from verification_core.webhooks import PullRequestWebhookEvent

BASE = "1" * 40
HEAD = "2" * 40
POLICY = """version: 1
trusted_workflows:
  - .github/workflows/ci.yml
runner_profiles:
  - pytest_targeted
severity_rules:
  critical:
    blocking: true
    human_approval_allowed: true
  high:
    blocking: true
    human_approval_allowed: true
  medium:
    blocking: false
    human_approval_allowed: true
  low:
    blocking: false
    human_approval_allowed: true
harness_sensitive_paths:
  - .verification-policy.yml
  - .github/workflows/
  - conftest.py
  - pytest.ini
  - pyproject.toml
  - package.json
obligations:
  - id: OBL-AUTH-01
    category: authorization
    severity: critical
    claim: A user cannot read another user's subscription.
    runner_profile: pytest_targeted
    selector: tests/test_authz.py::test_cross_user_access_returns_403
"""


def event() -> PullRequestWebhookEvent:
    return PullRequestWebhookEvent(
        delivery_id="delivery-123",
        action="opened",
        repository_full_name="acme/service",
        pr_number=12,
        base_sha=BASE,
        head_sha=HEAD,
        base_ref="main",
        head_ref="feature/security",
    )


def changed_file(
    filename: str = "src/authz.py",
    *,
    patch: str | None = "@@ -1 +1 @@\n-old\n+new",
    additions: int = 1,
    deletions: int = 1,
    status: str = "modified",
) -> dict[str, object]:
    return {
        "filename": filename,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "patch": patch,
    }


class FakeGitHub:
    def __init__(
        self,
        *,
        base_sha: str = BASE,
        head_sha: str = HEAD,
        base_ref: str = "main",
        state: str = "open",
        policy_text: str | None = POLICY,
        pages: Sequence[Sequence[Mapping[str, Any]]] | None = None,
    ) -> None:
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.base_ref = base_ref
        self.state = state
        self.policy_text = policy_text
        self.pages = list(pages or [[changed_file()]])
        self.policy_reads: list[tuple[str, str, str]] = []
        self.page_reads: list[int] = []

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]:
        assert repository == "acme/service"
        assert pr_number == 12
        return {
            "state": self.state,
            "base": {"sha": self.base_sha, "ref": self.base_ref},
            "head": {"sha": self.head_sha},
        }

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        self.policy_reads.append((repository, path, ref))
        return self.policy_text

    def list_pull_request_files(
        self, repository: str, pr_number: int, *, page: int, per_page: int
    ) -> Sequence[Mapping[str, Any]]:
        assert repository == "acme/service"
        assert pr_number == 12
        self.page_reads.append(page)
        if page > len(self.pages):
            return []
        return self.pages[page - 1]


def test_context_binds_policy_and_files_to_exact_base_and_head() -> None:
    client = FakeGitHub()
    context = assemble_pull_request_context(event(), client)
    assert context.commit.repo_full_name == "acme/service"
    assert context.commit.pr_number == 12
    assert context.commit.base_sha == BASE
    assert context.commit.head_sha == HEAD
    assert context.policy_source_ref == BASE
    assert context.commit.policy_sha256
    assert len(context.commit.policy_sha256) == 64
    assert context.changed_files[0].filename == "src/authz.py"
    assert context.files_complete
    assert client.policy_reads == [("acme/service", ".verification-policy.yml", BASE)]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"base_sha": "3" * 40}, "stale"),
        ({"head_sha": "3" * 40}, "stale"),
        ({"base_ref": "release"}, "stale"),
        ({"state": "closed"}, "no longer open"),
    ],
)
def test_stale_or_closed_pr_fails_closed(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(GitHubContextError, match=message):
        assemble_pull_request_context(event(), FakeGitHub(**kwargs))


def test_missing_policy_is_not_replaced_with_defaults() -> None:
    with pytest.raises(GitHubContextError, match=r"no \.verification-policy\.yml"):
        assemble_pull_request_context(event(), FakeGitHub(policy_text=None))


def test_invalid_policy_fails_closed() -> None:
    with pytest.raises(GitHubContextError, match="policy is invalid"):
        assemble_pull_request_context(event(), FakeGitHub(policy_text="version: 999"))


def test_policy_path_cannot_be_overridden_to_head_or_arbitrary_file() -> None:
    with pytest.raises(GitHubContextError, match="canonical"):
        assemble_pull_request_context(event(), FakeGitHub(), policy_path="README.md")


def test_all_changed_file_pages_are_consumed() -> None:
    client = FakeGitHub(
        pages=[
            [changed_file("src/one.py")],
            [changed_file("src/two.py")],
            [],
        ]
    )
    context = assemble_pull_request_context(event(), client, files_per_page=1)
    assert [file.filename for file in context.changed_files] == ["src/one.py", "src/two.py"]
    assert context.pages_read == 3
    assert client.page_reads == [1, 2, 3]


def test_duplicate_changed_paths_are_rejected() -> None:
    client = FakeGitHub(pages=[[changed_file("src/same.py"), changed_file("src/same.py")]])
    with pytest.raises(GitHubContextError, match="Duplicate"):
        assemble_pull_request_context(event(), client)


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"filename": "src/a.py"}, "status"),
        ({**changed_file(), "additions": True}, "additions"),
        ({**changed_file(), "deletions": -1}, "deletions"),
        ({**changed_file(), "patch": 123}, "patch"),
        ({**changed_file(), "filename": "../secret.py"}, "filename"),
    ],
)
def test_malformed_changed_file_record_is_rejected(record: dict[str, object], message: str) -> None:
    client = FakeGitHub(pages=[[record]])
    with pytest.raises((GitHubContextError, ValueError), match=message):
        assemble_pull_request_context(event(), client)


def test_non_sequence_page_is_rejected() -> None:
    class BadPageClient(FakeGitHub):
        def list_pull_request_files(
            self, repository: str, pr_number: int, *, page: int, per_page: int
        ) -> Sequence[Mapping[str, Any]]:
            return "not-a-list"  # type: ignore[return-value]

    with pytest.raises(GitHubContextError, match="sequence"):
        assemble_pull_request_context(event(), BadPageClient())


def test_excessive_pagination_fails_closed() -> None:
    client = FakeGitHub(pages=[[changed_file(f"src/{index}.py")] for index in range(30)])
    with pytest.raises(GitHubContextError, match="page limit"):
        assemble_pull_request_context(event(), client, files_per_page=1)


@pytest.mark.parametrize("files_per_page", [0, 101, True])
def test_invalid_page_size_fails_closed(files_per_page: int) -> None:
    with pytest.raises(GitHubContextError, match="files_per_page"):
        assemble_pull_request_context(event(), FakeGitHub(), files_per_page=files_per_page)


def test_context_invariants_reject_wrong_policy_ref_and_incomplete_files() -> None:
    context = assemble_pull_request_context(event(), FakeGitHub())
    with pytest.raises(GitHubContextError, match="exact base SHA"):
        replace(context, policy_source_ref=HEAD)
    with pytest.raises(GitHubContextError, match="cannot be marked complete"):
        replace(context, files_complete=False)
    with pytest.raises(GitHubContextError, match="At least one"):
        replace(context, pages_read=0)


def test_non_mapping_pull_request_response_is_rejected() -> None:
    class BadPullRequestClient(FakeGitHub):
        def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]:
            return None  # type: ignore[return-value]

    with pytest.raises(GitHubContextError, match="pull_request must be an object"):
        assemble_pull_request_context(event(), BadPullRequestClient())


def test_non_text_policy_response_is_rejected() -> None:
    class BadPolicyClient(FakeGitHub):
        def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
            return cast(str, b"not text")

    with pytest.raises(GitHubContextError, match="decoded UTF-8 text"):
        assemble_pull_request_context(event(), BadPolicyClient())


def test_changed_file_count_limit_fails_closed() -> None:
    client = FakeGitHub(
        pages=[[changed_file("src/one.py"), changed_file("src/two.py")]]
    )
    limits = DiffLimits(
        max_input_files=1,
        max_files=1,
        max_changed_lines_per_file=100,
        max_patch_chars_per_file=100,
        max_total_patch_chars=100,
    )
    with pytest.raises(GitHubContextError, match="input limit"):
        assemble_pull_request_context(event(), client, diff_limits=limits)


def test_empty_changed_file_inventory_fails_closed() -> None:
    with pytest.raises(GitHubContextError, match="No changed files"):
        assemble_pull_request_context(event(), FakeGitHub(pages=[[]]))


def test_non_boolean_binary_metadata_is_rejected() -> None:
    client = FakeGitHub(pages=[[{**changed_file(), "is_binary": "false"}]])
    with pytest.raises(GitHubContextError, match="is_binary"):
        assemble_pull_request_context(event(), client)


def test_non_mapping_changed_file_record_is_rejected() -> None:
    client = FakeGitHub(pages=[["not-an-object"]])  # type: ignore[list-item]
    with pytest.raises(GitHubContextError, match="string keys"):
        assemble_pull_request_context(event(), client)
