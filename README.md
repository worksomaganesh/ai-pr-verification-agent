# AI PR Verification Agent

**Evidence-backed pull request verification — not another generic AI code reviewer.**

The agent evaluates what behavior could change in a pull request, derives verification obligations from trusted policy, checks evidence tied to the exact commit, and reports what is verified, unresolved, or explicitly accepted by a human.

> **Core safety rule: no evidence, no machine-verified pass.** An AI model may propose risk hypotheses and verification plans. It cannot independently mark an obligation as passed or decide the final conclusion.

## Current project status

<details>
<summary><strong>Latest integrated verification: passed</strong> — 4 November 2026</summary>

The integrated Phase III + Phase IV feature branch has completed its combined CI and exact-PR-head evidence workflow successfully.

| Verification | Result | Required |
| --- | ---: | ---: |
| Tests | **643 passed** | All pass |
| Overall coverage | **90.01%** | 90.00% |
| Phase I core coverage | **96.39%** | 95.00% |
| Phase II integration coverage | **85.99%** | 80.00% |
| Formatting | Passed | Pass |
| Ruff lint | Passed | Pass |
| Strict mypy | Passed | Pass |
| Evidence producer | Passed | Pass |

- Integrated branch: `phase-4-opt-in-dispatch`
- Exact verified head: `38d0c2bd4403dd0767d8d5705d87d5aa98b03026`
- Combined CI: [run #41816301952](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41816301952)
- Focused Phase IV governance CI: [run #41816301946](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41816301946)
- Phase III + IV integration: Phase III is included through the two-parent merge commit `8a17bd22abcfdea02111f7fa7768c5ba9b4c29a1`.

The exact-head evidence artifact was uploaded by the same successful full CI run:

| Artifact field | Verified value |
| --- | --- |
| Name | `verification-evidence` |
| Artifact ID | `13315116157` |
| Size | 46,919 bytes |
| SHA-256 | `b19e98d7264360a4af036a457fa84a4e351c873ece5ba8ad76bffa3412d1c964` |
| Archive members | `junit.xml`, `coverage-manifest.json` |
| JUnit inventory | 643 tests; 0 failures, 0 errors, 0 skips |
| Manifest inventory | 643 unique test entries; all outcomes passed |
| Manifest commit binding | Exact head `38d0c2bd4403dd0767d8d5705d87d5aa98b03026` |

The ZIP digest was independently recomputed and matched the GitHub artifact API digest. The JUnit and coverage-manifest inventories were inspected. Every `behavioral_assertion_verified` value in the manifest is `false`: the artifact proves test execution and measured coverage, **not that the tests' assertions establish every required behavior**.

</details>

### Release and deployment status

The repository-level integrated implementation is CI-verified on the feature branch. It is **not yet production/release accepted**:

- Phase III live deployment smoke test has not been run against the target deployment.
- Phase IV has not dispatched a real workflow; dispatch tests use mocked GitHub APIs.
- A staging-only authenticated operator entry point, deployment-specific operator policy, managed PostgreSQL configuration, installed App credentials, webhook/worker deployment, and live end-to-end validation remain operational work.
- Human review and release approval remain outstanding.
- Both [PR #6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6) and [PR #9](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/9) remain open and draft. The Phase III and Phase IV code is integrated on the Phase IV feature branch, but that does not mean either PR has been merged into `main`.

Keep production merge gating disabled until the staging smoke test and human review are complete.

## Architecture and phase status

| Phase | Responsibility | Current status |
| --- | --- | --- |
| **Phase I — deterministic core** | Domain models, verification state machine, policy validation, evidence parsers, obligation semantics, and adversarial scenarios | Implemented; core coverage gate passes at 96.39% |
| **Phase II — PR verification service** | GitHub App integration, diff/planning flow, persistence, webhook ingress, delivery/run ledgers, and deterministic Check Run publication | Implemented; integration coverage gate passes at 85.99% |
| **Phase III — authenticated evidence ingestion** | Authenticated GitHub Actions run/job/artifact retrieval, digest and archive validation, JUnit/coverage-manifest binding, durable evidence ledger, obligation reconciliation, and freshness-checked Check Runs | Integrated into the Phase IV branch; combined exact-head CI and evidence production pass; live deployment smoke test remains |
| **Phase IV — guarded dispatch and human governance** | Explicitly enabled workflow dispatch, strict workflow/input allowlists, operator authorization, write-ahead audit, duplicate protection, exact-SHA run reconciliation, and governance foundations | Implementation and integrated CI pass; real staging dispatch, deployment wiring, human review, and release acceptance remain |

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
