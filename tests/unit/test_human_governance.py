"""Tests for exact-head human approval verification and append-only audit."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from verification_core.human_governance import (
    GitHubReviewVerifier,
    GitHubPullRequestApproval,
    HumanReviewAuditConflict,
    HumanReviewVerificationError,
    SQLAlchemyHumanReviewAuditLog,
)

REPO = "acme/service"
PR = 7
BASE = "1" * 40
HEAD = "2" * 40
OTHER = "3" * 40
TOKEN = "example-review-token"
REVIEWER = "reviewer"


def review(
    *,
    review_id: int = 101,
    login: str = REVIEWER,
    state: str = "APPROVED",
    sha: str = HEAD,
    submitted: str = "2026-11-04T10:00:00Z",
    body: str = "Reviewed security boundaries and exact-head test evidence carefully.",
) -> dict[str, Any]:
    return {
        "id": review_id,
        "user": {"login": login},
        "state": state,
        "commit_id": sha,
        "submitted_at": submitted,
        "body": body,
    }


def transport(
    *,
    base: str = BASE,
    head: str = HEAD,
    reviews: list[Any] | None = None,
    state: str = "open",
    review_status: int = 200,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/repos/{REPO}/pulls/{PR}":
            return httpx.Response(
                200,
                json={
                    "state": state,
                    "base": {"sha": base, "repo": {"full_name": REPO}},
                    "head": {"sha": head, "repo": {"full_name": REPO}},
                },
            )
        if request.url.path == f"/repos/{REPO}/pulls/{PR}/reviews":
            return httpx.Response(review_status, json=reviews or [])
        return httpx.Response(404, json={"message": "not found"})

    return httpx.MockTransport(handler)


def verifier(
    mock: httpx.MockTransport, allow: tuple[str, ...] = (REVIEWER,)
) -> GitHubReviewVerifier:
    client = httpx.Client(base_url="https://api.github.com", transport=mock)
    return GitHubReviewVerifier(allowed_reviewers=allow, http_client=client)


def verify(
    v: GitHubReviewVerifier, *, base: str = BASE, head: str = HEAD
) -> tuple[GitHubPullRequestApproval, ...]:
    return v.verify_current_approvals(
        access_token=TOKEN,
        repository=REPO,
        pr_number=PR,
        expected_base_sha=base,
        expected_head_sha=head,
    )


def test_verifier_returns_allowlisted_approval_bound_to_exact_head() -> None:
    v = verifier(transport(reviews=[review()]))
    result = verify(v)
    assert len(result) == 1
    approval = result[0]
    assert approval.reviewer_login == REVIEWER
    assert approval.review_id == 101
    assert approval.head_sha == HEAD and approval.base_sha == BASE
    assert approval.rationale.startswith("Reviewed security")
    assert len(approval.rationale_sha256) == 64


@pytest.mark.parametrize("state", ["COMMENTED", "CHANGES_REQUESTED", "DISMISSED"])
def test_latest_nonapproval_supersedes_older_approval(state: str) -> None:
    v = verifier(
        transport(
            reviews=[
                review(review_id=100, submitted="2026-11-04T09:00:00Z"),
                review(review_id=101, state=state, submitted="2026-11-04T10:00:00Z"),
            ]
        )
    )
    assert verify(v) == ()


def test_older_approval_does_not_override_later_changes_requested() -> None:
    v = verifier(
        transport(
            reviews=[
                review(review_id=101, state="CHANGES_REQUESTED", submitted="2026-11-04T10:00:00Z"),
                review(review_id=100, submitted="2026-11-04T09:00:00Z"),
            ]
        )
    )
    assert verify(v) == ()


def test_nonallowlisted_reviewers_are_ignored() -> None:
    v = verifier(transport(reviews=[review(login="other-user")]))
    assert verify(v) == ()


def test_approval_for_an_old_commit_is_not_current_approval() -> None:
    v = verifier(transport(reviews=[review(sha=OTHER)]))
    assert verify(v) == ()


def test_stale_expected_head_is_rejected_before_review_acceptance() -> None:
    v = verifier(transport(head=OTHER, reviews=[review()]))
    with pytest.raises(HumanReviewVerificationError, match="changed"):
        verify(v)


def test_closed_or_fork_pr_is_not_accepted() -> None:
    v = verifier(transport(state="closed", reviews=[review()]))
    with pytest.raises(HumanReviewVerificationError, match="open same-repository"):
        verify(v)


@pytest.mark.parametrize("submitted", ["bad-time", "2026-11-04T10:00:00"])
def test_malformed_allowlisted_review_timestamp_fails_closed(submitted: str) -> None:
    v = verifier(transport(reviews=[review(submitted=submitted)]))
    with pytest.raises(HumanReviewVerificationError, match="timestamp"):
        verify(v)


@pytest.mark.parametrize("body", ["", "too short"])
def test_approval_without_minimum_rationale_is_not_accepted(body: str) -> None:
    v = verifier(transport(reviews=[review(body=body)]))
    assert verify(v) == ()


def test_malformed_review_collection_fails_closed() -> None:
    v = verifier(transport(reviews=None))
    v._client.close()
    with pytest.raises(HumanReviewVerificationError, match="collection"):
        verify(v)


def test_github_review_api_failure_is_fail_closed() -> None:
    v = verifier(transport(review_status=403))
    with pytest.raises(HumanReviewVerificationError, match="could not verify"):
        verify(v)


def make_approval(
    *,
    review_id: int = 101,
    rationale: str = "Reviewed security boundaries and exact-head test evidence carefully.",
) -> GitHubPullRequestApproval:
    return GitHubPullRequestApproval(
        repository=REPO,
        pr_number=PR,
        review_id=review_id,
        reviewer_login=REVIEWER,
        base_sha=BASE,
        head_sha=HEAD,
        submitted_at=datetime(2026, 11, 4, 10, 0, tzinfo=UTC),
        rationale=rationale,
    )


def test_audit_is_append_only_idempotent_and_digest_bound(tmp_path: Path) -> None:
    log = SQLAlchemyHumanReviewAuditLog(f"sqlite:///{tmp_path / 'reviews.sqlite3'}")
    approval = make_approval()
    assert log.record_approval(approval, now=100)
    assert not log.record_approval(approval, now=101)
    record = log.get_approval(REPO, PR, 101)
    assert record is not None
    assert record["head_sha"] == HEAD
    assert record["rationale_sha256"] == approval.rationale_sha256
    assert record["recorded_at"] == 100
    assert len(log.list_approvals(REPO, PR, HEAD)) == 1
    assert log.list_approvals(REPO, PR, OTHER) == ()
    log.close()


def test_audit_rejects_review_id_with_conflicting_content(tmp_path: Path) -> None:
    log = SQLAlchemyHumanReviewAuditLog(f"sqlite:///{tmp_path / 'reviews.sqlite3'}")
    log.record_approval(make_approval(), now=100)
    with pytest.raises(HumanReviewAuditConflict, match="different approval"):
        log.record_approval(
            make_approval(
                rationale="A materially different review rationale for this same ID."
            ),
            now=101,
        )
    log.close()


@pytest.mark.parametrize("bad_now", [float("nan"), float("inf"), -1, True])
def test_audit_rejects_invalid_record_timestamp(tmp_path: Path, bad_now: float) -> None:
    log = SQLAlchemyHumanReviewAuditLog(f"sqlite:///{tmp_path / 'reviews.sqlite3'}")
    with pytest.raises(ValueError, match="finite"):
        log.record_approval(make_approval(), now=bad_now)
    log.close()


def test_approval_model_rejects_naive_timestamp_and_short_rationale() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        GitHubPullRequestApproval(
            repository=REPO,
            pr_number=PR,
            review_id=101,
            reviewer_login=REVIEWER,
            base_sha=BASE,
            head_sha=HEAD,
            submitted_at=datetime(2026, 11, 4),
            rationale="Reviewed security boundaries and exact-head test evidence carefully.",
        )
    with pytest.raises(ValueError, match="rationale"):
        make_approval(rationale="short")
