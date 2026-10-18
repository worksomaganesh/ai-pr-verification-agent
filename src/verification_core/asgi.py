"""ASGI entry point for Uvicorn; requires deployment environment variables."""

from verification_core.runtime import create_webhook_app_from_environment

app = create_webhook_app_from_environment()
