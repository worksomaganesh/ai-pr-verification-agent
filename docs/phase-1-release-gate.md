# Phase 1 release gate

Phase 1 is complete only when all requirements below are implemented, tested, and green on the same commit.

## Deterministic core
- [x] Immutable domain records and explicit obligation states.
- [x] Guarded state transitions; human approvals and policy waivers are distinct from machine verification.
- [x] Deterministic GitHub Check Run conclusion mapping.
- [x] Property-based false-green invariant configured for 5,000 generated examples.

## Policy and execution boundary
- [x] Strict versioned YAML schema with duplicate-key and unknown-field rejection.
- [x] Anchors, aliases, merge keys, unsafe paths, missing harness-protection paths, and weakened critical/high blocking rejected.
- [x] Only verifier-owned runner profiles; argv tuples are built without a shell.
- [x] Narrow selector grammar rejects option injection, traversal, absolute paths, whitespace, and shell metacharacters.
- [x] Policy authenticity is an integration responsibility: load from the trusted base commit, never the PR head.

## Evidence ingestion and reporting
- [x] Bounded JUnit XML parser; DTD/entity protections; malformed and inconsistent counts fail closed.
- [x] Per-test outcomes normalized without treating artifact contents as proof of authenticity.
- [x] Evidence sufficiency filters: malformed/empty, contradictory, coverage miss, weak assertion evidence, sufficient.
- [x] Secret scrubbing applied to test details and report fields.
- [x] Deterministic Markdown ledger separates machine verification from human approval and policy waiver.
- [x] Adversarial scenario: 140 unrelated passes plus missing critical webhook and cross-user authorization obligations yields `action_required`.

## CI and bootstrap safety
- [x] CI uses `contents: read` only and disables persisted checkout credentials.
- [x] Formatting is check-only; CI never commits formatter output or pushes to `main`.
- [x] The legacy Phase 1A extractor preflights all destinations and refuses conflicting overwrites unless explicitly opted in.
- [x] ZIP output name is restricted to a filename, preventing path traversal outside the target directory.
- [x] Regression tests cover preflight behavior, existing archives, clean extraction, and explicit overwrite opt-in.

## Required verification commands

```bash
ruff format --check src tests
ruff check src tests
mypy --strict src tests
pytest --cov=src/verification_core --cov-report=term-missing --cov-report=xml
```

The CI workflow must pass all commands on the exact release-gate commit. A previous green run for an earlier SHA does not verify later changes.

## Explicit limits
- A syntactically valid JUnit report is not authenticated by this parser.
- Hashes in an artifact are corruption checks only, not provenance.
- Line/branch coverage is a necessary negative filter, not proof of correct behavior.
- The Phase 1 core does not yet query GitHub APIs or publish Check Runs; those are later integration phases.
