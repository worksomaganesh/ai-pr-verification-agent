# Phase III failure analysis and lessons

## Snapshot

- PR #6: 164 commit records, open/draft at audit time.
- Relevant CI runs: 120; 8 success, 104 failure, 8 cancelled.
- Latest audited SHA: `d9bc46f2fad9ac0527f87b6d692cb8f88929fc37`.
- Main SHA at audit time: `d9bc46f2fad9ac0527f87b6d692cb8f88929fc37`.
- Phase III estimate stays at 90% until actual acceptance gates pass; it is not a CI success percentage.

## Confirmed blocker sequence from inspected runs in this chat

1. Bootstrap workflow imported `verification_core.manifest_export` before the exporter module existed. Lesson: workflow producer and code must ship together.
2. Exporter initially had no measured coverage, pushing total coverage below threshold. Lesson: every new production module needs focused tests.
3. Very long pytest parameter values produced JUnit testcase names over 2,000 characters. Stable short parameter IDs fixed reporting without relaxing parser limits.
4. Large YAML/workflow parameter values produced JUnit node IDs above 500 characters. Use explicit bounded IDs in tests.
5. Trusted-base merge exposed exact-head formatting failures. CI is sequential; a formatter failure means downstream tests and coverage are skipped.
6. Ruff lint found issues after formatting, then strict typing exposed module re-export assumptions and import ordering.
7. A malformed workflow-run response was translated to a sanitized Actions-specific error, while the old test still expected an internal helper message.
8. Overall coverage was 87.53% against 90%; `phase_three_worker.py` had 23% coverage. Worker orchestration tests were added, but CI must prove they run and lift coverage.

## Why progress repeatedly stayed flat

- Formatting-only commits are necessary hygiene, not feature acceptance.
- A run that fails at formatting or lint never validates later gates.
- A green run on an older SHA does not validate the current head.
- A generated artifact is not proof unless it exists on the exact SHA and its identity/contents are validated.
- Completion cannot be credited for tests that were added but never executed successfully.

## Next move

1. Inspect the latest run's earliest failed step and fix it.
2. Re-run formatting → lint → strict mypy → full tests → overall coverage ≥90% → Phase I and II gates.
3. Inspect artifacts from the exact successful run and verify manifest commit/base/head identity.
4. Exercise exact trusted run selection → evidence ingestion → deterministic obligation reconciliation → durable ledger → Check Run publication.
5. Update the tracker only after every acceptance gate is evidenced; then review and merge PR #6.

## Process lessons for next projects

- Use a pre-push command that runs all inexpensive gates before triggering hosted CI.
- Test adversarial parameter IDs and parser limits early.
- Build one integration test from the external event through final publication, not only helper unit tests.
- Attach sanitized failure diagnostics to CI artifacts.
- Keep an immutable commit/run audit and never confuse activity/contribution count with verified progress.
