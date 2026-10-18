# Phase II Build History

## Goal

Phase II connected the deterministic Phase I core to GitHub events and Check Run publishing. It remained planning-only: it did not run PR code or ingest Actions artifacts.

## Pull request sequence

### PR #3 — bounded planning foundation
[PR #3](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/3) added bounded changed-file/diff analysis with explicit complete/incomplete/truncated states, conservative deterministic risk-to-obligation rules, candidate selectors drawn only from a known inventory, a provider-neutral model port, and deterministic fallback when model output is malformed or the provider fails. Model output could not set an obligation status or supply execution commands.

### PR #4 — webhook and trusted context
[PR #4](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/4) added HMAC-SHA256 validation over the original raw request body, strict event parsing, duplicate-key rejection, size limits, validated delivery identity, and exact-SHA PR context assembly loading policy only from the trusted base SHA. It rejected malformed, duplicated, stale, or incomplete changed-file pages.

### PR #5 — integrated planning service
[PR #5](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/5) added:
- GitHub App RS256 JWT and installation-token flow with least-privilege requested permissions.
- Bounded read-only REST transport, exact-SHA policy reads, pagination, and test inventory.
- FastAPI webhook ingress with signature-before-parse, body limits, duplicate-key rejection, and durable acknowledgement.
- SQLite delivery queue with unique delivery identity, conflict/idempotency handling, worker leases, retry/backoff, and expired-lease recovery.
- Durable run/obligation ledger using SQLite or PostgreSQL through SQLAlchemy.
- Worker orchestration, optional Gemini hypothesis adapter with deterministic fallback, and deterministic Check Run create/update with secret-scrubbed output.

No `actions:write`, `pull_requests:write`, workflow dispatch, PR-code execution, or Actions artifact ingestion was added.

## Verified result on main

Main commit `1ff87390071491a9a08c9748aca2f36887ac5d77` passed [CI #39103979912](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39103979912): formatting, Ruff, strict mypy, unit/property tests, Phase I core coverage, and Phase II integration coverage. Result: **353 passed, one warning, 92.66% overall coverage**; the core gate was about 96%, and the integration gate about 86%.

## Remaining follow-ups

**Freshness before publication:** a later review identified that the worker should re-fetch PR state/base/head immediately before publishing and compare them to the evaluated `CommitIdentity`. A metadata fetch without assertions is not enough. The user explicitly deferred this fix while work proceeds on Phase III. Do not state that it is fixed until a regression test proves it.

**Documentation drift:** `docs/phase-2-planning.md` retains an older “Remaining Phase II work” list inconsistent with the merged service. Reconcile the checklist with the code and operations document.

**Deployment limitations:** the SQLite delivery queue is single-host, not a distributed queue. Production work still includes metrics/alerting, key rotation, database migration/retention, concurrency tests, and deployment-specific TLS/reverse-proxy controls.

## Lessons

1. Webhook authenticity does not make every payload field inherently trustworthy.
2. Acknowledge only after durable enqueue.
3. Idempotency needs durable conflict handling, not an in-memory set.
4. “Planning complete” and “tests passed” are different claims.
5. Enforce least privilege in both App configuration and installation-token requests.
6. External integration needs bounded requests/responses, pagination, timeout/rate-limit handling, and race tests.
