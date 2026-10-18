"""Command-line entry point for Phase II ingress and queue worker."""

from __future__ import annotations

import argparse
import os
import time

import uvicorn

from verification_core.runtime import create_processor_from_environment


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ai-pr-verification-agent",
        description="Run the Phase II webhook ingress or durable event worker.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="start the GitHub webhook HTTP ingress")
    serve.add_argument("--host", default=os.environ.get("WEBHOOK_HOST", "127.0.0.1"))
    serve.add_argument(
        "--port",
        type=_positive_int,
        default=_positive_int(os.environ.get("WEBHOOK_PORT", "8000")),
    )
    worker = subparsers.add_parser("worker", help="process queued webhook deliveries")
    worker.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.environ.get("WORKER_POLL_SECONDS", "1.0")),
    )
    args = parser.parse_args()

    if args.command == "serve":
        if args.port > 65535:
            parser.error("--port must be <= 65535")
        uvicorn.run(
            "verification_core.asgi:app",
            host=args.host,
            port=args.port,
            log_level=os.environ.get("WEBHOOK_LOG_LEVEL", "info"),
            access_log=False,
        )
        return 0

    if args.poll_seconds <= 0 or args.poll_seconds > 60:
        parser.error("--poll-seconds must be greater than 0 and at most 60")
    processor, _store, authenticator = create_processor_from_environment()
    try:
        while True:
            result = processor.process_next()
            if result is None or result.status == "retrying":
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            processor.close()
        finally:
            authenticator.close()


if __name__ == "__main__":
    raise SystemExit(main())
