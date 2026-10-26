"""Explicit, read-only-preflight/real-write smoke test for a deployed Phase III service.

Required environment variables are documented in docs/phase-3-evidence-ingestion.md.
This test triggers a real pull_request webhook and publishes a real Check Run. It never prints
App credentials, webhook secrets, database URLs, signed artifact URLs, or artifact contents.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from verification_core.github_actions import GitHubActionsClient
from verification_core.github_app import GitHubAPIError, GitHubAppAuthenticator
from verification_core.runtime import _private_key

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECORD_KEY_RE = re.compile(r"evidence record ([0-9a-f]{64})\.")
_TRUSTED_WORKFLOW_PATH = ".github/workflows/ci.yml"
_ARTIFACT_NAME = "verification-evidence"
_CHECK_NAME = "AI PR Verification"
_CONFIRMATION = "YES_I_EXPECT_A_REAL_CHECK_RUN"


class SmokeTestError(RuntimeError):
    """A safe-to-display, secret-free smoke-test failure."""


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise SmokeTestError(f"Required environment variable {name} is missing.")
    return value


def _positive_integer(value: str, name: str) -> int:
    if not value.isdigit() or int(value) < 1:
        raise SmokeTestError(f"{name} must be a positive integer.")
    return int(value)


def _artifact_sha256(metadata: Mapping[str, object]) -> str:
    """Return the API-provided artifact SHA-256 digest in normalized hexadecimal form."""
    digest = metadata.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise SmokeTestError("GitHub artifact metadata has no SHA-256 digest.")
    normalized = digest.removeprefix("sha256:")
    if not _SHA256_RE.fullmatch(normalized):
        raise SmokeTestError("GitHub artifact metadata contains an invalid SHA-256 digest.")
    return normalized


def _record_key_from_summary(summary: str) -> str:
    """Extract the immutable evidence-record key published in the Check Run summary."""
    match = _RECORD_KEY_RE.search(summary)
    if match is None:
        raise SmokeTestError(
            "The Check Run summary does not identify a successfully persisted evidence record."
        )
    return match.group(1)


def _signed_webhook(
    secret: str, delivery_id: str, payload: Mapping[str, object]
) -> tuple[bytes, dict[str, str]]:
    """Serialize once and sign those exact bytes, as GitHub signs webhook requests."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    headers = {
        "content-type": "application/json",
        "x-hub-signature-256": f"sha256={digest}",
        "x-github-delivery": delivery_id,
        "x-github-event": "pull_request",
    }
    return body, headers


def _api_get(
    client: httpx.Client,
    path: str,
    *,
    params: Mapping[str, str | int] | None = None,
) -> dict[str, Any]:
    response = client.get(path, params=params)
    if response.status_code != 200:
        raise SmokeTestError(f"GitHub API GET {path} returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError:
        raise SmokeTestError("GitHub API returned malformed JSON.") from None
    if not isinstance(payload, dict):
        raise SmokeTestError("GitHub API returned a non-object response.")
    return payload


def _read_pr_identity(
    api: httpx.Client, repository: str, pr_number: int
) -> tuple[str, str, str, str]:
    pull_request = _api_get(api, f"/repos/{repository}/pulls/{pr_number}")
    if pull_request.get("state") != "open":
        raise SmokeTestError("The selected pull request must still be open.")
    base = pull_request.get("base")
    head = pull_request.get("head")
    if not isinstance(base, Mapping) or not isinstance(head, Mapping):
        raise SmokeTestError("GitHub returned malformed pull-request commit identity.")
    base_sha = base.get("sha")
    head_sha = head.get("sha")
    base_ref = base.get("ref")
    head_ref = head.get("ref")
    base_repo = base.get("repo")
    if (
        not isinstance(base_sha, str)
        or not _SHA_RE.fullmatch(base_sha)
        or not isinstance(head_sha, str)
        or not _SHA_RE.fullmatch(head_sha)
        or not isinstance(base_ref, str)
        or not base_ref.strip()
        or not isinstance(head_ref, str)
        or not head_ref.strip()
        or not isinstance(base_repo, Mapping)
        or base_repo.get("full_name") != repository
    ):
        raise SmokeTestError("GitHub returned an invalid pull-request identity.")
    if base_sha == head_sha:
        raise SmokeTestError("The pull-request base and head SHAs unexpectedly match.")
    return base_sha, head_sha, base_ref, head_ref


def _eligible_run(run: Mapping[str, object], *, pr_number: int, head_sha: str) -> bool:
    workflow_path = run.get("path")
    if not isinstance(workflow_path, str):
        return False
    pull_requests = run.get("pull_requests")
    associated = isinstance(pull_requests, list) and any(
        isinstance(item, Mapping) and item.get("number") == pr_number for item in pull_requests
    )
    return (
        run.get("head_sha") == head_sha
        and run.get("event") == "pull_request"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and workflow_path.split("@", maxsplit=1)[0] == _TRUSTED_WORKFLOW_PATH
        and associated
    )


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _check_run_for_delivery(
    api: httpx.Client,
    *,
    repository: str,
    head_sha: str,
    external_id: str,
    sent_at: datetime,
) -> dict[str, Any] | None:
    result = _api_get(
        api,
        f"/repos/{repository}/commits/{head_sha}/check-runs",
        params={"per_page": 100, "filter": "latest"},
    )
    raw_runs = result.get("check_runs")
    if not isinstance(raw_runs, list):
        raise SmokeTestError("GitHub returned a malformed Check Runs collection.")
    candidates: list[dict[str, Any]] = []
    minimum_time = sent_at - timedelta(seconds=5)
    for raw_run in raw_runs:
        if not isinstance(raw_run, dict) or raw_run.get("external_id") != external_id:
            continue
        started_at = _timestamp(raw_run.get("started_at"))
        if started_at is None or started_at < minimum_time:
            continue
        candidates.append(raw_run)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: _timestamp(item.get("started_at")) or datetime.min.replace(tzinfo=UTC),
    )


def _verify_database_record(
    engine: Any,
    *,
    record_key: str,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    workflow_run_id: int,
    artifact_id: int,
    artifact_sha256: str,
    conclusion: str,
    timeout_seconds: int,
) -> None:
    terminal_status = {
        "success": "PASSED",
        "failure": "FAILED",
        "cancelled": "STALE",
    }.get(conclusion)
    deadline = time.monotonic() + min(timeout_seconds, 30)
    latest: Mapping[str, object] | None = None
    while True:
        try:
            with engine.connect() as connection:
                row = (
                    connection.execute(
                        text(
                            "SELECT repository_full_name, pr_number, base_sha, head_sha, "
                            "workflow_run_id, artifact_id, artifact_sha256, "
                            "reconciliation_status, decision_sha256 "
                            "FROM authenticated_evidence_records WHERE record_key = :record_key"
                        ),
                        {"record_key": record_key},
                    )
                    .mappings()
                    .first()
                )
        except SQLAlchemyError:
            raise SmokeTestError(
                "Could not query the configured evidence database; details are redacted."
            ) from None

        if row is not None:
            latest = row
            matches = (
                row["repository_full_name"] == repository
                and row["pr_number"] == pr_number
                and row["base_sha"] == base_sha
                and row["head_sha"] == head_sha
                and row["workflow_run_id"] == workflow_run_id
                and row["artifact_id"] == artifact_id
                and row["artifact_sha256"] == artifact_sha256
            )
            if not matches:
                raise SmokeTestError(
                    "The persisted evidence record does not match the PR, run, artifact, and "
                    "digest."
                )
            if terminal_status is None or row["reconciliation_status"] == terminal_status:
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(1)

    if latest is None:
        raise SmokeTestError("No evidence record was found in the configured evidence database.")
    if terminal_status is not None:
        if latest["reconciliation_status"] != terminal_status:
            raise SmokeTestError(
                "The Check Run conclusion and durable reconciliation status do not agree."
            )
        if not isinstance(latest["decision_sha256"], str) or not _SHA256_RE.fullmatch(
            latest["decision_sha256"]
        ):
            raise SmokeTestError(
                "The terminal reconciliation is missing its durable decision digest."
            )


def run_smoke_test(environment: Mapping[str, str]) -> None:
    """Run preflight, webhook rejection/idempotency, ingestion, persistence and freshness checks."""
    if _required(environment, "PHASE3_SMOKE_CONFIRM_REAL_CHECK_RUN") != _CONFIRMATION:
        raise SmokeTestError(
            "Set PHASE3_SMOKE_CONFIRM_REAL_CHECK_RUN to the documented confirmation value "
            "only when a real Check Run write is intended."
        )

    base_url = _required(environment, "PHASE3_SMOKE_BASE_URL").rstrip("/")
    parsed_url = urlsplit(base_url)
    if (
        parsed_url.scheme not in {"https", "http"}
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise SmokeTestError(
            "PHASE3_SMOKE_BASE_URL must be an HTTP(S) origin/path without credentials."
        )
    if parsed_url.scheme != "https" and parsed_url.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise SmokeTestError("HTTP is allowed only for loopback smoke-test deployments.")

    repository = _required(environment, "PHASE3_SMOKE_REPOSITORY")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise SmokeTestError("PHASE3_SMOKE_REPOSITORY must use owner/repository format.")
    pr_number = _positive_integer(
        _required(environment, "PHASE3_SMOKE_PR_NUMBER"), "PHASE3_SMOKE_PR_NUMBER"
    )
    app_id = _positive_integer(_required(environment, "GITHUB_APP_ID"), "GITHUB_APP_ID")
    installation_id = _positive_integer(
        _required(environment, "GITHUB_INSTALLATION_ID"), "GITHUB_INSTALLATION_ID"
    )
    webhook_secret = _required(environment, "GITHUB_WEBHOOK_SECRET")
    database_url = _required(environment, "VERIFICATION_EVIDENCE_DATABASE_URL")
    timeout_text = environment.get("PHASE3_SMOKE_TIMEOUT_SECONDS", "180")
    timeout_seconds = _positive_integer(timeout_text, "PHASE3_SMOKE_TIMEOUT_SECONDS")
    if not 15 <= timeout_seconds <= 600:
        raise SmokeTestError("PHASE3_SMOKE_TIMEOUT_SECONDS must be between 15 and 600.")

    api = httpx.Client(
        base_url="https://api.github.com",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-pr-verification-agent-smoke-test/0.1",
        },
        timeout=10.0,
        follow_redirects=False,
    )
    service = httpx.Client(timeout=10.0, follow_redirects=False)
    authenticator = GitHubAppAuthenticator(app_id, _private_key(environment))
    actions: GitHubActionsClient | None = None
    engine = None
    try:
        token = authenticator.create_installation_token(installation_id, include_actions_read=True)
        api.headers["Authorization"] = f"Bearer {token.token}"
        actions = GitHubActionsClient(token.token)

        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, ValueError):
            raise SmokeTestError(
                "The evidence database URL is invalid or unavailable; details are redacted."
            ) from None

        health = service.get(f"{base_url}/healthz")
        if health.status_code != 200:
            raise SmokeTestError(f"Service health endpoint returned HTTP {health.status_code}.")
        try:
            health_payload = health.json()
        except ValueError:
            raise SmokeTestError("Service health endpoint returned malformed JSON.") from None
        if not isinstance(health_payload, dict) or health_payload.get("status") != "ok":
            raise SmokeTestError("Service health endpoint did not report status=ok.")
        print("PASS: deployment health endpoint is reachable.")

        base_sha, head_sha, base_ref, head_ref = _read_pr_identity(api, repository, pr_number)
        runs = actions.list_pull_request_workflow_runs(repository, head_sha)
        eligible = [
            run for run in runs if _eligible_run(run, pr_number=pr_number, head_sha=head_sha)
        ]
        if len(eligible) != 1:
            raise SmokeTestError(
                "Expected exactly one successful trusted workflow run for this exact PR head; "
                f"found {len(eligible)}. This deliberately fails closed on ambiguous runs."
            )
        raw_run_id = eligible[0].get("id")
        if type(raw_run_id) is not int or raw_run_id < 1:
            raise SmokeTestError("The eligible workflow run has an invalid identifier.")
        workflow_run_id = raw_run_id
        run = actions.get_workflow_run(repository, workflow_run_id)
        workflow_path = run.get("path")
        if (
            run.get("head_sha") != head_sha
            or run.get("event") != "pull_request"
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or not isinstance(workflow_path, str)
            or workflow_path.split("@", maxsplit=1)[0] != _TRUSTED_WORKFLOW_PATH
        ):
            raise SmokeTestError(
                "The selected workflow run changed or failed exact-head validation."
            )

        artifacts = actions.list_workflow_run_artifacts(repository, workflow_run_id)
        matching_artifacts = [item for item in artifacts if item.get("name") == _ARTIFACT_NAME]
        if len(matching_artifacts) != 1:
            raise SmokeTestError(
                "The selected workflow run must contain exactly one verification-evidence artifact."
            )
        artifact_metadata = matching_artifacts[0]
        raw_artifact_id = artifact_metadata.get("id")
        if type(raw_artifact_id) is not int or raw_artifact_id < 1:
            raise SmokeTestError("The evidence artifact has an invalid identifier.")
        artifact_id = raw_artifact_id
        expected_digest = _artifact_sha256(artifact_metadata)
        archive_bytes = actions.download_workflow_artifact(repository, artifact_id)
        actual_digest = hashlib.sha256(archive_bytes).hexdigest()
        if actual_digest != expected_digest:
            raise SmokeTestError("Downloaded artifact SHA-256 does not match GitHub's API digest.")
        size = artifact_metadata.get("size_in_bytes")
        if type(size) is int and size != len(archive_bytes):
            raise SmokeTestError("Downloaded artifact size does not match GitHub's metadata.")
        print(
            "PASS: installed App can read Actions runs/artifacts; the exact-head artifact's "
            f"downloaded SHA-256 matches ({expected_digest})."
        )

        invalid_delivery = f"phase3-invalid-{uuid.uuid4().hex}"
        invalid_response = service.post(
            f"{base_url}/webhooks/github",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "x-hub-signature-256": "sha256=" + ("0" * 64),
                "x-github-delivery": invalid_delivery,
                "x-github-event": "pull_request",
            },
        )
        if invalid_response.status_code != 401:
            raise SmokeTestError(
                "Webhook failure handling failed: an intentionally invalid signature "
                f"returned HTTP {invalid_response.status_code}, expected 401."
            )
        print("PASS: webhook ingress rejects an invalid HMAC signature.")

        payload: dict[str, object] = {
            "action": "synchronize",
            "installation": {"id": installation_id},
            "repository": {"full_name": repository},
            "pull_request": {
                "number": pr_number,
                "state": "open",
                "base": {
                    "sha": base_sha,
                    "ref": base_ref,
                    "repo": {"full_name": repository},
                },
                "head": {"sha": head_sha, "ref": head_ref},
            },
        }
        delivery_id = f"phase3-smoke-{uuid.uuid4().hex}"
        body, headers = _signed_webhook(webhook_secret, delivery_id, payload)
        sent_at = datetime.now(UTC)
        first = service.post(f"{base_url}/webhooks/github", content=body, headers=headers)
        if first.status_code != 202:
            raise SmokeTestError(
                f"Signed webhook was not durably accepted (HTTP {first.status_code})."
            )
        try:
            first_payload = first.json()
        except ValueError:
            raise SmokeTestError("Webhook ingress returned malformed acceptance JSON.") from None
        if not isinstance(first_payload, dict) or first_payload.get("accepted") is not True:
            raise SmokeTestError("Webhook ingress did not confirm durable acceptance.")

        duplicate = service.post(f"{base_url}/webhooks/github", content=body, headers=headers)
        if duplicate.status_code != 202:
            raise SmokeTestError(
                f"Duplicate webhook delivery was not acknowledged (HTTP {duplicate.status_code})."
            )
        try:
            duplicate_payload = duplicate.json()
        except ValueError:
            raise SmokeTestError("Duplicate-delivery response was malformed.") from None
        if (
            not isinstance(duplicate_payload, dict)
            or duplicate_payload.get("duplicate") is not True
        ):
            raise SmokeTestError("Duplicate webhook delivery was not handled idempotently.")
        print("PASS: signed webhook is accepted and a repeated delivery is idempotent.")

        external_id = f"ai-pr-verification-agent:phase3:{pr_number}:{head_sha}"
        deadline = time.monotonic() + timeout_seconds
        check_run: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            current_base, current_head, _, _ = _read_pr_identity(api, repository, pr_number)
            if current_base != base_sha or current_head != head_sha:
                raise SmokeTestError(
                    "PR base/head changed while the smoke test was running; freshness check failed."
                )
            check_run = _check_run_for_delivery(
                api,
                repository=repository,
                head_sha=head_sha,
                external_id=external_id,
                sent_at=sent_at,
            )
            if check_run is not None and check_run.get("status") == "completed":
                break
            time.sleep(2)
        if check_run is None or check_run.get("status") != "completed":
            raise SmokeTestError(
                "No completed freshness-bound Phase III Check Run appeared before the timeout."
            )
        if check_run.get("head_sha") != head_sha or check_run.get("name") != _CHECK_NAME:
            raise SmokeTestError("Published Check Run has the wrong name or head SHA.")
        conclusion = check_run.get("conclusion")
        output = check_run.get("output")
        summary = output.get("summary") if isinstance(output, Mapping) else None
        if not isinstance(conclusion, str) or not isinstance(summary, str):
            raise SmokeTestError("Published Check Run has incomplete result metadata.")
        if f"Authenticated workflow run {workflow_run_id}" not in summary:
            raise SmokeTestError(
                "Check Run does not prove ingestion of the preflight-verified workflow run."
            )
        if f"head {head_sha}" not in summary:
            raise SmokeTestError("Check Run summary is not bound to the exact PR head.")
        record_key = _record_key_from_summary(summary)
        _verify_database_record(
            engine,
            record_key=record_key,
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            workflow_run_id=workflow_run_id,
            artifact_id=artifact_id,
            artifact_sha256=expected_digest,
            conclusion=conclusion,
            timeout_seconds=timeout_seconds,
        )
        final_base, final_head, _, _ = _read_pr_identity(api, repository, pr_number)
        if final_base != base_sha or final_head != head_sha:
            raise SmokeTestError(
                "PR base/head changed before final acceptance; freshness check failed."
            )
        print(
            "PASS: exact-head Check Run references the ingested workflow run, and the same "
            "artifact ID/SHA-256 is persisted in the configured evidence database."
        )
        print(
            f"PASS: Check Run completed with conclusion={conclusion}; evidence record and "
            "PR freshness checks agree."
        )
        print("SMOKE TEST PASSED.")
    finally:
        if actions is not None:
            actions.close()
        api.close()
        service.close()
        if engine is not None:
            engine.dispose()
        authenticator.close()


def main() -> int:
    try:
        run_smoke_test(os.environ)
    except SmokeTestError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1
    except GitHubAPIError as exc:
        print(f"SMOKE TEST FAILED: GitHub App/API operation failed: {exc}", file=sys.stderr)
        return 1
    except (SQLAlchemyError, httpx.HTTPError, OSError, RuntimeError, ValueError):
        print(
            "SMOKE TEST FAILED: a required remote, key, or database operation failed; "
            "details are redacted.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
