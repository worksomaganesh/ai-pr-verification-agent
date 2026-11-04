# Phase IV governance CI — 2026-11-04

## Change set
- Commit 71079f09: new `src/verification_core/dispatch_governance.py` with GitHub user allowlist and repository permission checks, SQLAlchemy write-ahead dispatch audit, one-shot dispatch coordinator, workflow run correlation, and exact-SHA reconciliation.
- Commit 7654a229: focused `.github/workflows/phase4-governance.yml` running formatter, Ruff, strict mypy, and governance/dispatcher tests.
- Commit 76df7192: new `tests/unit/test_dispatch_governance.py` covering authorization, audit persistence, duplicate suppression, unknown dispatch outcome, exact-SHA success/mismatch, run visibility delay, and duplicate correlation.

## First CI attempt
- Run [#41802482290](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41802482290), exact PR head `76df719259435f9d99d55c51dbb1bfffbe9de822`, failed at `ruff format --check` only.
- Ruff identified formatting in the new governance module and test file. Lint, mypy, and tests were skipped—not passed.
- Next action: apply Ruff formatting, commit, and rerun exact-head focused CI. Do not count this run as test evidence.

## Security / implementation caveats to resolve in review
- Dispatch uses user-provided token and GitHub user/repository permission APIs; configure least-privilege scopes and do not store token.
- Audit stores request hash and operator identity, not raw inputs or credentials. It uses a durable SQLite/PostgreSQL URL; production must use managed PostgreSQL and migration/backup/retention controls.
- Run correlation requires workflow run-name `verification-dispatch:<verification_dispatch_id>`; no staging workflow has yet been created or dispatched.
- This reconciliation only ties a run to exact head SHA; it does not validate job/artifact authenticity or evidence completeness. Phase III evidence pipeline remains separate.
- No real dispatch, staging deploy, merge, or production rollout occurred.
