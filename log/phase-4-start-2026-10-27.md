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

### Validation status

- GitHub contents API accepted the implementation commit d0e69fa80f4883bbe91abef777c6dc855aaef0a7 and test commit a40ab51786899f41d1f9fc7f5e5f6c8363377753.
- Exact-head CI has not yet been confirmed in this log. Do not claim the change is complete or green until the workflow run for the latest branch head finishes and both jobs are inspected.
- The new tests cover allowed request shape, default-off behavior, workflow/ref validation, schema-required inputs, unknown keys, required fields, enumerations/patterns, malformed schema configuration, and sanitized API errors.

### Remaining blockers / next actions

1. Inspect exact-head workflow run and both job results for the latest commit; fix failures and repeat.
2. Verify the evidence artifact belongs to that exact SHA and inspect its contents/digest where tooling permits.
3. Add operator authorization and durable audit trail before exposing dispatch via a production API/UI.
4. Do not assume Phase III code is included: PR #6 remains separate and draft. Establish the intended branch lineage before building an end-to-end orchestration layer.
5. Keep live deployment smoke acceptance and human review as Phase IV ending gates; never enable production merge gating based on unit tests alone.
