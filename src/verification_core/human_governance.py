"""Fail-closed GitHub pull-request approval verification and immutable audit storage.

A human approval is useful only when GitHub reports it for the exact current PR head.
This module keeps reviewer decisions separate from machine-generated evidence and
stores verified approval facts as append-only records.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from verification_core.domain.models import (
    CommitIdentity,
    ConclusionPolicyConfig,
    HumanApprovalRecord,
    VerificationObligation,
)
from verification_core.domain.state_machine import apply_human_approval
from verification_core.github_app import _make_http_client

_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})$")
_ALLOWED_REVIEW_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"})
_MAX_REVIEW_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_REVIEWS = 100
_MIN_RATIONALE_LENGTH = 20
_MAX_RATIONALE_LENGTH = 10_000

_METADATA = MetaData()
_APPROVALS = Table(
    "human_review_approvals",
    _METADATA,
    Column("repository", String(200), primary_key=True),
    Column("pr_number", Integer, primary_key=True),
    Column("review_id", Integer, primary_key=True),
    Column("reviewer_login", String(39), nullable=False),
    Column("base_sha", String(40), nullable=False),
    Column("head_sha", String(40), nullable=False),
    Column("review_state", String(32), nullable=False),
    Column("submitted_at", String(40), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("rationale_sha256", String(64), nullable=False),
    Column("recorded_at", Float, nullable=False),
)


class HumanReviewVerificationError(RuntimeError):
    """GitHub did not establish one or more fresh, allowlisted human approvals."""


class HumanReviewAuditError(RuntimeError):
    """A verified human approval could not be safely recorded or read."""


class HumanReviewAuditConflict(HumanReviewAuditError):
    """A previously recorded GitHub review ID was presented with different content."""


def _validate_repository(repository: str) -> None:
    if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
        raise ValueError("repository must match owner/name")


def _validate_sha(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 40-character commit SHA")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise HumanReviewVerificationError("GitHub returned an invalid review timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HumanReviewVerificationError("GitHub returned an invalid review timestamp.") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HumanReviewVerificationError("GitHub returned a timezone-naive review timestamp.")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class GitHubPullRequestApproval:
    """An allowlisted GitHub approval bound to one exact PR base/head pair."""

    repository: str
    pr_number: int
    review_id: int
    reviewer_login: str
    base_sha: str
    head_sha: str
    submitted_at: datetime
    rationale: str

    def __post_init__(self) -> None:
        _validate_repository(self.repository)
        if type(self.pr_number) is not int or self.pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        if type(self.review_id) is not int or self.review_id < 1:
            raise ValueError("review_id must be a positive integer")
        if not isinstance(self.reviewer_login, str) or not _LOGIN_RE.fullmatch(self.reviewer_login):
            raise ValueError("reviewer_login must be a valid GitHub login")
        _validate_sha(self.base_sha, "base_sha")
        _validate_sha(self.head_sha, "head_sha")
        if not isinstance(self.submitted_at, datetime):
            raise ValueError("submitted_at must be a datetime")
        if self.submitted_at.tzinfo is None or self.submitted_at.utcoffset() is None:
            raise ValueError("submitted_at must be timezone-aware")
        if not isinstance(self.rationale, str):
            raise ValueError("rationale must be text")
        rationale = self.rationale.strip()
        if not _MIN_RATIONALE_LENGTH <= len(rationale) <= _MAX_RATIONALE_LENGTH:
            raise ValueError(
                f"rationale must contain {_MIN_RATIONALE_LENGTH} to "
                f"{_MAX_RATIONALE_LENGTH} non-whitespace characters"
            )

    @property
    def rationale_sha256(self) -> str:
        """Digest of the exact normalized rationale stored in the audit record."""
        return hashlib.sha256(self.rationale.strip().encode("utf-8")).hexdigest()


class GitHubReviewVerifier:
    """Read current PR/review state and return only fresh allowlisted approvals.

    The most recent submitted review by each allowed reviewer is authoritative.
    A later COMMENTED, CHANGES_REQUESTED, or DISMISSED review supersedes an older
    approval. The review must target the exact current head and include a rationale.
    """

    def __init__(
        self,
        *,
        allowed_reviewers: tuple[str, ...],
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not isinstance(allowed_reviewers, tuple) or not allowed_reviewers:
            raise ValueError("allowed_reviewers must be a non-empty tuple")
        if any(
            not isinstance(login, str) or not _LOGIN_RE.fullmatch(login)
            for login in allowed_reviewers
        ):
            raise ValueError("allowed_reviewers contains an invalid GitHub login")
        folded = tuple(login.casefold() for login in allowed_reviewers)
        if len(set(folded)) != len(folded):
            raise ValueError("allowed_reviewers must not contain duplicates")
        self._allowed_reviewers = frozenset(folded)
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None

    def _get_json(
        self,
        path: str,
        *,
        access_token: str,
        params: Mapping[str, str | int] | None = None,
    ) -> object:
        if not path.startswith("/") or path.startswith("//") or ".." in path.split("/"):
            raise HumanReviewVerificationError("Refusing an unsafe GitHub API path.")
        try:
            with self._client.stream(
                "GET",
                path,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                follow_redirects=False,
            ) as response:
                if response.status_code != 200:
                    raise HumanReviewVerificationError(
                        "GitHub could not verify pull-request review metadata."
                    )
                if response.links.get("next") is not None:
                    raise HumanReviewVerificationError(
                        "The pull request has more than 100 reviews; review pagination is "
                        "not supported by this verifier."
                    )
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        if int(length) > _MAX_REVIEW_RESPONSE_BYTES:
                            raise HumanReviewVerificationError(
                                "GitHub review response exceeded the size limit."
                            )
                    except ValueError:
                        raise HumanReviewVerificationError(
                            "GitHub returned an invalid response length."
                        ) from None
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > _MAX_REVIEW_RESPONSE_BYTES:
                        raise HumanReviewVerificationError(
                            "GitHub review response exceeded the size limit."
                        )
                    body.extend(chunk)
        except HumanReviewVerificationError:
            raise
        except httpx.TimeoutException:
            raise HumanReviewVerificationError("GitHub review lookup timed out.") from None
        except httpx.HTTPError:
            raise HumanReviewVerificationError("GitHub review lookup failed.") from None
        try:
            return json.loads(body)
        except (UnicodeDecodeError, ValueError):
            raise HumanReviewVerificationError("GitHub returned malformed review JSON.") from None

    def _read_pr_identity(
        self,
        *,
        access_token: str,
        repository: str,
        pr_number: int,
    ) -> tuple[str, str]:
        repo_path = quote(repository, safe="/")
        payload = self._get_json(
            f"/repos/{repo_path}/pulls/{pr_number}",
            access_token=access_token,
        )
        if not isinstance(payload, Mapping):
            raise HumanReviewVerificationError("GitHub returned malformed pull-request metadata.")
        base = payload.get("base")
        head = payload.get("head")
        if not isinstance(base, Mapping) or not isinstance(head, Mapping):
            raise HumanReviewVerificationError("GitHub returned malformed pull-request identity.")
        base_repo = base.get("repo")
        head_repo = head.get("repo")
        base_sha = base.get("sha")
        head_sha = head.get("sha")
        if (
            payload.get("state") != "open"
            or not isinstance(base_repo, Mapping)
            or base_repo.get("full_name") != repository
            or not isinstance(head_repo, Mapping)
            or head_repo.get("full_name") != repository
        ):
            raise HumanReviewVerificationError(
                "Human approval verification requires an open same-repository pull request."
            )
        if (
            not isinstance(base_sha, str)
            or not _SHA_RE.fullmatch(base_sha)
            or not isinstance(head_sha, str)
            or not _SHA_RE.fullmatch(head_sha)
        ):
            raise HumanReviewVerificationError("GitHub returned invalid pull-request SHAs.")
        return base_sha, head_sha

    def verify_current_approvals(
        self,
        *,
        access_token: str,
        repository: str,
        pr_number: int,
        expected_base_sha: str,
        expected_head_sha: str,
    ) -> tuple[GitHubPullRequestApproval, ...]:
        """Return each configured reviewer's latest approval for this exact open PR head."""
        _validate_repository(repository)
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("access_token must not be empty")
        if type(pr_number) is not int or pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        _validate_sha(expected_base_sha, "expected_base_sha")
        _validate_sha(expected_head_sha, "expected_head_sha")

        base_sha, head_sha = self._read_pr_identity(
            access_token=access_token,
            repository=repository,
            pr_number=pr_number,
        )
        if base_sha != expected_base_sha or head_sha != expected_head_sha:
            raise HumanReviewVerificationError(
                "The pull request base/head changed; prior approval is stale."
            )

        repo_path = quote(repository, safe="/")
        payload = self._get_json(
            f"/repos/{repo_path}/pulls/{pr_number}/reviews",
            access_token=access_token,
            params={"per_page": _MAX_REVIEWS, "page": 1},
        )
        if not isinstance(payload, list) or len(payload) > _MAX_REVIEWS:
            raise HumanReviewVerificationError("GitHub returned a malformed review collection.")

        latest: dict[str, tuple[datetime, int, Mapping[str, Any]]] = {}
        for item in payload:
            if not isinstance(item, Mapping):
                raise HumanReviewVerificationError("GitHub returned a malformed review entry.")
            user = item.get("user")
            login = user.get("login") if isinstance(user, Mapping) else None
            if not isinstance(login, str) or login.casefold() not in self._allowed_reviewers:
                continue
            review_id = item.get("id")
            state = item.get("state")
            commit_id = item.get("commit_id")
            if (
                type(review_id) is not int
                or review_id < 1
                or not isinstance(state, str)
                or state not in _ALLOWED_REVIEW_STATES
                or not isinstance(commit_id, str)
                or not _SHA_RE.fullmatch(commit_id)
            ):
                raise HumanReviewVerificationError(
                    "An allowlisted review contained malformed identity or state metadata."
                )
            submitted_at = _parse_timestamp(item.get("submitted_at"))
            previous = latest.get(login.casefold())
            if previous is None or (submitted_at, review_id) > (previous[0], previous[1]):
                latest[login.casefold()] = (submitted_at, review_id, item)

        approvals: list[GitHubPullRequestApproval] = []
        for _, (submitted_at, review_id, item) in latest.items():
            if item.get("state") != "APPROVED" or item.get("commit_id") != expected_head_sha:
                continue
            user = item.get("user")
            login = user.get("login") if isinstance(user, Mapping) else None
            rationale = item.get("body")
            if not isinstance(login, str) or not isinstance(rationale, str):
                continue
            normalized_rationale = rationale.strip()
            if not _MIN_RATIONALE_LENGTH <= len(normalized_rationale) <= _MAX_RATIONALE_LENGTH:
                continue
            approvals.append(
                GitHubPullRequestApproval(
                    repository=repository,
                    pr_number=pr_number,
                    review_id=review_id,
                    reviewer_login=login,
                    base_sha=expected_base_sha,
                    head_sha=expected_head_sha,
                    submitted_at=submitted_at,
                    rationale=normalized_rationale,
                )
            )

        final_base, final_head = self._read_pr_identity(
            access_token=access_token,
            repository=repository,
            pr_number=pr_number,
        )
        if final_base != expected_base_sha or final_head != expected_head_sha:
            raise HumanReviewVerificationError(
                "The pull request changed during review verification; approval is stale."
            )
        return tuple(
            sorted(approvals, key=lambda approval: (approval.submitted_at, approval.review_id))
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class SQLAlchemyHumanReviewAuditLog:
    """Append-only storage for verified GitHub approvals; records are never updated."""

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 5,
    ) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database_url must not be empty")
        if type(pool_size) is not int or not 1 <= pool_size <= 50:
            raise ValueError("pool_size must be between 1 and 50")
        if type(max_overflow) is not int or not 0 <= max_overflow <= 100:
            raise ValueError("max_overflow must be between 0 and 100")
        try:
            if database_url.startswith("sqlite:///"):
                self._engine: Engine = create_engine(
                    database_url,
                    connect_args={"check_same_thread": False},
                    pool_pre_ping=True,
                )
            else:
                self._engine = create_engine(
                    database_url,
                    pool_pre_ping=True,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                )
            _METADATA.create_all(self._engine)
        except SQLAlchemyError:
            raise HumanReviewAuditError(
                "Could not initialize the human-review audit database."
            ) from None

    def record_approval(
        self,
        approval: GitHubPullRequestApproval,
        *,
        now: float,
    ) -> bool:
        """Insert an immutable approval. Return False for an identical replay."""
        if not isinstance(approval, GitHubPullRequestApproval):
            raise ValueError("approval must be a verified GitHubPullRequestApproval")
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError("now must be a finite, non-negative timestamp")
        submitted_at = approval.submitted_at.astimezone(UTC).isoformat()
        values: dict[str, object] = {
            "repository": approval.repository,
            "pr_number": approval.pr_number,
            "review_id": approval.review_id,
            "reviewer_login": approval.reviewer_login,
            "base_sha": approval.base_sha,
            "head_sha": approval.head_sha,
            "review_state": "APPROVED",
            "submitted_at": submitted_at,
            "rationale": approval.rationale.strip(),
            "rationale_sha256": approval.rationale_sha256,
            "recorded_at": float(now),
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(_APPROVALS).values(**values))
            return True
        except IntegrityError:
            existing = self.get_approval(
                approval.repository, approval.pr_number, approval.review_id
            )
            if existing is not None and all(
                existing[field] == values[field]
                for field in (
                    "reviewer_login",
                    "base_sha",
                    "head_sha",
                    "review_state",
                    "submitted_at",
                    "rationale",
                    "rationale_sha256",
                )
            ):
                return False
            raise HumanReviewAuditConflict(
                "A GitHub review ID already exists with different approval content."
            ) from None
        except SQLAlchemyError:
            raise HumanReviewAuditError(
                "Could not persist the human-review audit record."
            ) from None

    def get_approval(
        self, repository: str, pr_number: int, review_id: int
    ) -> dict[str, object] | None:
        _validate_repository(repository)
        if type(pr_number) is not int or pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        if type(review_id) is not int or review_id < 1:
            raise ValueError("review_id must be a positive integer")
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        select(_APPROVALS).where(
                            _APPROVALS.c.repository == repository,
                            _APPROVALS.c.pr_number == pr_number,
                            _APPROVALS.c.review_id == review_id,
                        )
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else dict(row)
        except SQLAlchemyError:
            raise HumanReviewAuditError("Could not read the human-review audit record.") from None

    def list_approvals(
        self,
        repository: str,
        pr_number: int,
        head_sha: str,
    ) -> tuple[dict[str, object], ...]:
        _validate_repository(repository)
        if type(pr_number) is not int or pr_number < 1:
            raise ValueError("pr_number must be a positive integer")
        _validate_sha(head_sha, "head_sha")
        try:
            with self._engine.connect() as connection:
                rows = (
                    connection.execute(
                        select(_APPROVALS)
                        .where(
                            _APPROVALS.c.repository == repository,
                            _APPROVALS.c.pr_number == pr_number,
                            _APPROVALS.c.head_sha == head_sha,
                        )
                        .order_by(_APPROVALS.c.submitted_at, _APPROVALS.c.review_id)
                    )
                    .mappings()
                    .all()
                )
                return tuple(dict(row) for row in rows)
        except SQLAlchemyError:
            raise HumanReviewAuditError("Could not list human-review audit records.") from None

    def close(self) -> None:
        self._engine.dispose()



def apply_verified_human_approval(
    obligation: VerificationObligation,
    *,
    approval: GitHubPullRequestApproval,
    expected_commit: CommitIdentity,
    audit_log: SQLAlchemyHumanReviewAuditLog,
    now: float,
    policy_config: ConclusionPolicyConfig = ConclusionPolicyConfig(),
) -> VerificationObligation:
    """Apply a verified GitHub review to one obligation and persist its audit first.

    Repository, PR number, base SHA, and head SHA must all match the commit under
    evaluation. The domain state machine remains authoritative for transition and
    severity policy; the audit insert must succeed before the approved state is
    returned to the caller.
    """
    if (
        approval.repository != expected_commit.repo_full_name
        or approval.pr_number != expected_commit.pr_number
        or approval.base_sha != expected_commit.base_sha
        or approval.head_sha != expected_commit.head_sha
    ):
        raise HumanReviewVerificationError(
            "Verified review repository, PR, base, or head does not match the evaluated commit."
        )

    domain_record = HumanApprovalRecord(
        reviewer_login=approval.reviewer_login,
        review_id=approval.review_id,
        approved_head_sha=approval.head_sha,
        rationale=approval.rationale,
        approved_at=approval.submitted_at,
    )
    approved_obligation = apply_human_approval(
        obligation,
        approval=domain_record,
        expected_commit=expected_commit,
        policy_config=policy_config,
    )
    audit_log.record_approval(approval, now=now)
    return approved_obligation
