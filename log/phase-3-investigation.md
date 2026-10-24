# Phase III Investigation Log — Evidence Ingestion

## Intended trust chain

`authenticated Actions API` → `workflow/job/step/artifact identity` → `bounded bytes and digest` →
`strict JUnit and coverage reports` → `commit-bound durable evidence` →
`deterministic obligation reconciliation` → `final PR freshness check` → `Check Run publication`.

Downloading `junit.xml` is only one link in that chain.

## Initial implementation in the PR working tree

- `src/verification_core/github_actions.py`: authenticated Actions workflow-run reads, paginated jobs/artifacts, guarded ZIP download, HTTPS host allowlist, and prevention of installation-token forwarding to signed storage hosts.
- `src/verification_core/actions_evidence.py`: repository/PR/base/head/run binding, workflow trust metadata, artifact ID/name/size/digest checks, bounded ZIP validation, exact JUnit/coverage member checks, node-ID inventory and outcome consistency.
- `src/verification_core/phase_three.py`: worker-facing orchestration; PR state/base/head checks before and after retrieval; workflow source loaded from the exact base SHA; missing/ambiguous artifacts rejected; optional persistence to the ledger.
- `src/verification_core/evidence_ledger.py`: SQLAlchemy persistence of evidence identity and summary metadata; new records begin `INCONCLUSIVE`; ingestion itself does not mark anything passed.
- Tests cover malformed/stale evidence, redirect hosts, artifact ambiguity, PR-head changes, idempotent persistence, conflicting replays, and terminal-decision immutability.

This is an initial slice on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), not a production-ready or merged feature.

## What CI actually says

Latest inspected PR run: [#39129484914](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39129484914).  
Tested SHA: `19ebc5be866adfbe9f0993a3dd62a1f2db146cdf`.

- Formatting: **passed**.
- Ruff: **failed** with `I001` import-block ordering in `tests/unit/test_evidence_ledger.py`.
- Strict mypy: **skipped**.
- Unit/property tests: **skipped**.
- Coverage and phase-specific coverage gates: **skipped**.

Therefore no test or coverage success may be inferred for this Phase III SHA.

## Repeated import-order failure: what went wrong

The conversation repeatedly attempted to fix Ruff `I001` by manually swapping imports in
`tests/unit/test_evidence_ledger.py`. Several replies declared the fix done, but fresh CI logs kept
showing the same failure on that path. The correct loop should be:

1. Reproduce the exact configured Ruff version and command.
2. Capture the complete `ruff check --fix tests/unit/test_evidence_ledger.py` diff.
3. Inspect the actual post-fix file rather than trusting the planned replacement.
4. Commit that exact result.
5. Verify the live branch ref, PR head, file content in the commit tree, and workflow SHA all agree.
6. Read the new run before touching later code or reporting success.

Manually alternating line order without verifying the exact output was an inefficient and unreliable
debugging approach.

## Branch and commit consistency

Several intermediate chat replies reported later commit SHAs. A retrospective read of live GitHub refs
and PR #6 resolved the current branch/PR head to `19ebc5be866adfbe9f0993a3dd62a1f2db146cdf`. The
branch ref and PR head outrank any claim in an assistant message. Future changes must confirm that
the commit SHA reported by the write API is the branch ref, that the PR points to that same SHA, that
the changed files are in that SHA's tree, and that CI runs against that SHA. If they disagree, stop and
reconcile the refs before claiming a change is delivered.

## Conversation progress estimates (historical)

| Reported estimate | Implementation slice associated in the chat | Important caveat |
|---:|---|---|
| 45% | Initial Actions API client and artifact parser | Initial code; not fully CI-verified |
| 50% | Worker-facing orchestration and PR freshness checks | Initial tests; full CI still red |
| 55% | Initial SQLAlchemy evidence ledger and persistence tests | Not yet connected to final reconciliation |
| 58% | Policy-aware identity, timestamp checks, conditional reconciliation updates | Full CI not green |
| 60% | Ingestion-to-ledger wiring and ledger key returned from service | Full CI not green |
| 62% | Reported persistence/integrity hardening | Still not a release-readiness measure; full CI red |

These percentages were rough conversational estimates, not an audited weighted-completion measure, a
test-pass ratio, or a coverage metric. This log preserves them historically; this documentation commit
does not increase the Phase III estimate.

## Why reconciliation is still pending

A report field such as `behavioral_assertion_verified: true` is a self-assertion. A matching archive
digest establishes consistency with the expected digest; it does not prove the claim's meaning.
Platform provenance is necessary, but not by itself sufficient evidence that the risky behavior was
properly tested.

The next code milestone must derive expected target lines/branches from trusted diff/policy data, match
exact JUnit node IDs to per-test coverage, fail closed on missing/skipped/stale/partial/contradictory
evidence, call the existing Phase I deterministic evidence/state machine, then recheck current PR base
and head immediately before publication.

## Acceptance checklist

- [ ] Resolve Ruff `I001` on the actual current PR head.
- [ ] Pass strict mypy on the same SHA.
- [ ] Pass the complete unit/property test suite on that SHA.
- [ ] Pass overall and Phase I/Phase II coverage gates.
- [ ] Confirm ingestion-to-ledger integration tests execute and pass in CI.
- [ ] Implement/test deterministic obligation reconciliation.
- [ ] Resolve reruns, artifacts expiry, duplicate artifacts, shards, partial reports, and contradictions.
- [ ] Protect final Check Run publication with immediate PR freshness revalidation.
- [ ] Align PR description and Phase III status docs with actual code.
- [ ] Record a green merge-candidate SHA and CI URL before removing draft status.


---

# Phase III engineering retrospective — 2026-10-23

This addendum reconciles the progress estimates reported in chat with repository refs and CI evidence. It intentionally preserves failed attempts: the repeated red runs explain the eventual design and are not to be erased.

## The 75% → 80% milestone: evidence finally became a real artifact

### What was built

The exporter `verification_core.manifest_export` connects pytest-cov per-test contexts to the JUnit inventory and emits `coverage-manifest.json` bound to the exact PR head. A separate CI job checks out that exact PR head with a pinned checkout action, runs pytest with `--cov-context=test` and `--junitxml=junit.xml`, exports the manifest, and uploads exactly `junit.xml` plus `coverage-manifest.json` with a pinned upload action and `if-no-files-found: error`.

The evidence consumer verifies the authenticated Actions run/job/artifact metadata, artifact digest, archive size and member constraints, exact JUnit/manifest inventory and outcome consistency, and the manifest's head SHA. It keeps the uploaded archive inert and does not execute or extract untrusted files.

### Failures that shaped the exporter

1. **Formatting failures blocked downstream gates.** Several early runs stopped at `ruff format --check` due to quote style, line wrapping, or blank-line differences. In those runs Ruff lint, strict typing, tests, coverage, and artifact production were skipped—not passed. Fixes were applied from the exact formatter output rather than weakening checks.
2. **A 256 KiB YAML test input leaked into a JUnit testcase name.** Pytest serializes parameter representations in testcase IDs by default. The test itself was valid; the XML identifier was not usefully bounded. Explicit short stable IDs were added to the large-parameter workflow/policy tests. The parser's 10,000-character safety bound was deliberately retained.
3. **The exporter initially mapped pytest context paths incorrectly.** A context such as `tests/unit/test_evidence_ledger.py::...` was mapped to `test_evidence_ledger::...`, while JUnit used `tests.unit.test_evidence_ledger::...`. The fix preserves the repository-relative dotted module name.
4. **Parameter values can contain `::` and arbitrary brackets.** A plain split on `::` incorrectly split selectors containing paths/test IDs; enforcing balanced brackets was also incorrect because pytest parameter suffixes are opaque representations. The safer rule recognizes the source `.py::` boundary, parses scope separators before the parameter suffix, and preserves the suffix verbatim. Exact JUnit inventory matching remains required.
5. **Some tests do not execute tracked production-source lines.** Requiring every non-skipped JUnit test to have measured source-line context rejected valid tests. The exporter now preserves the full JUnit inventory and can represent a test with empty measured line/branch maps. It still rejects a context that cannot match JUnit, and rejects a run when no run-phase contexts match any JUnit test.
6. **Artifact production did not mean every later change was verified.** Green runs belonged to exact SHAs. A later validator or run-discovery commit could fail formatting, lint, typing or coverage even if an older SHA produced a valid artifact.

### Exact verified producer runs

- [Run #39814823241](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39814823241), SHA `f721d73dea35a04889878b776b7e87f61ae0206c`: reported successful artifact production; 460 JUnit test IDs and 460 manifest IDs matched.
- [Run #39817505536](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817505536), SHA `e6b394ea9f598a7a12d4b98728eeb94d6f4cdc32`: both the quality job and evidence producer job succeeded. Artifact ID `12443191583`, 39,797 bytes, GitHub digest `sha256:c9ceded9a4d92f3cf713fdcbcff7fb190b68e8bfdc5faa6ddf2db574784f0a67`. Independently downloaded artifact matched the API digest; JUnit and manifest had 463 distinct IDs each and identical ID sets. The entries did not assert behavioral-assertion verification.

These runs support moving the rough estimate from 75% to 80%: the evidence-production pipeline works on those exact commit snapshots. They do not establish live production ingestion.

## The 80% → 85% step: what actually progressed, and what did not

The branch later added a bounded `list_pull_request_workflow_runs` method that queries by exact head SHA and pull-request event. It validates the supplied SHA, requires stable `total_count` across pages, rejects malformed collections, wrong-head records, invalid/duplicate IDs, empty incomplete pages, excess items, and a pagination limit reached before all results are collected. Parameterized tests were added for these fail-closed cases.

However, the implementation has not yet earned its next green milestone:

- [Run #39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124), SHA `0a4e8ee419859d79367a5100ab31b1bfbc66337b`: formatting, Ruff, and strict mypy passed; 465 tests ran, but total coverage was 89.32%, below the configured 90% gate. The evidence job and downstream gates were skipped.
- [Run #39907824858](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907824858), SHA `ce5f0c5b70112bc4885aaf5c4a2442637345deaa`: stopped at formatting because an extra blank line preceded a parameterized test in `tests/unit/test_github_actions.py:94`; all downstream checks were skipped.

The 85% value was a rough conversational estimate after the run-discovery changes, not a passed acceptance milestone. The current candidate must be corrected, all gates rerun, and its artifact produced before this can be elevated to verified progress.

## Critical worker-integration correction

The conversation explored wiring Phase III into `PhaseTwoProcessor` and `runtime.py` behind `VERIFICATION_EVIDENCE_DATABASE_URL`, including exact-head run selection and a forced incomplete/non-passing conclusion until obligation reconciliation is available. Those changes were not confirmed as committed to the current branch. The current source still needs a verified runtime integration, and the evidence ingestion helper must not be described as automatically active in the worker merely because the helper itself exists.

A complete runtime change needs:
- explicit opt-in configuration and durable ledger lifecycle;
- exact PR number/base/head/workflow-path binding, not just a webhook's claims;
- zero or multiple trusted candidates treated as inconclusive;
- authenticated artifact ingest and persisted provenance;
- deterministic mapping from trusted changed-line/branch targets and independently bound assertions to exact test IDs and coverage records;
- state-machine evaluation that cannot allow missing/partial/skipped/stale/contradictory data to produce success;
- live PR open/base/head freshness verification immediately before the Check Run write;
- tests for happy path, ambiguous runs, no runs, API failure, ledger failure, stale PR, and non-passing outcome on incomplete reconciliation.

## Lessons recorded from this slice

- Keep input size limits. Make test IDs explicit instead of expanding XML identifiers with huge arbitrary parameter reprs.
- Treat pytest parameter suffixes as opaque; normalize only the source path and test-scope portion.
- Use JUnit as the complete testcase inventory; coverage is per-case measured evidence, not a substitute inventory.
- Test pagination's error paths because exact-head selection is security-sensitive.
- Never count a CI stage that was skipped as passed.
- Do not merge a trusted workflow to `main` just to satisfy tests; require a green candidate first and a controlled follow-up integration check.
