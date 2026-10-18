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

- [ ] Wire Actions API client into a worker-facing evidence ingestion service and durable evidence ledger.
- [ ] Revalidate current PR base/head immediately before publishing any Check Run; stale runs must not publish a success.
- [ ] Bind each workflow ID/path and evidence-upload step to the exact trusted workflow file from the base SHA, not just a string in a run response.
- [ ] Resolve workflow reruns, multiple artifacts, shard aggregation, missing artifacts, and contradictory outcomes with fail-closed rules.
- [ ] Validate GitHub artifact digest semantics against live API responses and supported artifact service versions.
- [ ] Reconcile changed-line and branch targets with coverage data and the existing obligation state machine.
- [ ] Add adversarial tests for pagination races, truncated results, artifact redirect hosts, oversized/changing streams, duplicate ZIP entries, compression bombs, symlinks, stale PR heads, forged digest, and partial shard evidence.
- [ ] Add deployment configuration, retention and redaction rules for evidence records.
- [ ] Run format, lint, strict typing, complete tests, and coverage gates on the exact merge candidate.

## Security note

The current API client uses an explicit timeout, bounded JSON bodies, and no automatic redirects. Artifact signed URLs are bearer capabilities: never log them, persist them, or forward the GitHub installation token to the storage host. Keep artifact contents inert; never extract them to the filesystem or execute code from them.
