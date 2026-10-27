# Phase IV start — 2026-10-27

## Starting point

- Repository: worksomaganesh/ai-pr-verification-agent
- Phase IV branch: phase-4-opt-in-dispatch
- Base commit: d9bc46f2fad9ac0527f87b6d692cb8f88929fc37
- Phase III work remains on draft PR #6 and must not be treated as merged by this Phase IV branch.
- Phase III live deployment smoke acceptance and human review are intentionally deferred to the Phase IV ending.

## First implementation slice

Added a guarded workflow-dispatch client in src/verification_core/workflow_dispatch.py and focused tests in tests/unit/test_workflow_dispatch.py. Added docs/phase-4-opt-in-dispatch.md to define phase goals, security boundaries, verification plan, and release gates.

The dispatch client is intentionally disabled by default. It requires explicit enablement, an exact workflow filename allowlist, a safe repository/ref, bounded non-secret string inputs, and a caller-supplied token. It does not automatically mint actions:write credentials, dispatch workflows in CI, retry external side effects, merge PRs, or deploy to production.

## Verification status

- Unit tests and full CI: pending at branch creation.
- No real workflow dispatch has been triggered.
- No Phase III live deployment smoke test has been run.
- No human review has been performed.
- PR #6 remains draft; production merge gating remains disabled.

## Next steps

1. Run exact-head CI on this branch and fix failures before adding more scope.
2. Validate GitHub App Actions:write permission behavior against GitHub's workflow-dispatch API in a staging repository, without enabling production dispatch.
3. Add an authenticated operator authorization boundary and durable dispatch audit log before production exposure.
4. Finish Phase IV implementation and, at the phase ending, complete the Phase III live smoke test and human review.
