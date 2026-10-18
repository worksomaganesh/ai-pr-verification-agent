# Phase I Build History

## Goal and acceptance contract

Phase I was intentionally a zero-infrastructure deterministic core. It should not require GitHub credentials, network access, a database, or an LLM. It owns the vocabulary of obligations, permitted state transitions, evidence sufficiency, and deterministic conclusion mapping.

## Main components

### Domain model and state machine
Obligations have distinct proposed, scheduled, passed, failed, blocked, not-run, skipped, inconclusive, stale, human-approved, and policy-waived states. A machine pass requires trusted commit-bound provenance, a passing test outcome, and sufficient evidence. Human acceptance and policy waiver are not machine proof.

### Policy and runner safety
The versioned YAML policy rejects duplicate keys, unknown fields, unsafe paths, and configurations that weaken critical/high risk handling. Runner profiles and selector grammars are verifier-owned; the system does not accept arbitrary model-generated shell commands.

### Evidence parsing
JUnit parsing uses hardened, bounded XML handling. Per-test coverage is bound to exact test node IDs and outcomes. Missing, malformed, empty, contradictory, stale, or weak evidence cannot become passed. Secret scrubbing applies to test detail/report fields.

### False-green regression
An adversarial scenario includes many unrelated passing tests while critical webhook and cross-user authorization obligations remain unverified. The expected conclusion remains `action_required`; unrelated passes cannot hide absent evidence for high-risk behavior.

## Development corrections recorded in the commit history

- Safe XML parsing required correct `defusedxml` dependency metadata.
- The custom safe YAML loader needed strict typing compatibility with PyYAML, import-order fixes, and corrected newline fixtures in adversarial tests.
- Per-test coverage parsing received additional edge-case tests and mypy corrections.
- Formatting and lint had several iterations; the final hardening restored read-only CI, disabled persisted checkout credentials, and made formatting check-only rather than letting CI rewrite tracked files.
- The legacy snapshot extractor was made to preflight destinations and refuse conflicting overwrites unless explicitly opted in. ZIP output names were constrained to prevent path traversal.

The important pattern: failures were resolved by tightening behavior, tests, and release gates, not by weakening the safety contract.

## Release-gate evidence

PR [#1](https://github.com/worksomaganesh/ai-pr-verification-agent/pull/1) was merged. Commit
`5626ef5b5df58f288058977f73692947234abc1c` passed [CI #39036376525](https://github.com/worksomaganesh/ai-pr-verification-agent/actions/runs/39036376525):
formatting, Ruff, strict mypy, and tests. The result was **167 passing tests and 97.30% overall coverage** against a 95% floor.

## Lessons

1. Define state-transition rules before external integrations.
2. Treat absence, weak evidence, and malformed reports as explicit states.
3. Make the false-green example a regression test.
4. Keep CI least-privileged, with formatting check-only.
5. Tie release claims to one exact passing commit.
