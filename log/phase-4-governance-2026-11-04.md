# Phase IV governance CI — 2026-11-04

## Change set
- `71079f09`: `src/verification_core/dispatch_governance.py` adds GitHub operator allowlist/repository permission verification, SQLAlchemy write-ahead dispatch audit, one-shot coordinator, workflow-run correlation, and exact-SHA reconciliation.
- `7654a229`: focused `.github/workflows/phase4-governance.yml` (format, Ruff, strict mypy, governance/dispatcher tests).
- `76df7192`: `tests/unit/test_dispatch_governance.py` for auth, audit persistence, duplicate suppression, uncertain outcome, SHA success/mismatch, delayed run visibility, and ambiguous correlation.

## Exact-head CI attempts
1. [Run #41802482290](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41802482290), PR head `76df719259435f9d99d55c51dbb1bfffbe9de822`: failed at Ruff format check. All later steps skipped.
2. [Run #41802656874](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/41802656874), PR merge checkout included branch head `ec51f0700fa5fc2b635f0ead3dce65d22a2a2163`: failed at same format check. Original file contents were still unformatted; a log commit did not fix code. Ruff identified formatting only; lint/type/tests skipped.

**Next:** apply Ruff formatting to both Python files (not just document the diff), commit, rerun. No code behavior is CI-verified yet.

## Review cautions
- Tokens are caller-provided and never stored; configure least privilege.
- Audit stores operator/request metadata and input digest, not raw inputs or credentials. Production requires managed PostgreSQL, migrations, backups, retention, and access controls.
- Correlation expects Actions run-name `verification-dispatch:<verification_dispatch_id>`; staging workflow is not configured/dispatched.
- Exact-SHA reconciliation only links a workflow run to a commit. It does not validate job/artifact authenticity or evidence completeness; Phase III pipeline remains separate.
- No real dispatch, staging deployment, merge, or production rollout occurred.
