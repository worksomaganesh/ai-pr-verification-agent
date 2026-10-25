"""Phase II orchestration: authenticated GitHub context -> plan -> deterministic Check Run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from verification_core.delivery_store import DeliveryStoreError, SQLiteDeliveryStore
from verification_core.domain import (
    ConclusionPolicyConfig,
    VerificationRunEvaluation,
    evaluate_verification_run,
)
from verification_core.github_app import GitHubAPIError, GitHubRESTClient, InstallationToken
from verification_core.github_actions import GitHubActionsClient
from verification_core.github_context import assemble_pull_request_context
from verification_core.phase_three_worker import (
    PhaseThreeLedgerPort,
    PhaseThreeRunPending,
    WorkflowRunListingPort,
    process_pull_request_evidence,
)
from verification_core.planning import (
    PlanningResult,
    VerificationModelPort,
    analyze_changed_files,
    plan_verification,
)
from verification_core.policy import VerificationPolicy
from verification_core.run_ledger import VerificationRunLedger
from verification_core.security import scrub_secrets


class InstallationTokenProvider(Protocol):
    """Minimal token provider interface, injectable for tests and alternate runtimes."""

    def create_installation_token(self, installation_id: int) -> InstallationToken: ...


class PhaseThreeInstallationTokenProvider(InstallationTokenProvider, Protocol):
    """Installation-token provider capable of adding Actions read permission on demand."""

    def create_installation_token(
        self, installation_id: int, *, include_actions_read: bool = False
    ) -> InstallationToken: ...


class ActionsClientFactory(Protocol):
    """Build one token-scoped Actions client for a single queue-processing attempt."""

    def __call__(self, installation_token: str) -> WorkflowRunListingPort: ...


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
    run_key: str | None = None


def _policy_config(policy: VerificationPolicy) -> ConclusionPolicyConfig:
    """Translate the validated trusted-base policy into deterministic conclusion settings."""
    severity_rule = policy.severity_rule
    critical = severity_rule("critical")
    high = severity_rule("high")
    medium = severity_rule("medium")
    return ConclusionPolicyConfig(
        treat_medium_as_mandatory=bool(medium.blocking),
        allow_human_approval_for_critical=bool(critical.human_approval_allowed),
        allow_human_approval_for_high=bool(high.human_approval_allowed),
    )


def _inline(value: object) -> str:
    """Escape untrusted inline values before inserting them into Markdown output."""
    text = scrub_secrets(str(value)).replace("\\", "\\\\")
    text = text.replace("\r", " ").replace("\n", " ")
    for char in (chr(96), "*", "_", "[", "]", "|"):
        text = text.replace(char, "\\" + char)
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _summary(
    *,
    planning: PlanningResult,
    evaluation: VerificationRunEvaluation,
    analysis_issues: tuple[str, ...],
    model_mode: str,
    degradation_reason: str | None,
) -> str:
    """Render bounded, secret-scrubbed Check Run evidence and outstanding obligations."""
    obligations = planning.obligations
    completeness = planning.analysis_completeness
    commit = planning.commit
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
                f"{_inline(obligation.description)}"
            )
            lines.append(f"  - Status: {obligation.status.value} (proposed; not executed)")
            changed_files = ", ".join(_inline(path) for path in obligation.affected_files)
            lines.append(f"  - Changed files: {changed_files}")
            lines.append(f"  - Candidate test: {_inline(selector)}")
    if analysis_issues:
        lines.extend(["", "## Analysis limitations", ""])
        lines.extend(f"- {_inline(issue)}" for issue in analysis_issues[:30])
    if degradation_reason:
        lines.extend(["", "## Planner fallback", "", _inline(degradation_reason)])
    lines.extend(
        [
            "",
            "## Deterministic conclusion",
            "",
            f"- **Conclusion:** {evaluation.github_conclusion.value}",
            f"- **Reason:** {_inline(evaluation.summary_rationale)}",
        ]
    )
    return scrub_secrets("\n".join(lines))[:59_000]


class PhaseTwoProcessor:
    """Process durable events using only read-only GitHub context and Checks API writes."""

    def __init__(
        self,
        *,
        store: SQLiteDeliveryStore,
        authenticator: InstallationTokenProvider,
        model_factory: ModelFactory | None = None,
        run_ledger: VerificationRunLedger | None = None,
        check_name: str = "AI PR Verification",
        phase_three_enabled: bool = False,
        evidence_ledger: PhaseThreeLedgerPort | None = None,
        actions_client_factory: ActionsClientFactory | None = None,
    ) -> None:
        if not check_name or len(check_name) > 100:
            raise ValueError("check_name must contain 1-100 characters")
        if type(phase_three_enabled) is not bool:
            raise ValueError("phase_three_enabled must be a boolean")
        if phase_three_enabled and evidence_ledger is None:
            raise ValueError("Phase III requires a durable evidence ledger")
        self._store = store
        self._run_ledger = run_ledger or store
        self._authenticator = authenticator
        self._model_factory = model_factory
        self._check_name = check_name
        self._phase_three_enabled = phase_three_enabled
        self._evidence_ledger = evidence_ledger
        self._actions_client_factory = actions_client_factory or GitHubActionsClient

    def close(self) -> None:
        """Release database pools owned by this processor."""
        if self._run_ledger is not self._store:
            self._run_ledger.close()
        if self._evidence_ledger is not None:
            self._evidence_ledger.close()

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
            if self._phase_three_enabled:
                phase_three_authenticator = cast(
                    PhaseThreeInstallationTokenProvider, self._authenticator
                )
                installation_token = phase_three_authenticator.create_installation_token(
                    event.installation_id, include_actions_read=True
                )
            else:
                installation_token = self._authenticator.create_installation_token(
                    event.installation_id
                )
            client = GitHubRESTClient(installation_token.token)
            actions_client: WorkflowRunListingPort | None = None
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
                if self._phase_three_enabled:
                    if self._evidence_ledger is None:
                        raise RuntimeError("Phase III evidence ledger is unavailable")
                    actions_client = self._actions_client_factory(installation_token.token)
                    phase_three_result = process_pull_request_evidence(
                        github=client,
                        actions=actions_client,
                        commit=context.commit,
                        planning=planning,
                        analysis=analysis,
                        policy=context.policy,
                        evidence_ledger=self._evidence_ledger,
                        policy_config=_policy_config(context.policy),
                        check_name=self._check_name,
                    )
                    evaluation = phase_three_result.publication.evaluation
                    summary = scrub_secrets(
                        evaluation.summary_rationale + "\\n\\n" + phase_three_result.summary
                    )[:59_000]
                    run_key = self._run_ledger.save_verification_run(
                        commit=planning.commit,
                        analysis_completeness=evaluation.analysis_completeness.value,
                        planner_mode=f"phase3:{planning.planner_mode}"[:80],
                        conclusion=evaluation.github_conclusion.value,
                        summary=summary,
                        obligations=evaluation.obligations,
                    )
                    check_run_id = phase_three_result.publication.check_run_id
                    self._run_ledger.set_check_run_id(run_key, check_run_id)
                else:
                    evaluation = evaluate_verification_run(
                        commit=context.commit,
                        obligations=planning.obligations,
                        analysis_completeness=planning.analysis_completeness,
                        policy_config=_policy_config(context.policy),
                        policy_valid=True,
                    )
                    pull_request = client.get_pull_request(
                        event.repository_full_name, event.pr_number
                    )
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
                    run_key = self._run_ledger.save_verification_run(
                        commit=planning.commit,
                        analysis_completeness=planning.analysis_completeness.value,
                        planner_mode=planning.planner_mode,
                        conclusion=evaluation.github_conclusion.value,
                        summary=summary,
                        obligations=planning.obligations,
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
                    self._run_ledger.set_check_run_id(run_key, check_run_id)
            finally:
                if actions_client is not None:
                    actions_client.close()
                client.close()

            self._store.mark_completed(event.delivery_id)
            return ProcessingResult(
                delivery_id=event.delivery_id,
                status="completed",
                conclusion=evaluation.github_conclusion.value,
                check_run_id=check_run_id,
                run_key=run_key,
            )
        except (GitHubAPIError, ValueError) as exc:
            reason_code = {
                "PhaseThreeRunPending": "phase3_run_pending",
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
                reason_code="unexpected_processing_error",
            )
