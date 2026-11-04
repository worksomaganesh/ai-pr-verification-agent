# Phase IV — Opt-in Dispatch and Human Governance

## Status

Phase IV now contains the guarded dispatch client, strict per-workflow schemas, GitHub operator allowlisting and repository permission checks, a SQLAlchemy write-ahead audit store, a one-shot dispatch coordinator, and exact-SHA workflow-run reconciliation. Exact-head CI on `15245242e967d1fdb6e912c8686446f5188795e5` passed [run #41805099119](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41805099119): 406 tests, 90% overall coverage, Phase I core 96%, Phase II integration 86%; formatting, Ruff, strict mypy, and all configured coverage gates passed. Focused governance CI passed 43 tests. Artifact 13309248666 (32,239 bytes; SHA-256 `78166497cc7a77d7caacd44ab89282136197240b351905d02f9c7a4b2b0643f4`) was downloaded and independently checked. Its ZIP contains junit.xml and coverage-manifest.json; both identify 406 passing tests with zero failures/errors/skips and exact head `15245242e967d1fdb6e912c8686446f5188795e5`. All behavioral_assertion_verified flags are false; it is test/coverage evidence, not behavioral proof. All dispatch tests use mocked GitHub APIs. No real workflow has been dispatched. PR #9 remains draft. Phase III integration, live deployment smoke acceptance, and human review remain open and are retained as Phase IV ending gates.

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

Workflow dispatch is an external side effect. The new governance coordinator verifies the token identity against a configured login allowlist and GitHub repository permission, writes dispatch intent before network I/O, prevents duplicate dispatch IDs, and reconciles one correlated Actions run against the authorized SHA. It stores an input digest rather than raw inputs or credentials. This is a library-level capability with mocked API tests; no production route or live staging dispatch has been wired or exercised. Schema validation and a login allowlist do not replace deployment-specific operator policy, least-privilege token configuration, managed database operations, or human approval.

## Verification plan

- Unit tests: disabled-by-default behavior, allowlist rejection, unsafe ref rejection, schema-required inputs, unknown input rejection, required fields, regex/enumeration validation, input count/size/type checks, secret-like input rejection, malformed repository rejection, configuration validation, and sanitized API failures.
- Integration tests with a mock GitHub API: request shape and auth header; never use real dispatch in ordinary CI.
- Staging acceptance: manually opt in with a staging-only workflow and a non-production PR; verify workflow run identity and exact SHA, then reconcile evidence through the Phase III authenticated pipeline.
- Governance acceptance: record human review against the same exact head SHA and confirm that stale approvals cannot authorize a newer commit.
- Release rule: keep PR #6 draft and production merge gating disabled until the live Phase III smoke test and human review both pass.

## Remaining work

- Re-run exact-head CI after any further source or documentation edits; current exact-head CI is green on `15245242e967d1fdb6e912c8686446f5188795e5`.
- Review workflow dispatch API behavior against the supported GitHub App installation permission and repository settings.
- Wire the governance coordinator into a deliberate, authenticated staging-only operator entry point; configure a managed PostgreSQL store and operator policy.
- Integrate dispatch with Phase III evidence reconciliation only after the Phase III implementation is available in the same branch lineage.
- Add exact-SHA and stale-run checks to orchestration; no dispatch result may imply verification success.
- Complete Phase III deployment smoke acceptance and Phase IV human review at the phase ending.
