# Phase IV build log — 2026-10-27

## Change: explicit per-workflow input schemas

### Why this was the next step

The initial dispatch client had generic bounds and rejected credential-like input names, but any other input name/value pair could still be sent to an allowlisted workflow. That is too permissive for an external side effect: a workflow may interpret an arbitrary input as a mode, target, or operational flag that the caller did not intend to expose.

### Implementation

- Added immutable WorkflowInputRule with required/optional status, maximum value length, optional full-match regular expression, and optional enumerated values.
- Made input_schemas a required constructor argument and require its workflow keys to match the allowlist exactly.
- Reject unconfigured input names, missing required inputs, invalid patterns/enumerations, malformed schema definitions, credential-like names, excess inputs, oversized values, non-string values, and control characters before network I/O.
- Kept dispatch disabled by default and retained the exact HTTP 204 success contract, sanitized remote failures, and no automatic retry.
- Updated mocked-API tests and Phase IV documentation. No live dispatch was performed.

### CI and evidence verification

- First exact-head run #40469664384 failed only the formatting check. The CI log pinpointed two formatting-only changes in workflow_dispatch.py; these were corrected in commit 94f25098af2fd048fe404cd9110ce12ee4a8b308.
- Exact-head CI run #40469768700 passed on code head 94f25098af2fd048fe404cd9110ce12ee4a8b308: formatting, Ruff lint, strict mypy, all configured coverage gates, and 391 tests. Overall coverage was 91.28%; Phase I core was 96%; Phase II integration was 86%. One non-blocking Starlette/httpx deprecation warning and GitHub Actions Node 20 deprecation warnings remain.
- Evidence artifact: verification-evidence, ID 12717323937, size 30,643 bytes, GitHub SHA-256 646caf63c61a3cc598680bb3c0b1c2494c186416b2604a70969462c0db28b615.
- Downloaded artifact bytes independently hashed to the same SHA-256. ZIP contains exactly junit.xml and coverage-manifest.json. JUnit has 391 unique testcases, zero failures/errors/skips. Manifest contains 391 unique node IDs, all outcomes passed, and head_sha exactly 94f25098af2fd048fe404cd9110ce12ee4a8b308. Every behavioral_assertion_verified flag is false; the artifact is test/coverage evidence, not proof of behavior beyond those assertions.
- The docs/log reconciliation itself creates a new branch head; its own exact-head CI/evidence run is still required before the branch's latest SHA can be marked verified.

### Remaining blockers / next actions

1. Verify exact-head CI and artifact after this documentation/log reconciliation commit; fix any failures and repeat against the new head.
2. Add authenticated operator authorization and a durable audit trail before exposing dispatch via a production API/UI.
3. Do not assume Phase III code is included: PR #6 remains separate and draft. Establish the intended branch lineage before building an end-to-end orchestration layer.
4. Keep live deployment smoke acceptance and human review as Phase IV ending gates; never enable production merge gating based on unit tests alone.
