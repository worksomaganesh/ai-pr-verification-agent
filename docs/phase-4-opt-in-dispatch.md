# Phase IV — Opt-in Dispatch and Human Governance

## Status

Latest integrated branch head: `9ca28e185c586ec3b05549635baca2482fda35b6` on `phase-4-opt-in-dispatch` (PR #9).

Exact-head verification on 5 November 2026:
- Full CI [#42055438789](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42055438789): success on `9ca28e185c586ec3b05549635baca2482fda35b6`; formatting, Ruff, strict mypy, all tests, all coverage gates, and exact-head evidence producer passed.
- Focused Phase IV governance [#42055438742](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42055438742): success on the same head.
- 710 tests passed; one non-blocking warning.
- Overall coverage 90.28%; Phase I core 96.39%; Phase II integration 85.99%.
- Artifact `verification-evidence`, ID `13429121701`, 51,738 bytes, digest `sha256:679cae107d2488a39c9396d95231a651b12bbe28bfa4863b4d6cb6710b1dfc6e`. Downloaded ZIP digest independently matched. The archive contains `junit.xml` and `coverage-manifest.json`; both inventories contain 710 unique matching test IDs, all passed, and manifest head binding matches `9ca28e185c586ec3b05549635baca2482fda35b6`. All `behavioral_assertion_verified` flags are false.
- The staging workflow was registered on the default branch in commit [`59b3610`](https://github.com/worksomaganesh/ai-pr-verification-agent/commit/59b361012e47f5c62db6d508a87b040f1297a623) and is also present on this feature branch.

**Implementation/CI status: complete for the current integrated source checkpoint. Operational acceptance is still open.** No operator-mediated live dispatch/reconciliation or Phase III deployed smoke test has been recorded. The workflow references the GitHub `staging` environment, but environment protection rules and credentials are not verified here. PR #9 remains draft. No review is recorded yet. Keep production merge gating disabled.

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

The exact-SHA and stale-run protections are implemented in the coordinator and covered by mocked adversarial tests. The remaining work is deployment/operator acceptance:

1. Provision a staging-only deployment and an authenticated operator entry point that calls the coordinator; keep it unavailable to production by default.
2. Configure the deployment-specific operator login allowlist, a least-privilege Actions-write token, GitHub App installation permissions, and managed PostgreSQL audit/evidence databases through the deployment secret manager.
3. Configure an allowlisted staging workflow with the required `verification_dispatch_id` input and run-name correlation contract.
4. Perform one deliberate non-production dispatch. Verify actor, workflow, dispatch ID, repository, requested ref, authorized SHA and unique run ID; exercise duplicate, timeout, ambiguous-run and stale-SHA fail-closed behavior against the real staging API.
5. Follow that exact run through Phase III authenticated job/artifact retrieval, digest and archive validation, exact-SHA binding, evidence-ledger persistence, obligation reconciliation, freshness re-check and Check Run publication.
6. Run `scripts/phase3_deployment_smoke.py` against the real installed App, webhook ingress/worker and same durable evidence database.
7. Obtain human review against the same exact head, confirm that a later head invalidates the approval, and record explicit release acceptance.
8. Only after these gates pass, remove draft status and follow the repository's normal review/merge process. Do not enable production merge gating before approval.

