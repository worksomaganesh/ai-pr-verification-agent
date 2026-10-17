# AI PR Verification Agent

Evidence-backed verification for pull requests — not another generic AI code reviewer.

The system is designed to answer:
1. What behavior could this change affect?
2. Which verification obligations follow from that risk?
3. What evidence was actually produced for the exact commit?
4. What remains unverified, weakly evidenced, or explicitly accepted by a human?

**Core safety rule: no evidence, no machine-verified pass.** A model may propose risk hypotheses, but it cannot mark an obligation as passed or decide the final conclusion.

## Current status

Phase 1A (deterministic domain core) is complete: immutable domain records, explicit obligation states, guarded transitions, deterministic Check Run conclusion evaluation, unit tests, and a Hypothesis false-green invariant test configured for 5,000 generated examples. CI validates formatting, lint, strict typing, tests, and a 95% minimum coverage threshold.

The full Phase 1 milestone is still in progress. Policy parsing and fixed runner profiles, safe JUnit ingestion, per-test coverage reconciliation, secret scrubbing, deterministic ledger rendering, adversarial parser fixtures, and the standalone running-scenario fixture remain Phase 1B work. Do not represent Phase 1A completion as completion of the full product.

## Security principles

- Integrity is not authenticity. Hashes detect changes; they do not prove who generated a report.
- Platform workflow, job, step, artifact, and commit metadata must be verified out-of-band through GitHub's API.
- Coverage is a negative filter, not behavioral proof. Happy-path line hits do not prove negative or boundary behavior.
- Untrusted PR code, artifact fields, and LLM output are data, never authority.
- Human approvals and policy waivers are distinct from machine-verified results.
- Missing, malformed, stale, or weak evidence for critical/high-risk obligations must never become success or neutral.
- The local core needs no GitHub permissions; passive CI consumption is the intended default integration model.

## Development

Requires Python 3.12+.

    python -m pip install -e ".[dev]"
    ruff format --check src tests
    ruff check src tests
    mypy --strict src tests
    pytest --cov=src/verification_core --cov-report=term-missing

CI runs these gates on pushes to main and pull requests targeting main.

## Roadmap

| Phase | Goal | Status |
| --- | --- | --- |
| 1A | Deterministic domain models and state machine | Complete; CI green, 5,000-example property test, ≥95% coverage |
| 1B | Policy validator, runner allowlist, evidence parsers, ledger, adversarial scenario | Next; not complete |
| 2 | Diff analysis, planning, persistence, webhook and Check Run service | Not started |
| 3 | Platform-anchored passive CI artifact ingestion and reconciliation | Not started |
| 4 | Opt-in dispatch, additional adapters, human governance hooks | Not started |

See docs/verification-semantics.md for the current state-machine contract and docs/phase-0-architecture.md for trust boundaries and design constraints.
