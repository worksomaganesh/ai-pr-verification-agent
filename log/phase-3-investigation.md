# Phase III Investigation Log — Evidence Ingestion

## Intended trust chain

`authenticated Actions API` → `workflow/job/step/artifact identity` → `bounded bytes and digest` →
`strict JUnit and coverage reports` → `commit-bound durable evidence` →
`deterministic obligation reconciliation` → `final PR freshness check` → `Check Run publication`.

Downloading `junit.xml` is only one link in that chain.

## Initial implementation in the PR working tree

- `src/verification_core/github_actions.py`: authenticated Actions workflow-run reads, paginated jobs/artifacts, guarded ZIP download, HTTPS host allowlist, and prevention of installation-token forwarding to signed storage hosts.
- `src/verification_core/actions_evidence.py`: repository/PR/base/head/run binding, workflow trust metadata, artifact ID/name/size/digest checks, bounded ZIP validation, exact JUnit/coverage member checks, node-ID inventory and outcome consistency.
- `src/verification_core/phase_three.py`: worker-facing orchestration; PR state/base/head checks before and after retrieval; workflow source loaded from the exact base SHA; missing/ambiguous artifacts rejected; optional persistence to the ledger.
- `src/verification_core/evidence_ledger.py`: SQLAlchemy persistence of evidence identity and summary metadata; new records begin `INCONCLUSIVE`; ingestion itself does not mark anything passed.
- Tests cover malformed/stale evidence, redirect hosts, artifact ambiguity, PR-head changes, idempotent persistence, conflicting replays, and terminal-decision immutability.

This is an initial slice on draft PR [#6](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/6), not a production-ready or merged feature.

## What CI actually says

Latest inspected PR run: [#39129484914](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39129484914).  
Tested SHA: `19ebc5be866adfbe9f0993a3dd62a1f2db146cdf`.

- Formatting: **passed**.
- Ruff: **failed** with `I001` import-block ordering in `tests/unit/test_evidence_ledger.py`.
- Strict mypy: **skipped**.
- Unit/property tests: **skipped**.
- Coverage and phase-specific coverage gates: **skipped**.

Therefore no test or coverage success may be inferred for this Phase III SHA.

## Repeated import-order failure: what went wrong

The conversation repeatedly attempted to fix Ruff `I001` by manually swapping imports in
`tests/unit/test_evidence_ledger.py`. Several replies declared the fix done, but fresh CI logs kept
showing the same failure on that path. The correct loop should be:

1. Reproduce the exact configured Ruff version and command.
2. Capture the complete `ruff check --fix tests/unit/test_evidence_ledger.py` diff.
3. Inspect the actual post-fix file rather than trusting the planned replacement.
4. Commit that exact result.
5. Verify the live branch ref, PR head, file content in the commit tree, and workflow SHA all agree.
6. Read the new run before touching later code or reporting success.

Manually alternating line order without verifying the exact output was an inefficient and unreliable
debugging approach.

## Branch and commit consistency

Several intermediate chat replies reported later commit SHAs. A retrospective read of live GitHub refs
and PR #6 resolved the current branch/PR head to `19ebc5be866adfbe9f0993a3dd62a1f2db146cdf`. The
branch ref and PR head outrank any claim in an assistant message. Future changes must confirm that
the commit SHA reported by the write API is the branch ref, that the PR points to that same SHA, that
the changed files are in that SHA's tree, and that CI runs against that SHA. If they disagree, stop and
reconcile the refs before claiming a change is delivered.

## Conversation progress estimates (historical)

| Reported estimate | Implementation slice associated in the chat | Important caveat |
|---:|---|---|
| 45% | Initial Actions API client and artifact parser | Initial code; not fully CI-verified |
| 50% | Worker-facing orchestration and PR freshness checks | Initial tests; full CI still red |
| 55% | Initial SQLAlchemy evidence ledger and persistence tests | Not yet connected to final reconciliation |
| 58% | Policy-aware identity, timestamp checks, conditional reconciliation updates | Full CI not green |
| 60% | Ingestion-to-ledger wiring and ledger key returned from service | Full CI not green |
| 62% | Reported persistence/integrity hardening | Still not a release-readiness measure; full CI red |

These percentages were rough conversational estimates, not an audited weighted-completion measure, a
test-pass ratio, or a coverage metric. This log preserves them historically; this documentation commit
does not increase the Phase III estimate.

## Why reconciliation is still pending

A report field such as `behavioral_assertion_verified: true` is a self-assertion. A matching archive
digest establishes consistency with the expected digest; it does not prove the claim's meaning.
Platform provenance is necessary, but not by itself sufficient evidence that the risky behavior was
properly tested.

The next code milestone must derive expected target lines/branches from trusted diff/policy data, match
exact JUnit node IDs to per-test coverage, fail closed on missing/skipped/stale/partial/contradictory
evidence, call the existing Phase I deterministic evidence/state machine, then recheck current PR base
and head immediately before publication.

## Acceptance checklist

- [ ] Resolve Ruff `I001` on the actual current PR head.
- [ ] Pass strict mypy on the same SHA.
- [ ] Pass the complete unit/property test suite on that SHA.
- [ ] Pass overall and Phase I/Phase II coverage gates.
- [ ] Confirm ingestion-to-ledger integration tests execute and pass in CI.
- [ ] Implement/test deterministic obligation reconciliation.
- [ ] Resolve reruns, artifacts expiry, duplicate artifacts, shards, partial reports, and contradictions.
- [ ] Protect final Check Run publication with immediate PR freshness revalidation.
- [ ] Align PR description and Phase III status docs with actual code.
- [ ] Record a green merge-candidate SHA and CI URL before removing draft status.
