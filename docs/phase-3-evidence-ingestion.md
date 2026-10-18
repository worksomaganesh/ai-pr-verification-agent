# Phase III — Authenticated evidence ingestion

## Status

Phase III has begun with a first implementation slice for authenticated GitHub Actions metadata and bounded artifact ingestion. It is not a release-complete evidence reconciliation service yet. Do not enable merge gating based on these primitives until the CI suite passes on the exact commit and the remaining items below are implemented.

## Trust model

1. Obtain workflow-run, job, and artifact metadata directly from the authenticated GitHub Actions REST API using an installation token. Webhook fields and artifact contents are not authoritative.
2. Bind the run to the expected repository, pull request number, base SHA, and head SHA. Only completed successful `pull_request` runs are eligible.
3. Require the workflow path to match the trusted workflow list loaded from the base-commit policy. Reject a PR that changes a harness-sensitive path.
4. Require a completed successful job step named `Upload verification evidence`. This is an initial contract; the caller must source the step definition from a workflow that the base policy trusts.
5. Bind artifact metadata to the exact workflow-run ID and repository identity. Require a GitHub-provided SHA-256 digest and compare it to the downloaded bytes before parsing.
6. Enforce archive size, member count, member size, expansion ratio, regular-file-only entries, exact member names, and safe paths. The accepted archive contains exactly `junit.xml` and `coverage-manifest.json`.
7. Parse reports with the Phase I bounded parsers and require identical exact test-node inventories, matching outcomes, and the coverage manifest's head SHA to equal the expected head SHA.

## Current modules

- `verification_core.github_actions.GitHubActionsClient`: bounded API reads for workflow runs, fully paginated jobs and artifacts, and controlled artifact ZIP download. Signed redirects are allowed only to a narrow HTTPS storage-host allowlist; installation credentials are not forwarded to that host.
- `verification_core.actions_evidence.ingest_authenticated_artifact`: validates API metadata, workflow trust, artifact digest, ZIP members, JUnit and coverage consistency, and exact commit binding.
- `verification_core.evidence` and `verification_core.coverage`: deterministic parsers and per-test evidence sufficiency rules from Phase I.

## Critical limitation

A JSON field such as `behavioral_assertion_verified: true` is still a claim inside an artifact. Artifact digest and trusted workflow provenance establish which workflow-produced bytes were retrieved, not that the claim is semantically correct. The current ingestion function preserves this field only as an input to the existing deterministic coverage logic; it does **not** establish a passing obligation by itself. Before a production success can be published, the next slice must derive target lines/branches from the analyzed diff and trusted source metadata, reconcile each obligation against exact JUnit node IDs and coverage records, validate the test harness/workflow definition against the base commit, and call the Phase I state machine.

## Remaining Phase III release gates

- [x] Wire the Actions API client into worker-facing evidence ingestion and persist authenticated metadata in the durable evidence ledger (initial slice; requires full CI verification).
- [x] Revalidate current PR base/head immediately before publishing a Phase III Check Run; stale runs are rejected before any Check Run API call (covered by regression test).
- [ ] Bind each workflow ID/path and evidence-upload step to the exact trusted workflow file from the base SHA, not just a string in a run response.
- [ ] Resolve workflow reruns, multiple artifacts, shard aggregation, missing artifacts, and contradictory outcomes with fail-closed rules.
- [ ] Validate GitHub artifact digest semantics against live API responses and supported artifact service versions.
- [x] Add an initial deterministic obligation-to-evidence reconciliation bridge using exact test IDs, trusted target locations, an independent trusted assertion binding, and the Phase I state machine. End-to-end trusted target/assertion derivation still belongs to the caller.
- [ ] Add adversarial tests for pagination races, truncated results, artifact redirect hosts, oversized/changing streams, duplicate ZIP entries, compression bombs, symlinks, stale PR heads, forged digest, and partial shard evidence.
- [ ] Add deployment configuration, retention and redaction rules for evidence records.
- [ ] Run format, lint, strict typing, complete tests, and coverage gates on the exact merge candidate.

## Security note

The current API client uses an explicit timeout, bounded JSON bodies, and no automatic redirects. Artifact signed URLs are bearer capabilities: never log them, persist them, or forward the GitHub installation token to the storage host. Keep artifact contents inert; never extract them to the filesystem or execute code from them.


## Durable evidence ledger (initial implementation)

`verification_core.evidence_ledger.SQLAlchemyEvidenceLedger` stores authenticated evidence metadata
and test-inventory digests in SQLite or PostgreSQL. It intentionally does not store artifact ZIPs,
JUnit bodies, signed download URLs, or secrets. A record is keyed by repository, PR, exact base/head,
policy digest, workflow run/attempt, and artifact ID. Replays of the same identity are idempotent;
conflicting content for that identity is rejected.

Every newly ingested record starts with reconciliation status `INCONCLUSIVE`. A separate
`record_reconciliation` call is required to persist a terminal decision and its digest, and terminal
decisions are immutable. This is persistence infrastructure only: the caller must still run the
deterministic obligation reconciliation and state machine before recording a result. The ledger
does not independently prove behavioral assertions.


### Worker and ledger integration

`ingest_pull_request_run` accepts an optional `EvidenceLedgerPort`. It performs the final freshness
check before recording metadata and returns the ledger record key. The ledger stores only normalized
metadata and digests, starts records as `INCONCLUSIVE`, and treats repeated identical ingestion as
idempotent. A stale PR discovered during collection is rejected before persistence. These changes
do not publish a Check Run or substitute for the pending obligation reconciliation stage.


## Deterministic obligation reconciliation (initial integration)

`verification_core.phase_three.reconcile_authenticated_obligation` now connects the authenticated
artifact to the Phase I coverage evaluator and obligation state machine. It requires the exact
candidate test node ID, commit-bound workflow provenance, target line/branch sets from trusted
analysis, and a separate `trusted_assertion_bindings` mapping. The artifact's own
`behavioral_assertion_verified` field is never treated as authority to pass an obligation.

A missing trusted assertion binding or missing target coverage results in an inconclusive obligation;
contradictory outcomes fail closed through the existing state machine. The caller remains responsible
for deriving target locations and assertion bindings from trusted base-policy/deterministic analysis.
This helper is not yet connected to Check Run publication, and the ledger decision write remains a
separate explicit step.


## Deterministic publication bridge

`publish_reconciled_verification` evaluates the supplied reconciled obligations using the Phase I
state machine and publishes its conclusion only after a final live PR open/base/head comparison. A
stale PR is rejected before the Check Run API call. The summary is generated from the deterministic
evaluation and obligation states; no model or artifact conclusion is accepted.

If a durable evidence record key is supplied, successful Check Run publication is followed by a
separate ledger terminal-decision write. Only deterministic `success`, `failure`, and `cancelled`
conclusions map to `PASSED`, `FAILED`, and `STALE` evidence reconciliation statuses. An
`action_required` or `neutral` conclusion leaves the evidence record `INCONCLUSIVE`. If the
post-publication ledger write fails, the result explicitly reports `ledger_persisted=False` so the
decision can be retried idempotently; the code does not claim durable completion.
