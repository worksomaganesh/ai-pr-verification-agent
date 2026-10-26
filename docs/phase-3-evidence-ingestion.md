# Phase III — Authenticated evidence ingestion and reconciliation

## Verified baseline and release status

As of 2026-10-26, the previous branch head \`04e20cec32ebba28543c9baabc2b8bd759d51822\` passed exact-head CI in [run #40273344438](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40273344438). Both the Python quality gate and the exact-PR-head evidence producer passed. That CI run is a code/evidence-production verification, not proof that a customer or staging deployment is configured.

- Formatting, Ruff, and strict mypy passed on that baseline.
- 539 tests passed with one non-blocking Starlette/httpx deprecation warning.
- Coverage: 90.49% overall, 96% Phase I core, and 86% Phase II integration; all configured gates passed.
- The exact-head artifact was \`verification-evidence\`, ID \`12628049808\`, 42,862 bytes, API digest \`sha256:c48d46b1a88d2391462afc53dc7c6b90cdba8226c73e5b6b4270eac3e40f6dab\`.
- The current revision adds the explicit deployment smoke test described below. Wait for CI on that exact revision before treating the new script as CI-verified.

Keep PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6) in draft and do not enable production merge gating until the smoke test and human review have passed.

## Trust chain

1. Obtain workflow-run, job, and artifact metadata from the authenticated GitHub Actions REST API; webhook body fields and artifact contents are not authoritative.
2. Bind the run to the expected repository, PR number, base SHA, and head SHA. Only a completed successful \`pull_request\` run matching the exact head is eligible.
3. Load policy and workflow source from the trusted PR base SHA. The current base policy lists \`.github/workflows/ci.yml\` as trusted and marks workflow/policy/harness paths sensitive.
4. Validate the workflow contract before downloading evidence: exact PR-head checkout, disabled checkout credentials, per-test coverage and JUnit output, manifest export bound to the same PR-head SHA, and one final unconditional artifact upload using a full-SHA-pinned action, exact filenames, expected name, and \`if-no-files-found: error\`. Ambiguous or duplicate-key YAML fails closed.
5. Bind artifact metadata to the requested workflow run and repository identity. Require the platform-reported SHA-256 digest and compare it with the downloaded ZIP bytes.
6. Enforce archive/member/expanded-size limits, safe relative paths, regular files only, no encryption, bounded compression ratio, no duplicates, and exactly the two expected members.
7. Parse JUnit and the coverage manifest with Phase I parsers; require exact matching node inventories/outcomes and manifest head SHA equal to the expected commit.
8. Re-read the workflow-run identity/attempt and the live PR base/head after download; do not persist or publish a decision for stale metadata.
9. Record authenticated evidence idempotently in the durable ledger starting at INCONCLUSIVE; reconcile obligations using trusted target locations and separate assertion bindings; run the Phase I deterministic state machine and publish a freshness-checked Check Run. Ingestion alone never marks an obligation passed.

## Main modules

- \`verification_core.github_actions.GitHubActionsClient\`: authenticated, bounded and fully paginated run/job/artifact reads plus guarded ZIP download. Signed storage redirects are limited to an HTTPS allowlist, and the installation token is not forwarded to external storage.
- \`verification_core.actions_evidence\`: run/workflow/artifact identity, digest, bounded ZIP, JUnit/manifest inventory, outcome, and exact-commit validation.
- \`verification_core.manifest_export\`: exports measured per-test lines and branch arcs. It always emits \`behavioral_assertion_verified: false\`.
- \`verification_core.evidence_ledger.SQLAlchemyEvidenceLedger\`: immutable evidence identity and digest metadata, idempotent ingestion, separate terminal reconciliation writes, and conflict protection.
- \`verification_core.phase_three\` and \`verification_core.phase_three_worker\`: trusted-base workflow validation, live PR freshness checks, conservative run selection, obligation reconciliation, and deterministic Check Run publication.
- \`verification_core.phase_two.PhaseTwoProcessor\` and \`verification_core.runtime\`: explicit \`VERIFICATION_PHASE_THREE_ENABLED=true\` opt-in; Actions read permission is requested only on that path; \`VERIFICATION_EVIDENCE_DATABASE_URL\` is mandatory when enabled; clients/ledgers are closed through the worker lifecycle.

## Deployment smoke test

The repository has no declared hosting provider, deployment endpoint, or production credentials. The smoke test is therefore an executable acceptance path, not a claim that a live deployment has already passed. Run it from the deployed worker/container or from an operator environment connected to the same evidence database used by that worker.

Install the integration dependencies in the smoke-test environment:

\`\`\`bash
python -m pip install -e ".[integration]"
\`\`\`

Configure these values through your deployment secret manager/environment (do not paste credentials into chat, commit them, or put a private key/database URL directly on a command line):

- \`PHASE3_SMOKE_BASE_URL\`: the deployed service origin, for example \`https://staging.example.net\`.
- \`PHASE3_SMOKE_REPOSITORY\`: \`owner/repository\` containing the test PR.
- \`PHASE3_SMOKE_PR_NUMBER\`: an open PR number whose current head has exactly one successful trusted \`.github/workflows/ci.yml\` run and one \`verification-evidence\` artifact.
- \`GITHUB_APP_ID\`, \`GITHUB_INSTALLATION_ID\`, and \`GITHUB_APP_PRIVATE_KEY_PATH\` (or \`GITHUB_APP_PRIVATE_KEY\`): the installed App used by the service.
- \`GITHUB_WEBHOOK_SECRET\`: the exact webhook secret configured on the deployed endpoint.
- \`VERIFICATION_EVIDENCE_DATABASE_URL\`: the same evidence-ledger database URL as the worker; \`sqlite:///...\` requires the same host/file, while shared deployments should use the same \`postgresql+psycopg://...\` database.
- \`PHASE3_SMOKE_CONFIRM_REAL_CHECK_RUN=YES_I_EXPECT_A_REAL_CHECK_RUN\`: explicit consent to create a real Check Run for the chosen PR head.
- Optional \`PHASE3_SMOKE_TIMEOUT_SECONDS\`: 15–600 seconds; defaults to 180.

Run:

\`\`\`bash
python scripts/phase3_deployment_smoke.py
\`\`\`

The script fails closed unless all of these checks pass:

1. The service health endpoint responds.
2. The installed GitHub App can request a token with \`actions:read\`, read the exact-head successful workflow run, list its artifact, download the ZIP through the production allowlist logic, and independently match the downloaded bytes to GitHub's SHA-256 digest.
3. An invalid HMAC receives HTTP 401.
4. A valid, signed \`synchronize\` webhook is durably accepted and submitting that same delivery again is recognized as a duplicate.
5. A fresh completed Check Run appears for the exact current PR head and references the same successful workflow run plus a persisted evidence-record key.
6. The configured database contains that record with the same repository, PR, base/head SHA, workflow-run ID, artifact ID, and artifact SHA-256. If the Check Run yields a terminal success/failure/cancelled conclusion, the separately persisted terminal reconciliation status and decision digest must agree.
7. The PR base/head are unchanged through completion; stale publication fails the test.

This deliberately writes a real Check Run and enqueues a real webhook event. Use a staging installation/repository when possible. The script does not perform destructive failure injection against a live database; database outage, stale-PR races, malformed artifacts, and GitHub API failure handling remain covered by automated unit/regression tests. A health response alone is not accepted as proof that Phase III is operational.

## Security properties and limits

- **Integrity is not authenticity:** the artifact digest verifies bytes; workflow/job/run metadata from the authenticated API establishes provenance.
- **Coverage is not semantic proof:** the exporter never asserts behavioral assertion verification. Only independently trusted base-policy selector/category/severity bindings can supply assertion semantics to reconciliation.
- **Fail closed:** stale, missing, malformed, oversized, ambiguous, contradictory, untrusted, or failed evidence cannot become a machine-verified pass. A pending workflow is retryable; invalid completed evidence yields an inconclusive/action-required path.
- **V1 aggregation policy:** one eligible trusted run and exactly one configured artifact. Multiple eligible runs are treated as ambiguous. Shards and cross-run/rerun aggregation are deliberately unsupported until a separate protocol defines identity, completeness, conflict handling, and freshness semantics.
- **Operational boundary:** repository CI proves automated tests and the trusted evidence producer on the exact PR head. A live App/webhook/database/Check Run path must be tested in the target deployment before merge gating is enabled.

## Acceptance status

- [x] Exact-head formatting, Ruff, strict mypy, tests, and all configured coverage gates passed on baseline \`04e20cec32ebba28543c9baabc2b8bd759d51822\` (run [#40273344438](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40273344438)).
- [x] Exact-PR-head evidence producer succeeded and uploaded the required artifact on that baseline.
- [x] The baseline artifact SHA-256 matched GitHub's artifact API digest, with exactly \`junit.xml\` and \`coverage-manifest.json\`; JUnit/manifest inventories and exact head binding were verified.
- [x] Runtime integration is behind explicit opt-in, requests Actions read permission only on that path, and requires durable evidence-ledger configuration.
- [x] Regression tests cover missing/in-progress/failed/ambiguous workflow paths, malformed metadata/archive, stale PR/run identities, reconciliation and publication/ledger failure behavior.
- [ ] Run \`scripts/phase3_deployment_smoke.py\` against the actual staging/target deployment and record its output without recording secrets.
- [ ] Complete human review and merge PR #6 after the operational smoke test passes.
