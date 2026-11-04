# AI PR Verification Agent

Evidence-backed verification for pull requests — not another generic AI code reviewer.

The system answers: what behavior could change, which obligations follow from that risk, what evidence exists for the exact commit, and what remains unverified or explicitly accepted by a human.

**Core safety rule: no evidence, no machine-verified pass.** A model may propose risk hypotheses, but it cannot mark an obligation as passed or decide the final conclusion.

## Current status

Phase I and Phase II provide the deterministic domain core, strict policy validation, bounded evidence parsing, authenticated GitHub App transport, durable delivery/run ledgers, webhook ingress, planning, and deterministic Check Run publication. Phase III implementation and exact-head CI/evidence production are on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6); the live deployment smoke test remains unperformed because target deployment configuration is not available through the repository integration. Human review is deferred to Phase IV. Do not enable production merge gating before both gates pass.

Phase IV is on branch phase-4-opt-in-dispatch and draft PR [#9](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/9). It now includes guarded workflow dispatch, explicit per-workflow schemas, GitHub operator allowlisting and repository permission checks, SQLAlchemy write-ahead audit, one-shot dispatch coordination, and workflow-run exact-SHA reconciliation. Exact-head CI on `15245242e967d1fdb6e912c8686446f5188795e5` passed [run #41805099119](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41805099119): 406 tests, 90% overall coverage, Phase I core 96%, Phase II integration 86%; format, Ruff, strict mypy, and all configured coverage gates passed. The focused governance workflow also passed 43 tests. Evidence artifact 13309248666 (32,239 bytes; SHA-256 `78166497cc7a77d7caacd44ab89282136197240b351905d02f9c7a4b2b0643f4`) was downloaded and independently checked: ZIP contains junit.xml and coverage-manifest.json; 406 matching testcases, zero failures/errors/skips; manifest is bound to exact SHA `15245242e967d1fdb6e912c8686446f5188795e5`. All behavioral_assertion_verified flags are false, so this is test/coverage evidence, not independent proof of behavior. No real workflow was dispatched. PR #9 remains draft. Phase III integration/deployment smoke acceptance and human review remain open; no production merge gating is enabled.

## Security principles

- Integrity is not authenticity. Hashes detect changes; they do not prove who generated a report.
- Platform workflow, job, step, and artifact metadata must be verified out-of-band through GitHub's API.
- Coverage is a negative filter, not behavioral proof. Happy-path line hits do not prove negative or boundary behavior.
- Untrusted PR code, artifact fields, and LLM output are data, never authority.
- Human approvals and policy waivers are distinct from machine proof.
- Missing, malformed, stale, or weak evidence for critical/high-risk obligations must never become success or neutral.
- The Phase I core requires no GitHub permissions and makes no network calls.

## Development

Requires Python 3.12+.

    python -m pip install -e ".[dev]"
    ruff format --check src tests
    ruff check src tests
    mypy --strict src tests
    pytest --cov=src/verification_core --cov-report=term-missing --cov-report=xml

CI runs formatting, lint, strict typing, and tests with a 90% overall coverage floor, a 95% Phase I core coverage gate, and an 80% Phase II integration coverage gate.

## Roadmap

| Phase | Goal | Status |
| --- | --- | --- |
| 1A | Deterministic domain models and state machine | Implemented |
| 1B | Policy validator, runner allowlist, evidence parsers, ledger, adversarial scenarios | Implemented |
| 2 | Diff analysis, planning, persistence, webhook and Check Run service | Implemented; release review pending |
| 3 | Platform-anchored passive CI artifact ingestion and reconciliation | Implementation and exact-head CI/evidence production verified on draft PR #6; live deployment smoke test pending |
| 4 | Opt-in dispatch, additional adapters, human governance hooks | Guarded dispatch plus explicit workflow input schemas; orchestration, operator audit, staging validation, human review, and live Phase III smoke acceptance remain |

See docs/phase-4-opt-in-dispatch.md and docs/verification-semantics.md.
