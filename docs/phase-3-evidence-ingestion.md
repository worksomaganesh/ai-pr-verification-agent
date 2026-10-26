# Phase III — Authenticated evidence ingestion and reconciliation

## Current status (2026-10-26)

The Phase III implementation on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6) passed its exact-SHA CI and evidence-producer jobs on exact head 24de828e415e115d9a2992c527b60d32a09eddf4. See [CI run #40272969409](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40272969409).

- Formatting, Ruff, and strict mypy passed.
- 539 tests passed with one non-blocking Starlette/httpx deprecation warning.
- Overall coverage: 90.49% (90% required); Phase I core: 96% (95% required); Phase II integration: 86% (80% required).
- The exact-PR-head evidence job passed its per-test test run, manifest export, and artifact upload.
- Artifact verification-evidence, ID 12629355625, size 42,663 bytes; GitHub SHA-256 digest 915205085a98dd7f33cedc8ae7ea7e6ed203c63db034ae82d36b58a22dbbaac1.
- Independent download inspection confirmed exactly junit.xml and coverage-manifest.json, 539 unique matching test IDs in both, equal passing outcomes, exact head binding, no invalid structural entries, and all exporter assertion flags false.

The implementation and CI gates are verified on exact head `5658106e6ef03f6e46e8f5dfefad38056aaebccd` (98% implementation/CI acceptance). A deployment-specific smoke test using the configured GitHub App installation, webhook ingress, evidence database, and Check Run path remains a release-operational prerequisite. Keep the PR draft until that smoke test and human review are complete.

## Trust chain

1. Obtain workflow-run, job, and artifact metadata from the authenticated GitHub Actions REST API; webhook body fields and artifact contents are not authoritative.
2. Bind the run to the expected repository, PR number, base SHA, and head SHA. Only a completed successful pull_request run matching the exact head is eligible.
3. Load policy and workflow source from the trusted PR base SHA. The current base policy lists .github/workflows/ci.yml as trusted and marks workflow/policy/harness paths sensitive.
4. Validate the workflow contract before downloading evidence: exact PR-head checkout, disabled checkout credentials, per-test coverage and JUnit output, manifest export bound to the same PR-head SHA, and one final unconditional artifact upload using a full-SHA-pinned action, exact filenames, expected name, and if-no-files-found: error. Ambiguous or duplicate-key YAML fails closed.
5. Bind artifact metadata to the requested workflow run and repository identity. Require the platform-reported SHA-256 digest and compare it with the downloaded ZIP bytes.
6. Enforce archive/member/expanded-size limits, safe relative paths, regular files only, no encryption, bounded compression ratio, no duplicates, and exactly the two expected members.
7. Parse JUnit and the coverage manifest with Phase I parsers; require exact matching node inventories/outcomes and manifest head SHA equal to the expected commit.
8. Re-read the workflow-run identity/attempt and the live PR base/head after download; do not persist or publish a decision for stale metadata.
9. Record authenticated evidence idempotently in the durable ledger starting at INCONCLUSIVE; reconcile obligations using trusted target locations and separate assertion bindings; run the Phase I deterministic state machine and publish a freshness-checked Check Run. Ingestion alone never marks an obligation passed.

## Main modules

- verification_core.github_actions.GitHubActionsClient: authenticated, bounded and fully paginated run/job/artifact reads plus guarded ZIP download. Signed storage redirects are limited to an HTTPS allowlist, and the installation token is not forwarded to external storage.
- verification_core.actions_evidence: run/workflow/artifact identity, digest, bounded ZIP, JUnit/manifest inventory, outcome, and exact-commit validation.
- verification_core.manifest_export: exports measured per-test lines and branch arcs. It always emits behavioral_assertion_verified: false.
- verification_core.evidence_ledger.SQLAlchemyEvidenceLedger: immutable evidence identity and digest metadata, idempotent ingestion, separate terminal reconciliation writes, and conflict protection.
- verification_core.phase_three and verification_core.phase_three_worker: trusted-base workflow validation, live PR freshness checks, conservative run selection, obligation reconciliation, and deterministic Check Run publication.
- verification_core.phase_two.PhaseTwoProcessor and verification_core.runtime: explicit VERIFICATION_PHASE_THREE_ENABLED=true opt-in; Actions read permission is requested only on the Phase III path; VERIFICATION_EVIDENCE_DATABASE_URL is mandatory when enabled; clients/ledgers are closed through the worker lifecycle.

## Security properties and limits

- **Integrity is not authenticity:** the artifact digest verifies bytes; workflow/job/run metadata from the authenticated API establishes provenance.
- **Coverage is not semantic proof:** the exporter never asserts behavioral assertion verification. Only independently trusted base-policy selector/category/severity bindings can supply assertion semantics to reconciliation.
- **Fail closed:** stale, missing, malformed, oversized, ambiguous, contradictory, untrusted, or failed evidence cannot become a machine-verified pass. A pending workflow is retryable; invalid completed evidence yields an inconclusive/action-required path.
- **V1 aggregation policy:** one eligible trusted run and exactly one configured artifact. Multiple eligible runs are treated as ambiguous. Shards and cross-run/rerun aggregation are deliberately unsupported until a separate protocol defines identity, completeness, conflict handling, and freshness semantics.
- **Operational boundary:** CI proves the code's automated tests and the repository's trusted evidence producer on the exact PR head. It is not a deployment smoke test for a live installed GitHub App or user-specific webhook/DB configuration. That must be run in the target deployment before merge gating is enabled.

## Acceptance status

- [x] Exact-SHA formatting, Ruff, strict mypy, tests, and all configured coverage gates pass.
- [x] Exact-PR-head evidence producer succeeds and uploads the required artifact.
- [x] Actual uploaded ZIP SHA-256 independently matches GitHub's artifact API digest.
- [x] JUnit and manifest node inventories, outcomes, and manifest head SHA match; exporter assertion flags remain false.
- [x] Runtime integration is behind explicit opt-in, uses Actions read permission only on that path, and requires durable evidence-ledger configuration.
- [x] Regression tests cover missing/in-progress/failed/ambiguous workflow paths, malformed metadata/archive, stale PR/run identities, reconciliation and publication/ledger failure behavior.
- [ ] Run a deployment-specific smoke test with the target installed GitHub App: confirm actions:read, accepted real artifact ingestion, evidence-ledger persistence, and freshness-checked Check Run publication end to end.
- [ ] Complete human review and merge PR #6 after that operational smoke test.
