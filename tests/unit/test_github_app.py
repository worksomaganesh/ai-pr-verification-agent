"""Tests for bounded GitHub App auth, read-only REST access, and Checks API writes."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from verification_core.github_app import (
    GitHubAPIError,
    GitHubAppAuthenticator,
    GitHubRESTClient,
    GitHubResponseTooLarge,
)

HEAD = "2" * 40
TREE = "3" * 40
BASE = "1" * 40


def make_client(handler: Any) -> tuple[GitHubRESTClient, httpx.Client]:
    transport = httpx.MockTransport(handler)
    raw = httpx.Client(transport=transport, base_url="https://api.github.com")
    return GitHubRESTClient("installation-token", http_client=raw), raw


def json_response(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_github_app_jwt_and_installation_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return json_response(
            {"token": "ghs-installation-token", "expires_at": "2030-01-01T00:00:00Z"}
        )

    raw = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")
    authenticator = GitHubAppAuthenticator(123, private_pem, http_client=raw)
    app_jwt = authenticator.create_app_jwt(now=1_800_000_000)
    claims = jwt.decode(
        app_jwt,
        public_pem,
        algorithms=["RS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert claims["iss"] == 123
    assert claims["iat"] == 1_799_999_970
    assert seen == {}
    token = authenticator.create_installation_token(456)
    assert token.token == "ghs-installation-token"
    assert token.expires_at.tzinfo is not None
    assert seen["path"] == "/app/installations/456/access_tokens"
    assert str(seen["authorization"]).startswith("Bearer ")
    assert seen["body"]["permissions"] == {
        "contents": "read",
        "pull_requests": "read",
        "checks": "write",
    }
    with pytest.raises(ValueError):
        authenticator.create_installation_token(0)
    authenticator.close()
    raw.close()


@pytest.mark.parametrize("app_id", [0, -1, True])
def test_authenticator_rejects_invalid_app_ids(app_id: int) -> None:
    with pytest.raises(ValueError):
        GitHubAppAuthenticator(app_id, "-----BEGIN PRIVATE KEY-----")


def test_authenticator_rejects_bad_private_key() -> None:
    authenticator = GitHubAppAuthenticator(123, "-----BEGIN PRIVATE KEY-----")
    with pytest.raises(GitHubAPIError, match="could not sign"):
        authenticator.create_app_jwt(now=1_800_000_000)
    authenticator.close()


def test_rest_client_validates_constructor_and_repository() -> None:
    with pytest.raises(ValueError):
        GitHubRESTClient("")
    client, raw = make_client(lambda _request: json_response({}))
    with pytest.raises(GitHubAPIError, match="owner/name"):
        client.get_pull_request("../evil", 1)
    with pytest.raises(ValueError):
        client.get_pull_request("acme/repo", 0)
    client.close()
    raw.close()


def test_pull_request_and_paginated_files_are_parsed() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/pulls/5"):
            return json_response({"state": "open", "number": 5})
        if request.url.path.endswith("/pulls/5/files"):
            page = request.url.params["page"]
            if page == "1":
                return json_response([{"filename": "src/a.py"}])
            return json_response([])
        return json_response({"message": "not found"}, 404)

    client, raw = make_client(handler)
    assert client.get_pull_request("acme/repo", 5)["state"] == "open"
    assert (
        client.list_pull_request_files("acme/repo", 5, page=1, per_page=100)[0]["filename"]
        == "src/a.py"
    )
    assert client.list_pull_request_files("acme/repo", 5, page=2, per_page=100) == ()
    assert len(seen) == 3
    with pytest.raises(ValueError):
        client.list_pull_request_files("acme/repo", 5, page=0, per_page=100)
    with pytest.raises(ValueError):
        client.list_pull_request_files("acme/repo", 5, page=1, per_page=101)
    client.close()
    raw.close()


def test_content_is_loaded_at_exact_sha_and_bounded() -> None:
    encoded = base64.b64encode(b"print('safe')\n").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["ref"] == BASE
        return json_response({"type": "file", "encoding": "base64", "content": encoded})

    client, raw = make_client(handler)
    assert client.get_file_content("acme/repo", "tests/test_example.py", BASE) == "print('safe')\n"
    with pytest.raises(GitHubAPIError, match="unsafe repository file"):
        client.get_file_content("acme/repo", "../secret", BASE)
    with pytest.raises(GitHubAPIError, match="exact 40-character"):
        client.get_file_content("acme/repo", "tests/test_example.py", "bad")
    client.close()
    raw.close()


def test_missing_content_returns_none_and_bad_base64_fails_closed() -> None:
    def missing(_request: httpx.Request) -> httpx.Response:
        return json_response({"message": "not found"}, 404)

    client, raw = make_client(missing)
    assert client.get_file_content("acme/repo", "tests/test_x.py", BASE) is None
    client.close()
    raw.close()

    client, raw = make_client(
        lambda _request: json_response(
            {"type": "file", "encoding": "base64", "content": "!!!"}
        )
    )
    with pytest.raises(GitHubAPIError, match="base64 UTF-8"):
        client.get_file_content("acme/repo", "tests/test_x.py", BASE)
    client.close()
    raw.close()


def test_test_inventory_uses_commit_tree_and_parses_ast_without_execution() -> None:
    source = "def test_top():\n    assert True\n\nclass TestGroup:\n    def test_nested(self):\n        pass\n"
    encoded = base64.b64encode(source.encode()).decode()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith(f"/git/commits/{HEAD}"):
            return json_response({"tree": {"sha": TREE}})
        if request.url.path.endswith(f"/git/trees/{TREE}"):
            return json_response(
                {
                    "truncated": False,
                    "tree": [
                        {"path": "tests/test_example.py", "type": "blob"},
                        {"path": "src/not_a_test.py", "type": "blob"},
                    ],
                }
            )
        if request.url.path.endswith("/contents/tests/test_example.py"):
            return json_response({"type": "file", "encoding": "base64", "content": encoded})
        raise AssertionError(f"unexpected path {request.url.path}")

    client, raw = make_client(handler)
    inventory = client.list_test_inventory("acme/repo", HEAD)
    assert [item.selector for item in inventory] == [
        "tests/test_example.py::TestGroup::test_nested",
        "tests/test_example.py::test_top",
    ]
    assert f"/repos/acme/repo/git/commits/{HEAD}" in seen
    assert f"/repos/acme/repo/git/trees/{TREE}" in seen
    client.close()
    raw.close()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"tree": {"sha": "bad"}}, "tree SHA"),
        ({"tree": {"sha": TREE}}, "truncated"),
    ],
)
def test_test_inventory_rejects_malformed_tree(payload: object, message: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/git/commits/{HEAD}"):
            return json_response(payload)
        return json_response({"truncated": True, "tree": []})

    client, raw = make_client(handler)
    with pytest.raises(GitHubAPIError, match=message):
        client.list_test_inventory("acme/repo", HEAD)
    client.close()
    raw.close()


def test_check_run_is_created_then_updated_by_external_id() -> None:
    state: dict[str, Any] = {"id": 55, "external_id": "aiprv:5:" + HEAD, "created": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if state["created"]:
                return json_response({"check_runs": [{"id": 55, "external_id": state["external_id"]}]})
            return json_response({"check_runs": []})
        if request.method == "POST":
            state["created"] = True
            body = json.loads(request.content)
            assert body["conclusion"] == "action_required"
            return json_response({"id": 55}, 201)
        if request.method == "PATCH":
            body = json.loads(request.content)
            assert body["output"]["summary"] == "safe summary"
            return json_response({"id": 55}, 200)
        raise AssertionError("unexpected request method")

    client, raw = make_client(handler)
    created = client.publish_check_run(
        repository="acme/repo",
        head_sha=HEAD,
        name="AI PR Verification",
        conclusion="action_required",
        title="Evidence required",
        summary="safe summary",
        external_id=state["external_id"],
    )
    updated = client.publish_check_run(
        repository="acme/repo",
        head_sha=HEAD,
        name="AI PR Verification",
        conclusion="action_required",
        title="Evidence required",
        summary="safe summary",
        external_id=state["external_id"],
    )
    assert created == updated == 55
    client.close()
    raw.close()


@pytest.mark.parametrize("conclusion", ["stale", "unknown", ""])
def test_check_run_rejects_unsupported_conclusions(conclusion: str) -> None:
    client, raw = make_client(lambda _request: json_response({"check_runs": []}))
    with pytest.raises(ValueError):
        client.publish_check_run(
            repository="acme/repo",
            head_sha=HEAD,
            name="AI PR Verification",
            conclusion=conclusion,
            title="title",
            summary="summary",
            external_id="x",
        )
    client.close()
    raw.close()


def test_transport_errors_and_large_responses_are_sanitized() -> None:
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return json_response({"message": "token=secret"}, 401)

    client, raw = make_client(unauthorized)
    with pytest.raises(GitHubAPIError, match="authentication failed") as exc:
        client.get_pull_request("acme/repo", 1)
    assert "secret" not in str(exc.value)
    client.close()
    raw.close()

    def large(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "999999999"}, content=b"{}")

    client, raw = make_client(large)
    with pytest.raises(GitHubResponseTooLarge):
        client.get_pull_request("acme/repo", 1)
    client.close()
    raw.close()


def test_rate_limit_is_classified() -> None:
    def limited(_request: httpx.Request) -> httpx.Response:
        return json_response({}, 429,)

    client, raw = make_client(limited)
    with pytest.raises(GitHubAPIError, match="rate limit"):
        client.get_pull_request("acme/repo", 1)
    client.close()
    raw.close()


def test_token_expiry_must_be_timezone_aware() -> None:
    from verification_core.github_app import InstallationToken

    with pytest.raises(ValueError):
        InstallationToken(token="ghs_token", expires_at=datetime.now())
    assert InstallationToken(
        token="ghs_token", expires_at=datetime.now(UTC) + timedelta(hours=1)
    ).token == "ghs_token"
