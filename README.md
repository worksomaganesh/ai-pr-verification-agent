# AI PR Verification Agent

**Evidence-backed pull request verification — not another generic AI code reviewer.**

The agent evaluates what behavior could change in a pull request, derives verification obligations from trusted policy, checks evidence tied to the exact commit, and reports what is verified, unresolved, or explicitly accepted by a human.

> **Core safety rule: no evidence, no machine-verified pass.** An AI model may propose risk hypotheses and verification plans. It cannot independently mark an obligation as passed or decide the final conclusion.

## Current project status

<details>
<summary><strong>Latest integrated verification: passed</strong> — 4 November 2026</summary>

The previous integrated source checkpoint `851d94369cccb17c0fce2bb084332afaa097f656` on `phase-4-opt-in-dispatch` (PR #9) passed exact-head CI on 5 November 2026. The latest audit-ID remediation source commit is `a898506fef046b453d3a04d14b03a5772138600e`; its new CI verification is pending.

| Verification | Result | Required |
| --- | ---: | ---: |
| Tests | **710 passed** (1 non-blocking warning) | All pass |
| Overall coverage | **90.28%** | 90.00% |
| Phase I core coverage | **96.39%** | 95.00% |
| Phase II integration coverage | **85.99%** | 80.00% |
| Ruff formatting | Passed | Pass |
| Ruff lint | Passed | Pass |
| Strict mypy | Passed | Pass |
| Exact-head evidence producer | Passed | Pass |
| Phase IV governance suite | Passed | Pass |

- Full CI run [#42065231885](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42065231885) passed on previous exact head `851d94369cccb17c0fce2bb084332afaa097f656`; both quality and evidence jobs succeeded.
- Focused Phase IV governance run [#42065232420](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42065232420) passed on that same SHA.
- Evidence artifact for the previous checkpoint `verification-evidence`, ID `13433002745`, has GitHub SHA-256 `f548ab23efc090fc32d5be21da697da8b486129f8735d8a0f64bf85bcda74520`; its downloaded ZIP digest matched. The artifact was bound to the then-current exact head. All `behavioral_assertion_verified` flags were false: this proves test execution/coverage and exact-head binding, not semantic adequacy of every assertion.
- The staging `workflow_dispatch` workflow is registered on `main` in commit [`59b3610`](https://github.com/worksomaganesh/ai-pr-verification-agent/commit/59b361012e47f5c62db6d508a87b040f1297a623), and exists on the Phase IV branch. This registers the workflow but does not mean it has been dispatched.
- On 7 November 2026, operator run [#42365086398](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/42365086398) passed authentication, exact-SHA checkout, installation, and dispatch. GitHub accepted one staging dispatch, but reconciliation failed when PostgreSQL rejected the 32-bit `workflow_run_id` column (`integer out of range`). The dispatch is not counted as accepted staging completion; the child run's final outcome/SHA still needs independent confirmation.
- The remediation changes `workflow_run_id` and GitHub human `review_id` fields to 64-bit `BIGINT`, with PostgreSQL widening migrations and regression tests. Latest source fix commit: [`a898506`](https://github.com/worksomaganesh/ai-pr-verification-agent/commit/a898506fef046b453d3a04d14b03a5772138600e). Fresh exact-head CI is pending.
- Phase III source integration remains present in the Phase IV branch through merge commit `8a17bd22abcfdea02111f7fa7768c5ba9b4c29a1`.


</details>

### Release and deployment status

The integrated implementation is **CI-verified on the exact current feature-branch head**, but operational/release acceptance is not complete:

- One owner-authorized Phase IV staging dispatch was accepted by GitHub, but audit reconciliation failed due the PostgreSQL 32-bit run-ID column. A corrected 64-bit schema is now committed; a successful fresh dispatch/reconciliation is still outstanding.
- The repository owner has configured the `staging` Environment secret `PHASE4_GITHUB_TOKEN`. The secret value is not stored in source. The old failed operator job must not be blindly rerun because its dispatch step would issue another external dispatch.
- No live Phase III deployment smoke test has been run against an installed GitHub App, webhook ingress/worker, durable evidence database, and Check Run publication.
- Human review and release approval remain outstanding. PR #9 remains open and draft; PR #6 also remains open/draft as a historical review surface, even though its code is integrated into PR #9's branch lineage.
- The Phase IV staging workflow is a bounded dispatch-correlation/exact-SHA check. It is not itself a deployment of the application or a substitute for the Phase III smoke test.


Keep production merge gating disabled until the staging smoke test and human review are complete.

## Architecture and phase status

| Phase | Responsibility | Current status |
| --- | --- | --- |
| **Phase I — deterministic core** | Domain models, verification state machine, policy validation, evidence parsers, obligation semantics, and adversarial scenarios | Implemented; core coverage gate passes at 96.39% |
| **Phase II — PR verification service** | GitHub App integration, diff/planning flow, persistence, webhook ingress, delivery/run ledgers, and deterministic Check Run publication | Implemented; integration coverage gate passes at 85.99% |
| **Phase III — authenticated evidence ingestion** | Authenticated GitHub Actions run/job/artifact retrieval, digest and archive validation, JUnit/coverage-manifest binding, durable evidence ledger, obligation reconciliation, and freshness-checked Check Runs | Integrated into the Phase IV branch; combined exact-head CI and evidence production pass; live deployment smoke test remains |
| **Phase IV — guarded dispatch and human governance** | Explicitly enabled workflow dispatch, strict workflow/input allowlists, operator authorization, write-ahead audit, duplicate protection, exact-SHA run reconciliation, and governance foundations | Implementation and exact-head CI pass; live operator dispatch/reconciliation and faculty/release review remain |

### Phase I — deterministic verification core

The core defines the obligations, evidence requirements, policy rules, and state transitions that determine whether a change can be considered verified. It does not require GitHub permissions and makes no network calls.

The core is deliberately conservative: missing evidence for critical or high-risk obligations cannot become success or neutral merely because other checks passed.

### Phase II — pull request verification service

The service connects the deterministic core to GitHub. It handles pull request context, planning, durable processing state, webhook delivery, and Check Run publication.

The current reference delivery queue uses SQLite for a single-host deployment. Horizontally scaled ingress/worker deployment requires a shared queue backend. The Phase II integration coverage group is independently enforced at 80%.

### Phase III — authenticated evidence ingestion

Phase III treats the GitHub Actions API as the source of platform provenance. Webhook payloads and downloaded artifact contents are untrusted until independently checked.

The ingestion path:
1. Selects a completed successful workflow run for the expected repository, pull request, base SHA, and exact head SHA.
2. Validates the trusted base-branch workflow contract before accepting evidence.
3. Retrieves run, job, and artifact metadata through authenticated GitHub API calls.
4. Checks the artifact's API-reported SHA-256 digest against the downloaded ZIP bytes.
5. Enforces archive size, member count, path, file-type, duplicate, and compression limits.
6. Parses JUnit and the per-test coverage manifest, requiring matching test inventories/outcomes and exact commit binding.
7. Rechecks run and pull-request freshness before persisting or publishing a result.
8. Records evidence durably, reconciles obligations deterministically, and publishes a freshness-checked Check Run.

The per-test exporter intentionally sets `behavioral_assertion_verified: false`. Coverage and test execution are not substitutes for independently trusted assertion semantics.

Phase III runtime integration is opt-in. The live deployment smoke test still needs the installed App credentials, webhook secret, worker configuration, and evidence database used by the target deployment. See [Phase III deployment and trust-chain notes](docs/phase-3-evidence-ingestion.md).

### Phase IV — guarded dispatch and human governance

Phase IV adds a controlled way for an authorized operator to request a workflow dispatch without granting arbitrary workflow execution.

The current implementation includes:
- A dispatcher that is disabled unless explicitly enabled by its caller.
- Exact workflow filename allowlists and a schema for every allowlisted workflow.
- Required-field, pattern, enumeration, length, count, and control-character validation.
- Rejection of credential-like input names and unsafe repository/ref values.
- Sanitized GitHub API and transport errors.
- GitHub operator identity allowlisting and repository permission checks.
- A SQLAlchemy write-ahead dispatch audit and duplicate-dispatch protection.
- A one-shot dispatch coordinator and exact-SHA workflow-run reconciliation.
- Fail-closed handling for malformed, incomplete, over-limit, ambiguous, or incorrectly correlated workflow-run responses.
- Durable distinction between rejected, unknown, submitted-unreconciled, reconciled, and mismatched outcomes.
- Exact-head GitHub review verification with a configured reviewer allowlist, latest-review semantics, rationale checks, same-repository/open-PR checks, pagination/response limits, and fail-closed API handling.
- Append-only SQLAlchemy human-review audit records with rationale digests, replay idempotency, and conflicting review-ID detection.
- An adapter that binds verified review repository, PR number, base SHA, and head SHA to the evaluated commit, then applies the existing domain state-machine severity/transition policy and persists the audit before returning the approved obligation.

A successful dispatch is **not** evidence of successful verification. The resulting workflow must still pass the Phase III provenance, artifact, freshness, and obligation-reconciliation checks. The current dispatcher has mocked API tests; it has not been used to dispatch a real workflow. The staging operator entry point and deployment-specific governance policy remain to be wired and exercised.

See [Phase IV dispatch and governance notes](docs/phase-4-opt-in-dispatch.md).

## Security and verification principles

- **Integrity is not authenticity.** A matching hash establishes byte integrity; authenticated platform metadata establishes provenance.
- **Exact commit binding matters.** Evidence from a different, stale, or ambiguous head cannot verify the current pull request.
- **Coverage is not behavioral proof.** Line and branch execution show what ran, not whether assertions adequately prove the required behavior.
- **Untrusted data has no authority.** Pull request code, artifact fields, webhook payloads, and LLM output are treated as data, not instructions or policy.
- **Models do not decide outcomes.** Models may help propose risks and plans; deterministic policy and state transitions decide machine-verification status.
- **Human approval is separate.** Reviews, waivers, and policy exceptions must be attributed and bound to the exact commit.
- **Fail closed.** Missing, malformed, stale, contradictory, ambiguous, untrusted, or weak evidence for critical/high-risk obligations must not become success or neutral.
- **Least privilege.** Phase I needs no GitHub permissions. Read and write capabilities are separated; dispatch is explicitly opt-in and should use staging-only credentials during acceptance.

## Development

Requires Python 3.12 or later.

Install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the same quality checks used by the combined CI workflow:

```bash
ruff format --check src tests scripts
ruff check src tests scripts
mypy --strict src tests scripts
pytest --cov=src/verification_core --cov-report=term-missing --cov-report=xml
coverage report --fail-under=90
```

The CI workflow also enforces separate coverage gates:

- Phase I core: at least 95%.
- Phase II integration: at least 80%.
- Overall project: at least 90.00%.

Coverage reporting uses two-decimal precision so values below the configured threshold cannot appear to pass through integer rounding. Do not lower a threshold or exclude production code merely to make a failing report green.

## Remaining acceptance work

1. Deploy the integrated worker/webhook path to a staging environment with the installed GitHub App, least-privilege permissions, webhook secret, and shared evidence database configured.
2. Run `scripts/phase3_deployment_smoke.py` against a staging pull request and record the result without recording credentials or secrets.
3. Wire a deliberately authenticated, staging-only Phase IV operator entry point and managed PostgreSQL audit storage.
4. Dispatch a non-production workflow, verify the exact run identity and commit SHA, and follow it through Phase III evidence ingestion and deterministic reconciliation.
5. Verify that stale heads, duplicate requests, ambiguous run results, provider timeouts, and human approvals cannot bypass the audit or evidence rules.
6. Complete human review and release approval for the integrated branch.
7. Merge the reviewed work into `main` only after operational acceptance; keep production merge gating disabled until then.

## Repository references

- [Phase III evidence-ingestion design](docs/phase-3-evidence-ingestion.md)
- [Phase IV opt-in dispatch and governance design](docs/phase-4-opt-in-dispatch.md)
- [Verification semantics](docs/verification-semantics.md)
- [Current engineering status and CI investigation](log/current-status.md)
- [Phase IV CI commit-by-commit journal](log/phase-4-ci-journey-2026-11-04.md)
- [Combined CI run #41816301952](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41816301952)
- [Phase IV governance CI run #41816301946](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41816301946)
