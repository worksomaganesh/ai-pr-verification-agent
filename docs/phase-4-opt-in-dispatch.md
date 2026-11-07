# Phase IV — Opt-in Dispatch and Human Governance

## Status — updated 7 November 2026

Current branch: `phase-4-opt-in-dispatch`; integrated PR #9 remains open and draft. The latest code changes are recorded in commits `89c089305d7c84a0c5b49902efb2315d6411bfd6` and `f0e64e6701f4ba031e20cbca10f1abc333c648cc`; large-ID regression coverage is in `a898506fef046b453d3a04d14b03a5772138600e`. The current documentation/log checkpoint may be newer than that source commit.

The previous integrated source head `851d94369cccb17c0fce2bb084332afaa097f656` passed full CI [#42065231885](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42065231885) and Phase IV governance [#42065232420](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42065232420): 710 tests passed, 0 failures/errors/skips; coverage was 90.28% overall, 96.39% Phase I core, and 85.99% Phase II integration. These results predate the 64-bit identifier fix; the new head requires fresh exact-head CI evidence.

### First owner-authorized staging dispatch attempt

The owner configured `staging` → `PHASE4_GITHUB_TOKEN` as an Environment secret. No secret value is stored in the repository.

Operator run [#42365086398](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42365086398) targeted `851d94369cccb17c0fce2bb084332afaa097f656`. Token validation, owner/confirmation checks, exact-SHA checkout, Python setup, dependency installation, and the dispatch step passed. The operator submitted one `phase4-staging-dispatch.yml` request with correlation ID `0c8383a3e0b6426793ab4c556144a021`.

The reconciliation step failed while persisting the GitHub Actions run ID. PostgreSQL reported `integer out of range` for `workflow_dispatch_audit.workflow_run_id`, because that column used a 32-bit `INTEGER` but GitHub run IDs exceed that range. The API dispatch was accepted, but the audit update did not complete. The child's final conclusion and exact SHA have not yet been independently confirmed, so this attempt is not an accepted staging result.

The Node.js 20 deprecation warning for pinned actions and the `ubuntu-latest` migration notice were non-blocking notices, unrelated to the database failure.

### Remediation now present on the Phase IV branch

- `workflow_dispatch_audit.workflow_run_id` now uses SQLAlchemy `BigInteger`; an idempotent PostgreSQL startup migration widens an existing `INTEGER` column to `BIGINT`.
- `human_review_approvals.review_id` now also uses `BigInteger`, with its own PostgreSQL widening migration, because GitHub review IDs can exceed 32-bit range too.
- Regression coverage includes IDs above the 32-bit boundary and explicit assertions that both audit schemas use 64-bit types.
- The incident and remediation are recorded in [`log/current-status.md`](../log/current-status.md).

Do not use **Re-run jobs** on failed operator run #42365086398: rerunning that job would execute its dispatch step again and create another external workflow. First verify CI on the corrected exact head and inspect the existing child run by its correlation marker. Then start a fresh, explicitly authorized operator run only when ready for one additional staging dispatch.

**Operational acceptance remains open.** The staging dispatch/reconciliation has not yet completed successfully on the corrected schema; the Phase III deployed smoke test has not run against an installed GitHub App/webhook/worker/durable evidence database; human/faculty review and release acceptance remain outstanding. Keep PR #9 draft and production merge gating disabled.

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

