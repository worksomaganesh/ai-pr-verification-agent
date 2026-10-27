# Phase IV — Opt-in Dispatch and Human Governance

## Status

Phase IV has started. The initial implementation slice adds a guarded GitHub Actions workflow-dispatch client and unit tests. Dispatch remains disabled by default; no workflow has been dispatched by this change. Phase III deployment smoke acceptance and human review remain open and are retained as Phase IV ending gates.

## Phase goals

1. **Opt-in dispatch:** allow only explicitly approved workflow files, refs, and bounded non-secret inputs; keep write-capable credentials separate from Phase II/III read-only clients.
2. **Safe orchestration:** dispatch only after a deliberate operator action, record the target repository/workflow/ref and operational identifiers where available, and handle retries without accidentally creating uncontrolled work.
3. **Evidence reconciliation:** preserve the Phase III rule that dispatched execution is not itself proof; authenticate run/job/artifact metadata, bind results to the exact commit, and fail closed for missing, stale, ambiguous, or contradictory evidence.
4. **Human governance:** preserve an auditable reviewer identity, review identifier, timestamp, rationale, and exact head SHA; human approval must remain distinct from machine evidence.
5. **Operational acceptance:** at Phase IV ending, configure a real staging deployment and run the Phase III live smoke test against the installed GitHub App, webhook ingress/worker, durable evidence database, and Check Run publication. Complete human review before enabling production merge gating.

## Initial dispatch safety contract

The initial client in verification_core.workflow_dispatch:

- is disabled unless the caller explicitly passes enabled=True;
- accepts only workflow filenames from a caller-supplied allowlist;
- validates repository names and branch/tag refs before network I/O;
- accepts at most 10 named string inputs, with a 1,024-character limit per value;
- rejects input names that look like credentials and rejects control characters;
- requires a caller-supplied token already scoped for the intended repository and Actions write access;
- sends only the requested workflow, ref, and normalized inputs; it does not run arbitrary shell commands or execute PR code itself;
- sanitizes API failures and does not echo remote error bodies;
- has no automatic retry, background dispatch, merge, or production rollout behavior.

Workflow dispatch is an external side effect. Production callers must add an authenticated operator authorization layer and durable audit trail before exposing this client through an API or UI. Never place secrets in workflow inputs. Store credentials in a secret manager and pass only secret references or non-sensitive identifiers.

## Verification plan

- Unit tests: disabled-by-default behavior, allowlist rejection, unsafe ref rejection, input count/size/type checks, secret-like input rejection, malformed repository rejection, and sanitized API failures.
- Integration tests with a mock GitHub API: request shape and auth header; never use real dispatch in ordinary CI.
- Staging acceptance: manually opt in with a staging-only workflow and a non-production PR; verify workflow run identity and exact SHA, then reconcile evidence through the Phase III authenticated pipeline.
- Governance acceptance: record human review against the same exact head SHA and confirm that stale approvals cannot authorize a newer commit.
- Release rule: keep PR #6 draft and production merge gating disabled until the live Phase III smoke test and human review both pass.

## Remaining work

- Review workflow dispatch API behavior against the supported GitHub App installation permission and repository settings.
- Add an authenticated operator authorization and durable dispatch audit record before production exposure.
- Define a narrow workflow-input schema per allowlisted workflow rather than relying only on generic bounded strings.
- Add exact-SHA and stale-run checks to orchestration; no dispatch result may imply verification success.
- Complete Phase III deployment smoke acceptance and Phase IV human review at the phase ending.
