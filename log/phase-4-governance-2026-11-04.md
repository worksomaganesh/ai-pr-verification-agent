# Phase IV governance and CI record — 2026-11-04

## Latest integrated state and corrections

- Current Phase IV branch head: `0c9ef6056123ad3b5b9103e85d31b0a9648b8068`.
- Full exact-head CI [#41850967572](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850967572): passed — 687 tests, 90.23% overall coverage, 96.39% Phase I coverage, 85.99% Phase II coverage; formatting, Ruff, strict mypy and all coverage gates passed.
- Focused governance CI [#41850967471](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850967471): passed — formatting, Ruff, strict mypy and dispatch/workflow/human-governance tests.
- Exact-head artifact `13335151007`, size 49,841 bytes, SHA-256 `30d2efc2f3b0b5abfd9b3882c78c6a902781f21c4f7aa247b7370738529f1bc8`; CI upload and GitHub metadata confirm the artifact belongs to the exact branch head. It has not been independently downloaded and parsed.
- Phase III is no longer awaiting source integration. PR #6 head `9611cbc6504f3844770540c9d45f87864bdfae08` is an ancestor of this branch (72 commits ahead, 0 behind) through merge commit `8a17bd22abcfdea02111f7fa7768c5ba9b4c29a1`. The earlier statement below that Phase III was still separate is a historical snapshot and is superseded.
- Live deployment smoke testing, real staging dispatch, operator entry-point configuration and human release approval remain outstanding. No production merge gating should be enabled.

---

# Phase IV governance and CI record — 2026-11-04

## Implemented on branch `phase-4-opt-in-dispatch`

- `dispatch_governance.py`: GitHub `/user` identity lookup, configured login allowlist, repository collaborator permission check, SQLAlchemy audit table, write-ahead authorization record, duplicate dispatch ID rejection, explicit outcome states, one-shot dispatch coordinator, unique correlation marker, and workflow-run lookup.
- Reconciliation requires exactly one matching workflow run for the expected workflow, dispatch ID, actor, and time window. It compares the run's `head_sha` to the authorized SHA; mismatch is recorded and rejected.
- `tests/unit/test_dispatch_governance.py`: 13 test functions / parameterized cases covering auth, audit durability, duplicate prevention, unknown timeout outcome, exact-SHA match/mismatch, delayed run visibility, duplicate correlation, and malformed dispatch IDs.
- `.github/workflows/phase4-governance.yml`: focused formatter, Ruff, strict mypy, and governance/dispatcher test workflow.

## CI investigation lessons

1. Runs `#41802482290`, `#41802656874`, `#41802776573`, `#41802841709`, `#41802867491`, `#41803091957`, `#41803406025`, and `#41803580242` surfaced formatter drift. The attempted newline-only updates did not apply Ruff's exact changes. We retrieved Ruff's unified diff from job logs and corrected the actual source/test formatting.
2. Run `#41804078616` passed formatting but found an unused `WorkflowInputRule` import, one long line, and import ordering. These were removed/fixed.
3. Run `#41804293145` passed formatting and Ruff but strict mypy rejected an `object` timestamp from the audit mapping. The timestamp is now type-checked (numeric, not bool, non-negative) before conversion.
4. Run `#41804904624` caught the resulting long condition line. It was wrapped to Ruff's canonical formatting.
5. The workflow-name regex initially had an over-escaped dot, which would have rejected valid `.yml`/`.yaml` names. It is corrected to a literal-dot expression. The focused test suite dispatches a valid `manual-verification.yml` workflow, exercising the accepted filename path.

## Final exact-head verification

- Head SHA: `15245242e967d1fdb6e912c8686446f5188795e5`.
- Full repository CI: [run #41805099119](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41805099119), successful. Formatting, Ruff, strict mypy, 406 tests, and all coverage gates passed.
- Overall coverage: 90% (gate 90%).
- Phase I core coverage: 96% (gate 95%).
- Phase II integration coverage: 86% (gate 80%).
- Focused governance workflow: [run #41805099089](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41805099089), successful; 43 tests passed.
- Evidence artifact: `verification-evidence`, ID `13309248666`, 32,239 bytes, SHA-256 `78166497cc7a77d7caacd44ab89282136197240b351905d02f9c7a4b2b0643f4`.
- Downloaded ZIP SHA-256 independently matches GitHub metadata. ZIP has exactly `junit.xml` and `coverage-manifest.json`. JUnit contains 406 testcases, zero failures/errors/skips. Manifest contains 406 tests and exact `head_sha` `15245242e967d1fdb6e912c8686446f5188795e5`. All `behavioral_assertion_verified` flags are false: this artifact supports test/coverage claims only, not behavioral proof.

## Explicit limitations and remaining acceptance

- Tests use mocked GitHub API transports. No real workflow was dispatched and no staging deployment was exercised.
- The coordinator is a library component; a production/staging API entry point, deployment-specific operator policy, managed PostgreSQL operations, token-scope validation, and human review wiring remain.
- Phase III PR #6 remains separate/draft and is not in this Phase IV branch lineage. End-to-end evidence reconciliation cannot be claimed until Phase III implementation is deliberately integrated and staging-tested.
- The Phase III live deployment smoke test (installed App, webhook delivery, worker, durable evidence DB, exact-head artifact ingestion, ledger persistence, Check Run publication) and human review remain required Phase IV ending gates.
- PR #9 remains draft and unmerged. Do not enable production merge gating. No production workflow, merge, or rollout was triggered.

## Next sequence

1. Integrate the Phase III implementation through an explicit reviewed branch-lineage decision.
2. Wire a staging-only authenticated operator action to this coordinator; use a managed PostgreSQL database and least-privilege GitHub credentials.
3. Add a staging workflow with the required correlation run-name/input contract and verify run/job/artifact authenticity, freshness, and exact SHA against Phase III.
4. Execute the Phase III live smoke test and record the human review against the same exact head.
5. Only after all gates and review pass, remove draft status and request review; keep production merge gating disabled until approved.


## Human review verification and state-machine integration — 2026-11-04

The following human-governance implementation is now part of the integrated branch:

- `src/verification_core/human_governance.py`:
  - `GitHubPullRequestApproval` is an immutable validated review fact containing repository, PR number, review ID, reviewer, base/head SHA, timezone-aware submitted timestamp and rationale.
  - `GitHubReviewVerifier` reads GitHub PR identity and review history, checks an explicit reviewer allowlist, requires an open same-repository PR, rejects stale expected base/head SHAs, and re-reads PR identity after review collection to detect a head change during verification.
  - Only the latest review by each allowlisted reviewer is authoritative; a later COMMENTED, CHANGES_REQUESTED or DISMISSED review supersedes an earlier approval.
  - Approvals must target the exact current head and include a bounded minimum rationale. Malformed identity/timestamps, unsupported pagination, oversized response bodies, HTTP errors, timeouts and malformed JSON fail closed.
  - `SQLAlchemyHumanReviewAuditLog` stores immutable approval records with rationale SHA-256, idempotent exact replay and conflict detection for reuse of a review ID with different content.
  - `apply_verified_human_approval` verifies repository, PR, base and head against `CommitIdentity`, converts the review into `HumanApprovalRecord`, delegates transition/severity policy to `apply_human_approval`, and writes the audit before returning the approved obligation.
- `tests/unit/test_human_governance.py` now exercises the verifier, malformed/hostile API inputs, transport failures, audit behavior and the domain state-machine adapter.
- `.github/workflows/phase4-governance.yml` now explicitly runs formatting, Ruff, mypy and pytest for both dispatch governance and human governance files.

## Final exact-head verification

- Branch head: `3046eeb2681e0102f4ca9b978802e008a6baa13a`.
- Combined full CI: [#41850039278](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850039278), success.
- Focused governance CI: [#41850039261](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850039261), success.
- 687 tests passed; formatting, Ruff, strict mypy and all coverage gates passed.
- Overall coverage 90.23%; Phase I 96.39%; Phase II 85.99%.
- Evidence artifact ID 13334261929, 50,013 bytes, SHA-256 `72d5a21ff1bf191f4f56e84d9a14db8242db71e28ee4de2cca361d48eb76ae87`. Downloaded ZIP hash independently matches GitHub metadata. Exactly `junit.xml` and `coverage-manifest.json`; each inventory has 687 unique passing tests, zero failures/errors/skips and exact head binding. All behavioral assertion flags remain false.

## Explicit operational boundary

The repository implementation and exact-head CI are green. No real staging workflow dispatch or target deployment smoke test has been performed. A production/staging operator route, managed PostgreSQL configuration, installed App credentials, webhook/worker deployment, and a human release approval remain environment/operator acceptance tasks. PR #9 remains draft. Do not enable production merge gating or merge on the strength of mocked API tests alone.
