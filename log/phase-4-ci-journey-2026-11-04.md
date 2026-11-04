# Phase IV CI commit journey — 2026-11-04

This file is the detailed engineering journal for the integrated Phase III + Phase IV work on `phase-4-opt-in-dispatch`. It records the code change between CI checkpoints, what the CI actually ran, what failed, the root cause, the correction, and the next experiment. A run on a given SHA is not attributed to a later commit. Push and pull-request runs on the same SHA are grouped as duplicate event executions, not separate revisions.

## Starting state and integration

- Phase IV implementation and governance CI were green on `44a98059632ba07f262c8772ef18bbfee8ad494c`.
- Phase III implementation was on `9611cbc6504f3844770540c9d45f87864bdfae08`, with its own exact-head full CI success recorded as run #40465327360.
- Two-parent merge `8a17bd22abcfdea02111f7fa7768c5ba9b4c29a1` integrated Phase III into the Phase IV branch. Parent order: Phase IV `44a9805...`, Phase III `9611cbc...`.
- Merge-head focused governance CI passed (#41812644117 and #41812647351). Full CI #41812647400 was cancelled by a newer pull-request run. Cancellation is not success.
- `78fb1bf02c9b8c7fee72a6ad9d9cad74c5ce0b78` changed coverage report precision to two decimals while retaining `fail_under=90`.

## CI run #41812698040 — combined full CI failed on true coverage

**Commit:** `78fb1bf02c9b8c7fee72a6ad9d9cad74c5ce0b78`

- Formatting: passed, 63 files already formatted.
- Ruff: passed.
- Strict mypy: passed, 63 source files.
- Pytest: 593 passed, 1 warning.
- Overall coverage: 89.19%; gate: 90.00%; failed.
- Evidence job: skipped because it depends on successful quality job.
- Phase I and Phase II coverage gates: skipped after pytest-cov returned nonzero.

### Why the earlier report misled us

Before precision was set to two decimals, the previous full CI showed 89.82% but integer display rounded it to 90. The strict gate had not been exposed clearly in the displayed report. After exact precision, the integrated branch measured 89.19%, because Phase III and Phase IV modules added substantial measured production code without proportionate negative/error-branch coverage. The test count was healthy but coverage was not.

### Largest identified coverage gaps

- `dispatch_governance.py`: 303 statements, 75.68%.
- `workflow_dispatch.py`: 133 statements, 83.89%.
- `phase_three_worker.py`: 110 statements, 81.41%.
- `github_actions.py`: 181 statements, 84.64%.
- `github_app.py`: 292 statements, 81.58%.
- `manifest_export.py`: 161 statements, 77.29%.
- `run_ledger.py`: 116 statements, 79.49%.
- `actions_evidence.py`: 222 statements, 89.63%.
- `phase_three.py`: 274 statements, 87.76%.

The total report was 4,046 statements, 362 missed, 1,614 branches, 238 partial branches, 89.19% total. All 593 tests passed. This is a test coverage gap, not a functional test failure.

## Commit chronology: each revision and CI lesson

### `71079f09b66c` — governance implementation

Added GitHub user identity lookup, configured operator allowlist, repository collaborator permission check, SQLAlchemy write-ahead audit log, duplicate dispatch ID protection, explicit dispatch outcomes, one-shot coordinator, correlation marker and exact-SHA workflow-run verifier.

### `7654a229ec19` — focused governance workflow

Added the dedicated Phase IV workflow. Run #41802425875 failed formatting and was at an intermediate tree where the governance test path did not yet exist. Lesson: commit the implementation and its tests before treating the focused workflow as a reliable complete gate.

### `76df71925943`, `ec51f0700fa5`, `ab7afea7bce0` — test addition and repeated formatter failures

Added governance/reconciliation tests and recorded the CI issue. Runs #41802476153, #41802646916 and #41802776573 all reported two files needing Ruff formatting. The correction had to match Ruff's exact formatting, not just manually wrap a few lines.

### `28bb17b06e55`, `912b9005c771`, `141b49003c0c`, `f309692dd647` — iterative exact formatting

Formatted source, tests, then residual SHA validation line. CI continued to expose remaining drift one file at a time. Run #41803573915 still found a test file unformatted. Lesson: format both changed files in one pass and run the exact workflow command locally/against the candidate before pushing.

### `9234feda656c` — workflow filename validation

Fixed a workflow filename regex and formatting. Run #41804078616 passed formatting but strict mypy found an unused/incorrect import and import-order issues. The filename regex was corrected to accept valid literal-dot `.yml`/ `.yaml` suffixes.

### `708a61b769c4`, `bc53557ce2d3`, `86558845bc40`, `15245242e967` — audit timestamp typing

Run #41804293145: formatter and Ruff passed; mypy rejected `float(object)`. Timestamp checks were added, then narrowed further after run #41804570101 reported incomplete type narrowing. Run #41804897801 exposed one Ruff wrap. Commit `15245242` corrected the format. Runs #41805093613 (push), #41805099119 (full PR CI), and #41805099089 (focused PR CI) passed. Lesson: validate type, bool exclusion and non-negative range before conversion; inspect strict-mypy output after every correction.

### `911bf5881b70` — governance documentation

Recorded the governance design and exact-head verification. Runs #41805818410 (push), #41805830214 (full CI) and #41805830592 (focused governance) passed.

### `a22a39fb3eb6` — complete bounded run-list reconciliation

Added fail-closed handling for incomplete or over-limit GitHub workflow-run pages and malformed entries, with regression tests. First CI attempt found Ruff formatting in the fixture. The implementation intent was correct but formatting prevented the focused and full jobs from passing.

### `44a98059632b` — exact formatter correction

Applied Ruff's exact parameter formatting. Runs #41811752312 (push), #41811759527 (full PR CI) and #41811759410 (focused PR CI) passed. This established the last fully green pre-integration checkpoint.

### `8a17bd22abcf` — Phase III integration

Created a true two-parent feature-branch merge of Phase III into Phase IV. Focused governance passed in runs #41812644117 and #41812647351. Full CI #41812647400 was cancelled, so no full CI success is inferred from it.

### `78fb1bf02c9b` — exact coverage reporting

Set `precision = 2` in coverage reporting without changing the 90% floor. Focused governance passed in #41812690587 and #41812697953. Full CI #41812698040 revealed 89.19% and failed; 593 tests passed. This was the key discovery: coverage was the actual combined CI stopper.

## Theoretical solution review and implementation

### Failure modes examined

- Duplicate dispatch identifiers must block a second external side effect.
- A timeout after POST is ambiguous and cannot be retried automatically.
- A successful POST followed by HTTP client close failure must not leave audit state as `authorized`.
- A workflow-run list response that is incomplete, over 100 entries, malformed, ambiguous or incorrectly correlated cannot be treated as a match.
- Boolean values must not pass integer identifier checks in Python (`bool` subclasses `int`).
- NaN, positive/negative infinity, negative timestamps and boolean timestamps are invalid.
- Workflow run timestamps must be timezone-aware, not host-local ambiguous values.
- A wrong commit SHA must become a recorded head mismatch, never evidence success.

### Commit `d3e3565dde8e6800c16debd3150ff9f41443f8a3`

Changes:
- Audit authorization timestamps reject NaN, infinity, negative values and booleans.
- Reconciliation cutoff timestamps receive equivalent validation.
- Out-of-range Unix timestamp conversion is caught and returned as a sanitized reconciliation error.
- Workflow-run `workflow_id` requires exact integer type, preventing `True == 1` from passing.
- Workflow-run `created_at` must contain a timezone.
- After GitHub confirms a dispatch POST, audit state is advanced to `submitted_unreconciled` before closing the HTTP client. This closes a duplicate-dispatch hazard if cleanup fails.
- Added regression tests for invalid audit timestamps, rejected/unknown/head-mismatch state transitions, naive workflow timestamps, invalid cutoff and cleanup failure after successful dispatch.

### CI for `d3e3565`

- Focused push workflow #41814172307: **passed** (Ruff format, Ruff lint, strict mypy, governance/dispatcher tests).
- Full CI pull-request run #41814179708: in progress at log creation.
- Focused governance pull-request run #41814179691: in progress at log creation.
- Do not claim the full CI or evidence artifact succeeded until the exact-head runs finish.

## Execution plan after this checkpoint

1. Read exact-head full CI logs from #41814179708. If tests fail, fix the behavior/test mismatch; if coverage fails, use the new coverage table and missing branches to add direct tests.
2. Keep the 90.00% gate intact. Do not reduce the gate, exclude production files, or add tests that merely execute lines without asserting meaningful behavior.
3. Aim for a margin above 90%, not a fragile 90.00% pass.
4. Confirm Phase I >=95% and Phase II >=80%.
5. Confirm evidence job runs on the exact PR head and inspect artifact digest, JUnit and manifest.
6. Continue with Phase III + IV staging integration only after CI is green. Real GitHub App credentials, managed PostgreSQL, deployment URL, webhook secret and operator allowlist are external acceptance prerequisites, not facts to fabricate.
7. Keep PR #9 draft and production merge gating disabled until staging smoke and human review pass.

## Honest status

At the time this file was authored, repository-level governance CI on `d3e3565` was green, while the combined full CI was still running. Phase IV is not yet complete.
