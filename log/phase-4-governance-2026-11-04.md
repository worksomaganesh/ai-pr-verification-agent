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
