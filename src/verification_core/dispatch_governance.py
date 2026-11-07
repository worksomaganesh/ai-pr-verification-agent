"""Operator authorization, write-ahead audit, and exact-SHA dispatch reconciliation."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import (
    Column,
    Float,
    BigInteger,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from verification_core.delivery_store import DeliveryStoreError
from verification_core.github_app import GitHubAPIError, _make_http_client, _request_json
from verification_core.workflow_dispatch import (
    GitHubWorkflowDispatchError,
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9_.-]+\.ya?ml$")
_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})$")
_PERMISSION_LEVELS = frozenset({"admin", "maintain", "write"})
CORRELATION_INPUT = "verification_dispatch_id"
RUN_NAME_PREFIX = "verification-dispatch:"

_METADATA = MetaData()
_DISPATCHES = Table(
    "workflow_dispatch_audit",
    _METADATA,
    Column("dispatch_id", String(32), primary_key=True),
    Column("repository", String(200), nullable=False),
    Column("workflow", String(128), nullable=False),
    Column("ref", String(255), nullable=False),
    Column("expected_head_sha", String(40), nullable=False),
    Column("inputs_sha256", String(64), nullable=False),
    Column("operator_login", String(39), nullable=False),
    Column("operator_permission", String(20), nullable=False),
    Column("state", String(40), nullable=False),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    Column("workflow_run_id", BigInteger, nullable=True),
    Column("observed_head_sha", String(40), nullable=True),
    Column("failure_code", String(80), nullable=True),
)


class DispatchAuthorizationError(RuntimeError):
    """GitHub did not establish an allowlisted operator with write permission."""


class DispatchAuditError(DeliveryStoreError):
    """A dispatch audit record could not be safely persisted or transitioned."""


class DuplicateDispatchError(DispatchAuditError):
    """A dispatch identifier was already used and cannot cause another dispatch."""


class DispatchReconciliationError(RuntimeError):
    """GitHub workflow-run metadata did not identify one safe matching run."""


class ExactHeadMismatchError(DispatchReconciliationError):
    """The dispatched workflow ran against a commit other than the authorized SHA."""


@dataclass(frozen=True, slots=True)
class GitHubOperator:
    """Identity and repository permission reported by GitHub for the user token."""

    login: str
    permission: str


class OperatorAuthenticator(Protocol):
    """Resolve a GitHub user access token to a verified operator."""

    def authenticate(self, access_token: str, repository: str) -> GitHubOperator: ...


class WorkflowDispatcher(Protocol):
    """Minimal transport port; dispatch implementation remains separately allowlisted."""

    def dispatch(
        self,
        *,
        repository: str,
        workflow: str,
        ref: str,
        inputs: Mapping[str, str] | None = None,
    ) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    """Accepted dispatch receipt; it is not a test or verification result."""

    dispatch_id: str
    repository: str
    workflow: str
    expected_head_sha: str
    operator_login: str
    state: str


@dataclass(frozen=True, slots=True)
class WorkflowRunObservation:
    """Workflow-run identity obtained from GitHub's Actions API."""

    run_id: int
    head_sha: str
    head_branch: str
    created_at: float


class GitHubOperatorAuthenticator:
    """Require an allowlisted GitHub login and write-capable repository permission.

    The supplied user token is not retained. It must have sufficient GitHub scopes
    for GET /user, repository collaborator-permission lookup, and Actions write.
    A username allowlist supplements GitHub repository ACLs; it does not replace them.
    """

    def __init__(
        self,
        *,
        allowed_logins: tuple[str, ...],
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not isinstance(allowed_logins, tuple) or not allowed_logins:
            raise ValueError("allowed_logins must be a non-empty tuple")
        if any(
            not isinstance(name, str) or not _LOGIN_RE.fullmatch(name) for name in allowed_logins
        ):
            raise ValueError("allowed_logins contains an invalid GitHub login")
        folded = tuple(name.casefold() for name in allowed_logins)
        if len(set(folded)) != len(folded):
            raise ValueError("allowed_logins must not contain duplicates")
        self._allowed_logins = frozenset(folded)
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None

    def authenticate(self, access_token: str, repository: str) -> GitHubOperator:
        _validate_repository(repository)
        if not isinstance(access_token, str) or not access_token.strip():
            raise DispatchAuthorizationError("A GitHub user access token is required.")
        owner, name = repository.split("/", maxsplit=1)
        headers_token = f"Bearer {access_token}"
        try:
            identity = _request_json(self._client, "GET", "/user", authorization=headers_token)
            if not isinstance(identity, Mapping):
                raise DispatchAuthorizationError("GitHub returned invalid user identity.")
            login = identity.get("login")
            if not isinstance(login, str) or not _LOGIN_RE.fullmatch(login):
                raise DispatchAuthorizationError("GitHub returned invalid user identity.")
            if login.casefold() not in self._allowed_logins:
                raise DispatchAuthorizationError("This GitHub account is not an allowed operator.")
            path = (
                f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
                f"/collaborators/{quote(login, safe='')}/permission"
            )
            permission_data = _request_json(self._client, "GET", path, authorization=headers_token)
            if not isinstance(permission_data, Mapping):
                raise DispatchAuthorizationError("GitHub returned invalid repository permissions.")
            permission = permission_data.get("permission")
            if not isinstance(permission, str) or permission not in _PERMISSION_LEVELS:
                raise DispatchAuthorizationError(
                    "The operator needs write, maintain, or admin access to the repository."
                )
            return GitHubOperator(login=login, permission=permission)
        except DispatchAuthorizationError:
            raise
        except GitHubAPIError:
            raise DispatchAuthorizationError(
                "GitHub could not authenticate or authorize this operator."
            ) from None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class SQLAlchemyDispatchAuditLog:
    """Durable SQLite/PostgreSQL write-ahead log without raw inputs or credentials."""

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 5,
    ) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database_url must not be empty")
        if not database_url.startswith(("postgresql+psycopg://", "sqlite:///")):
            raise ValueError("database_url must use postgresql+psycopg:// or sqlite:///")
        if type(pool_size) is not int or not 1 <= pool_size <= 50:
            raise ValueError("pool_size must be between 1 and 50")
        if type(max_overflow) is not int or not 0 <= max_overflow <= 100:
            raise ValueError("max_overflow must be between 0 and 100")
        try:
            if database_url.startswith("sqlite:///"):
                self._engine = create_engine(
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
            raise DispatchAuditError("Could not initialize the dispatch audit database.") from None

    def record_authorized(
        self,
        *,
        dispatch_id: str,
        repository: str,
        workflow: str,
        ref: str,
        expected_head_sha: str,
        inputs_sha256: str,
        operator: GitHubOperator,
        now: float,
    ) -> None:
        """Insert intent before network I/O. A repeated ID always blocks re-dispatch."""
        _validate_dispatch_id(dispatch_id)
        _validate_repository(repository)
        _validate_workflow(workflow)
        _validate_sha(expected_head_sha, "expected_head_sha")
        if not re.fullmatch(r"[0-9a-f]{64}", inputs_sha256):
            raise ValueError("inputs_sha256 must be a SHA-256 hex digest")
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError("now must be a finite, non-negative timestamp")
        values: dict[str, object] = {
            "dispatch_id": dispatch_id,
            "repository": repository,
            "workflow": workflow,
            "ref": ref,
            "expected_head_sha": expected_head_sha,
            "inputs_sha256": inputs_sha256,
            "operator_login": operator.login,
            "operator_permission": operator.permission,
            "state": "authorized",
            "created_at": float(now),
            "updated_at": float(now),
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(_DISPATCHES).values(**values))
        except IntegrityError:
            raise DuplicateDispatchError(
                "This dispatch identifier was already recorded; inspect its audit state "
                "instead of retrying."
            ) from None
        except SQLAlchemyError:
            raise DispatchAuditError("Could not write the dispatch authorization record.") from None

    def _transition(
        self,
        dispatch_id: str,
        *,
        states: tuple[str, ...],
        changes: Mapping[str, object],
    ) -> None:
        _validate_dispatch_id(dispatch_id)
        try:
            with self._engine.begin() as connection:
                result = connection.execute(
                    update(_DISPATCHES)
                    .where(
                        _DISPATCHES.c.dispatch_id == dispatch_id,
                        _DISPATCHES.c.state.in_(states),
                    )
                    .values(**dict(changes))
                )
                if result.rowcount != 1:
                    raise DispatchAuditError(
                        "The dispatch audit record is missing or has an invalid state transition."
                    )
        except SQLAlchemyError:
            raise DispatchAuditError("Could not update the dispatch audit record.") from None

    def mark_submitted(self, dispatch_id: str, *, now: float) -> None:
        self._transition(
            dispatch_id,
            states=("authorized",),
            changes={"state": "submitted_unreconciled", "updated_at": now},
        )

    def mark_rejected(self, dispatch_id: str, *, now: float) -> None:
        self._transition(
            dispatch_id,
            states=("authorized",),
            changes={
                "state": "rejected",
                "failure_code": "dispatch_request_rejected",
                "updated_at": now,
            },
        )

    def mark_outcome_unknown(self, dispatch_id: str, *, now: float) -> None:
        self._transition(
            dispatch_id,
            states=("authorized",),
            changes={
                "state": "dispatch_outcome_unknown",
                "failure_code": "dispatch_response_not_confirmed",
                "updated_at": now,
            },
        )

    def mark_head_mismatch(
        self, dispatch_id: str, *, run_id: int, observed_sha: str, now: float
    ) -> None:
        _validate_sha(observed_sha, "observed_sha")
        self._transition(
            dispatch_id,
            states=("submitted_unreconciled",),
            changes={
                "state": "head_mismatch",
                "workflow_run_id": run_id,
                "observed_head_sha": observed_sha,
                "failure_code": "workflow_head_did_not_match_expected_sha",
                "updated_at": now,
            },
        )

    def mark_reconciled(
        self, dispatch_id: str, *, run_id: int, observed_sha: str, now: float
    ) -> None:
        _validate_sha(observed_sha, "observed_sha")
        record = self.get_dispatch(dispatch_id)
        if record is None:
            raise DispatchAuditError("The dispatch audit record does not exist.")
        if record["expected_head_sha"] != observed_sha:
            self.mark_head_mismatch(dispatch_id, run_id=run_id, observed_sha=observed_sha, now=now)
            raise ExactHeadMismatchError(
                "The workflow run SHA does not match the authorized commit."
            )
        self._transition(
            dispatch_id,
            states=("submitted_unreconciled",),
            changes={
                "state": "reconciled",
                "workflow_run_id": run_id,
                "observed_head_sha": observed_sha,
                "updated_at": now,
            },
        )

    def get_dispatch(self, dispatch_id: str) -> dict[str, object] | None:
        _validate_dispatch_id(dispatch_id)
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        select(_DISPATCHES).where(_DISPATCHES.c.dispatch_id == dispatch_id)
                    )
                    .mappings()
                    .first()
                )
                return None if row is None else dict(row)
        except SQLAlchemyError:
            raise DispatchAuditError("Could not read the dispatch audit record.") from None

    def close(self) -> None:
        self._engine.dispose()


class GitHubWorkflowRunVerifier:
    """Find one run from a complete, bounded page matching workflow, event, marker, actor, and time.

    Each workflow must set its Actions run-name to
    'verification-dispatch:<input verification_dispatch_id>'. The Actions inputs
    schema must declare verification_dispatch_id. A dispatch is not accepted as
    reconciled until the resulting run is independently found through GitHub's API.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._client = http_client or _make_http_client(timeout_seconds)
        self._owns_client = http_client is None

    def find_dispatch_run(
        self,
        *,
        access_token: str,
        repository: str,
        workflow: str,
        dispatch_id: str,
        operator_login: str,
        created_after: float,
    ) -> WorkflowRunObservation | None:
        _validate_dispatch_id(dispatch_id)
        _validate_repository(repository)
        _validate_workflow(workflow)
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("access_token must not be empty")
        if (
            type(created_after) not in (int, float)
            or not math.isfinite(created_after)
            or created_after < 0
        ):
            raise ValueError("created_after must be a finite, non-negative timestamp")
        repo_path = quote(repository, safe="/")
        authorization = f"Bearer {access_token}"
        try:
            workflow_data = _request_json(
                self._client,
                "GET",
                f"/repos/{repo_path}/actions/workflows/{quote(workflow, safe='')}",
                authorization=authorization,
            )
            if not isinstance(workflow_data, Mapping):
                raise DispatchReconciliationError("GitHub returned invalid workflow metadata.")
            workflow_id = workflow_data.get("id")
            if type(workflow_id) is not int or workflow_id < 1:
                raise DispatchReconciliationError("GitHub returned an invalid workflow identifier.")
            try:
                created_filter = datetime.fromtimestamp(created_after, UTC).isoformat()
            except (OverflowError, OSError, ValueError):
                raise DispatchReconciliationError(
                    "The dispatch creation timestamp is outside the supported range."
                ) from None
            runs_data = _request_json(
                self._client,
                "GET",
                f"/repos/{repo_path}/actions/workflows/{workflow_id}/runs",
                params={
                    "event": "workflow_dispatch",
                    "per_page": 100,
                    "created": f">={created_filter}",
                },
                authorization=authorization,
            )
            if not isinstance(runs_data, Mapping):
                raise DispatchReconciliationError("GitHub returned invalid workflow-run metadata.")
            workflow_runs = runs_data.get("workflow_runs")
            total_count = runs_data.get("total_count")
            if (
                not isinstance(workflow_runs, list)
                or type(total_count) is not int
                or total_count < 0
                or total_count > 100
                or len(workflow_runs) != total_count
            ):
                raise DispatchReconciliationError(
                    "GitHub returned an incomplete or over-limit workflow-run page."
                )
            marker = f"{RUN_NAME_PREFIX}{dispatch_id}"
            matches: list[Mapping[str, object]] = []
            for candidate in workflow_runs:
                if not isinstance(candidate, Mapping):
                    raise DispatchReconciliationError(
                        "GitHub returned an invalid workflow-run entry."
                    )
                actor = candidate.get("actor")
                login = actor.get("login") if isinstance(actor, Mapping) else None
                if (
                    type(candidate.get("workflow_id")) is int
                    and candidate.get("workflow_id") == workflow_id
                    and candidate.get("event") == "workflow_dispatch"
                    and candidate.get("display_title") == marker
                    and isinstance(login, str)
                    and login.casefold() == operator_login.casefold()
                ):
                    matches.append(candidate)
            if not matches:
                return None
            if len(matches) != 1:
                raise DispatchReconciliationError(
                    "Multiple workflow runs matched one dispatch identifier."
                )
            run = matches[0]
            run_id = run.get("id")
            head_sha = run.get("head_sha")
            branch = run.get("head_branch")
            created_at = run.get("created_at")
            if (
                type(run_id) is not int
                or run_id < 1
                or not isinstance(head_sha, str)
                or not _SHA_RE.fullmatch(head_sha)
                or not isinstance(branch, str)
                or not isinstance(created_at, str)
            ):
                raise DispatchReconciliationError("The matching workflow run was malformed.")
            try:
                parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if parsed_created_at.tzinfo is None or parsed_created_at.utcoffset() is None:
                    raise ValueError("workflow-run timestamp must include a timezone")
                timestamp = parsed_created_at.timestamp()
            except ValueError:
                raise DispatchReconciliationError(
                    "The matching workflow run has an invalid timestamp."
                ) from None
            if timestamp < created_after:
                return None
            return WorkflowRunObservation(run_id, head_sha, branch, timestamp)
        except GitHubAPIError:
            raise DispatchReconciliationError(
                "GitHub could not verify workflow-run metadata."
            ) from None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class WorkflowDispatchCoordinator:
    """Authorize, write-ahead audit, dispatch once, then reconcile an exact SHA."""

    def __init__(
        self,
        *,
        authenticator: OperatorAuthenticator,
        audit_log: SQLAlchemyDispatchAuditLog,
        dispatcher_factory: Callable[[str], WorkflowDispatcher],
        run_verifier: GitHubWorkflowRunVerifier,
    ) -> None:
        self._authenticator = authenticator
        self._audit_log = audit_log
        self._dispatcher_factory = dispatcher_factory
        self._run_verifier = run_verifier

    def dispatch(
        self,
        *,
        access_token: str,
        dispatch_id: str,
        repository: str,
        workflow: str,
        ref: str,
        expected_head_sha: str,
        inputs: Mapping[str, str],
        now: float | None = None,
    ) -> DispatchReceipt:
        _validate_dispatch_id(dispatch_id)
        _validate_repository(repository)
        _validate_workflow(workflow)
        _validate_sha(expected_head_sha, "expected_head_sha")
        if not isinstance(ref, str) or not ref or len(ref) > 255:
            raise ValueError("ref must be a non-empty bounded git ref")
        if not isinstance(inputs, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in inputs.items()
        ):
            raise ValueError("inputs must map strings to strings")
        if CORRELATION_INPUT in inputs:
            raise ValueError(f"{CORRELATION_INPUT} is reserved for dispatch correlation")
        dispatch_inputs = dict(inputs)
        dispatch_inputs[CORRELATION_INPUT] = dispatch_id
        if len(dispatch_inputs) > 10:
            raise ValueError("inputs exceed the 10-field limit after correlation input is added")
        digest = hashlib.sha256(
            json.dumps(dispatch_inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        operator = self._authenticator.authenticate(access_token, repository)
        timestamp = time.time() if now is None else now
        self._audit_log.record_authorized(
            dispatch_id=dispatch_id,
            repository=repository,
            workflow=workflow,
            ref=ref,
            expected_head_sha=expected_head_sha,
            inputs_sha256=digest,
            operator=operator,
            now=timestamp,
        )
        dispatcher: WorkflowDispatcher | None = None
        try:
            dispatcher = self._dispatcher_factory(access_token)
            dispatcher.dispatch(
                repository=repository,
                workflow=workflow,
                ref=ref,
                inputs=dispatch_inputs,
            )
            # Record confirmed submission before client cleanup can raise.
            self._audit_log.mark_submitted(
                dispatch_id, now=time.time() if now is None else timestamp
            )
        except GitHubWorkflowDispatchError as exc:
            if exc.status_code is not None and exc.status_code < 500:
                self._audit_log.mark_rejected(dispatch_id, now=timestamp)
            else:
                self._audit_log.mark_outcome_unknown(dispatch_id, now=timestamp)
            raise
        except Exception:
            self._audit_log.mark_outcome_unknown(dispatch_id, now=timestamp)
            raise
        finally:
            if dispatcher is not None:
                dispatcher.close()
        return DispatchReceipt(
            dispatch_id,
            repository,
            workflow,
            expected_head_sha,
            operator.login,
            "submitted_unreconciled",
        )

    def reconcile(
        self, *, access_token: str, dispatch_id: str, now: float | None = None
    ) -> DispatchReceipt | None:
        _validate_dispatch_id(dispatch_id)
        record = self._audit_log.get_dispatch(dispatch_id)
        if record is None:
            raise DispatchAuditError("The dispatch audit record does not exist.")
        if record["state"] != "submitted_unreconciled":
            raise DispatchAuditError("Only submitted, unreconciled dispatches may be reconciled.")
        repository = str(record["repository"])
        operator = self._authenticator.authenticate(access_token, repository)
        if operator.login.casefold() != str(record["operator_login"]).casefold():
            raise DispatchAuthorizationError(
                "Only the operator who authorized the dispatch may reconcile it."
            )
        created_at = record["created_at"]
        if (
            not isinstance(created_at, (int, float))
            or isinstance(created_at, bool)
            or created_at < 0
        ):
            raise DispatchAuditError("The dispatch audit record has an invalid creation timestamp.")
        observation = self._run_verifier.find_dispatch_run(
            access_token=access_token,
            repository=repository,
            workflow=str(record["workflow"]),
            dispatch_id=dispatch_id,
            operator_login=operator.login,
            created_after=float(created_at),
        )
        if observation is None:
            return None
        timestamp = time.time() if now is None else now
        expected_sha = str(record["expected_head_sha"])
        if observation.head_sha != expected_sha:
            self._audit_log.mark_head_mismatch(
                dispatch_id,
                run_id=observation.run_id,
                observed_sha=observation.head_sha,
                now=timestamp,
            )
            raise ExactHeadMismatchError(
                "The workflow ran against a different commit; its evidence must not be accepted."
            )
        self._audit_log.mark_reconciled(
            dispatch_id,
            run_id=observation.run_id,
            observed_sha=observation.head_sha,
            now=timestamp,
        )
        return DispatchReceipt(
            dispatch_id,
            repository,
            str(record["workflow"]),
            expected_sha,
            operator.login,
            "reconciled",
        )


def _validate_dispatch_id(value: str) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError("dispatch_id must be 32 lowercase hexadecimal characters")


def _validate_repository(value: str) -> None:
    if not isinstance(value, str) or not _REPOSITORY_RE.fullmatch(value):
        raise ValueError("repository must match owner/name")
    owner, name = value.split("/", maxsplit=1)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ValueError("repository must match owner/name")


def _validate_workflow(value: str) -> None:
    if not isinstance(value, str) or len(value) > 128 or not _WORKFLOW_RE.fullmatch(value):
        raise ValueError("workflow must be a YAML filename")


def _validate_sha(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 40-character Git SHA")
