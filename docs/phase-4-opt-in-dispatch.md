# Phase IV — Opt-in Dispatch and Human Governance

## Status

Phase IV's guarded dispatch client now requires an explicit schema for every allowlisted workflow. Exact-head CI must be checked on the latest branch head before claiming the change is validated. Dispatch remains disabled by default; all tests use a mocked GitHub API and no workflow has been dispatched by this change. Phase III deployment smoke acceptance and human review remain open and are retained as Phase IV ending gates.

## Phase goals

1. **Opt-in dispatch:** allow only explicitly approved workflow files, refs, and bounded non-secret inputs; keep write-capable credentials separate from Phase II/III read-only clients.
2. **Safe orchestration:** dispatch only after a deliberate operator action, record the target repository/workflow/ref and operational identifiers where available, and handle retries without accidentally creating uncontrolled work.
3. **Evidence reconciliation:** preserve the Phase III rule that dispatched execution is not itself proof; authenticate run/job/artifact metadata, bind results to the exact commit, and fail closed for missing, stale, ambiguous, or contradictory evidence.
4. **Human governance:** preserve an auditable reviewer identity, review identifier, timestamp, rationale, and exact head SHA; human approval must remain distinct from machine evidence.
5. **Operational acceptance:** at Phase IV ending, configure a real staging deployment and run the Phase III live smoke test against the installed GitHub App, webhook ingress/worker, durable evidence database, and Check Run publication. Complete human review before enabling production merge gating.

## Dispatch safety contract

The client in verification_core.workflow_dispatch:

- is disabled unless the caller explicitly passes enabled=True;
- accepts only workflow filenames from a caller-supplied allowlist;
- requires a schema for exactly each allowlisted workflow, with no implicit fallback;
- permits only schema-declared input names, validates required inputs, optional regex patterns, enumerated values, and per-field length limits;
- retains the overall maximum of 10 inputs and 1,024 characters per value;
- rejects input names that look like credentials and rejects control characters;
- requires a caller-supplied token already scoped for the intended repository and Actions write access;
- validates repository names and branch/tag refs before network I/O;
- sends only the requested workflow, ref, and validated inputs; it does not run arbitrary shell commands or execute PR code itself;
- sanitizes API failures and does not echo remote error bodies;
- has no automatic retry, background dispatch, merge, or production rollout behavior.

WorkflowInputRule is immutable and validates its own configuration. The caller must supply input_schemas; an empty schema for an allowlisted workflow means that workflow accepts no inputs. Never put secrets in workflow inputs. Store credentials in a secret manager and pass only secret references or non-sensitive identifiers.

Workflow dispatch is an external side effect. Before production exposure, callers must still add authenticated operator authorization and a durable audit trail; schema validation alone is not authorization.

## Verification plan

- Unit tests: disabled-by-default behavior, allowlist rejection, unsafe ref rejection, schema-required inputs, unknown input rejection, required fields, regex/enumeration validation, input count/size/type checks, secret-like input rejection, malformed repository rejection, configuration validation, and sanitized API failures.
- Integration tests with a mock GitHub API: request shape and auth header; never use real dispatch in ordinary CI.
- Staging acceptance: manually opt in with a staging-only workflow and a non-production PR; verify workflow run identity and exact SHA, then reconcile evidence through the Phase III authenticated pipeline.
- Governance acceptance: record human review against the same exact head SHA and confirm that stale approvals cannot authorize a newer commit.
- Release rule: keep PR #6 draft and production merge gating disabled until the live Phase III smoke test and human review both pass.

## Remaining work

- Verify exact-head CI and its evidence artifact on the current Phase IV head.
- Review workflow dispatch API behavior against the supported GitHub App installation permission and repository settings.
- Add authenticated operator authorization and a durable dispatch audit record before production exposure.
- Integrate dispatch with Phase III evidence reconciliation only after the Phase III implementation is available in the same branch lineage.
- Add exact-SHA and stale-run checks to orchestration; no dispatch result may imply verification success.
- Complete Phase III deployment smoke acceptance and Phase IV human review at the phase ending.
