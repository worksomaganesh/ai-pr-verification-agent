# Verification Semantics & State Machine Specification (Phase 1A)

This document defines the deterministic verification semantics implemented in
`verification_core.domain`.

## 1. Core Invariants

1. **No Untrusted `PASSED` Assignment:** A `VerificationObligation` starts in `PROPOSED` and can
   reach `PASSED` only via `reconcile_obligation_evidence()` after verifying platform provenance
   (`workflow_head_sha == commit.head_sha`, `workflow_base_sha == commit.base_sha`, trusted base
   workflow, untampered test harness) and `EvidenceSufficiency.SUFFICIENT`.
2. **Coverage Is Necessary, Not Sufficient:** A passing test that fails to exercise modified target
   lines (`COVERAGE_MISS`), fails to exercise modified branches, or lacks behavioral assertion
   confirmation (`WEAK_EVIDENCE`) transitions to `INCONCLUSIVE`, never `PASSED`.
3. **Human Governance vs. Machine Proof:** `APPROVED_BY_HUMAN` and `WAIVED_BY_POLICY` are modeled
   and reported separately from machine-verified `PASSED` obligations. `CRITICAL` and `HIGH`
   obligations cannot be statically waived via `WAIVED_BY_POLICY`.
4. **Separation of Internal State and External GitHub API Conclusions:** Superseded runs transition
   internally to `InternalRunOutcome.STALE_SUPERSEDED` (and obligations to
   `ObligationStatus.STALE`), while mapping externally to `GitHubCheckConclusion.CANCELLED`
   (`"cancelled"`). The system never emits `"stale"` as a GitHub Check Run conclusion because
   GitHub reserves that value for internal platform use.
5. **Safe Empty-Obligation Handling:** `GitHubCheckConclusion.NEUTRAL` for an empty obligation set
   is permitted **only** when `analysis_completeness == AnalysisCompleteness.COMPLETE`,
   `policy_valid == True`, and `has_unsupported_critical_changes == False`.

## 2. Obligation State Transitions

| From State | Permitted Target States | Transition Guard |
| :--- | :--- | :--- |
| `PROPOSED` | `SCHEDULED`, `BLOCKED`, `NOT_RUN`, `WAIVED_BY_POLICY`, `STALE` | Scheduling requires a non-empty `candidate_test_id`; policy waivers forbid `CRITICAL`/`HIGH`. |
| `SCHEDULED` | `PASSED`, `FAILED`, `SKIPPED`, `BLOCKED`, `NOT_RUN`, `INCONCLUSIVE`, `STALE` | `PASSED` requires authentic commit-bound provenance + `ExecutionOutcome.PASSED` + `EvidenceSufficiency.SUFFICIENT`. Contradictory evidence fails closed to `FAILED`. |
| `NOT_RUN` / `SKIPPED` | `APPROVED_BY_HUMAN`, `WAIVED_BY_POLICY`, `STALE` | `APPROVED_BY_HUMAN` requires SHA-matching `HumanApprovalRecord` permitted by policy. |
| `INCONCLUSIVE` | `APPROVED_BY_HUMAN`, `STALE` | Requires SHA-matching `HumanApprovalRecord`. |
| `PASSED` / `FAILED` / `BLOCKED` / `APPROVED_BY_HUMAN` / `WAIVED_BY_POLICY` | `STALE` | Terminal unless superseded by a newer commit on the pull request. |

## 3. Conclusion Priority Order (`evaluate_verification_run`)

1. **Superseded Run (`superseded_by_sha` present or `STALE` obligations):** Internal
   `STALE_SUPERSEDED` -> GitHub `cancelled`.
2. **Invalid Base Policy (`policy_valid == False`):** Internal `FAILED_VERIFICATION` -> GitHub
   `failure`.
3. **Any `FAILED` or `BLOCKED` Obligation:** Internal `FAILED_VERIFICATION` -> GitHub `failure`.
4. **Incomplete/Truncated Context, Analyzer Error, or Unsupported Critical Change:** Internal
   `ACTION_REQUIRED_MISSING_EVIDENCE` (or `FAILED_VERIFICATION` in strict mode) -> GitHub
   `action_required` (or `failure`). Never `neutral` or `success`.
5. **Any Unverified Mandatory Obligation (`CRITICAL`/`HIGH` in `PROPOSED`, `SCHEDULED`, `NOT_RUN`,
   `SKIPPED`, or `INCONCLUSIVE`):** Internal `ACTION_REQUIRED_MISSING_EVIDENCE` (or
   `FAILED_VERIFICATION` in strict mode) -> GitHub `action_required` (or `failure`).
6. **Zero Obligations after Confirmed Complete Analysis:** Internal `NEUTRAL_NO_BEHAVIORAL_CHANGE`
   -> GitHub `neutral`.
7. **All Mandatory Satisfied, >=1 Unverified Advisory (`MEDIUM`/`LOW`):** Internal
   `NEUTRAL_ADVISORY_GAPS_ONLY` -> GitHub `neutral` (when `advisory_gaps_return_neutral=True`).
8. **All Mandatory Obligations Satisfied (`PASSED` or policy-permitted `APPROVED_BY_HUMAN`):**
   Internal `VERIFIED_SUCCESS` -> GitHub `success`.
