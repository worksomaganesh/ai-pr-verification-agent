"""FastAPI webhook ingress: authenticate raw bytes, normalize, then durably enqueue."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from verification_core.delivery_store import DeliveryStoreError, SQLiteDeliveryStore
from verification_core.webhooks import (
    DEFAULT_MAX_WEBHOOK_BODY_BYTES,
    parse_pull_request_webhook,
    verify_github_signature,
)


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


async def _read_bounded_body(request: Request, maximum_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        if not content_length.isdigit():
            raise ValueError("invalid content length")
        if int(content_length) > maximum_bytes:
            raise OverflowError("request body too large")
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > maximum_bytes:
            raise OverflowError("request body too large")
        chunks.extend(chunk)
    return bytes(chunks)


def create_webhook_app(
    *,
    webhook_secret: str,
    delivery_store: SQLiteDeliveryStore,
    max_body_bytes: int = DEFAULT_MAX_WEBHOOK_BODY_BYTES,
) -> FastAPI:
    """Build a webhook-only ASGI app with injected secret and durable event store.

    Configure the GitHub App to subscribe to pull_request events. The service
    acknowledges only after the delivery has been committed to the durable ledger.
    """
    if not isinstance(webhook_secret, str) or not webhook_secret:
        raise ValueError("webhook_secret must not be empty")
    if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 10 * 1024 * 1024:
        raise ValueError("max_body_bytes must be between 1 byte and 10 MiB")

    app = FastAPI(
        title="AI PR Verification Agent webhook ingress",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/github", include_in_schema=False)
    async def github_webhook(request: Request) -> Response:
        signature = request.headers.get("x-hub-signature-256")
        delivery_id = request.headers.get("x-github-delivery")
        event_name = request.headers.get("x-github-event")
        try:
            raw_body = await _read_bounded_body(request, max_body_bytes)
        except OverflowError:
            return JSONResponse(status_code=413, content={"error": "payload_too_large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "invalid_request_body"})

        if not verify_github_signature(
            raw_body, signature, webhook_secret, max_body_bytes=max_body_bytes
        ):
            return JSONResponse(status_code=401, content={"error": "invalid_signature"})
        if not delivery_id or not event_name:
            return JSONResponse(status_code=400, content={"error": "missing_github_headers"})

        try:
            payload = json.loads(
                raw_body.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("invalid constant")),
            )
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            event = parse_pull_request_webhook(
                delivery_id=delivery_id,
                event_name=event_name,
                payload=payload,
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "invalid_webhook_payload"})

        if event is None:
            return Response(status_code=204)
        if event.installation_id is None:
            return JSONResponse(status_code=400, content={"error": "missing_app_installation"})

        try:
            result = delivery_store.enqueue(event)
        except DeliveryStoreError:
            # Never acknowledge an event that was not durably accepted.
            return JSONResponse(status_code=503, content={"error": "delivery_store_unavailable"})
        return JSONResponse(
            status_code=202,
            content={
                "accepted": result.accepted,
                "duplicate": result.duplicate,
                "delivery_id": event.delivery_id,
                "status": result.status,
            },
        )

    return app


def create_app_from_environment(
    *, database_path: str | None = None, environ: Mapping[str, str] | None = None
) -> FastAPI:
    """Construct the ingress app from deployment environment without import-time side effects."""
    environment = os.environ if environ is None else environ
    secret = environment.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        raise RuntimeError("GITHUB_WEBHOOK_SECRET must be configured.")
    path = database_path or environment.get(
        "VERIFICATION_DATABASE_PATH", "verification-events.sqlite3"
    )
    return create_webhook_app(
        webhook_secret=secret,
        delivery_store=SQLiteDeliveryStore(path),
    )
