# Phase IV CI fix and evidence log — 2026-10-27

## Exact-head result

- Branch: phase-4-opt-in-dispatch
- Draft PR: [#9](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/9)
- Verified head: dbfc223d80d7cf2412e2223d09e3cdbe728520e2
- CI: [run #40467702807](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40467702807) — success; both jobs green on the same head.
- Quality: formatting, Ruff lint, strict mypy all passed; 383 tests passed; overall coverage 91.35%; Phase I core 96%; Phase II integration 86%. One non-blocking Starlette/httpx deprecation warning remains.
- Artifact: verification-evidence, ID 12717286109, 30,204 bytes, GitHub SHA-256 78151c4cdfff9706098f1f416b3a1c937104ef711efaa4a9edbad1c3160e33db.
- Downloaded ZIP SHA-256 independently matched GitHub's digest. The ZIP contains exactly junit.xml and coverage-manifest.json. Both inventories contain 383 unique matching test IDs; all tests passed with zero failures, errors, or skips. The manifest head_sha matches the tested commit, and every behavioral_assertion_verified flag is false.

## CI iteration history

1. Run #40467194376 on commit 92ede3f43438688f9d538d0b59613ca9742ee201 failed at format-check. Lint, type-check, tests, and evidence production were skipped. The dispatcher/test files needed Ruff formatting.
2. Run #40467336840 on commit 2a3179083a7522a22977da83eb5597112fa24f5b passed formatting but failed Ruff S105 because the test token fixture looked like a hard-coded credential. Strict mypy, tests, and evidence production were skipped.
3. Run #40467459676 on commit c7b392f97a6c76f6c99491f372bb3484456c18b2 passed formatting but failed the same S105 rule for a token-named fixture. The fixture was renamed to a neutral name and given a non-secret example value.
4. Run #40467588927 on commit d13d762797cbd8faa35b3a65ff40e35c14bd2555 still failed S105 because the fixture identifier retained the word token. This confirmed that the rule also matches the variable name, not only the string.
5. Run #40467702807 on commit dbfc223d80d7cf2412e2223d09e3cdbe728520e2 passed both jobs. The quality job reported 383 passed and all configured coverage gates green; the exact-head evidence job uploaded the artifact described above.

## Lessons and boundaries

- A green format step does not imply lint, type-check, tests, or artifact production ran; skipped steps are not passes.
- Secret-scanning lint rules can flag fixture names as well as values. Use neutral fixture names and obviously synthetic values.
- The dispatcher remains disabled by default, only accepts a caller-provided token, and does not automatically dispatch, retry, merge, or deploy.
- This CI verifies the Phase IV branch's current base tree plus this Phase IV slice. Phase III implementation remains on draft PR #6; its live deployment smoke test and human review are still pending for the Phase IV ending.
