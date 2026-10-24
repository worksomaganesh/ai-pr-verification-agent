# Phase III Progress and Evidence Log

This file tracks the recent 75% → 80% → 85% estimates as a historical engineering narrative. Percentages are rough scope estimates and not code coverage, test-pass ratios, or release-readiness scores. Exact SHAs and CI results control what is considered verified.

## Snapshot — 2026-10-23

- Main before this documentation-only update: `4362899a74eafc5e31a8f244de439b9dcd2132fd`.
- Phase III branch: `phase-3-evidence-ingestion`.
- Current branch head: `ce5f0c5b70112bc4885aaf5c4a2442637345deaa`.
- Draft PR: [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6).
- Current CI run: [#39907824858](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907824858), failed at Ruff formatting in `tests/unit/test_github_actions.py:94`. Later stages were skipped.
- Previous candidate [#39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124) passed formatting, Ruff and strict mypy, but failed overall coverage at 89.32% versus a 90% requirement after 465 tests ran. Phase coverage gates and evidence job were skipped.

## Milestone A — 75%: bounded evidence creation and ingestion (work then in progress)

### Work completed in this slice

- Added authenticated GitHub Actions API retrieval for workflow runs, jobs, and artifacts, with bounded pagination.
- Added controlled artifact downloads with strict HTTPS host handling and without forwarding the installation token to the signed storage URL host.
- Added archive constraints for size, member count/size, path safety, regular files only, duplicate names, directory/symlink rejection and compression-ratio checks.
- Added strict JUnit and coverage-manifest parsing with exact testcase inventory/outcome correlation and exact head-SHA binding.
- Added a durable evidence ledger that records normalized provenance and digests, keeps raw archives and signed URLs out of storage, starts new records as inconclusive, and prevents conflicting or terminal-state rewrites.
- Added workflow-contract validation using the workflow source from the base commit.

### What failed and what we learned

- Format-only CI failures were common. When format/lint failed, typing/tests/coverage/evidence steps were skipped. The fix was to apply exact Ruff output, not to relax Ruff.
- Earlier CI also exposed a strict-mypy failure in a test helper return type and a total-coverage shortfall. A green older run never substitutes for a new head.

## Milestone B — 75% → 80%: real artifact upload, independently checked

### Exporter and workflow

A dedicated job now checks out the exact PR-head repository/SHA with a pinned checkout action and credentials disabled; runs pytest with per-test coverage contexts and JUnit XML; builds `coverage-manifest.json`; and uploads exactly those two files using a pinned upload action and `if-no-files-found: error`.

The exporter maps pytest-cov `<node-id>|run` contexts to JUnit classname/name identifiers and emits measured line/branch evidence. It never uses a manifest flag to assert that behavior was semantically verified.

### Debugging record

1. A 256 KiB workflow/policy fixture made generated JUnit testcase names too large because pytest included the parameter's textual representation. Tests got short explicit IDs; parser size bounds remained.
2. Contexts from `tests/unit/test_*.py` must map to JUnit's dotted classname (for example, `tests.unit.test_example::test_case`), not just the filename stem.
3. Test parameter values can include `::`, and their textual reprs can have arbitrary bracket shapes. Splitting all `::` markers or demanding balanced brackets corrupts valid node IDs. The parameter suffix needs to be opaque.
4. Passed JUnit tests may execute no tracked production-source line. These remain part of the inventory with empty measured line/branch maps; unmatched actual contexts still fail closed.
5. Exact artifact integrity and inventory checks are distinct from semantic assertion trust.

### Proof

- [#39814823241](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39814823241), SHA `f721d73dea35a04889878b776b7e87f61ae0206c`: producer succeeded and exact inventory matched 460 ↔ 460 tests.
- [#39817505536](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817505536), SHA `e6b394ea9f598a7a12d4b98728eeb94d6f4cdc32`: quality and producer jobs succeeded. Artifact `verification-evidence`, ID `12443191583`, 39,797 bytes, digest `sha256:c9ceded9a4d92f3cf713fdcbcff7fb190b68e8bfdc5faa6ddf2db574784f0a67`. Downloaded ZIP digest matched metadata and the two reports had 463 unique IDs each with exact equality. Behavioral assertion flags remained false.
- This evidence justified a move to roughly 80% for artifact creation/production. It did not complete runtime integration.

## Milestone C — 80% → 85% conversational estimate: safer workflow-run selection; new gates exposed

### Code and tests

A new `list_pull_request_workflow_runs(repository, head_sha)` function filters by exact `head_sha` and `event=pull_request`, checks the returned SHA on every item, bounds pages and item count, requires stable `total_count`, and rejects malformed or incomplete result sets. Tests cover wrong head and bad SHA, multi-page success, malformed counts/collections, invalid or duplicate IDs, changing counts, and missing page items.

### What CI revealed

- [#39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124), SHA `0a4e8ee419859d79367a5100ab31b1bfbc66337b`: 465 tests passed, but the suite/coverage command failed because overall coverage was 89.32% (required 90%). Phase-specific coverage gates and artifact producer were skipped.
- [#39907824858](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907824858), SHA `ce5f0c5b70112bc4885aaf5c4a2442637345deaa`: Ruff format failed before lint/type/test. One extra blank line before a parameterized test at line 94 was reported.

The latest 85% estimate should be treated as **unverified** until the newest changes pass the full gates.

## Worker integration and live deployment — open

The planned Phase II worker/runtime integration behind `VERIFICATION_EVIDENCE_DATABASE_URL` was discussed but is not verified as committed to the current head. The actual `phase_two.py` and `runtime.py` still need to invoke Phase III authenticated ingestion, persist the record, preserve fail-closed behavior, and prove freshness before Check Run publication.

Additionally, the current `main` workflow does not satisfy the trusted evidence producer contract. Do not enable ingestion until a trusted producer is deployed to main and a subsequent PR validates it.

## Current acceptance checklist

- [ ] Fix Ruff formatting on `ce5f0c5b...`.
- [ ] Get formatting, Ruff, strict mypy, unit/property tests, 90% overall coverage, and Phase I/II gates green on one SHA.
- [ ] Get the evidence producer green on that same SHA, and inspect its artifact digest and inventories.
- [ ] Wire the Phase II worker/runtime to the Phase III service with durable ledger configuration and explicit failure handling.
- [ ] Call the deterministic Phase I reconciliation/state-machine path with independently supplied trusted target lines/branches and assertion bindings.
- [ ] Test missing, duplicate, expired, stale, skipped, partial, contradictory and API-error paths; no inconclusive data can publish success.
- [ ] Deploy the trust-compliant producer to main and verify live ingestion on a new PR.
- [ ] Update PR description; keep PR draft until one complete candidate is green.
