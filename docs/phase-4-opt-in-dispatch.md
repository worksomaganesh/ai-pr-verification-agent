# Phase IV — Opt-in Dispatch and Human Governance

## Status

Phase IV contains the guarded dispatch client, strict per-workflow schemas, GitHub operator allowlisting and repository permission checks, a SQLAlchemy write-ahead dispatch audit, a one-shot dispatch coordinator, exact-SHA workflow-run reconciliation, and exact-head human-review verification/audit integration.

The latest integrated exact-head full CI passed on `3046eeb2681e0102f4ca9b978802e008a6baa13a` ([run #41850039278](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850039278)):
- **687 tests passed**, one non-blocking Starlette/httpx deprecation warning.
- Overall coverage **90.23%** (90.00% gate).
- Phase I core coverage **96.39%** (95.00% gate).
- Phase II integration coverage **85.99%** (80.00% gate).
- Formatting, Ruff, strict mypy, all coverage gates, and the exact-head evidence producer passed.
- Focused Phase IV governance CI passed on the same SHA ([run #41850039261](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850039261)).

The same full run produced artifact `verification-evidence`, ID `13334261929`, size 50,013 bytes, SHA-256 `72d5a21ff1bf191f4f56e84d9a14db8242db71e28ee4de2cca361d48eb76ae87`. Its ZIP contains `junit.xml` and `coverage-manifest.json`; both inventories contain 687 unique passing tests, zero failures/errors/skips, and the exact head SHA above. The downloaded ZIP digest was independently recomputed and matched GitHub's artifact metadata. All manifest `behavioral_assertion_verified` flags are false: this artifact proves test execution and measured coverage, not behavioral assertion sufficiency.

Human-governance implementation now includes `src/verification_core/human_governance.py` and `tests/unit/test_human_governance.py`. The verifier accepts only current approvals from configured reviewers on an open same-repository PR and exact base/head SHA; later non-approval reviews supersede earlier approvals. The audit ledger is append-only through its API, idempotent for exact replay, and rejects conflicting content for the same review ID. `apply_verified_human_approval` checks repository/PR/base/head binding, delegates severity and state-transition decisions to the existing domain state machine, and records the audit before returning the approved obligation.

**Repository CI is green; operational acceptance is not complete.** Dispatch and review tests use mocked GitHub APIs. No real staging workflow dispatch has been performed, no staging-only authenticated operator entry point has been exercised, and no target deployment smoke test or human release approval has been completed. PR #9 remains draft. Keep production merge gating disabled.

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

- Re-run exact-head CI after any further source or documentation edits; current exact-head CI is green on `3046eeb2681e0102f4ca9b978802e008a6baa13a`.
- Review workflow dispatch API behavior against the supported GitHub App installation permission and repository settings.
- Wire the governance coordinator into a deliberate, authenticated staging-only operator entry point; configure a managed PostgreSQL store and operator policy.
- Wire the dispatch coordinator into the staging-only operator entry point and follow its exact-SHA run through the already-integrated Phase III evidence reconciliation path.
- Add exact-SHA and stale-run checks to orchestration; no dispatch result may imply verification success.
- Complete Phase III deployment smoke acceptance and Phase IV human review at the phase ending.
