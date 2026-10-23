# Current Verified Status

**Snapshot date:** 2026-10-18  
**Main/base SHA for Phase III PR:** `1ff87390071491a9a08c9748aca2f36887ac5d77`  
**Last inspected Phase III head:** `d2a1e0c2a08e3a702ff9814eee408b3606e4ea37`  
**Phase III PR:** [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), open and draft.  
**Last completed CI run:** [#39149971965](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39149971965).

## Verified on main

### Phase I
- Exact run: [#39036376525](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39036376525).
- Tested SHA: `5626ef5b5df58f288058977f73692947234abc1c`.
- Formatting, Ruff, strict mypy, and tests passed: 167 tests and 97.30% overall coverage against the 95% Phase I release gate.

### Phase II
- Exact run: [#39103979912](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39103979912).
- Tested SHA: `1ff87390071491a9a08c9748aca2f36887ac5d77`.
- Formatting, Ruff, strict mypy, tests, Phase I core gate, and Phase II integration gate passed: 353 tests, one warning, 92.66% overall coverage.

## Phase III: last observed verification

- Run [#39149971965](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39149971965) tested exact PR head `a2e4b5a49717b350a59d980bc659aea86a47adac`; it was not green.
- Formatting failed in exactly two files: `src/verification_core/phase_three.py` (conditional-step error formatting and the workflow-run recheck call) and `tests/unit/test_actions_evidence.py` (one parametrized test signature plus an extra blank line).
- Ruff lint, strict mypy, unit/property tests, overall coverage, Phase I coverage, and Phase II integration coverage were **skipped**. They are unverified for that SHA. The exact formatter diff is now applied in the follow-up commit; this next CI run must verify it.
- The current `main` workflow file at the base SHA does not declare the required evidence-upload step. The new trust validator correctly rejects it. A production-capable ingestion run therefore requires a separate trusted-workflow deployment and an honest per-test evidence-manifest producer; a green library test suite alone cannot prove live ingestion is enabled.
- The implementation uses one run and exactly one configured artifact. Cross-run and shard aggregation are not implemented. Missing or ambiguous evidence is rejected. This change adds an explicit post-download reread of the workflow run and rejects an attempt/identity change.

## Completion estimate

**Working estimate: 70% implemented / 30% remaining (unchanged).** This is an engineering-scope estimate, not code coverage or release readiness. The remaining release work is concrete: obtain green full CI on the exact candidate SHA; satisfy the coverage gates; deploy a trusted base-branch uploader and per-test manifest producer; validate live GitHub artifact digest behavior; and reconcile the PR metadata, repository logs, and latest CI evidence to the same immutable SHA. Do not report 100% until those conditions are met.

## Acceptance checklist

1. Formatting, Ruff, strict mypy, tests, and all coverage gates pass on the same exact candidate SHA.
2. The run's ID, workflow ID/path, attempt, event, status, conclusion, and head SHA stay unchanged while evidence is retrieved; rerun or ambiguity fails closed.
3. The exact base-SHA workflow contract is validated. Production enablement waits for a trusted deployed workflow that emits the exact two-file archive and does not fabricate behavioral proof.
4. Publication tests prove no ledger terminal decision is written when Check Run publication fails and that post-publication persistence failure is surfaced as `ledger_persisted=False`.
5. Progress and investigation logs explain the failure, correction, evidence, and remaining deployment prerequisite without deleting failed history.
6. Branch head, PR head, changed tree, and CI-tested SHA are re-read and agree before claiming completion.


## Ruff findings and explicit fixes — 2026-10-19

Run [#39168709842](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39168709842) passed formatting and failed Ruff with eight findings. The corrections preserve strict linting: the duplicate-key YAML parser remains a `SafeLoader` subclass and has a narrow `S506` suppression on the loader invocation; trigger logic now explicitly groups mixed boolean operators; error text is wrapped; regex-based `pytest.raises(match=...)` values are raw strings; the duplicate ZIP fixture combines context managers; and the trusted workflow fixture string is split into adjacent literals. Strict mypy and tests were skipped in that run and remain unverified until CI executes them.


## Follow-up Ruff suppression and fixture corrections — 2026-10-19

Run [#39169027616](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169027616) passed formatting but Ruff found three issues: the `S506` suppression was attached to the wrong line and was consequently unused, the custom-loader argument itself was flagged, and a long embedded workflow fixture line exceeded the configured line length. The suppression is now attached to the `Loader=_UniqueKeySafeLoader` argument with a comment documenting that it subclasses `yaml.SafeLoader`; the fixture is split into adjacent literals without changing the YAML bytes. Strict typing/tests were skipped in that run and remain pending.


## Full-test findings and regression additions — 2026-10-19

Run [#39169277725](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169277725) passed format, Ruff, and strict mypy, then ran 424 tests: 422 passed and two failed in the new workflow-contract parameterization. The wildcard-path case expected the wrong error wording; the conditional-upload fixture accidentally contained a literal backslash-n, so YAML parsing correctly rejected it before reaching the conditional-step assertion. The expected message and fixture are corrected. Overall coverage was 89.68%, below the required 90%; added parametrized regression cases for changes to every workflow-run identity field and invalid original attempt metadata to increase meaningful branch coverage. These fixes remain unverified until a new exact-head CI run passes.


## Overall coverage gate correction — 2026-10-19

Run [#39169688736](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39169688736) passed formatting, Ruff, strict mypy, 433 tests, and both phase-specific gates (Phase I 96%, Phase II 86%). Its report nevertheless showed 89.77% total coverage. Inspection of the workflow confirmed that `coverage.report.fail_under=90` is not enforced by the existing `pytest --cov` invocation, because pytest-cov needs `--cov-fail-under=90` explicitly. Added that flag to the project's pytest default options and added direct regression tests for missing/malformed/oversized trusted workflow inputs. The next exact-head run must prove both the tests and the total gate; this change is not yet verified.


## Explicit overall-coverage enforcement and ingestion precondition tests — 2026-10-19

The latest green run [#39170237791](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39170237791) passed formatter, Ruff, strict mypy, 438 tests, and the Phase I (96%) / Phase II (86%) gates. However, its report displayed 89.91% overall, below the intended 90% floor. The workflow lacked a dedicated overall `coverage report --fail-under=90` step, and the attempted pytest addopts flag did not cause the workflow to fail. The workflow now has an explicit total-coverage gate immediately after tests; no green overall result is claimed until a later run proves it.

New tests cover invalid workflow-run IDs (including bool-as-int), empty trust policy, missing/untrusted workflow paths and base-SHA workflow source, malformed workflow digest validation, and closed-PR rejection before any Actions API reads. The next CI iteration must show whether these meaningful negative cases raise overall coverage over the floor. Branch/PR heads and CI SHA must be checked together before assigning a completion percentage.


## Current CI exact-head failure — 2026-10-19

Run [#39171029125](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39171029125) tested `b4e43eb0111e80be060d7665e403b0fccd223f1c`. The overall-coverage workflow addition and test expansion were not yet evaluated: the run failed at `ruff format --check src tests` because `tests/unit/test_actions_evidence.py` needed one additional blank line before `test_phase_three_rejects_invalid_workflow_run_identifiers`. Ruff, strict mypy, tests, the overall 90% gate, and phase-specific gates were skipped on this SHA. This formatting-only correction is recorded separately; the next run must prove downstream checks on its own exact SHA.


## Evidence exporter CI result — 2026-10-19

- Commit `9b42aba85e0979af86ac704f4cb5926f298859bf` triggered [CI #39194526404](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194526404).
- The quality job failed at `ruff format --check src tests` on two formatting-only locations in `manifest_export.py` and `test_manifest_export.py`. Ruff, strict mypy, tests, total coverage, and phase coverage gates were skipped; the new evidence job was skipped because it depends on quality.
- A formatting-only fix is being committed separately. The exporter remains unverified until the next exact-head CI completes.


CI follow-up [#39194649771](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194649771) again stopped at formatting, now on one JUnit fixture string in `tests/unit/test_manifest_export.py`. All downstream checks and the dependent evidence job were skipped. The formatter-requested single-line fixture correction is committed separately; exporter behavior remains unverified.


CI run [#39194755446](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194755446) passed formatting but failed Ruff on one import-order issue and two long lines in the new exporter. Strict mypy, tests, coverage gates, and the dependent evidence job were skipped. Those three static-analysis findings are corrected in the next commit; no functional verification is claimed.


CI run [#39194881289](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39194881289) passed formatting and Ruff; strict mypy then found three exporter typing issues (an unnecessary ignore and variable reuse that made an optional context appear non-optional). Tests and coverage gates were skipped. The fix removes the stale ignore and gives raw versus per-test contexts distinct names; functional verification remains pending.


CI run [#39195030380](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195030380) passed formatting, Ruff, and strict mypy, then ran 455 tests: 453 passed and two exporter tests failed because the test expectations did not match actual fail-closed behavior. Total coverage was 89.54%, below 90%. The next commit adds an explicit empty-coverage-data rejection, tests path traversal directly at the boundary, and preserves the overall coverage gate. The new evidence job was skipped because quality failed.


CI run [#39195221364](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195221364) passed every quality gate (455 tests, total coverage ≥90%, Phase I and Phase II gates green). The evidence job ran pytest successfully but the exporter rejected the generated JUnit report because one legitimate parameterized testcase name exceeded the 2,000-character bound. This is an integration failure, not a test-suite failure. The parser and manifest node-ID bounds are being raised together to 10,000 characters; the XML and manifest remain independently capped at 5 MiB, so total input size remains bounded. Artifact upload has not succeeded yet.


## Latest CI exact-head formatter result — 2026-10-19

Run [#39195545167](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195545167) failed at `ruff format --check src tests` on one line in `src/verification_core/coverage.py` (the node-ID length validation error). Formatter output named no other files. Ruff, strict mypy, tests, total coverage, phase-specific gates and the dependent evidence job were skipped. This correction applies that exact formatter diff; it does not change semantics and does not count as verified functional progress.


## Evidence-producer root cause and correction — 2026-10-19

Exact quality CI [#39195904599](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39195904599) passed formatting, Ruff, strict mypy, 455 tests, and all overall/phase-specific coverage gates. The producer pytest step passed, but manifest export rejected JUnit testcase 42 because its name exceeded the 10,000-character parser limit. The source of the huge name was the parametrized workflow-input test whose parameter included a 256 KiB synthetic YAML string; pytest embeds parameter representations in JUnit testcase names by default. This was not a genuine test node needing a larger parser limit. The safe fix is to give those five parameterized cases short explicit IDs, preserving the strict 10,000-character bound and avoiding shipping arbitrary large parameter representations in JUnit. Exporter verification is pending the next run.


## Second oversized JUnit node diagnosed — 2026-10-19

Run [#39196884255](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39196884255) passed all quality gates and the exact-PR-head pytest step, but manifest export failed on `testcase[335].name` exceeding 10,000 characters. Reviewing parameterized tests found the second source: `tests/unit/test_policy.py::test_input_size_nul_and_invalid_unicode_are_rejected` includes a 256 KiB string in pytest parameters and had no explicit JUnit ID. The Phase III workflow-input test already received stable IDs in the previous commit, but this independent policy test also needed stable IDs. Added three short IDs (`oversized-policy`, `nul-policy`, `invalid-unicode-policy`) without reducing the oversized input or relaxing any parser limits. The next CI run must show exporter success and artifact upload; no success is assumed.


## Exact coverage/JUnit identifier mismatch corrected — 2026-10-19

Run [#39197824251](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39197824251) passed every quality gate, but the evidence producer failed on a real context-to-JUnit name mismatch. The diagnostic identified context node `tests/unit/test_evidence_ledger.py::test_ledger_policy_digest_is_part_of_evidence_identity`; the exporter mapped it to `test_evidence_ledger::...`, whereas pytest's JUnit artifact uses the repository-relative dotted classname `tests.unit.test_evidence_ledger`. The path normalizer incorrectly stripped non-package directory prefixes. It now translates the full safe repository-relative test path to dotted form, and exporter fixtures reflect the exact JUnit convention. Matching remains exact and ambiguous/partial evidence still fails closed. Artifact production is unverified until CI passes and the upload step completes.


CI run [#39219163228](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39219163228) stopped at Ruff after formatting passed. The only lint finding was E501 at line 94 of `tests/unit/test_manifest_export.py`: a single long JUnit XML string. Strict mypy, tests, coverage gates, and the evidence job were skipped. The string is split into adjacent literals preserving the exact XML bytes; this correction is pending verification.


Run [#39219463813](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39219463813) stopped at format-check on one quote-style difference in `tests/unit/test_manifest_export.py` line 96. All later quality gates and the artifact job were skipped. The exact Ruff correction is applied; this run does not verify functional behavior.


## Policy-fixture JUnit context name fixed — 2026-10-19

Run [#39219692769](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39219692769) passed the entire quality job and its coverage gates, but evidence export failed because JUnit testcase 335 represented the full policy YAML inside the `test_invalid_policies_fail_closed` parameter ID. That value is large but valid as a negative test input; the generated JUnit node ID was the issue. Added stable concise IDs to each of the 13 parametrized policy-failure cases, without trimming test input or weakening the 10,000-character field limit. The subsequent exact-head CI must verify this correction and artifact upload.


## Parameter IDs containing scope separators — 2026-10-19

Run [#39220114379](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39220114379) passed all quality and coverage gates, but manifest export rejected the test ID `tests/unit/test_policy.py::test_unsafe_or_ambiguous_selectors_are_rejected[tests/test_authz.txt::test_case]`. The parser used a plain split on `::`, which also split the literal separator inside the bracketed parameter ID. Added a bracket-aware node-ID splitter that recognizes pytest scope separators only outside parameter brackets and rejects unbalanced brackets. Added regression coverage for both a parameter containing `::` and malformed bracket nesting. The exporter remains unverified until a new run successfully exports and uploads both files.


## Exporter parameter-ID parser correction — 2026-10-22

Exact-head CI [#39224141676](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39224141676) passed every quality and coverage gate, but the artifact producer failed with `Coverage context contains an invalid pytest node ID`. The prior parser enforced balanced brackets, but pytest parameter IDs are opaque and can contain unbalanced-looking text from representations, nested brackets, and scope separators. The parser now identifies the source file boundary at `.py::`, splits scope markers only before the first parameter opener, and preserves the full parameter suffix verbatim. Replaced the incorrect balanced-bracket tests with opaque-suffix cases. Still require exact match against JUnit inventory; no unmatched evidence is dropped. This new correction requires fresh exact-SHA CI plus artifact upload verification.


## Zero-measured-coverage testcase fix — 2026-10-22

CI run [#39812879743](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39812879743) passed quality gates and PR-head tests, but export failed because a non-skipped JUnit testcase had no coverage context. Tests can pass without touching tracked production files; exporter now retains all JUnit cases and emits empty measured line/branch maps for those without a run context. It still rejects unmatched contexts and rejects the whole run if no run contexts match any JUnit testcase. Added regression test. This fix is pending exact-SHA CI and artifact upload.


## Exact formatting correction — 2026-10-22

Run [#39813965772](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39813965772) failed the format gate before lint/type checking/tests; Ruff requested quote style, a compact dictionary-comprehension line, and removal of one extra blank line in the new no-measured-coverage regression. These exact format changes are applied. The exporter now includes the opaque pytest-parameter suffix parser and the no-measured-production-coverage handling from the previous pushed slice; its behavior remains unverified until the next CI run reaches export and upload.


## Trusted producer chain hardened — 2026-10-22 (CI pending)

Added fail-closed validation that the base-SHA workflow contains exactly one pinned checkout of the exact PR head with credentials disabled, one pytest step using per-test coverage plus JUnit output, one exporter invocation bound to that same SHA, and one upload step. These steps must be ordered, unconditional where applicable, and in the same job. Tests now mutate checkout ref, remove the per-test coverage option, and replace the exporter module to prove those cases are rejected. This closes the gap where a workflow with a valid uploader but no trustworthy evidence-producing chain could pass the contract. The base `main` workflow still needs deployment; the new validator tests and latest exporter changes remain subject to the queued exact-head CI.


## Artifact producer verified; validator-head format failure fixed — 2026-10-22

**Producer milestone verified on exact run [#39814823241](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39814823241), SHA `f721d73dea35a04889878b776b7e87f61ae0206c`:**
- Quality job and evidence producer job succeeded; exporter step and upload step both succeeded.
- GitHub artifact `verification-evidence`, ID `12442240904`, size 37,909 bytes, listed as not expired; SHA-256 `8373269c915d6d8bb507df9b97f10d8446154f188ea4e786c65bf4c0fc1a6f6a`.
- Downloaded ZIP SHA-256 independently matches GitHub's artifact digest.
- ZIP has exactly `junit.xml` and `coverage-manifest.json`. JUnit and manifest each contain 460 distinct testcase IDs and their ID sets match exactly. Manifest is version 1, bound to `f721d73dea35a04889878b776b7e87f61ae0206c`, contains 460 passed outcomes, and all 460 `behavioral_assertion_verified` flags are false.
- A structural sanity check found zero bad path, line-number, branch-ID, or outcome entries.

The newer validator-chain commit `d5540a19a17c50b9dd7457ecfa4340afdd1d2365` failed before downstream checks at Ruff formatting: one extra blank line before `PullRequestReader` in `phase_three.py`. This is corrected in the current follow-up commit. The successful producer run verifies artifact production on SHA `f721d73...`; it does **not** automatically verify the newer validator changes. CI must still pass on the corrected validator head before it counts as verified.


## Strict-mypy follow-up on trusted workflow chain — 2026-10-22

Run [#39817064462](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39817064462) passed Ruff formatting and Ruff lint, then failed strict mypy at `src/verification_core/phase_three.py:231`: a redundant cast to `str`. Because `name` is already narrowed by membership in the tuple of string step names, the cast is unnecessary and has been removed. Unit/property tests, coverage gates and the evidence job were skipped in that run; this correction requires a new full CI result.


## Exact Ruff formatting correction — 2026-10-23

Run [#39894345129](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39894345129) stopped at formatting only: Ruff requires two blank lines between the module-level workflow-discovery test functions in `tests/unit/test_github_actions.py`. No lint/type/test/coverage/evidence step ran on that commit. Applied the exact spacing correction; the new run-discovery method still requires full CI verification.


## CI formatting fix — 2026-10-23

The latest attempted run-discovery tests still had three blank lines between module-level test functions; Ruff requires two. Corrected the exact whitespace. Earlier run [#39902193903](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39902193903) failed at formatting, so no lint, strict typing, tests, coverage, or artifact-production check executed for that SHA. This is a formatting-only fix, not a verified functionality milestone.
