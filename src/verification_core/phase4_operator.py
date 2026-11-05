"""Deliberate staging-only CLI for Phase IV dispatch and human-review audit."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from verification_core.dispatch_governance import (
    GitHubOperatorAuthenticator,
    GitHubWorkflowRunVerifier,
    SQLAlchemyDispatchAuditLog,
    WorkflowDispatchCoordinator,
)
from verification_core.human_governance import (
    GitHubReviewVerifier,
    SQLAlchemyHumanReviewAuditLog,
)
from verification_core.workflow_dispatch import GitHubWorkflowDispatcher, WorkflowInputRule

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DISPATCH_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MAX_INPUTS_FILE_BYTES = 16 * 1024
_GITHUB_API = "https://api.github.com"


@dataclass(frozen=True, slots=True)
class Phase4Settings:
    """Validated operator policy loaded from the staging environment."""

    token: str
    repository: str
    audit_database_url: str
    allowed_workflows: tuple[str, ...]
    allowed_logins: tuple[str, ...]
    input_schemas: Mapping[str, Mapping[str, WorkflowInputRule]]


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"Required staging environment setting {name} is missing.")
    return value


def _csv_setting(environment: Mapping[str, str], name: str) -> tuple[str, ...]:
    raw = _required(environment, name)
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError(f"{name} must contain at least one value.")
    if len({value.casefold() for value in values}) != len(values):
        raise ValueError(f"{name} must not contain duplicate values.")
    return values


def _parse_input_schemas(
    raw: str,
    *,
    allowed_workflows: tuple[str, ...],
) -> dict[str, dict[str, WorkflowInputRule]]:
    try:
        document = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("PHASE4_WORKFLOW_INPUT_SCHEMAS must contain valid JSON.") from None
    if not isinstance(document, Mapping) or set(document) != set(allowed_workflows):
        raise ValueError(
            "PHASE4_WORKFLOW_INPUT_SCHEMAS must define exactly the allowlisted workflows."
        )

    schemas: dict[str, dict[str, WorkflowInputRule]] = {}
    for workflow in allowed_workflows:
        workflow_rules = document.get(workflow)
        if not isinstance(workflow_rules, Mapping):
            raise ValueError(f"The input schema for {workflow} must be a JSON object.")
        rules: dict[str, WorkflowInputRule] = {}
        for input_name, raw_rule in workflow_rules.items():
            if not isinstance(input_name, str) or not isinstance(raw_rule, Mapping):
                raise ValueError("Workflow input schema entries must be named JSON objects.")
            unknown = set(raw_rule) - {"required", "max_length", "pattern", "allowed_values"}
            if unknown:
                raise ValueError(f"The input schema for {workflow} contains unknown rule keys.")
            required = raw_rule.get("required", False)
            max_length = raw_rule.get("max_length", 1024)
            pattern = raw_rule.get("pattern")
            allowed_values = raw_rule.get("allowed_values", [])
            if not isinstance(allowed_values, list) or any(
                not isinstance(value, str) for value in allowed_values
            ):
                raise ValueError("allowed_values must be a JSON array of strings.")
            if pattern is not None and not isinstance(pattern, str):
                raise ValueError("pattern must be a string when supplied.")
            rules[input_name] = WorkflowInputRule(
                required=required,
                max_length=max_length,
                pattern=pattern,
                allowed_values=tuple(allowed_values),
            )
        correlation = rules.get("verification_dispatch_id")
        if (
            correlation is None
            or correlation.required is not True
            or correlation.max_length != 32
            or correlation.pattern != r"[0-9a-f]{32}"
        ):
            raise ValueError(
                f"{workflow} must require the 32-character verification_dispatch_id input."
            )
        head_rule = rules.get("expected_head_sha")
        if (
            head_rule is None
            or head_rule.required is not True
            or head_rule.max_length != 40
            or head_rule.pattern != r"[0-9a-f]{40}"
        ):
            raise ValueError(
                f"{workflow} must require the exact 40-character expected_head_sha input."
            )
        schemas[workflow] = rules
    return schemas


def load_staging_settings(
    environment: Mapping[str, str] | None = None,
) -> Phase4Settings:
    """Require explicit staging mode, explicit dispatch opt-in, and PostgreSQL durability."""
    source = os.environ if environment is None else environment
    if source.get("PHASE4_ENVIRONMENT", "").strip().casefold() != "staging":
        raise ValueError("PHASE4_ENVIRONMENT must be exactly 'staging'.")
    if source.get("PHASE4_DISPATCH_ENABLED", "").strip().casefold() != "true":
        raise ValueError(
            "PHASE4_DISPATCH_ENABLED must be explicitly set to 'true' for an operator action."
        )
    token = _required(source, "PHASE4_GITHUB_TOKEN")
    repository = _required(source, "PHASE4_REPOSITORY")
    database_url = _required(source, "PHASE4_AUDIT_DATABASE_URL")
    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError("Staging governance audits require managed PostgreSQL via psycopg.")
    allowed_workflows = _csv_setting(source, "PHASE4_ALLOWED_WORKFLOWS")
    allowed_logins = _csv_setting(source, "PHASE4_OPERATOR_ALLOWED_LOGINS")
    schemas = _parse_input_schemas(
        _required(source, "PHASE4_WORKFLOW_INPUT_SCHEMAS"),
        allowed_workflows=allowed_workflows,
    )
    return Phase4Settings(
        token=token,
        repository=repository,
        audit_database_url=database_url,
        allowed_workflows=allowed_workflows,
        allowed_logins=allowed_logins,
        input_schemas=schemas,
    )


def verify_ref_head(
    *,
    token: str,
    repository: str,
    ref: str,
    expected_head_sha: str,
    http_client: httpx.Client | None = None,
) -> None:
    """Check the selected ref's current commit before causing the dispatch side effect."""
    if not _SHA_RE.fullmatch(expected_head_sha):
        raise ValueError("expected_head_sha must be a lowercase 40-character commit SHA.")
    owns_client = http_client is None
    client = http_client or httpx.Client(
        base_url=_GITHUB_API,
        timeout=httpx.Timeout(8.0, connect=3.0),
        follow_redirects=False,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    path = f"/repos/{quote(repository, safe='/')}/commits/{quote(ref, safe='')}"
    try:
        with client.stream("GET", path, follow_redirects=False) as response:
            if response.status_code != 200:
                raise RuntimeError("GitHub could not verify the requested staging ref.")
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > 64 * 1024:
                    raise RuntimeError("GitHub ref metadata exceeded the response size limit.")
                body.extend(chunk)
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, ValueError):
            raise RuntimeError("GitHub returned malformed staging ref metadata.") from None
        observed_sha = payload.get("sha") if isinstance(payload, Mapping) else None
        if observed_sha != expected_head_sha:
            raise RuntimeError(
                "The staging ref no longer points to expected_head_sha; no dispatch was sent."
            )
    except RuntimeError:
        raise
    except httpx.TimeoutException:
        raise RuntimeError(
            "GitHub staging ref verification timed out; no dispatch was sent."
        ) from None
    except httpx.HTTPError:
        raise RuntimeError(
            "GitHub staging ref verification failed; no dispatch was sent."
        ) from None
    finally:
        if owns_client:
            client.close()


def _read_inputs_file(path_text: str | None) -> dict[str, str]:
    if path_text is None:
        return {}
    path = Path(path_text)
    try:
        if not path.is_file() or path.stat().st_size > _MAX_INPUTS_FILE_BYTES:
            raise ValueError("The inputs file must be a regular file no larger than 16 KiB.")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise ValueError("The inputs file must contain a bounded JSON object.") from None
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError("The inputs file must map input names to string values.")
    return dict(value)


def _dispatch(args: argparse.Namespace, settings: Phase4Settings) -> int:
    if not args.confirm_staging:
        raise ValueError("Pass --confirm-staging to authorize a real staging workflow dispatch.")
    if not _SHA_RE.fullmatch(args.expected_head_sha):
        raise ValueError("--expected-head-sha must be a lowercase 40-character SHA.")
    if args.workflow not in settings.allowed_workflows:
        raise ValueError("The requested workflow is not in PHASE4_ALLOWED_WORKFLOWS.")
    verify_ref_head(
        token=settings.token,
        repository=settings.repository,
        ref=args.ref,
        expected_head_sha=args.expected_head_sha,
    )
    inputs = _read_inputs_file(args.inputs_file)
    supplied_head = inputs.get("expected_head_sha")
    if supplied_head is not None and supplied_head != args.expected_head_sha:
        raise ValueError(
            "The inputs file expected_head_sha must match --expected-head-sha exactly."
        )
    inputs["expected_head_sha"] = args.expected_head_sha
    authenticator = GitHubOperatorAuthenticator(allowed_logins=settings.allowed_logins)
    audit = SQLAlchemyDispatchAuditLog(settings.audit_database_url)
    run_verifier = GitHubWorkflowRunVerifier()

    def dispatcher_factory(access_token: str) -> GitHubWorkflowDispatcher:
        return GitHubWorkflowDispatcher(
            access_token,
            allowed_workflows=settings.allowed_workflows,
            input_schemas=settings.input_schemas,
            enabled=True,
        )

    coordinator = WorkflowDispatchCoordinator(
        authenticator=authenticator,
        audit_log=audit,
        dispatcher_factory=dispatcher_factory,
        run_verifier=run_verifier,
    )
    dispatch_id = uuid.uuid4().hex
    try:
        receipt = coordinator.dispatch(
            access_token=settings.token,
            dispatch_id=dispatch_id,
            repository=settings.repository,
            workflow=args.workflow,
            ref=args.ref,
            expected_head_sha=args.expected_head_sha,
            inputs=inputs,
        )
        print(f"Staging dispatch submitted; verification pending. ID={receipt.dispatch_id}")
        print(
            "Next command: ai-pr-verification-phase4 reconcile --dispatch-id " + receipt.dispatch_id
        )
        return 0
    finally:
        run_verifier.close()
        audit.close()
        authenticator.close()


def _reconcile(args: argparse.Namespace, settings: Phase4Settings) -> int:
    if not args.confirm_staging:
        raise ValueError("Pass --confirm-staging to authorize staging reconciliation.")
    if not _DISPATCH_ID_RE.fullmatch(args.dispatch_id):
        raise ValueError("--dispatch-id must be a 32-character lowercase hexadecimal ID.")
    authenticator = GitHubOperatorAuthenticator(allowed_logins=settings.allowed_logins)
    audit = SQLAlchemyDispatchAuditLog(settings.audit_database_url)
    run_verifier = GitHubWorkflowRunVerifier()
    coordinator = WorkflowDispatchCoordinator(
        authenticator=authenticator,
        audit_log=audit,
        dispatcher_factory=lambda access_token: GitHubWorkflowDispatcher(
            access_token,
            allowed_workflows=settings.allowed_workflows,
            input_schemas=settings.input_schemas,
            enabled=True,
        ),
        run_verifier=run_verifier,
    )
    try:
        receipt = coordinator.reconcile(access_token=settings.token, dispatch_id=args.dispatch_id)
        if receipt is None:
            print("Correlated run is not visible yet; audit remains submitted_unreconciled.")
            return 3
        print(
            f"Reconciled run_id={audit.get_dispatch(args.dispatch_id)['workflow_run_id']} "
            f"and exact head {receipt.expected_head_sha}."
        )
        print(
            "This confirms run identity/SHA only; Phase III evidence ingestion is still required."
        )
        return 0
    finally:
        run_verifier.close()
        audit.close()
        authenticator.close()


def _verify_review(args: argparse.Namespace, settings: Phase4Settings) -> int:
    if not args.confirm_staging_review:
        raise ValueError("Pass --confirm-staging-review to record a real GitHub review audit.")
    reviewers = _csv_setting(os.environ, "PHASE4_ALLOWED_REVIEWERS")
    verifier = GitHubReviewVerifier(allowed_reviewers=reviewers)
    audit = SQLAlchemyHumanReviewAuditLog(settings.audit_database_url)
    try:
        approvals = verifier.verify_current_approvals(
            access_token=settings.token,
            repository=settings.repository,
            pr_number=args.pr_number,
            expected_base_sha=args.expected_base_sha,
            expected_head_sha=args.expected_head_sha,
        )
        if not approvals:
            print("No qualifying current approval exists for the supplied exact PR head.")
            return 4
        recorded = 0
        for approval in approvals:
            if audit.record_approval(approval, now=datetime.now(UTC).timestamp()):
                recorded += 1
            print(
                f"Verified approval: reviewer={approval.reviewer_login}, "
                f"review_id={approval.review_id}, head={approval.head_sha}"
            )
        print(f"Human-review audit complete; {recorded} new approval record(s) persisted.")
        return 0
    finally:
        audit.close()
        verifier.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-pr-verification-phase4",
        description="Explicit staging-only Phase IV dispatch and review-audit operator CLI.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    dispatch = commands.add_parser("dispatch", help="dispatch one allowlisted staging workflow")
    dispatch.add_argument("--workflow", required=True)
    dispatch.add_argument("--ref", required=True)
    dispatch.add_argument("--expected-head-sha", required=True)
    dispatch.add_argument("--inputs-file")
    dispatch.add_argument("--confirm-staging", action="store_true")
    reconcile = commands.add_parser("reconcile", help="reconcile one recorded staging dispatch")
    reconcile.add_argument("--dispatch-id", required=True)
    reconcile.add_argument("--confirm-staging", action="store_true")
    review = commands.add_parser(
        "verify-review", help="verify and audit current exact-head reviews"
    )
    review.add_argument("--pr-number", required=True, type=int)
    review.add_argument("--expected-base-sha", required=True)
    review.add_argument("--expected-head-sha", required=True)
    review.add_argument("--confirm-staging-review", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_staging_settings()
        if args.command == "dispatch":
            return _dispatch(args, settings)
        if args.command == "reconcile":
            return _reconcile(args, settings)
        if args.command == "verify-review":
            return _verify_review(args, settings)
        raise ValueError("Unsupported Phase IV operator command.")
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Phase IV operator rejected the request: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
