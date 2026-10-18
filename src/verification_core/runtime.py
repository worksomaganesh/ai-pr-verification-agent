"""Deployment wiring for the Phase II webhook and worker processes."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI

from verification_core.delivery_store import SQLiteDeliveryStore
from verification_core.gemini_planner import gemini_model_from_environment
from verification_core.github_app import GitHubAppAuthenticator
from verification_core.phase_two import PhaseTwoProcessor
from verification_core.webhook_app import create_app_from_environment


def _private_key(environment: Mapping[str, str]) -> str:
    key_path = environment.get("GITHUB_APP_PRIVATE_KEY_PATH", "")
    if key_path:
        path = Path(key_path)
        if not path.is_file():
            raise RuntimeError("GITHUB_APP_PRIVATE_KEY_PATH must reference a readable PEM file.")
        if path.stat().st_size > 128 * 1024:
            raise RuntimeError("GitHub App private key file exceeds 128 KiB.")
        key = path.read_text(encoding="utf-8")
    else:
        key = environment.get("GITHUB_APP_PRIVATE_KEY", "")
    if not key or "PRIVATE KEY" not in key:
        raise RuntimeError(
            "Configure GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY with a PEM key."
        )
    return key


def create_processor_from_environment(
    environ: Mapping[str, str] | None = None,
) -> tuple[PhaseTwoProcessor, SQLiteDeliveryStore, GitHubAppAuthenticator]:
    """Build the worker from explicit environment configuration without printing secrets."""
    environment = os.environ if environ is None else environ
    app_id_text = environment.get("GITHUB_APP_ID", "")
    if not app_id_text.isdigit() or int(app_id_text) < 1:
        raise RuntimeError("GITHUB_APP_ID must be a positive integer.")
    database_path = environment.get(
        "VERIFICATION_DATABASE_PATH", "verification-events.sqlite3"
    )
    store = SQLiteDeliveryStore(database_path)
    authenticator = GitHubAppAuthenticator(
        int(app_id_text),
        _private_key(environment),
    )
    model = gemini_model_from_environment(environment)
    processor = PhaseTwoProcessor(
        store=store,
        authenticator=authenticator,
        model_factory=lambda: model,
    )
    return processor, store, authenticator


def create_webhook_app_from_environment(environ: dict[str, str] | None = None):
    """Create the ASGI ingress app with the configured durable SQLite store."""
    environment = os.environ if environ is None else environ
    return create_app_from_environment(
        database_path=environment.get(
            "VERIFICATION_DATABASE_PATH", "verification-events.sqlite3"
        ),
        environ=environment,
    )
