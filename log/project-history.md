# Project History — AI PR Verification Agent

**Retrospective date:** 2026-10-18  
**Main baseline before this log:** `1ff87390071491a9a08c9748aca2f36887ac5d77`

## 1. Purpose

The project is not a generic AI code reviewer that writes comments. Its job is to identify behavior at risk, define verification obligations, collect evidence produced by a trusted workflow for the exact commit, and report whether evidence is sufficient or whether risk remains unresolved.

The core contract is **“no evidence, no machine-verified pass.”** Models can propose risk hypotheses, but they cannot set test outcomes, mark obligations passed, or decide the final conclusion. Artifacts are data to validate, not authority.

## 2. Architecture / Phase 0 — trust model before integrations

The initial architecture separated five different properties:

| Property | Question | Required controls |
|---|---|---|
| Integrity | Were bytes malformed or changed? | Size limits, strict schemas, safe parsers, digest checks |
| Authenticity | Did evidence originate from the claimed platform run? | Authenticated GitHub Actions API metadata |
| Commit attribution | Does evidence apply to this exact change? | Repository/PR/base/head/policy identity and supersession checks |
| Actual execution | Did the reported test actually run? | Run/job/step metadata, JUnit node IDs and outcomes |
| Behavioral sufficiency | Did the test check the risky behavior? | Relevant line/branch targets and behavioral assertion/scenario evidence |

A hash can detect changes relative to a trusted expected digest, but does not prove who produced the data. Platform provenance can anchor the workflow and artifact, but it does not automatically prove the semantic quality of the test. Coverage is a useful negative filter, not proof that the required behavior is correct. Human approvals and policy waivers must remain auditable and distinct from machine proof.

The planned privilege progression is Phase I pure deterministic core; Phase II passive PR-context collection and Check Run publishing; Phase III read-only workflow/job/artifact ingestion; Phase IV explicitly opt-in workflow dispatch. This keeps external APIs and models from weakening the deterministic core.

## 3. Phase I — deterministic core and release hardening

Phase I delivered immutable domain records and explicit obligation states; guarded state transitions; deterministic conclusion mapping; a 5,000-example property-based false-green invariant; strict versioned YAML policy validation; verifier-owned runner profiles and safe selectors; bounded JUnit and per-test coverage parsing; evidence-sufficiency checks; secret scrubbing; a deterministic Markdown ledger; and an adversarial scenario where many unrelated passing tests cannot conceal missing critical webhook or cross-user authorization evidence.

Release-hardening also restored read-only CI permissions, disabled persisted checkout credentials, made formatting check-only, hardened the legacy extractor against conflicting overwrites, and constrained ZIP extraction names to prevent traversal.

PR [#1](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/1) was merged. Exact release-gate commit `5626ef5b5df58f288058977f73692947234abc1c` passed [CI #39036376525](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39036376525): formatting, Ruff, strict mypy, and tests passed; **167 tests passed with 97.30% overall coverage**, exceeding the 95% gate.

Key Phase I lesson: build the state model and adversarial invariants before integrations; do not let absence or malformed evidence collapse into success. See [Phase I build history](phase-1-build-history.md).

## 4. Phase II — bounded planning and GitHub service

Phase II added a planning/service layer while remaining planning-only: it does not execute PR code or ingest Actions artifacts.

- PR [#3](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/3): bounded diff analysis, explicit `COMPLETE`/`INCOMPLETE`/`TRUNCATED` states, deterministic risk-to-obligation rules, selector choices from a known inventory, and an optional provider-neutral model port whose output remains an untrusted hypothesis.
- PR [#4](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/4): raw-body HMAC validation, strict webhook event parsing, duplicate JSON-key rejection, and trusted exact-SHA PR context assembly.
- PR [#5](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/5): GitHub App JWT/install-token transport, bounded read-only REST client, SQLite delivery queue with idempotency/leases/retries, run/obligation ledger, worker orchestration, optional Gemini hypotheses, and deterministic Check Run create/update.

Permissions are limited to `contents:read`, `pull_requests:read`, and `checks:write`. There is no workflow dispatch, `actions:write`, `pull_requests:write`, or execution of untrusted PR code. Check Runs explicitly represent planning, not passed tests.

Main commit `1ff87390071491a9a08c9748aca2f36887ac5d77` passed [CI #39103979912](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39103979912): formatting, Ruff, strict mypy, tests, Phase I core and Phase II integration coverage gates all passed. Result: **353 tests passed, one warning, 92.66% overall coverage**; Phase I core coverage was about 96%, Phase II integration coverage about 86%.

Later reviews identified a deferred Phase II race to revisit: immediately before Check Run publication, the service must compare freshly fetched PR open/base/head state against the exact commit being evaluated. Fetching metadata without asserting those fields is insufficient. The user asked to postpone this while Phase III continues.

Documentation debt was also noticed: `docs/phase-2-planning.md` has an updated status and an older “Remaining Phase II work” list that conflicts with the subsequently merged implementation. Reconcile the stale checklist rather than relying on it as current status. The SQLite delivery queue remains single-host, and production operations still need observability, key rotation, retention/migrations, concurrency testing, and a secure TLS/reverse-proxy deployment plan. See [Phase II build history](phase-2-build-history.md).

## 5. Phase III — authenticated evidence ingestion (in progress)

Phase III is being developed on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6). The working tree contains initial versions of:
- `github_actions.py`: authenticated run/job/artifact metadata reads, pagination and guarded artifact downloads.
- `actions_evidence.py`: run/artifact identity validation, digest checking, bounded ZIP validation, JUnit and coverage-manifest consistency.
- `phase_three.py`: worker-facing ingestion orchestration, workflow-source retrieval at the exact base SHA, ambiguous-artifact rejection, PR freshness checks, and optional evidence-ledger persistence.
- `evidence_ledger.py`: SQLAlchemy evidence metadata persistence. New records start `INCONCLUSIVE`; ingestion itself never marks an obligation passed.
- Unit tests for malformed/stale evidence, redirect policy, ambiguous artifacts, PR head changes, idempotent persistence, conflicting replays, and terminal reconciliation behavior.

The pipeline is not yet complete. The evidence-to-obligation reconciliation path is not end-to-end; final Check Run publication based on reconciled evidence is not complete; reruns/shards/expired/missing/contradictory artifacts need stronger fail-closed rules; and the exact PR head has not passed full CI.

### A process-tracking problem discovered in the conversation

Several replies reported later Phase III commit SHAs as pushed. A fresh read of live GitHub refs and PR #6 shows the authoritative head as `19ebc5be866adfbe9f0993a3dd62a1f2db146cdf`, not several later SHAs mentioned in intermediate replies. A commit mentioned in chat must not be assumed delivered until the branch ref, PR head, tree, and workflow SHA agree.

Repeated manual changes to the same Ruff import block also failed to resolve Ruff `I001`. CI passed formatting but failed lint in `tests/unit/test_evidence_ledger.py`; mypy, tests, and coverage were skipped. The repeated false claims of a resolved lint issue are an important process failure, not a success to hide. See [Phase III investigation log](phase-3-investigation.md).

## 6. The progress percentages used in chat

The dialogue reported rough Phase III estimates of 45%, 50%, 55%, 58%, 60%, and 62% as partial slices were added. Those values were never measured against a weighted acceptance matrix, and some increases preceded CI verification. They are preserved as historical estimates—not test-pass percentages or release-readiness claims. This retrospective does not increase Phase III's percentage.

## 7. Next meaningful milestone

The next milestone is a **verified Phase III baseline**: resolve the Ruff failure at the actual branch head; pass strict mypy; run unit/property tests; pass overall and phase-specific coverage gates on the same SHA; then connect the persisted evidence to the Phase I state machine and test missing/stale/contradictory evidence against false-green outcomes. Keep PR #6 in draft until then.


## 8. Phase III artifact producer and 2026-10-23 audit

The Phase III branch reached a verified artifact-production milestone on SHA `e6b394ea9f598a7a12d4b98728eeb94d6f4cdc32`: [CI run #39817505536](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817505536) reports both jobs successful, artifact `verification-evidence` ID `12443191583` was uploaded, and an independent download check matched GitHub's advertised digest. JUnit and coverage-manifest inventories contained the same 463 unique node IDs. This moved the conversation's rough estimate from 75% to 80%.

The subsequent 85% estimate accompanied exact-head Actions run discovery and its defensive tests, but current CI is not green: [#39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124) ran 465 tests and failed the 90% total coverage gate at 89.32%; [#39907824858](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907824858) failed at Ruff formatting before downstream checks. The latest branch head at audit is `ce5f0c5b70112bc4885aaf5c4a2442637345deaa`.

The log audit also found that proposed Phase II worker/runtime wiring was discussed but not confirmed as landed. Phase III remains a draft PR. The `main` workflow still lacks the trusted producer required by the new validator. Progress percentages are therefore historical scope estimates, not verified completion measures; see [the detailed Phase III progress log](phase-3-progress.md) and [the investigation log](phase-3-investigation.md).
