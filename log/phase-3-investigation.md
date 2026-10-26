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


## Latest retry after main synchronization — 2026-10-18

The sync commit `b8f4c6c` made the branch accurately inherit the root-level engineering journal from
main and ensured CI runs against the synchronized PR head. Its run [#39132715519](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39132715519)
still failed on Ruff `I001` for adjacent imports from `verification_core.evidence` and
`verification_core.evidence_ledger`, despite the prior ordering attempts. Formatting passed, and
mypy/tests/coverage were skipped.

The new attempt moves the JUnit fixture imports into the `make_evidence` factory, which removes that
two-module import-order interaction from the module-level block. This is intended to break the lint
loop; its effectiveness remains unverified until CI on the new SHA. No progress increase is assigned.


## Third CI attempt — 2026-10-18

Run #39143573401 passed formatting but failed Ruff `I001` on the import block in
`tests/unit/test_evidence_ledger.py`. Moving the JUnit imports into the fixture factory did not resolve
the lint failure, so the cause is broader than the relative ordering of those imports. The current runner
excerpt identifies the rule but does not expose the complete autofix diff; local Ruff installation was
unavailable because the environment has no package-network access.

A narrowly scoped file-level `I001` suppression is a temporary diagnostic step to let strict typing,
tests, and coverage execute. It must be removed before Phase III is release-complete. The suppression is
not counted as a quality fix or progress increase.


## Strict typing now reached

After the temporary single-file Ruff suppression, CI run #39143710693 passed formatting and lint and
reached `mypy --strict src tests`. It failed with 28 errors: an `object`-typed JUnit map prevented
safe `.outcome` access, one test helper lacked a return annotation, and several test calls used
`**dict[str, object]` against a fully typed keyword-only API. The fix uses inferred concrete JUnit
case values and explicit keyword arguments in tests. These are actual type-safety improvements, not
type-ignore suppressions; the next run must confirm.


## Formatter correction after typing edits

CI run #39143886828 exposed one formatting-only issue: the annotated `ingest` helper signature was
split over three lines, while Ruff formats it on one line. The exact one-line form is now restored.
No test or type result is inferred from this formatter failure.


## First CI-green Phase III foundation and next slice

Run [#39143973263](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39143973263)
passed all existing release gates on `db2cb27b5d23187cd8f4917b41303a8a2b84183a`, including strict
mypy, all tests, and both explicit coverage gates. The green result still includes a temporary
file-scoped `I001` suppression in the evidence-ledger test; this is diagnostic only and must be removed.

The next implementation adds a deterministic bridge from authenticated ingestion to the Phase I
state machine. It accepts target line/branch sets and exact obligation-to-test assertion bindings from
trusted analysis; it deliberately ignores the artifact's self-certified assertion flag when deciding
whether a passing test is sufficient. This prevents an authenticated ZIP from self-authorizing a
PASSED obligation. The new reconciliation code and tests require their own full CI run.


## Reconciliation-slice formatter failure

Run #39144197581 failed only at `ruff format --check` before any lint, type, or test step. Its exact
diff showed an extra blank line before `reconcile_authenticated_obligation` and three long imports
in the new tests. Those exact changes are applied; no behavioral test result is inferred from this run.


The second formatter retry found only one extra blank line before the first newly added reconciliation test;
it is corrected without changing test behavior.


## Publication boundary and contradictory-result hardening — 2026-10-18

The latest previously green commit, `54498841ad391442f6746cd4e0cc52a6aaf0c1e6`, passed every existing
CI gate [#39144389166](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39144389166).
It still carried a temporary module-scoped Ruff suppression. The next slice removes that suppression
and adds the first Check Run publication API around the Phase I deterministic evaluation.

The publishing helper re-reads PR state/base/head immediately before its one Check Run side effect and
refuses to publish when any identity is stale. Another defensive fix keeps `CONTRADICTORY` evidence
contradictory all the way into the Phase I state machine, rather than allowing subsequent sufficiency
calculation to overlook the contradiction. New adversarial tests exercise these contracts; CI for the
new SHA remains the required validation.


## Publication-slice formatter correction

Run #39144723077 failed at formatting only. Ruff's diff identified the conditional expression's
indentation, three line-wrapping differences in the publication helper, and one extra blank line before
the new fake publisher. These formatting-only edits are now applied; the next CI run must reach lint,
mypy and tests to validate the implementation.


The follow-up CI attempt found only two formatting diffs: the conditional expression was indented
incorrectly after adding contradiction preservation, and the ledger test had two blank lines between
its module docstring and future import. Both exact diffs are corrected; no behavioral gate has yet run
on this revision.


## Ruff lint diagnostics after formatting passed

Run `39144951098` passed format but failed lint with six diagnostics: import sorting in the new module
and two test locations, an undefined `ExecutionOutcome` in the adversarial test, an unused
`ObligationStatus` import in the service module, and naturally sorted slots. These are now corrected
without weakening Ruff. Strict typing and test behavior have not yet been validated on this SHA.


The latest run passed format and all production/test lint checks except one long import in
`tests/unit/test_evidence_ledger.py`. It is now a parenthesized multi-line import; no test result is
claimed until CI proceeds past lint.


The import members are now parenthesized and sorted. Ruff's remaining diff points only to the import-to-
constant spacing; the configured style expects one blank line here, which this commit applies.


## Exact-head CI failure and next diagnostic — 2026-10-18

A fresh read of the live PR, branch tree, and workflow API supersedes the older status snapshot above:
PR #6 currently points at `34df9e9c9aaf8f58bdd62a0a2070169da563a4df`, and CI run [#39145290937](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39145290937)
tested that exact SHA. Formatting and Ruff both passed; strict mypy then stopped the job at
`tests/unit/test_actions_evidence.py:517` because `_scheduled_high_obligation` had no return annotation.
Tests and both coverage gates were skipped, not passed.

The corrective change imports `VerificationObligation` at module scope and annotates the helper's
return type. It preserves `mypy --strict`; the fix is not considered verified until a later run reaches
and passes the test and coverage steps.

A second issue is more architectural: `ingest_pull_request_run` fetches the trusted workflow text at
the base SHA and records its SHA-256, but the current code does not parse that definition to prove that
the configured step actually invokes the expected artifact-upload action or names the required artifact.
A job step's display name alone is not a reliable semantic contract. The next trust-boundary implementation
must make the upload contract explicit and reject unsupported or ambiguous workflow shapes, with tests
for look-alike names, missing uploader actions, mismatched artifact names, duplicate candidate upload
steps, and unpinned/unapproved action references.

For run/shard handling, one requested run currently requires exactly one artifact with the configured
name. That is a useful fail-closed primitive, but it is not a documented aggregation protocol for
multiple successful runs, reruns, or test shards. Until a deterministic aggregation contract exists,
ambiguous or partial evidence must remain inconclusive rather than being combined optimistically.


## Trusted workflow semantics and adversarial ZIP boundaries — implementation slice

The ingestion service previously fetched the workflow at the base SHA and stored its digest, but treated the path and a successful display-name step as enough. That was incomplete: a same-named shell step or an uploader configured with a different name/path could satisfy the shallow check. The service now validates a bounded, duplicate-key-rejecting YAML document, a pull-request trigger, one precisely named and sole artifact uploader, a full immutable upload-artifact commit pin, the exact evidence filenames, the literal artifact name, and `if-no-files-found: error`. Unsupported/ambiguous workflows fail closed before artifact downloads. The repository's current base workflow does not itself meet this contract; that is a deployment prerequisite, not a reason to weaken the validator.

The archive regression suite now exercises malformed/empty ZIP input, excess members, traversal/absolute/backslash paths, duplicate names, symlinks, empty/oversized files, excessive compression ratios, and directory entries. These tests are meant to lock the parser's boundary behavior; they are not release proof until they pass on the exact new SHA.

A review also found that ingestion timestamps were already checked for finiteness, while terminal-decision timestamps only checked negativity. The ledger now rejects boolean, NaN, infinite, and negative decision timestamps too, keeping the decision-write validation contract consistent.


## Exact formatting failure and run-attempt race — 2026-10-18

Run [#39147354586](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39147354586) tested the PR merge ref containing branch head `d2a1e0c2a08e3a702ff9814eee408b3606e4ea37`. The first gate, `ruff format --check src tests`, failed at exactly four emitted diff locations: the reconciliation timestamp guard in `evidence_ledger.py`, two formatting groups in `phase_three.py`, and the parametrized trusted-workflow tests. Ruff lint, strict mypy, tests, and every coverage gate were skipped. These locations are now corrected according to the emitted diff; CI on the corrective commit remains the authority.

Reviewing rerun semantics also found a collection race: job-list APIs can represent the latest attempt while the original run payload still describes an earlier attempt. The service now re-reads the run after artifact validation and compares run ID, workflow ID, attempt, path, event, status, conclusion, and head SHA before final PR freshness validation. If any field changes, the evidence is discarded. The supported contract remains one workflow run and exactly one artifact; shards are not combined.

The upload step validator now rejects conditional upload steps as well as duplicate/missing uploaders, unpinned references, dynamic/wildcard paths, mismatched names, duplicate YAML keys, and missing-file warning modes. This is intentionally fail-closed. The workflow currently at the PR's base SHA lacks the required uploader and the repository does not yet have a deployed per-test manifest producer. This is recorded as a release/deployment prerequisite; the validator must not be weakened to conceal it.

The regression suite also adds checks for run-attempt changes, publication API failures preventing terminal ledger writes, and post-publication ledger persistence failures reporting `ledger_persisted=False`. These tests are part of the next full CI attempt and must not be called passed until that run proves it.


## Follow-up CI formatting failure — 2026-10-18

Run [#39149971965](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39149971965) tested the exact PR head `a2e4b5a49717b350a59d980bc659aea86a47adac` and failed `ruff format --check src tests`. Its actual output identified two files and four formatting adjustments: collapse the conditional-upload error constructor; collapse the workflow-run recheck call; collapse the parametrized trusted-workflow test signature; and remove an extra blank line. Ruff lint, strict mypy, tests, and coverage were skipped. These exact formatting changes are applied in the next commit. No test or coverage result is inferred from this run.


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


## Latest CI lint correction — 2026-10-23

Run [#39902428152](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39902428152) passed formatting and failed Ruff lint with one import-order issue in `src/verification_core/github_actions.py`: `import re` must precede `from collections.abc import Mapping`. Strict typing, tests, coverage gates, and the evidence job were skipped. Import order is corrected in this follow-up; it still requires a fresh full CI run.


## Coverage gate blocker and response — 2026-10-23

Run [#39907385124](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39907385124) passed formatting, Ruff, and strict mypy but failed the test command's total coverage threshold: **465 passed, 1 warning, 89.32% total (required 90%)**. Phase-specific coverage gates and the evidence producer were skipped after pytest returned nonzero. The newly added exact-head Actions run-discovery method introduced several defensive branches that lacked tests. Added parameterized API-boundary regressions for malformed totals, negative counts, malformed run collections, non-object items, invalid/duplicate run IDs, pagination-count changes, and missing page items. This is a targeted coverage increase, not a gate bypass; next exact-commit CI must pass all gates before counting progress.


## Exact-SHA CI, trusted producer, and artifact integrity verified — 2026-10-26

**Candidate SHA:** a5b09ac5a34d458e80b89d3b0d1bacc43b98b236  
**CI:** [run #40269457351](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40269457351), conclusion success on that exact SHA.

This resolves several earlier recurring blockers documented above: formatter failures, a strict-mypy issue in the new override-parameterized test, and the 90% overall coverage shortfall. The final quality run passed formatting, Ruff, strict mypy, 539 tests, 90.49% total coverage, 96% Phase I core coverage, and 86% Phase II integration coverage.

The same run's evidence job checked out the exact PR head, passed the per-test test run, exported the manifest, and uploaded the artifact. GitHub reported artifact ID 12627419483, size 42,805 bytes, and digest sha256:d9017cddb74aba35f5f5ddf4f0e04bb476c1127a7d4754201a72bb93d3848e62. I downloaded the artifact and verified that its byte digest matches the API digest, it contains exactly the two expected files, the JUnit and manifest each contain 539 unique matching test node IDs, all outcomes agree as passed, and the manifest head SHA equals the tested candidate. The exporter correctly sets all behavioral-assertion flags to false; it does not claim that line coverage proves assertion semantics.

**Correction to earlier deployment notes:** the current main/base policy trusts .github/workflows/ci.yml, and the workflow source retrieved from main includes the exact-PR-head checkout, per-test coverage/JUnit output, SHA-bound manifest export, and pinned artifact upload contract. Older notes saying this producer was absent from main are superseded by this direct inspection of the current base workflow/policy and successful exact-head producer run.

**Remaining boundary:** this verifies CI and artifact production and the repository's automated worker/service regression coverage. It does not constitute a deployment smoke test of the user's configured GitHub App installation, webhook ingress, database, and Check Run against a live target installation. Phase III should remain draft until that operational smoke test and human review are complete. V1 intentionally rejects ambiguous or multiple eligible runs; cross-run/rerun/shard aggregation is deferred rather than inferred.


## Latest exact-head confirmation — 2026-10-26

- Documentation-aligned branch head tested: d68aa02175f412600575e87b2d50e7afcd1198e8.
- Final workflow [#40269923540](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40269923540) completed successfully on that exact SHA; both quality and evidence jobs succeeded.
- Quality job: formatting, Ruff, strict mypy passed; 539 tests passed; overall coverage 90.49%, Phase I core 96%, Phase II integration 86%.
- Evidence artifact: verification-evidence, ID 12628125640, 42,639 bytes, GitHub SHA-256 sha256:669dda634a1b5d44a5ea9760a479c5314d982b112ee7a617832c69984fb99ffd.
- Downloaded ZIP SHA-256 independently matches the API digest. ZIP has exactly junit.xml and coverage-manifest.json. Both inventories contain 539 unique matching IDs, all passing outcomes, zero duplicate IDs, and manifest head SHA d68aa02175f412600575e87b2d50e7afcd1198e8. Structural validation found no unsafe path/line/branch entries; assertion flags are all false.
- Remaining acceptance is deployment-specific: exercise the target installed GitHub App, webhook-to-worker path, evidence database, and Check Run publication; then complete human review. No live deployment smoke test was run in this environment.

The previous 95% milestone on a5b09ac remains valid for that implementation checkpoint. The documentation-aligned head d68aa02 was subsequently tested end-to-end with both CI jobs green; use run #40269923540 and artifact 12628125640 as the latest verification anchor. The outstanding deployment-specific smoke test is not achievable without the target installation/configuration and has not been claimed.


## Final close-out verification — 2026-10-26

Branch head `5658106e6ef03f6e46e8f5dfefad38056aaebccd` passed [CI run #40270614782](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40270614782) on the exact same SHA. Both the quality and evidence-producer jobs succeeded. Formatting, Ruff, strict mypy, 539 tests, 90.49% overall coverage, 96% Phase I core coverage, and 86% Phase II integration coverage all passed.

The new uploaded artifact `12628146952` has GitHub-reported digest `sha256:c508f72a6c3faed815d881da2627608c8f82bf78368c9b39e2d1a96e70d5e572` and size 42,823 bytes. Independently downloaded bytes match that digest. The ZIP has exactly `junit.xml` and `coverage-manifest.json`; each contains 539 unique matching IDs, all outcomes pass, and the manifest's head SHA equals `5658106e6ef03f6e46e8f5dfefad38056aaebccd`. Structural checks found no unsafe path/line/branch entries. Exported assertion flags remain false by design: line/branch coverage is not treated as semantic assertion verification.

The exact-head check resolves the final repository-CI blocker. The only declared remaining release prerequisite is operational: smoke-test the real installed GitHub App, webhook-to-worker path, configured evidence database, and Check Run publication in the target deployment, then complete human review. Those external environment steps were not executed here; PR #6 remains draft until done.


## Final close-out SHA green — 2026-10-26

Candidate `e736fc3f92529169f4a8396afed75166dcb00263` passed [CI run #40270996414](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40270996414) with conclusion success. Both quality and exact-head evidence jobs succeeded. Quality gates: formatting, Ruff, strict mypy, 539 passing tests, 90.49% total coverage, 96% Phase I, 86% Phase II. Artifact `12628870686` (42,658 bytes) digest `308f3de9cc21fc1dda080f8ee8c99ce95b23a222884eaacc70727c989e6cff00`; its downloaded ZIP hash independently matches GitHub metadata. Exact contents are `junit.xml` and `coverage-manifest.json`, both with 539 unique matching IDs, every outcome passing, manifest SHA bound to the candidate, no structural anomalies, and all semantic assertion flags false. Repository implementation/CI is complete; target-deployment smoke test and human review remain external release prerequisites.


## Deterministic idempotent-replay fixture fix passed — 2026-10-26

The exact-head producer job in run 40271256105 failed 1 test (538 passed): `test_phase_three_service_persists_evidence_as_inconclusive_and_idempotently`. The production ledger raised its intended `EvidenceLedgerConflict` because ZIP archives constructed by the shared test helper included variable ZIP entry timestamps; repeated logical fixtures could therefore have different content digests. Fix commit `61811292a9a87282b04758cbb3e4ecfa46160cb6` pins ZIP entry timestamps to `(2020, 1, 1, 0, 0, 0)` and explicitly sets ZIP_DEFLATED at the test-helper boundary. Production identity checks and conflict semantics were untouched.

[CI run #40271529641](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40271529641) passed both jobs on the exact fixed SHA. 539 tests passed; 90.49% overall coverage, 96% Phase I core coverage, 86% Phase II integration coverage. Artifact `12628348250` (42,840 bytes, SHA-256 `bbf8a7d24ecaf32d46faf163b3e6446d96dc1d99608309d9ac584bda4ee1e0d4`) was downloaded and independently verified. It contains exactly `junit.xml` and `coverage-manifest.json`; both have 539 unique matching test IDs, every outcome passed, manifest head SHA equals the tested SHA, no unsafe paths or invalid line/branch entries were found, and all behavioral assertion flags remain false.

This resolves the repository's current code/CI blockers. A live target deployment smoke test and human review remain external release prerequisites and have not been claimed.


## Deterministic replay fixture and final exact-head CI verified — 2026-10-26

Final exact head `0a15bab79bc285f3da80eb79e529ee8cea91a615` passed [CI run #40272532304](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40272532304); both jobs passed. The quality job reports 539 passing tests, total coverage 90.49%, Phase I core 96%, Phase II integration 86%, formatting, Ruff, and strict mypy all green. The exact-PR-head producer generated and uploaded artifact `12628423276` (42,796 bytes, SHA-256 `9e22995baff947d32a6c8d2908bdc518513cd927bd2ec2e2601e9df764d66610`).

I downloaded that ZIP and independently verified its byte digest against GitHub's API. Contents are exactly `junit.xml` and `coverage-manifest.json`; each has 539 unique IDs, their ID sets and outcomes match, all outcomes are passed, and manifest head equals `0a15bab79bc285f3da80eb79e529ee8cea91a615`. No unsafe paths or invalid line/branch entries were found; every `behavioral_assertion_verified` field remains false.

The immediately previous CI failure was caused by the shared test ZIP helper using variable timestamps. The fix pins ZIP timestamps and compression in the test helper only. The production ledger's immutable replay-conflict checks are unchanged.

Remaining release boundary: the repository's actual target deployment must be smoke-tested using the installed GitHub App, its `actions:read` permission, webhook ingress, worker, configured evidence database, and Check Run publication. That environment is not configured through the connected GitHub API tool, and there are no human review submissions yet; do not claim production acceptance or merge PR #6 until these are satisfied.
