# AI PR Verification Agent

Evidence-backed verification for pull requests — not another generic AI code reviewer.

The system answers: what behavior could change, which obligations follow from that risk, what evidence exists for the exact commit, and what remains unverified or explicitly accepted by a human.

**Core safety rule: no evidence, no machine-verified pass.** A model may propose risk hypotheses, but it cannot mark an obligation as passed or decide the final conclusion.

## Current status

Phase 1A and 1B provide the deterministic domain core, strict base-policy schema, fixed runner profiles, bounded evidence parsing, evidence sufficiency rules, secret scrubbing, and the adversarial false-green scenario. The Phase I release gate was previously verified with 167 tests and 97.30% coverage; Phase II CI reruns the expanded suite against the integration code.

Phase II now adds:
- GitHub App RS256 JWT and short-lived installation-token exchange, requesting contents:read, pull_requests:read, and checks:write; Phase III opts in to additional actions:read only when evidence ingestion is enabled;
- bounded GitHub REST access with exact-SHA policy reads, paginated PR files, commit/tree-based test inventory, response-size limits, timeout/rate-limit classification, and no redirect following;
- a FastAPI webhook endpoint that verifies the raw HMAC-SHA256 body before parsing, rejects duplicate JSON keys, caps streamed request bodies, and acknowledges only after durable enqueue;
- a transactional SQLite delivery queue with delivery-ID fingerprinting, duplicate suppression, worker leases, bounded retries, and recovery of expired leases;
- a durable run/obligation ledger that can use SQLite locally or PostgreSQL through SQLAlchemy, preserving the exact repository, PR, base/head SHA, policy hash, planning mode, deterministic conclusion, Check Run ID, summary, and individual obligation records;
- a provider-agnostic planning port and optional Gemini hypothesis adapter; model failures fall back to deterministic path rules, and model output cannot mark evidence as passed;
- deterministic Check Run publication with an external ID, secret-scrubbed summary, and explicit disclosure that Phase II performs planning only and runs no untrusted tests.

The Phase II reference deployment keeps the webhook delivery queue on SQLite and can store run/obligation audit records in PostgreSQL. The queue is still single-host and is not a distributed queue; horizontally scaled ingress/worker deployment requires a shared queue backend. Deploy the ingress behind the operator's normal TLS/reverse-proxy boundary.

Phase III implementation and exact-head CI/evidence-producer gates are verified on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6). The latest verified code head is 61811292a9a87282b04758cbb3e4ecfa46160cb6; GitHub Actions run [#40271529641](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40271529641) succeeded on that exact SHA with both jobs green. Formatting, Ruff, strict mypy, 539 tests, 90.49% overall coverage, 96% Phase I coverage, and 86% Phase II integration coverage passed. Exact-PR-head artifact 12628348250 was downloaded and independently verified against GitHub SHA-256 bbf8a7d24ecaf32d46faf163b3e6446d96dc1d99608309d9ac584bda4ee1e0d4: exactly junit.xml and coverage-manifest.json, 539 unique matching test IDs, all passing outcomes, exact-head binding, and no structural anomalies. A previously failing idempotent-replay test was fixed by making ZIP test fixtures deterministic; production ledger conflict detection remains intact. V1 accepts one trusted run/artifact and fails closed on ambiguity; cross-run/rerun/shard aggregation is deferred. Before production merge gating, run the target deployment smoke test using its installed GitHub App and complete human review.

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

CI runs formatting, lint, strict typing, and tests with a 90% overall coverage floor, a 95% Phase I core coverage gate, and an 80% Phase II integration coverage gate.

## Roadmap

| Phase | Goal | Status |
| --- | --- | --- |
| 1A | Deterministic domain models and state machine | Implemented; previously green with 5,000-example property test |
| 1B | Policy validator, runner allowlist, evidence parsers, ledger, adversarial scenario | Release gate passed on the Phase I release-hardening tree; Phase II CI continues to run the expanded suite |
| 2 | Diff analysis, planning, persistence, webhook and Check Run service | Implemented on the Phase II integration branch; awaiting CI/review before merge. Includes authenticated GitHub REST transport, durable delivery queue, SQLite/PostgreSQL run ledger, worker orchestration, optional Gemini planning, and honest planning-only Check Runs |
| 3 | Platform-anchored passive CI artifact ingestion and reconciliation | Implementation + exact-head CI/evidence producer verified on PR #6; deployment-specific GitHub App smoke test and review remain |
| 4 | Opt-in dispatch, additional adapters, human governance hooks | Not started |

See [docs/verification-semantics.md](docs/verification-semantics.md), [docs/phase-0-architecture.md](docs/phase-0-architecture.md), [docs/phase-1-release-gate.md](docs/phase-1-release-gate.md), [docs/phase-2-planning.md](docs/phase-2-planning.md), and [docs/phase-2-operations.md](docs/phase-2-operations.md).
