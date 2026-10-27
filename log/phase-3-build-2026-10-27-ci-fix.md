# Phase III build log — CI failure fixes and exact-head artifact verification — 2026-10-27

## Starting state

- Branch: `phase-3-evidence-ingestion`
- PR: [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), left open and draft.
- Starting head: `42d4682ddb37000705064ec304575f4879f6ef04`.
- Latest CI was failing; no artifact existed for that head.

## Iteration 1 — formatting failure

Run [#40302458004](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40302458004) failed at `ruff format --check src tests scripts`. Ruff identified two long assertions in `tests/unit/test_phase3_smoke.py` that needed multiline formatting.

### Fix

Commit `39d0375c2d160b3d69df41533177d97d9a20fb17` reformatted those assertions only. It did not lower any lint/type/coverage thresholds.

### Result

The next run's formatting, Ruff, and strict mypy all passed. The test suite exposed a genuine failure in the evidence-record key parser test.

## Iteration 2 — evidence-record summary casing

Run [#40464507140](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40464507140) passed formatting, Ruff, and strict mypy, but failed `test_check_summary_must_bind_to_a_persisted_record_key`. The smoke-test parser used a case-sensitive regular expression for `evidence record`, while the test exercised the natural summary prefix `Evidence record`. Result: 1 failed, 546 passed; the evidence producer was skipped because the quality job failed.

### Root cause and fix

This was a real parser/test contract mismatch, not flaky CI and not a reason to weaken the assertion. Commit `64700d7ed575296e6874a185938ef585e0f7c5de` made the record-key pattern explicitly case-insensitive while retaining the required 64-character lowercase hexadecimal key and terminating period.

## Final verification — exact same SHA

Run [#40464702014](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40464702014) completed with conclusion **success** on `64700d7ed575296e6874a185938ef585e0f7c5de`. Both jobs passed:

- Quality job: formatter, Ruff, strict mypy passed; **547 tests passed**, one non-blocking Starlette/httpx deprecation warning; overall coverage **90.49%**, Phase I core **96%**, Phase II integration **86%**. All gates passed.
- Evidence producer: exact PR head checked out; per-test coverage/JUnit generated; manifest export passed; artifact upload passed.
- Artifact: `verification-evidence`, ID `12716496067`, size 43,149 bytes, GitHub digest `sha256:b71ff7c4f65a3c4b2e248a293d7ac5aa9c1872104e080ef3b767e7df033c299b`.
- Independently downloaded ZIP SHA-256: `b71ff7c4f65a3c4b2e248a293d7ac5aa9c1872104e080ef3b767e7df033c299b` — exact match.
- ZIP members: exactly `junit.xml`, `coverage-manifest.json`; JUnit: 547 test cases, zero failures/errors/skips; manifest: 547 unique node IDs, all outcomes `passed`; JUnit and manifest IDs match exactly; manifest head SHA equals the tested commit; every `behavioral_assertion_verified` flag is `false`.

## What was learned

1. Do not declare a CI fix from an intended patch: inspect the next run's exact failing step and test.
2. Strict CI exposed both formatting drift and a case-sensitive parser mismatch; fixing the actual root cause preserved all gates.
3. Green CI plus an independently digest-verified artifact proves repository CI/evidence production on this SHA, not the live App/webhook/database deployment.
4. The deployment smoke test needs a real service URL, installed GitHub App credentials, the exact configured webhook secret, and the same evidence database as the worker. Those values are not available through the connected repository integration. Do not invent them or ask the user to paste secrets into chat.
5. Keep PR #6 draft and production merge gating disabled. Human review is deferred to Phase IV; the remaining Phase III operational acceptance is the real target/staging smoke test.

## Phase III tracker after this run

- [x] Code + smoke-test regression fix committed
- [x] Formatting, Ruff, strict mypy, tests, and all coverage gates green on exact head
- [x] Exact-head evidence artifact produced and independently digest-verified
- [ ] Live target/staging deployment smoke test with the installed App, webhook/worker, and same evidence DB
- [ ] Phase IV human review (intentionally deferred)
