# Phase IV — Opt-in Dispatch and Human Governance

## Status

The integrated Phase IV feature branch is at exact head `0c9ef6056123ad3b5b9103e85d31b0a9648b8068`. The latest full CI run [#41850967572](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850967572) and focused governance run [#41850967471](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41850967471) both completed successfully on that exact SHA.

The full workflow passed:
- **687 tests passed**, one non-blocking Starlette/httpx deprecation warning.
- Overall coverage **90.23%** (90.00% gate).
- Phase I core coverage **96.39%** (95.00% gate).
- Phase II integration coverage **85.99%** (80.00% gate).
- Ruff formatting, Ruff lint, strict mypy, all configured coverage gates, and the exact-head evidence producer passed.

The exact-head producer uploaded artifact `verification-evidence`, ID `13335151007`, size 49,841 bytes, GitHub SHA-256 `30d2efc2f3b0b5abfd9b3882c78c6a902781f21c4f7aa247b7370738529f1bc8`. The run log confirms upload and GitHub metadata confirms the exact head association. The archive has not been independently downloaded and parsed as part of this checkpoint. The preceding source-bearing head `3046eeb2681e0102f4ca9b978802e008a6baa13a` produced artifact `13334261929`, which was independently downloaded and checked; its JUnit and coverage-manifest inventories each contained 687 unique matching passing tests and all behavioral assertion flags were false.

Phase III implementation is **already integrated into this Phase IV branch**. GitHub commit comparison confirms Phase III PR #6 head `9611cbc6504f3844770540c9d45f87864bdfae08` is an ancestor of Phase IV head `0c9ef6056123ad3b5b9103e85d31b0a9648b8068` (72 commits ahead, 0 behind); the explicit integration commit is `8a17bd22abcfdea02111f7fa7768c5ba9b4c29a1`. Therefore, remaining Phase III work is operational smoke acceptance, not source integration.

Human-governance code includes exact-head GitHub review verification, reviewer allowlisting, latest-review supersession, rationale validation, fail-closed API handling, append-only review audit, and an adapter into the existing obligation state machine. Dispatch governance includes explicit operator authorization, write-ahead audit, duplicate protection, a one-shot coordinator, and workflow-run exact-SHA reconciliation.

**Repository implementation and CI are verified; operational acceptance is not complete.** Tests use mocked GitHub APIs. No real staging workflow dispatch has been performed, no authenticated staging-only operator entry point has been exercised, no target deployment smoke test has passed, and no human release approval has been recorded. PR #9 remains open and draft. Keep production merge gating disabled.

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

