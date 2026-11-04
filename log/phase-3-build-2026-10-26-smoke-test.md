# Phase III build log — deployment smoke-test path — 2026-10-26

## Starting checkpoint

The implementation started from branch head \`04e20cec32ebba28543c9baabc2b8bd759d51822\`. Its exact-head workflow run [#40273344438](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/40273344438) completed successfully on 2026-10-26: both Python quality and authenticated evidence-artifact production jobs passed. The artifact was ID \`12628049808\`, 42,862 bytes, and the API digest was \`sha256:c48d46b1a88d2391462afc53dc7c6b90cdba8226c73e5b6b4270eac3e40f6dab\`.

This baseline did not prove live deployment wiring. The repository has a webhook ingress and worker/runtime code, but the connected repository tools expose no configured staging endpoint, App private key, webhook secret, or database URL. No attempt was made to invent an endpoint or claim an unperformed live test.

## Work added in this revision

- Added \`scripts/phase3_deployment_smoke.py\` as an explicit integration acceptance command.
- Added focused unit tests for artifact-digest parsing, evidence-record-key binding, and exact-byte HMAC signing.
- Expanded CI's format/lint/type-check commands to include the smoke-test script.
- Expanded the Phase III runbook and handoff with required environment configuration, explicit real-Check-Run confirmation, expected assertions, and the boundary between unit tests and live deployment testing.
- Kept PR #6 draft and did not alter main or production merge-gating configuration.

## Root cause addressed

Earlier CI verification proved the repository code and synthetic evidence artifact but did not exercise the installed GitHub App, deployed webhook URL, worker process, or configured evidence database. The gap was operational, not a known failing unit test. The smoke command now requires all external identities explicitly and fails closed rather than fabricating a service URL or silently skipping missing configuration.

## Test design and safeguards

1. Request an installation token with Actions read permission; use the authenticated Actions client to find one successful, trusted run for the exact current PR head.
2. Download the named artifact through the same bounded and hostname-allowlisted client used by the application; compare local SHA-256 with GitHub's digest before sending a webhook.
3. Check \`/healthz\`, then send a deliberately invalid HMAC and require HTTP 401.
4. Serialize and sign one synthetic \`pull_request:synchronize\` delivery; require durable acceptance and verify replaying the same delivery ID is recognized as a duplicate.
5. Poll for a newly started Check Run with the Phase III external ID; require completion, exact head binding, the expected workflow-run identifier, and a persisted evidence-record key.
6. Query \`authenticated_evidence_records\` through the configured evidence database URL and match repository, PR, base/head SHA, workflow run, artifact ID, and artifact digest. For terminal conclusions the persisted decision state/digest must agree.
7. Re-read the PR during polling and before acceptance; reject any base/head movement.
8. Require an explicit confirmation environment variable because a successful execution creates a real Check Run and queues a real event.

The smoke command intentionally does not induce destructive database failure or mutate the PR to simulate a stale-head race. Existing automated tests cover those paths. It must run against staging where possible and against the same database used by the worker; a different local database URL cannot prove deployment persistence.

## Expected gates for this change

- [ ] Exact-commit CI passes formatting, Ruff, strict mypy, unit/property tests, and coverage gates.
- [ ] Exact-commit evidence producer uploads JUnit and coverage manifest.
- [ ] Human review is still required.
- [ ] Live smoke test remains pending until an actual endpoint and secret-managed configuration are available.

After CI completes, the current tested SHA and run URL are captured in PR #6's current status. Do not treat the previously verified baseline as the head of this smoke-test revision.
