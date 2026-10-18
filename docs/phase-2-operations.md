# Phase II Operations and Security Boundaries

Phase II connects authenticated GitHub events to bounded planning and a deterministic GitHub Check Run. It does **not** run repository tests and does not ingest Actions artifacts. Those are Phase III responsibilities.

## Components

1. **Webhook ingress** (verification_core.webhook_app) verifies X-Hub-Signature-256 against the original raw request bytes before JSON parsing. It rejects oversized streamed bodies, duplicate JSON object keys, malformed events, and events without an installation ID.
2. **Durable delivery ledger** (verification_core.delivery_store) stores normalized event identity in SQLite. A delivery ID is unique, and reusing it with different event content is rejected. The endpoint returns HTTP 202 only after the delivery is committed.
3. **GitHub App transport** (verification_core.github_app) creates a short-lived RS256 App JWT and exchanges it for an installation token. The token request explicitly limits permissions to contents: read, pull_requests: read, and checks: write. Metadata is inherently readable. There is no actions: write or pull_requests: write.
4. **Trusted context assembly** re-reads PR metadata, checks the exact base/head SHAs, reads .verification-policy.yml at the base SHA, and consumes all bounded changed-file pages.
5. **Planning** runs deterministic path rules first. The optional Gemini adapter can add structured hypotheses only; invalid output and provider errors fall back to deterministic planning. No model can mark an obligation passed or choose the Check Run conclusion.
6. **Check Run publication** publishes the deterministic result against the exact head SHA. An external ID makes retries update the same check rather than intentionally create a new one. Output is bounded and secret-scrubbed.

## Install and run

Python 3.12+ is required.

Install the project and integration dependencies:

    python -m pip install -e ".[integration]"

Configure the GitHub App with:
- Repository permissions: **Contents: read**, **Pull requests: read**, **Checks: write**.
- Webhook subscription: **Pull requests**.
- A webhook secret, App ID, and App private key.
- The app installed on each repository to be monitored.

Set the ingress environment:

    export GITHUB_WEBHOOK_SECRET='use-a-random-secret-from-your-secret-manager'
    export VERIFICATION_DATABASE_PATH='./var/verification-events.sqlite3'
    python -m verification_core serve --host 127.0.0.1 --port 8000

In a separate process, configure the worker:

    export GITHUB_APP_ID='123456'
    export GITHUB_APP_PRIVATE_KEY_PATH='/run/secrets/github-app-private-key.pem'
    export VERIFICATION_DATABASE_PATH='./var/verification-events.sqlite3'
    python -m verification_core worker --poll-seconds 1

The ingress and worker must point to the same database file and host. Do not commit secrets or the database file. Terminate the process normally so the worker can close resources.

Optional model planning:

    export GEMINI_API_KEY='use-your-secret-manager'
    export GEMINI_MODEL='your-enabled-Gemini-model-id'

If GEMINI_API_KEY is absent, deterministic planning is used. If a key is set, GEMINI_MODEL is required. Model output is validated against the bounded diff and existing test inventory. The model is not used in evidence reconciliation or conclusion calculation.

For a local health check, request GET /healthz. Configure the public GitHub webhook URL to the externally reachable /webhooks/github route over HTTPS. TLS termination and public ingress protection belong at the deployment reverse proxy/load balancer; do not expose the development server directly to the public internet.

## Delivery and retry semantics

- HTTP 202 means the signed event was durably enqueued, not that planning has finished.
- Repeated delivery IDs with identical event metadata return a duplicate acknowledgement. Reuse with different event metadata is rejected by the store.
- The worker claims one event with a lease. Expired leases are recoverable, failures use bounded exponential backoff, and attempts are capped.
- Check Run publication is retried with the same external_id. If publication succeeds but marking the delivery complete fails, a retry should update the same check.
- SQLite uses WAL and full synchronous mode. This reference implementation assumes one host and a small worker count; it is not a distributed queue or a horizontal-scaling design.

## Honest result semantics

Phase II Check Runs are **planning-only**. The report explicitly states that no test commands ran. Critical/high obligations that remain proposed or unverified result in action_required; failures and policy blocks remain failures. A complete docs-only change may be neutral according to the deterministic Phase I policy. Branch protection must require the exact AI PR Verification check if the repository intends this signal to participate in merge gating.

A Phase II Check Run does not establish:
- that an Actions workflow ran or used a trusted workflow definition;
- that an artifact came from GitHub's artifact service;
- that a test node actually executed;
- that line/branch coverage or assertions prove the required behavior.

Those require Phase III platform-anchored workflow/job/artifact metadata and evidence reconciliation. Phase II does not dispatch workflows, execute PR code, comment on PRs, alter PR descriptions, or auto-merge.

## Permission and deployment caveats

- Installation token requests are reduced to the required permissions, but the GitHub App itself must be configured with no broader permissions than needed.
- The SQLite database contains repository names, commit SHAs, PR numbers, and delivery metadata. Protect it as operational data and apply retention/backup policy.
- Keep the webhook secret and App private key in a secret manager or protected runtime secret mount. Do not pass them in command-line arguments.
- Use a separate process for the worker. The ingress does not synchronously call GitHub or Gemini and does not acknowledge a delivery that could not be persisted.
- Before a production rollout, add operational metrics, alerting, key rotation procedures, database migration/retention policy, multi-worker concurrency tests, and a deployment-specific TLS/reverse-proxy configuration.
