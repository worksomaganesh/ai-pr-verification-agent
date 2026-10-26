# Phase III handoff — AI PR Verification Agent

Last reconciled: 2026-10-26

## Repository and latest verified baseline

- Repository: \`worksomaganesh/ai-pr-verification-agent\`
- Branch: \`phase-3-evidence-ingestion\`
- PR: [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), open and draft
- Previous exact-head CI checkpoint: \`04e20cec32ebba28543c9baabc2b8bd759d51822\`
- Exact-SHA CI: [run #40273344438](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40273344438) — success; both quality and evidence-producer jobs passed.
- Progress: 99% implementation/CI/evidence-production verified; live deployment smoke test and human review remain.
- Current change adds \`scripts/phase3_deployment_smoke.py\` and its runbook/tests. Treat this addition as unverified until CI passes on its exact commit. Do not reuse the baseline SHA as the new branch head.

## Baseline verified results

- Formatting, Ruff, strict mypy passed.
- 539 tests passed, with one non-blocking deprecation warning.
- Coverage: 90.49% overall, 96% Phase I core, and 86% Phase II integration.
- Artifact \`verification-evidence\`, ID \`12628049808\`, size 42,862 bytes, SHA-256 \`c48d46b1a88d2391462afc53dc7c6b90cdba8226c73e5b6b4270eac3e40f6dab\`.
- Artifact ZIP matched the API digest. Expected members are \`junit.xml\` and \`coverage-manifest.json\`; test inventories match and all exporter assertion flags are false.
- The deterministic-fixture fix pins ZIP entry timestamps/compression only in the test helper; production evidence-ledger conflict detection is unchanged.

## Implemented trust chain

Authenticated GitHub Actions run/job/artifact metadata → trusted-base workflow contract validation → digest-checked bounded ZIP → matching JUnit and manifest inventory → exact-commit durable evidence ledger → policy-bound obligation reconciliation → freshness-checked Check Run publication.

Runtime integration is opt-in via \`VERIFICATION_PHASE_THREE_ENABLED=true\`; the enabled path requires \`VERIFICATION_EVIDENCE_DATABASE_URL\` and an installed GitHub App authorized for Actions read. V1 intentionally accepts one eligible trusted run and one artifact. Missing, malformed, stale, ambiguous, or contradictory evidence fails closed.

## New operational smoke-test path

Read \`docs/phase-3-evidence-ingestion.md\` before running \`scripts/phase3_deployment_smoke.py\`. It requires the deployed service URL, the App ID/installation/private key, exact webhook secret, and the *same* evidence database used by the worker. The explicit opt-in \`PHASE3_SMOKE_CONFIRM_REAL_CHECK_RUN=YES_I_EXPECT_A_REAL_CHECK_RUN\` is mandatory because the script creates a real Check Run and enqueues a signed webhook for an open PR.

The smoke test performs a preflight on the exact current PR head, reads the successful trusted Actions run/artifact through the App, independently verifies downloaded ZIP SHA-256, checks invalid-signature rejection and duplicate-delivery idempotency, waits for a new freshness-bound Check Run, and compares its evidence record to the database row. It avoids destructive failure injection; automated regression tests remain responsible for stale-race, malformed-artifact, DB/API failure branches.

## Release blockers

1. CI must pass on the new smoke-test commit.
2. The deployment smoke test must pass against the real target/staging service and same database.
3. A human must review PR #6.

The live target endpoint, App private key, webhook endpoint configuration, and evidence DB connection are not available through the repository integration. The live smoke test has not been performed. Keep PR #6 draft and production merge gating disabled until these release gates are complete.

## Current evidence anchor

- Previous exact-head CI run: [#40273344438](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40273344438)
- Current smoke-test implementation and its exact-head CI result must be read from PR #6 and the latest Actions run after this commit.
