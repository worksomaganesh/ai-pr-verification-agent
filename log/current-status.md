# Current Verified Status

**Snapshot date:** 2026-10-23  
**Main snapshot before this log update:** `4362899a74eafc5e31a8f244de439b9dcd2132fd`  
**Phase III branch:** `phase-3-evidence-ingestion`  
**Current Phase III PR:** [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), open and draft  
**Current Phase III branch head at snapshot:** `ce5f0c5b70112bc4885aaf5c4a2442637345deaa`

## Verified on main

### Phase I

- Exact CI run: [#39036376525](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39036376525)
- Tested SHA: `5626ef5b5df58f288058977f73692947234abc1c`.
- Formatting, Ruff, strict mypy, and tests passed.
- Result: 167 passed; 97.30% overall coverage against the 95% gate.

### Phase II

- Exact CI run: [#39103979912](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39103979912)
- Tested SHA: `1ff87390071491a9a08c9748aca2f36887ac5d77`.
- Formatting, Ruff, strict mypy, tests, Phase I core coverage, and Phase II integration coverage passed.
- Result: 353 passed, one warning, 92.66% overall; core coverage about 96%, integration coverage about 86%.

## Phase III: latest verified position

Phase III has a verified evidence-producer milestone, but it is **not release-complete**.

### Evidence producer milestone — verified on an older SHA

- CI run: [#39817505536](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817505536).
- Exact tested SHA: `e6b394ea9f598a7a12d4b98728eeb94d6f4cdc32`.
- Quality/coverage job and the separate exact-PR-head evidence job were both reported successful by GitHub Actions.
- Uploaded artifact: `verification-evidence`, ID `12443191583`, 39,797 bytes, digest `sha256:c9ceded9a4d92f3cf713fdcbcff7fb190b68e8bfdc5faa6ddf2db574784f0a67`.
- The downloaded ZIP was independently hashed and the hash matched GitHub's artifact metadata. It contained the expected `junit.xml` and `coverage-manifest.json`; the manifest was bound to the tested head SHA. JUnit and manifest contained 463 unique test IDs each, with exactly matching inventories. The exporter left `behavioral_assertion_verified` false for all entries.
- This proves that the evidence exporter and upload path worked for SHA `e6b394ea...`. It does **not** verify later commits.

### Newer run-discovery changes — not yet green

- Latest branch head at this snapshot: `ce5f0c5b70112bc4885aaf5c4a2442637345deaa`.
- Latest CI: [#39907824858](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907824858).
- Formatting failed at `tests/unit/test_github_actions.py:94` because an extra blank line preceded the parameterized malformed-response cases.
- Ruff, strict mypy, unit/property tests, coverage gates, and evidence production were skipped on that exact SHA.
- Preceding run [#39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124) passed formatting, Ruff, and strict mypy, but the test command finished with 465 passed and total coverage of 89.32%, below the required 90%. The test/coverage step failed; subsequent coverage gates and the evidence producer were skipped.
- The next candidate must first fix the formatting issue and then pass **all** checks on one SHA.

### What is and is not wired

- Present in the PR branch: authenticated Actions API methods (including bounded exact-head run listing), pinned workflow/artifact checks, bounded ZIP and JUnit/coverage validation, evidence ledger, per-test coverage exporter, artifact workflow, and Phase III orchestration/reconciliation primitives.
- Not yet established as a verified live service: the Phase II worker/runtime does not yet automatically run the new Phase III ingestion-to-ledger-to-reconciliation path under a proven production configuration. The proposed worker integration was explored in conversation but the intended end-to-end code change was not confirmed on the current branch head. Do not describe the worker as fully wired until its implementation is found in the branch and its tests pass.
- `main` remains at `4362899a74eafc5e31a8f244de439b9dcd2132fd` before this log-only commit, and its existing `.github/workflows/ci.yml` does not satisfy the new trusted evidence producer contract. Phase III ingestion is intentionally fail-closed until the trusted producer workflow is deployed and verified on `main` and a subsequent PR proves live ingestion.
- PR #6 remains draft; it has not been merged.

## Percentage history — estimates, not measurements

The conversation reported a progression of 75% → 80% → 85%. These are **rough scope estimates**, not a test ratio, code coverage, or release-readiness score.

- **75%:** the ingestion/parser/orchestration primitives were in place, but the evidence producer kept failing on real fixture and identifier mismatches.
- **80%:** the exact-PR-head producer successfully emitted and uploaded an artifact; the downloaded archive digest matched GitHub's metadata, and the JUnit and manifest inventories matched exactly on the tested SHA.
- **85%:** later run-discovery and defensive-validation code was added. However, a strict audit shows the most recent branch head still fails before tests at formatting, and the attempted Phase II worker wiring is not verified as present. Treat 85% as the latest conversation estimate only, not as evidence that the remaining service integration is complete.

Do not increase the percentage for documentation-only commits, formatting fixes, or code that has not passed the relevant gates.

## Remaining release gates

1. Fix the current Ruff-format failure on `ce5f0c5b...`.
2. Pass formatting, Ruff, strict mypy, unit/property tests, overall coverage, and Phase I/II gates on one exact candidate SHA.
3. Resolve the 90% coverage shortfall seen on `0a4e8ee4...` with meaningful tests, without weakening coverage thresholds.
4. Verify evidence artifact production on the same SHA as the green quality job.
5. Finish and test the Phase II worker/runtime path: exact PR-head run discovery, authenticated ingestion, durable ledger write, deterministic evidence/obligation reconciliation, and safe Check Run publication.
6. Test missing, ambiguous, expired, stale, skipped, partial, malformed, and contradictory evidence; ensure none can produce a false success.
7. Deploy a trusted producer workflow on `main`, then verify live ingestion in a subsequent PR.
8. Refresh the draft PR body and create a single green merge-candidate SHA before considering removal of draft status.
