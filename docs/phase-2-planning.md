# Phase II — Bounded Diff Analysis and Verification Planning

## Status

This branch begins Phase II with a pure, deterministic planning foundation. It does not yet implement the GitHub App, webhook receiver, persistence layer, GitHub API client, or live Check Run publisher. Those integrations must be built only after the planning contracts are tested.

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

## Remaining Phase II work

1. Review and merge this planning foundation after CI passes.
2. Add a deterministic diff-to-obligation evaluation corpus with expected risk categories and false-negative review.
3. Add a pure, strict PR-context/event model and idempotency-key contract.
4. Implement a minimal GitHub API adapter with explicit read-only context collection and bounded pagination; policy must be fetched at `base_sha`.
5. Add webhook signature verification and delivery deduplication only when the HTTP service is introduced.
6. Add persistence only after the domain/event contracts are stable.
7. Publish Check Runs through `checks: write` only after the adapter validates exact base/head identity and uses the Phase I conclusion engine.
8. Run CI on the exact merge candidate and document verified results.

## Not claimed yet

- The planner has not been evaluated on a representative production PR corpus.
- Path-based rules can miss risks hidden in ordinary filenames or over-classify harmless changes.
- Static line ranges do not prove semantic behavior.
- The current module does not fetch GitHub data, verify webhook signatures, authenticate artifacts, persist state, call Gemini, or publish Check Runs.
- Phase II is not complete merely because this initial foundation is merged.
