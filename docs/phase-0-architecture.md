# Phase 0.1 — Architecture and Threat-Model Decisions

## Status and evidence boundary

This document records implementation constraints, not a claim that every component is implemented or independently verified. Earlier audit work could not access every blueprint source file; assumptions must be checked against the actual source before integration work.

## Product contract

The agent identifies behavioral risks, tracks verification obligations, reconciles test evidence, and reports what is proven versus uncertain. It is not a generic comment-generating code reviewer. An LLM may propose risks but is never authoritative for test outcomes or final conclusions.

## Trust boundaries

1. The PR workspace, application/test code, repository configuration, and test-generated files are untrusted.
2. GitHub workflow, job/step, and artifact metadata fetched independently through the GitHub API is the provenance anchor.
3. Artifacts are inputs to validate, not self-authenticating claims.
4. Policy evaluation, parsing, reconciliation, and conclusion computation belong in the verifier control plane, outside the untrusted PR process.
5. Human governance decisions must remain auditable and separate from machine proof.

## Five separate verification properties

| Property | Question | Required control | Limitation |
| --- | --- | --- | --- |
| Integrity | Was data corrupted or malformed? | Size/ratio limits, digest checks, safe XML parsing, strict schemas | Does not authenticate the author |
| Authenticity | Did it originate from the claimed platform run? | Query GitHub run/job/artifact APIs using an installation token | Does not prove semantic quality |
| Commit attribution | Is evidence bound to this exact change? | Verify base/head SHAs, trusted workflow path, policy digest, supersession | Does not prove changed behavior was tested |
| Actual execution | Did the reported test step execute? | Reconcile job/step status, non-zero test counts, JUnit node IDs, per-test coverage | Same-process malicious code can tamper with test internals |
| Behavioral sufficiency | Did the test check the risky contract? | Target-line/branch evidence plus assertion/scenario signals | Static checks and coverage cannot prove arbitrary business correctness |

Hashes generated inside an untrusted runner are corruption checks only. A malicious process sharing the workspace could rewrite both a report and its manifest. Signed artifact attestations may add a verifiable layer for higher-assurance deployments.

## Evidence and state semantics

A machine-verified pass requires trusted provenance bound to expected base/head SHAs, a passing mapped test, a valid non-empty report, relevant target-line/branch execution where available, and sufficient behavioral assertion/scenario evidence. A happy-path authorization test does not prove cross-user denial; a webhook test without event replay does not prove idempotency. Coverage is a necessary negative filter, not a standalone correctness proof.

Keep PROPOSED, SCHEDULED, PASSED, FAILED, BLOCKED, NOT_RUN, SKIPPED, INCONCLUSIVE, STALE, APPROVED_BY_HUMAN, and WAIVED_BY_POLICY distinct. Missing, malformed, stale, or weak evidence for critical/high obligations cannot silently become success. Human approvals must record reviewer identity, review ID, timestamp, rationale, and approved head SHA. Static policy waivers must not waive critical/high obligations.

Internal outcomes and external GitHub Check Run conclusions are separate. Supersession must invalidate old evidence and prevent a delayed older run overwriting the latest head. The publisher must use supported API conclusions and account for branch protection: neutral and skipped may be non-blocking, so neither may represent an unverified critical/high obligation.

## Least privilege by phase

| Phase | Scope | Permissions |
| --- | --- | --- |
| 1 | Pure deterministic Python core; no network or credentials | None |
| 2 | Passive PR context collection and Check Run publishing | metadata: read, contents: read, pull_requests: read, checks: write |
| 3 | Workflow/job/artifact metadata and passive evidence ingestion | Phase 2 plus actions: read |
| 4 | Explicit opt-in workflow dispatch only | Phase 3 plus opt-in actions: write |

The app does not need pull_requests: write; Check Runs publish verification without editing PR descriptions, labels, or comments.

## Runner and policy controls

- Load the policy from the protected base SHA, never from the PR head.
- Permit only fixed runner-profile argument templates; do not accept free-form shell commands or arbitrary flags.
- Reject traversal, leading-option selectors, shell metacharacters, NULs, and paths outside approved directories.
- Detect changes to policy files, workflows, and test bootstrap files such as conftest.py, pytest.ini, pyproject.toml, and package.json. Such changes create a critical governance obligation and may invalidate affected evidence.
- Parse JUnit using hardened XML parsing, enforce compressed/uncompressed size and compression-ratio limits, and scrub secrets from failure output.
- Treat missing artifacts, zero-test reports, mismatched SHAs, and invalid schemas as inconclusive, never passed.

## Shared-process limitation

Platform metadata can show that a report came from a run for a commit, but ordinary in-process unit tests do not prove malicious application code did not monkeypatch the test runner. Reports must label this as in-process evidence. Security-critical obligations may require out-of-process black-box tests or explicit human risk acceptance.

## Phase 1 acceptance direction

Phase 1 is a zero-infrastructure deterministic core: state machine, policy schema and validator, fixed runner profiles, safe report parsing, evidence sufficiency, deterministic conclusion engine, report renderer, adversarial fixtures, and the running scenario. No web server, database, GitHub API, or LLM API belongs in this milestone. Passing a partial Phase 1A suite is not passing the complete Phase 1 acceptance gate.
