# AI PR Verification Agent

Evidence-backed verification for pull requests — not another generic AI code reviewer.

The system answers: what behavior could change, which obligations follow from that risk, what evidence exists for the exact commit, and what remains unverified or explicitly accepted by a human.

**Core safety rule: no evidence, no machine-verified pass.** A model may propose risk hypotheses, but it cannot mark an obligation as passed or decide the final conclusion.

## Current status

Phase I and Phase II provide the deterministic domain core, strict policy validation, bounded evidence parsing, authenticated GitHub App transport, durable delivery/run ledgers, webhook ingress, planning, and deterministic Check Run publication. The Phase II reference deployment still uses a single-host SQLite delivery queue; horizontally scaled ingress/worker deployment requires a shared queue backend.

### Phase III — authenticated evidence ingestion

The Phase III implementation is on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), branch `phase-3-evidence-ingestion`. Its current branch head is `9611cbc6504f3844770540c9d45f87864bdfae08`; exact-head workflow run [#40465327360](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40465327360) completed successfully on that SHA, including the quality and evidence-producer jobs. The code-bearing checkpoint `64700d7ed575296e6874a185938ef585e0f7c5de` previously passed [run #40464702014](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40464702014) with 547 tests, 90.49% overall coverage, 96% Phase I core coverage, and 86% Phase II integration coverage. Its evidence artifact `12716496067` was independently checked against GitHub's SHA-256 digest `b71ff7c4f65a3c4b2e248a293d7ac5aa9c1872104e080ef3b767e7df033c299b`; the JUnit and manifest inventories matched, were bound to the exact head, and did not claim behavioral assertions were proven.

Phase III adds authenticated Actions run/job/artifact retrieval, bounded archive and JUnit/coverage validation, a durable evidence ledger, deterministic obligation reconciliation, and freshness-checked Check Run publication. The enabled worker path is opt-in. **The live deployment smoke test has not been performed** because the target URL, installed App credentials, webhook secret, and worker database configuration are not available through this repository integration. Keep PR #6 draft until that operational gate and review are complete.

### Phase IV — guarded dispatch and human governance

Phase IV is developed on branch `phase-4-opt-in-dispatch` and draft PR [#9](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/9). It now includes a disabled-by-default workflow dispatcher, exact workflow allowlists, per-workflow input schemas, credential-like input rejection, GitHub operator login allowlisting and repository permission checks, SQLAlchemy write-ahead audit, duplicate-dispatch protection, one-shot dispatch coordination, and exact-SHA workflow-run reconciliation.

The verifier now rejects incomplete or over-limit run-list responses and malformed run entries instead of silently ignoring them. On pre-integration head `44a98059632ba07f262c8772ef18bbfee8ad494c`, full CI [#41811759527](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41811759527) and focused governance CI [#41811759410](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41811759410) passed. The full suite reported 409 passing tests; its detailed overall coverage was 89.82% (the current integer-rounded gate displayed 90%), Phase I core coverage 96%, and Phase II integration coverage 86%. **The overall coverage threshold is being tightened to enforce a true 90.00% minimum rather than relying on rounded reporting.** Exact-head artifact `13311839944` (32,424 bytes; SHA-256 `e55d439f6ed8d411d62c86adf581e9a0de434ad5adf8f645db7c5cbfef715aa4`) was uploaded by the exact-PR-head evidence job.

No real workflow has been dispatched. The coordinator is not yet wired to a staging-only authenticated operator entry point with managed PostgreSQL and deployment-specific operator policy. Phase III has now been integrated into this Phase IV feature branch as a two-parent feature-branch merge; combined-head CI is required before the integrated tree is treated as verified. Do not enable production merge gating. Keep both PRs draft while operational smoke acceptance and human review remain open.

## Security principles

- Integrity is not authenticity. Hashes detect changes; they do not prove who generated a report.
- Platform workflow, job, step, artifact, and commit metadata must be verified out-of-band through GitHub's API.
- Coverage is a negative filter, not behavioral proof. Happy-path line hits do not prove negative or boundary behavior.
- Untrusted PR code, artifact fields, and LLM output are data, never authority.
- Human approvals and policy waivers are distinct from machine-verified results.
- Missing, malformed, stale, ambiguous, or weak evidence for critical/high-risk obligations must never become success or neutral.
- The Phase I core requires no GitHub permissions and makes no network calls.

## Development

Requires Python 3.12+.

    python -m pip install -e ".[dev]"
    ruff format --check src tests
    ruff check src tests
    mypy --strict src tests
    pytest --cov=src/verification_core --cov-report=term-missing --cov-report=xml
    coverage report --fail-under=90

The intended gates are formatting, Ruff, strict mypy, the full test suite, 90% overall coverage, 95% Phase I core coverage, and 80% Phase II integration coverage. The overall coverage report must use sufficient precision so a value below 90.00% cannot round up and pass.

## Roadmap

| Phase | Goal | Status |
| --- | --- | --- |
| 1A | Deterministic domain models and state machine | Implemented |
| 1B | Policy validator, runner allowlist, evidence parsers, ledger, adversarial scenarios | Implemented |
| 2 | Diff analysis, planning, persistence, webhook and Check Run service | Implemented; release review pending |
| 3 | Platform-anchored passive CI artifact ingestion and reconciliation | Implementation and exact-head CI/evidence production verified on PR #6; live deployment smoke test pending |
| 4 | Opt-in dispatch, additional adapters, human governance hooks | Guarded dispatch and audit/reconciliation implementation; staging entry point, full integration validation, live smoke test, and human review remain |

See `docs/phase-3-evidence-ingestion.md`, `docs/phase-4-opt-in-dispatch.md`, and `docs/verification-semantics.md`.
