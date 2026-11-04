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


## Follow-up CI investigation and coverage closure attempt — 2026-11-04

### Commits and exact CI outcomes after the first journal entry

| Commit | Change since previous CI checkpoint | Exact CI result and diagnosis |
|---|---|---|
| `8a7e06413908` | Added the first integrated Phase III/IV CI journey and status log. | Full CI #41814439670 failed strict mypy because the new audit-state test indexed optional `get_dispatch()` results without narrowing. Focused governance #41814439754 passed. |
| `d3e3565dde8e` | Added dispatch accepted-before-cleanup state ordering, finite timestamp validation, timezone-aware run timestamps, exact-int workflow ID check, and regression tests. | Full CI #41814179708: formatting/Ruff/mypy passed; pytest coverage stage failed at 89.32%, 601 passed. Focused PR #41814179691 and push #41814172307 passed. |
| `054202eecd4a` | Narrowed the three optional audit records in the test with explicit non-None checks. | Full CI #41814491777: format/Ruff/mypy passed; 601 tests passed; coverage 89.32%, still below 90. Focused PR #41814491736 and push #41814487899 passed. |
| `65f97eb9fb9c` | Added parameterized dispatcher configuration, repository, Git ref, secret-like input, control-character, empty-schema and network-failure tests. | Full CI #41814683239 failed formatting only (one test file); focused PR #41814683343 and push #41814674189 passed. Ruff supplied exact formatting: wrap one long tuple and collapse one test signature. |
| `83b5b4c481b2` | Applied exact Ruff formatting to dispatcher tests. | Full CI #41814801425: format/Ruff/mypy passed; 634 passed, coverage 89.71%. Focused PR #41814801400 passed. This increased measured coverage by 0.39 percentage points but did not yet meet 90. |
| `b51832c3e709` | Added manifest exporter path and context-boundary tests: malformed node IDs, unsafe paths, external/non-Python files, duplicate JUnit IDs, and non-run-phase contexts. | First full CI #41815018465 failed Ruff formatting in the new manifest test. Focused PR #41815018472 and push #41815006136 passed. |
| `b524d6174ed4` | Applied exact Ruff formatting to manifest exporter tests. | Full CI #41815133710 failed Ruff S108 because the test fixture used a literal `/tmp` path. Focused PR #41815133630 and push #41815123279 passed. |
| `f747a68ddfb9` | Changed the test-only absolute path from `/tmp` to `/outside` to avoid the S108 temporary-path rule. | Full CI #41815235670: format/Ruff/mypy passed; coverage 89.92%; 641 passed but four exporter tests failed. Root causes: PurePosixPath normalizes duplicate slash and dot segments, a .txt filename fails the earlier .py:: node-ID marker, and CoverageData cannot combine line-only and branch-only measurement writes. Focused PR #41815235570 and push #41815230927 passed. |
| `87070d9a1132` | Corrected exporter tests to check actual traversal/absolute/backslash contract and use branch-only CoverageData for the setup-only context case. | Full CI #41815494157 failed Ruff RUF043 because the regex alternation passed to `match=` was not a raw string. Focused PR #41815493993 and push #41815486370 passed. |
| `1530dce3bb8c` | Made the regex assertion raw. | Full CI #41815605564: format/Ruff/mypy passed; 643 passed and one failed because a test expected a dot-prefixed intermediate path to be rejected, which the current exporter does not define as unsafe. Coverage was 90.01% despite the one failing test. Focused PR #41815605531 and push #41815598918 passed. |
| `3d512f7702ea` | Removed the unsupported dot-prefixed-directory expectation; retained absolute path, backslash, traversal and non-Python node-ID rejection coverage. | Latest focused push #41815752977 passed format, Ruff, strict mypy and Phase IV governance/dispatcher tests. **A full Phase II CI run on this exact SHA has not yet appeared in the Actions run list at the time of this update.** Do not infer the previous 90.01% result as a green full CI for this head. |

### What is actually stopping the project now

- The original combined full CI stopper was true coverage below 90%. It has been raised from 89.19% (`78fb1bf`) to 89.32% (`054202e`), 89.71% (`83b5b4c`), 89.92% (`f747a68`), and 90.01% on `1530dce` (but that run had one failing test).
- On `1530dce`, all quality gates through strict mypy passed; pytest had 643 passing tests and one failing assertion. Thus the last observed full-run state crossed coverage but did not pass tests.
- The latest commit `3d512f7` removes that unsupported assertion. Its focused governance CI is green. The exact-head full workflow still needs to run and prove all tests pass, coverage >=90.00%, Phase I >=95%, Phase II >=80%, and the dependent evidence producer job completes.
- No production code was excluded from coverage, no threshold was reduced, and no test failure was hidden.

### Theoretical test corrections and lessons

- Test the implemented trust contract, not an imagined stricter contract. `PurePosixPath` canonicalizes redundant slash and `.` segments; traversal `..` remains a security-sensitive case and is explicitly rejected by the exporter.
- A pytest node ID without the `.py::` delimiter is rejected before the filesystem path validator, so assertions must expect the actual first failing boundary.
- Coverage.py's `CoverageData` cannot accept line-only measurements and later branch-only measurements for the same file in the same data object. The non-run-phase fixture now writes branch arcs only.
- Ruff's S108 catches literal temporary paths in tests. Use a clearly external non-temporary path when testing absolute-path rejection.
- Ruff RUF043 requires a raw regex string for alternation in pytest `match=`.
- A green focused workflow validates governance code, not the combined application. Only the full exact-head Phase II CI and evidence job can close the combined CI gate.

### Current exact-head status

- Latest code head: `3d512f7702ea718a30ca2ed1a3cf0a0023494621`.
- Latest exact-head focused push: #41815752977, passed.
- Full Phase II CI on latest head: not yet present in Actions at the time of this update.
- Last full run with coverage >=90: #41815605564 on prior head `1530dce`, 90.01%, 643 passed / 1 failed; therefore not green.
- Phase IV remains draft. Live staging dispatch, PostgreSQL, installed App credentials, webhook/worker deployment and human review remain external acceptance gates.


## Full CI quality-gate result and evidence-job cancellation — 2026-11-04

A fresh full Phase II CI run was created for the PR update. GitHub reports run [#41815952938](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41815952938) as `cancelled`, so the overall workflow is not marked successful. However, inspection of the actual quality job's step conclusions and complete job log establishes that all quality/coverage steps completed successfully before cancellation:

- Ruff formatting: passed.
- Ruff lint: passed.
- Strict mypy: passed.
- Pytest: **643 passed**, 1 warning.
- Overall coverage: **90.01%**, threshold 90%.
- Phase I core coverage: **96.39%**, threshold 95%.
- Phase II integration coverage: **85.99%**, threshold 80%.
- The evidence producer job was cancelled before producing its artifact.

Why not call this a green full CI? Because GitHub's workflow-level conclusion is cancelled and no exact-head evidence artifact was produced. The quality job is a verified success; the workflow/evidence acceptance is still open. The run's Actions metadata lists head SHA `3d512f7702ea718a30ca2ed1a3cf0a0023494621` while the PR head snapshot had advanced to the documentation commit `c83ef6aa695d97deea2671738225099c81b96ed9`. This is a head-race/cancellation, not a test failure. A new exact-head run must complete both quality and evidence jobs.

The exact test correction on `3d512f7` removed only the unsupported expectation that a dot-prefixed intermediate directory is rejected. The exporter still rejects absolute paths, backslash paths, traversal segments, invalid node IDs and non-Python paths. The preceding run on `1530dce` had 643 passes, one incorrect assertion failure, and 90.01% coverage; this run confirms the corrected suite now has 643 passes and all three coverage gates pass.

Next: trigger/observe a fresh PR full CI for the latest branch head, verify the evidence job completes, then download and inspect its artifact digest and contents. Keep PR #9 draft until that evidence check and live staging acceptance pass.


## Exact-head full CI quality result and cancellation analysis — 2026-11-04

A second integrated full CI run [#41816006910](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41816006910) also reached the end of the quality checks but was cancelled at workflow level. The Actions metadata shows:
- Workflow run head SHA: `c83ef6aa695d97deea2671738225099c81b96ed9`.
- PR head snapshot at run completion: `b32ff2f952154334b334b19d400e669f72cc828c`.
- The branch was advanced by a documentation-only log commit while this workflow was running. GitHub's concurrency cancellation stopped the evidence job and marked the overall run cancelled.

The quality job's completed steps and log are independently readable:
- Formatting: passed.
- Ruff: passed.
- Strict mypy: passed.
- Tests: **643 passed**, 1 warning.
- Overall coverage: **90.01%** (90.00% gate).
- Phase I core: **96.39%** (95.00% gate).
- Phase II integration: **85.99%** (80.00% gate).
- Evidence artifact job: cancelled; artifact not produced by this run.

This confirms the corrected test suite is green and all three coverage thresholds pass, but it is not yet a workflow-level success and cannot be used as an exact-current-head artifact claim. The repeated cancellation pattern is explained by the branch being updated while a pull-request workflow is executing. The next attempt must be allowed to run without another commit or branch update until both quality and evidence jobs finish. No code change is needed solely to address the coverage threshold at this point.

### Current worktree/branch policy

- Keep the 90.00% overall, 95.00% Phase I and 80.00% Phase II thresholds unchanged.
- Do not make any further commits while the next exact-head full CI is running.
- Wait for the complete Phase II CI and dependent evidence job; inspect the artifact and only then update this journal.
- Focused governance success remains supplementary; it does not substitute for full CI.


## Human-review governance implementation and exact-head CI journey — 2026-11-04 evening

The following commits continue from the previously recorded Phase IV branch head `7bf7b43cfb213d821cb42a2d1d0b79a066a9b786`. Every CI result below is attributed only to the SHA it actually tested.

| Commit | Work between CI checkpoints | CI observation and root cause |
| --- | --- | --- |
| `7bf7b43` | Added `human_governance.py` and initial exact-head reviewer/audit tests. | Focused dispatch workflow passed but did not yet include the new files. Combined Phase II CI #41838773297 failed at Ruff formatting: the new module and test file were not Ruff-formatted. |
| `2c64a62` | Applied the initial Ruff formatting corrections. | Focused dispatch workflow #41846986007 passed its then-current, narrower scope. Combined CI #41846994429 still failed formatting; subsequent logs showed the canonical formatting corrections had not yet been fully applied. |
| `37c3089` | Added human-governance paths to the focused workflow, included the new module/tests in format, Ruff, mypy and pytest commands, and corrected the malformed-review fixture so a JSON object remains an object instead of being replaced by an empty list. | Combined CI #41847194450 and focused CI #41847180845 failed Ruff lint: S105 flagged a test constant named `TOKEN`, and I001 flagged import ordering. The focused workflow now exercised the new component, exposing issues previously missed. |
| `510fdd1` | Connected verified GitHub approvals to the existing domain state machine through `apply_verified_human_approval`; added repository/PR/base/head binding and integration tests. | Combined CI #41847431159 and focused CI #41847421432 failed Ruff formatting. The new adapter/test section needed canonical blank-line formatting. |
| `5cf413f` | Attempted to resolve the adapter/test formatting diff. | CI #41847596690 and focused #41847585738 still reported Ruff blank-line differences. The diff showed that the file-level separation and the test-section spacing were not yet canonical. |
| `1846b7d` | Adjusted module separation and reran checks. | CI #41848018754 and focused #41848007869 still found a formatting boundary; Ruff's diff indicated one more blank line was required before the module-level adapter. |
| `14a5d2c` | Restored the required module separation. | Focused CI #41848282395 then passed formatting but failed Ruff: B008 rejected constructing `ConclusionPolicyConfig()` in a function default, and I001 required import ordering. |
| `5f8ce5e` | Changed the adapter's policy argument to optional and instantiate the default inside the function; fixed import order. | Focused push #41848570800 passed. Full CI #41848583378 reached pytest: **667 passed**, but overall coverage was **89.19%**, below the unchanged 90.00% threshold. New governance code was only 76.26% covered. Formatting, lint and strict mypy had passed. |
| `9ee4c27` | Added adversarial tests for malformed model fields, reviewer allowlists, request identity, unsafe paths, malformed JSON, transport timeout/connection failures, oversized/paginated responses, malformed PR payloads, and audit constructor/lookup validation. | CI #41849091455 / focused #41849084207 failed Ruff formatting. The formatter identified one lambda layout and excess blank-line spacing. |
| `93f141e` | Applied the reported lambda formatting and test spacing correction. | CI #41849324739 / focused #41849313105 still reported one extra blank line before the parameterized adversarial tests. |
| `a5782c0` | Corrected the test-section blank-line count. | CI #41849578697 and focused #41849566731 advanced beyond formatting but Ruff lint reported a hardcoded blank auth value (S106) and an undefined `HumanReviewAuditError` test import (F821). |
| `063a043` | Applied another blank-line adjustment based on Ruff's exact diff. | CI #41849804368 / focused #41849792678 still showed the extra blank line; the source needed two blank lines between module-level definitions, while the decorated test group needed exactly the Ruff-required separation. |
| `3046eeb` | Imported `HumanReviewAuditError` and moved the blank auth fixture to a neutral-named constant, avoiding secret-scanner false positives. | **Full CI #41850039278 passed** on exact SHA `3046eeb2681e0102f4ca9b978802e008a6baa13a`. Focused Phase IV CI #41850039261 also passed. |

### Final CI and artifact evidence on `3046eeb`

- Formatting, Ruff lint and strict mypy: passed.
- Tests: **687 passed**, one non-blocking Starlette/httpx deprecation warning.
- Overall coverage: **90.23%** (90.00% required).
- Phase I core coverage: **96.39%** (95.00% required).
- Phase II integration coverage: **85.99%** (80.00% required).
- Evidence producer: passed on the exact PR head.
- Artifact: `verification-evidence`, ID `13334261929`, size 50,013 bytes, SHA-256 `72d5a21ff1bf191f4f56e84d9a14db8242db71e28ee4de2cca361d48eb76ae87`.
- Independently downloaded ZIP hash matched GitHub metadata. Archive has exactly `junit.xml` and `coverage-manifest.json`; JUnit and manifest each contain 687 unique matching test IDs, all passed, zero failures/errors/skips, exact head binding. All behavioral assertion flags are false.

### What the work taught us

1. A focused workflow is only meaningful if its path filters and commands include the new module and tests. The initial green focused runs were not evidence that human governance passed.
2. Test fixtures must preserve malformed data intentionally. Using `reviews or []` silently converted an empty/falsey fixture into a valid empty collection and invalidated the malformed-response test.
3. Exact Ruff output should be treated as the source of truth. Hand-adjusting blank lines without inspecting the diff caused several avoidable CI cycles.
4. Security lint checks apply to tests too. Even fake credentials and blank auth values should be named/constructed so scanners do not mistake them for real hardcoded secrets.
5. Human approval must not be a parallel, disconnected status. The adapter now binds the review to repository + PR + base/head, converts it to the existing domain record, applies the existing state machine and severity policy, and persists the audit before returning an approved obligation.
6. Coverage is a project-level gate, not a local-module vanity metric. The first implementation produced 667 passing tests but only 89.19% overall coverage. Adversarial tests raised the final overall coverage to 90.23% without changing thresholds or excluding production code.

### Remaining end-of-phase acceptance

Repository implementation and CI are green, but Phase IV is **not operationally released**. The following require staging configuration and an authorized human operator, not more speculative code commits:

- Configure a staging-only authenticated operator entry point and deployment-specific operator policy.
- Configure managed PostgreSQL and least-privilege GitHub App/Actions credentials in the target environment.
- Perform a real non-production workflow dispatch and reconcile the exact workflow/run/actor/SHA correlation.
- Follow the dispatched run through the integrated Phase III authenticated artifact ingestion, freshness checks, evidence ledger and Check Run publication.
- Execute the Phase III deployment smoke test against the installed App, webhook ingress/worker and durable evidence database.
- Complete human review and explicit release approval. Keep PR #9 draft and production merge gating disabled until these are done.
