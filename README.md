# AI PR Verification Agent

Evidence-backed verification for pull requests — not another generic AI code reviewer.

The system answers: what behavior could change, which obligations follow from that risk, what evidence exists for the exact commit, and what remains unverified or explicitly accepted by a human.

**Core safety rule: no evidence, no machine-verified pass.** A model may propose risk hypotheses, but it cannot mark an obligation as passed or decide the final conclusion.

## Current status

Phase 1A's deterministic domain core is implemented: immutable domain records, explicit obligation states, guarded transitions, deterministic Check Run conclusion evaluation, and a 5,000-example Hypothesis false-green invariant test.

Phase 1B implementation now includes:
- strict policy YAML validation with duplicate-key, alias/anchor, merge-key, unknown-field, path, severity, and selector rejection;
- verifier-owned fixed argv runner profiles (no user-supplied shell commands);
- bounded JUnit XML parsing with DTD/entity protection, size/count limits, and aggregate reconciliation;
- deterministic evidence sufficiency filters for malformed, contradictory, coverage-miss, weak, and sufficient evidence;
- common secret scrubbing and stable Markdown evidence-ledger rendering;
- an adversarial scenario proving 140 unrelated passing tests cannot hide missing critical webhook-idempotency and cross-user-authorization obligations.

**Phase 1 release gate: passed on the validated release-hardening tree.** GitHub Actions passed formatting, Ruff lint, strict mypy, and **167 tests with 97.30% coverage** (95% minimum). The CI-hardening changes are merged to `main` via [PR #1](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/1). This validates the zero-infrastructure Phase 1 core; it does not claim Phase 2 GitHub API integration or production deployment is complete. Callers must obtain workflow/job/step/artifact/head-SHA metadata out-of-band from GitHub's control plane and load policy from the trusted base commit.

## Security principles

- Integrity is not authenticity. Hashes detect changes; they do not prove who generated a report.
- Platform workflow, job, step, artifact, and commit metadata must be verified out-of-band through GitHub's API.
- Coverage is a negative filter, not behavioral proof. Happy-path line hits do not prove negative or boundary behavior.
- Untrusted PR code, artifact fields, and LLM output are data, never authority.
- Human approvals and policy waivers are distinct from machine-verified results.
- Missing, malformed, stale, or weak evidence for critical/high-risk obligations must never become success or neutral.
- The Phase 1 core requires no GitHub permissions and makes no network calls.

## Development

Requires Python 3.12+.

    python -m pip install -e ".[dev]"
    ruff format --check src tests
    ruff check src tests
    mypy --strict src tests
    pytest --cov=src/verification_core --cov-report=term-missing --cov-report=xml

CI runs formatting, lint, strict typing, and tests with a 95% coverage floor.

## Roadmap

| Phase | Goal | Status |
| --- | --- | --- |
| 1A | Deterministic domain models and state machine | Implemented; previously green with 5,000-example property test |
| 1B | Policy validator, runner allowlist, evidence parsers, ledger, adversarial scenario | Implementation committed; release gate awaiting exact-commit CI verification |
| 2 | Diff analysis, planning, persistence, webhook and Check Run service | Not started |
| 3 | Platform-anchored passive CI artifact ingestion and reconciliation | Not started |
| 4 | Opt-in dispatch, additional adapters, human governance hooks | Not started |

See [docs/verification-semantics.md](docs/verification-semantics.md), [docs/phase-0-architecture.md](docs/phase-0-architecture.md), and [docs/phase-1-release-gate.md](docs/phase-1-release-gate.md).
