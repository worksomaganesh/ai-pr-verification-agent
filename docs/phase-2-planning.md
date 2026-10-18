# Phase II — Bounded Diff Analysis and Verification Planning

## Status

Phase II implementation is present on the integration branch and is being validated through CI. It now includes the bounded planner, GitHub App authentication, read-only REST context client, HMAC-verified FastAPI ingress, durable SQLite delivery ledger, queue worker, optional Gemini hypothesis adapter, and deterministic Check Run publisher. See [phase-2-operations.md](phase-2-operations.md) for deployment instructions and explicit boundaries. This phase is planning-only: it does not execute PR tests or ingest Actions artifacts.

## Trust contract

- Inputs must already be bound to one `CommitIdentity` (`repo_full_name`, PR number, base SHA, head SHA, policy digest).
- The GitHub adapter is responsible for paginating every changed-file page and loading policy from the trusted base SHA. This module cannot independently authenticate GitHub data.
- Diff text is untrusted. It is bounded, never executed, and secret-scrubbed before a patch excerpt is retained.
- Missing patches, unparseable hunks, oversized patches, and file-count truncation lower analysis completeness. They must never be interpreted as proof that no risky change exists.
- Deterministic path rules run before optional model planning.
- Model output can add only structured risk hypotheses. It cannot assign obligation status, provide commands, alter severity rules, or introduce paths/selectors outside the analyzed diff and known test inventory.
- Model errors and invalid payloads fall back to deterministic obligations.
- Every generated obligation starts as `PROPOSED`. The planner cannot mark any behavior passed.

## Current API

```python
analysis = analyze_changed_files(
    commit=commit_identity,
    changed_files=all_changed_file_records,
    policy=policy_loaded_from_base_sha,
)

result = plan_verification(
    analysis,
    test_inventory=known_test_selectors,
    model=optional_verification_model_port,
)
```

`ChangedFileInput` is an adapter-neutral representation of the pull-request-files API. `DiffLimits` bounds the number of files, changed lines, per-file patch bytes/characters, and aggregate patch characters. The analysis reports `COMPLETE`, `INCOMPLETE`, or `TRUNCATED` explicitly.

## Deterministic risk categories

| Category | Default severity | Initial path signals |
| --- | --- | --- |
| `governance_config_tamper` | Critical | Policy, workflow, and harness-sensitive files |
| `database_migration` | Critical | Migration/schema directories and SQL files |
| `webhook_idempotency` | Critical | Webhook implementation paths |
| `tenant_authorization` | Critical | Auth, authorization, permissions, and access-control paths |
| `billing_regression` | High | Billing, payment, checkout, subscription, and invoice paths |
| `dependency_integrity` | High | Dependency lockfiles and requirement/constraint files |
| `runtime_regression` | Medium | Other executable source files |

These rules are intentionally conservative and heuristic. They are risk signals, not semantic proof or a complete taxonomy. A later ruleset should be versioned and evaluated against a curated PR corpus. An incomplete diff must still prevent a false-green conclusion through the existing domain conclusion engine.

## Test-selector policy

A candidate selector is only selected from a caller-supplied test inventory and validated with the Phase I selector grammar. The planner never constructs an arbitrary shell command or executes a selector. A missing candidate remains `None`; the obligation remains unverified.

## Model port

`VerificationModelPort` is provider-agnostic. A Gemini adapter may be added later behind this interface, but the model response is always untrusted data. Schema validation restricts the response to bounded hypotheses, changed-file paths, and known test selectors. No model is called by the deterministic core, and no model response is evidence of test execution.

## Phase II implementation update

The next slice now adds two adapter-neutral boundaries:

- `verification_core.webhooks` validates `X-Hub-Signature-256` against the exact raw request bytes using HMAC-SHA256 and constant-time comparison, and parses only `opened`, `reopened`, and `synchronize` pull-request events. It returns a stable delivery idempotency key, but intentionally does not pretend that an in-memory key prevents retries; durable deduplication belongs in the service/persistence layer.
- `verification_core.github_context` defines a narrow read-only `GitHubReadClient` protocol and assembles an immutable PR context. It re-reads PR metadata to reject stale base/head SHAs, loads `.verification-policy.yml` only at the exact `base_sha`, hashes the raw policy text, validates it with the Phase I validator, and consumes changed-file pages with strict shape, path, count, and duplicate checks. Missing/invalid policy, stale PR metadata, and incomplete pagination fail closed.

These are interfaces and pure orchestration over an injected client, not a live GitHub HTTP client. The concrete installation-token transport, HTTP timeouts/retries/rate limits, durable delivery ledger, webhook server, database, and Check Run publisher remain future work. `GitHubReadClient` implementations must enforce authentication and bounded response bodies.

## Remaining Phase II work

1. Add and review a deterministic diff-to-obligation evaluation corpus with expected risk categories and false-negative analysis.
2. Implement a concrete read-only GitHub REST client with installation-token authentication, bounded timeouts/retries, pagination, and response-size limits.
3. Add a minimal webhook service with constant-time signature verification and durable `X-GitHub-Delivery` deduplication.
4. Add persistence only after domain/event contracts are stable.
5. Publish Check Runs through `checks: write` only after exact-SHA context validation and the Phase I conclusion engine are wired together.
6. Add adversarial mocked end-to-end tests for races, pagination, invalid payloads, API failures, and duplicate deliveries.
7. Run CI on the exact merge candidate and document verified results.

## Not claimed yet

- The planner has not been evaluated on a representative production PR corpus.
- Path-based rules can miss risks hidden in ordinary filenames or over-classify harmless changes.
- Static line ranges do not prove semantic behavior.
- The GitHub REST adapter uses bounded response sizes, explicit timeouts, no redirects, exact-SHA reads, and an installation token reduced to contents:read, pull_requests:read, and checks:write.
- The SQLite ledger is a single-host reference queue, not a distributed worker queue. Production multi-host deployment needs a shared database/queue and operational controls.
- Phase II does not prove workflow/artifact authenticity or actual test execution. Those are Phase III obligations.
- Phase II completion is gated on CI, adversarial tests, and review of the merged integration; code being present is not itself evidence that release gates passed.
