"""Tests for the Phase II command-line entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import pytest

import verification_core.__main__ as cli


def test_positive_int_parser() -> None:
    assert cli._positive_int("7") == 7
    with pytest.raises(argparse.ArgumentTypeError):
        cli._positive_int("zero")
    with pytest.raises(argparse.ArgumentTypeError):
        cli._positive_int("0")


def test_serve_command_passes_host_and_port_to_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(sys, "argv", ["agent", "serve", "--host", "127.0.0.1", "--port", "9000"])
    monkeypatch.setattr(
        "verification_core.__main__.uvicorn.run", lambda *args, **kwargs: seen.update(kwargs)
    )
    assert cli.main() == 0
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 9000
    assert seen["access_log"] is False


def test_worker_stops_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAuthenticator:
        closed = False

        def close(self) -> None:
            self.closed = True

    class FakeProcessor:
        def process_next(self) -> None:
            return None

    authenticator = FakeAuthenticator()
    monkeypatch.setattr(
        cli,
        "create_processor_from_environment",
        lambda: (FakeProcessor(), object(), authenticator),
    )
    monkeypatch.setattr(sys, "argv", ["agent", "worker", "--poll-seconds", "0.5"])

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("verification_core.__main__.time.sleep", interrupt)
    assert cli.main() == 0
    assert authenticator.closed


def test_worker_rejects_invalid_poll_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["agent", "worker", "--poll-seconds", "0"])
    with pytest.raises(SystemExit):
        cli.main()


def test_serve_rejects_out_of_range_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["agent", "serve", "--port", "65536"])
    with pytest.raises(SystemExit):
        cli.main()
