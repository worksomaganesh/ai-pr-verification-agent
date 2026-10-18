"""Tests for runtime environment validation and CLI argument bounds."""

from __future__ import annotations

from pathlib import Path
import pytest

from verification_core.runtime import (
    _private_key,
    create_processor_from_environment,
    create_webhook_app_from_environment,
)


def test_private_key_can_be_loaded_from_file(tmp_path: Path) -> None:
    path = tmp_path / "app.pem"
    path.write_text("-----BEGIN PRIVATE KEY-----\nfake\n", encoding="utf-8")
    assert "PRIVATE KEY" in _private_key({"GITHUB_APP_PRIVATE_KEY_PATH": str(path)})


def test_private_key_rejects_missing_or_oversized_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Configure"):
        _private_key({})
    with pytest.raises(RuntimeError, match="readable PEM"):
        _private_key({"GITHUB_APP_PRIVATE_KEY_PATH": str(tmp_path / "missing.pem")})
    large = tmp_path / "large.pem"
    large.write_text("x" * (128 * 1024 + 1), encoding="utf-8")
    with pytest.raises(RuntimeError, match="128 KiB"):
        _private_key({"GITHUB_APP_PRIVATE_KEY_PATH": str(large)})


def test_webhook_app_environment_requires_secret_and_builds_app(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="GITHUB_WEBHOOK_SECRET"):
        create_webhook_app_from_environment({})
    app = create_webhook_app_from_environment(
        {
            "GITHUB_WEBHOOK_SECRET": "test-secret",
            "VERIFICATION_DATABASE_PATH": str(tmp_path / "webhooks.sqlite3"),
        }
    )
    assert app.title == "AI PR Verification Agent webhook ingress"


def test_worker_environment_requires_app_id_and_key(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="GITHUB_APP_ID"):
        create_processor_from_environment({})
    with pytest.raises(RuntimeError, match="GITHUB_APP_PRIVATE_KEY"):
        create_processor_from_environment(
            {"GITHUB_APP_ID": "123", "VERIFICATION_DATABASE_PATH": str(tmp_path / "events.sqlite3")}
        )


def test_worker_environment_builds_processor_without_model(tmp_path: Path) -> None:
    processor, store, authenticator = create_processor_from_environment(
        {
            "GITHUB_APP_ID": "123",
            "GITHUB_APP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\nfake\n",
            "VERIFICATION_DATABASE_PATH": str(tmp_path / "events.sqlite3"),
        }
    )
    assert processor is not None
    assert store is not None
    authenticator.close()


@pytest.mark.parametrize("app_id", ["", "0", "-1", "abc"])
def test_worker_rejects_invalid_app_id(app_id: str, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="GITHUB_APP_ID"):
        create_processor_from_environment(
            {
                "GITHUB_APP_ID": app_id,
                "GITHUB_APP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----",
                "VERIFICATION_DATABASE_PATH": str(tmp_path / "events.sqlite3"),
            }
        )
