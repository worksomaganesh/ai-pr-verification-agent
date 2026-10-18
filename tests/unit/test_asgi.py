"""Tests that the deployment ASGI entry point is created from environment configuration."""

from __future__ import annotations

import importlib

from fastapi import FastAPI


def test_asgi_entrypoint_builds_only_after_configuration(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "asgi-test-secret")
    monkeypatch.setenv("VERIFICATION_DATABASE_PATH", str(tmp_path / "asgi.sqlite3"))
    module = importlib.import_module("verification_core.asgi")
    module = importlib.reload(module)
    assert isinstance(module.app, FastAPI)
    assert module.app.title == "AI PR Verification Agent webhook ingress"
