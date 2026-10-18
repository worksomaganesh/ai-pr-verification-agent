"""Phase II orchestration: authenticated GitHub context -> plan -> deterministic Check Run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from verification_core.delivery_store import DeliveryStoreError, SQLiteDeliveryStore
from verification_core.domain import ConclusionPolicyConfig, evaluate_verification_run
from verification_core.github_app import (
    GitHubAPIError,
    GitHubAppAuthenticator,
    GitHubRESTClient,
)
from verification_core.github_context import GitHubContextError, assemble_pull_request_context
from verification_core.planning import (
    DiffAnalysisError,
    VerificationModelPort,
    analyze_changed_files,
    plan_verification,
)
from verification_core.security import scrub_secrets


class ModelFactory(Protocol):
    """Construct an optional model port for one installation-scoped processing attempt."""

    def __call__(self) -> VerificationModelPort | None: ...


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Public, secret-free outcome of one queue processing attempt."""

    delivery_id: str
    status: str
    conclusion: str | None
    check_run_id: int | None
    reason_code: str | None = None


def _policy_config(policy: object) -> ConclusionPolicyConfig:
    """Translate the validated trusted-base policy into deterministic conclusion settings."""
    severity_rule = getattr(policy, "severity_rule")
    critical = severity_rule("critical")
    high = severity_rule("high")
    medium = severity_rule("medium")
    return ConclusionPolicyConfig(
        treat_medium_as_mandatory=bool(medium.blocking),
        allow_human_approval_for_critical=bool(critical.human_approval_allowed),
        allow_human_approval_for_high=bool(high.human_approval_allowed),
    )


def _summary(
    *,
    planning: object,
    evaluation: object,
    analysis_issues: tuple[str, ...],
    model_mode: str,
    degradation_reason: str | None,
) -> str:
    """Render bounded, secret-scrubbed Check Run evidence and outstanding obligations."""
    obligations = tuple(getattr(planning, "obligations"))
    completeness = getattr(planning, "analysis_completeness")
    commit = getattr(planning, "commit")
    lines = [
        "## Verification planning result",
        "",
        f"- **Commit:** {commit.head_sha}",
        f"- **Base commit:** {commit.base_sha}",
        f"- **Diff analysis:** {completeness.value}",
        f"- **Planner mode:** {model_mode}",
        "- **Execution evidence:** Not collected in Phase II. No test commands were run.",
        "",
        "This Check Run reports a bounded verification plan. It does not claim that any "
        "obligation has passed. Test execution and platform-anchored artifact reconciliation "
        "are later-phase capabilities.",
        "",
        "## Verification obligations",
        "",
    ]
    if not obligations:
        lines.append("No path-based behavioral obligations were generated from the analyzed diff.")
    else:
        for obligation in obligations:
            selector = obligation.candidate_test_id or "No matching test found"
            lines.append(
                f"- **{obligation.severity.value.upper()} · {obligation.obligation_id}** — "
                f"{scrub_secrets(obligation.description)}"
            )
            lines.append(f"  - Status: {obligation.status.value} (proposed; not executed)")
            lines.append(f"  - Changed files: {', '.join(obligation.affected_files)}")
            lines.append(f"  - Candidate test: {scrub_secrets(selector)}")
    if analysis_issues:
        lines.extend(["", "## Analysis limitations", ""])
        lines.extend(f"- {scrub_secrets(issue)}" for issue in analysis_issues[:30])
    if degradation_reason:
        lines.extend(["", "## Planner fallback", "", scrub_secrets(degradation_reason)])
    lines.extend(
        [
            "",
            "## Deterministic conclusion",
            "",
            f"- **Conclusion:** {getattr(evaluation, 'github_conclusion').value}",
            f"- **Reason:** {scrub_secrets(getattr(evaluation, 'summary_rationale'))}",
        ]
    )
    return scrub_secrets("\n".join(lines))[:59_000]


class PhaseTwoProcessor:
    """Process durable events using only read-only GitHub context and Checks API writes."""

    def __init__(
        self,
        *,
        store: SQLiteDeliveryStore,
        authenticator: GitHubAppAuthenticator,
        model_factory: ModelFactory | None = None,
        check_name: str = "AI PR Verification",
    ) -> None:
        if not check_name or len(check_name) > 100:
            raise ValueError("check_name must contain 1-100 characters")
        self._store = store
        self._authenticator = authenticator
        self._model_factory = model_factory
        self._check_name = check_name

    def process_next(self) -> ProcessingResult | None:
        """Claim and process one delivery. Failures are retried with bounded backoff."""
        try:
            queued = self._store.claim_next()
        except DeliveryStoreError:
            return ProcessingResult(
                delivery_id="",
                status="failed",
                conclusion=None,
                check_run_id=None,
                reason_code="delivery_claim_failed",
            )
        if queued is None:
            return None

        event = queued.event
        try:
            if event.installation_id is None:
                raise GitHubAPIError("Webhook event did not contain an App installation ID.")
            installation_token = self._authenticator.create_installation_token(
                event.installation_id
            )
            client = GitHubRESTClient(installation_token.token)
            try:
                context = assemble_pull_request_context(event, client)
                inventory = client.list_test_inventory(event.repository_full_name, event.head_sha)
                analysis = analyze_changed_files(
                    commit=context.commit,
                    changed_files=context.changed_files,
                    policy=context.policy,
                )
                model = self._model_factory() if self._model_factory is not None else None
                planning = plan_verification(
                    analysis,
                    test_inventory=inventory,
                    model=model,
                )
                evaluation = evaluate_verification_run(
                    commit=context.commit,
                    obligations=planning.obligations,
                    analysis_completeness=planning.analysis_completeness,
                    policy_config=_policy_config(context.policy),
                    policy_valid=True,
                )
                pull_request = client.get_pull_request(event.repository_full_name, event.pr_number)
                html_url = pull_request.get("html_url")
                details_url = (
                    html_url
                    if isinstance(html_url, str)
                    and html_url.startswith("https://github.com/")
                    and len(html_url) <= 2_000
                    else None
                )
                summary = _summary(
                    planning=planning,
                    evaluation=evaluation,
                    analysis_issues=planning.issues,
                    model_mode=planning.planner_mode,
                    degradation_reason=planning.degradation_reason,
                )
                external_id = f"aiprv:{event.pr_number}:{event.head_sha}"
                check_run_id = client.publish_check_run(
                    repository=event.repository_full_name,
                    head_sha=event.head_sha,
                    name=self._check_name,
                    conclusion=evaluation.github_conclusion.value,
                    title=evaluation.summary_title,
                    summary=summary,
                    external_id=external_id,
                    details_url=details_url,
                )
            finally:
                client.close()

            self._store.mark_completed(event.delivery_id)
            return ProcessingResult(
                delivery_id=event.delivery_id,
                status="completed",
                conclusion=evaluation.github_conclusion.value,
                check_run_id=check_run_id,
            )
        except (GitHubAPIError, GitHubContextError, DiffAnalysisError, ValueError) as exc:
            reason_code = {
                "GitHubRateLimitError": "github_rate_limited",
                "GitHubResponseTooLarge": "github_response_too_large",
                "GitHubContextError": "github_context_rejected",
                "DiffAnalysisError": "diff_analysis_rejected",
            }.get(type(exc).__name__, "processing_failed")
            try:
                self._store.mark_failed(event.delivery_id, error_code=reason_code, retry=True)
            except DeliveryStoreError:
                return ProcessingResult(
                    delivery_id=event.delivery_id,
                    status="failed",
                    conclusion=None,
                    check_run_id=None,
                    reason_code="delivery_state_update_failed",
                )
            return ProcessingResult(
                delivery_id=event.delivery_id,
                status="retrying",
                conclusion=None,
                check_run_id=None,
                reason_code=reason_code,
            )
        except Exception:
            # Do not include exception strings or tracebacks: they may contain secrets.
            try:
                self._store.mark_failed(
                    event.delivery_id, error_code="unexpected_processing_error", retry=True
                )
            except DeliveryStoreError:
                pass
            return ProcessingResult(
                delivery_id=event.delivery_id,
                status="retrying",
                conclusion=None,
                check_run_id=None,
                reason_code="unexpected_processing_error",
            )
