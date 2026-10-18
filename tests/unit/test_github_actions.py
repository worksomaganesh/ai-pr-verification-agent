"""HTTP-boundary tests for the authenticated GitHub Actions client."""

from __future__ import annotations

import httpx
import pytest

from verification_core.github_app import GitHubResponseTooLarge
from verification_core.github_actions import GitHubActionsAPIError, GitHubActionsClient


REPO = "acme/service"
TOKEN = "test-installation-token"


def test_get_workflow_run_uses_authenticated_api_and_checks_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/repos/{REPO}/actions/runs/99"
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        return httpx.Response(200, json={"id": 99, "event": "pull_request"})

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        assert client.get_workflow_run(REPO, 99)["id"] == 99


def test_get_workflow_run_rejects_mismatched_response_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 100})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="requested ID"):
            client.get_workflow_run(REPO, 99)


def test_job_listing_retrieves_every_page() -> None:
    requests: list[httpx.Request] = []
    pages = {
        1: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"total_count": 3, "jobs": pages[page]})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        result = client.list_workflow_run_jobs(REPO, 99)

    assert [item["id"] for item in result] == [1, 2, 3]
    assert [int(req.url.params["page"]) for req in requests] == [1, 2]
    assert all(req.url.params["per_page"] == "100" for req in requests)


def test_pagination_rejects_count_changes_and_missing_pages() -> None:
    def changing_count(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        total = 2 if page == 1 else 3
        items = [{"id": page}]
        return httpx.Response(200, json={"total_count": total, "jobs": items})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(changing_count)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="pagination changed"):
            client.list_workflow_run_jobs(REPO, 99)

    def missing_items(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_count": 1, "jobs": []})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(missing_items)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="ended before"):
            client.list_workflow_run_jobs(REPO, 99)


def test_artifact_listing_rejects_artifact_from_another_run() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "artifacts": [{"id": 7, "workflow_run": {"id": 100}}],
            },
        )

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="requested workflow run"):
            client.list_workflow_run_artifacts(REPO, 99)


def test_artifact_download_does_not_forward_installation_token() -> None:
    signed_url = "https://pipelines.actions.githubusercontent.com/signed/archive"
    archive_bytes = b"zip-content"
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("Authorization")))
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"Location": signed_url})
        return httpx.Response(200, content=archive_bytes)

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        assert client.download_workflow_artifact(REPO, 7) == archive_bytes

    assert seen == [
        ("api.github.com", f"Bearer {TOKEN}"),
        ("pipelines.actions.githubusercontent.com", None),
    ]


def test_artifact_download_rejects_untrusted_redirect_and_oversize_body() -> None:
    def bad_redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/archive"})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(bad_redirect)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="disallowed host"):
            client.download_workflow_artifact(REPO, 7)

    def large_body(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"12345")

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(large_body)
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw, max_archive_bytes=4)
        with pytest.raises(GitHubResponseTooLarge):
            client.download_workflow_artifact(REPO, 7)


def test_client_rejects_invalid_ids_and_repository_paths() -> None:
    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"id": 1})),
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(ValueError, match="run_id"):
            client.get_workflow_run(REPO, 0)
        with pytest.raises(GitHubActionsAPIError, match="owner/name"):
            client.get_workflow_run("../acme/service", 1)


def test_artifact_redirect_is_not_auto_followed_even_with_redirects_enabled() -> None:
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.host)
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"Location": "https://evil.example/collect"})
        return httpx.Response(200, content=b"should never be downloaded")

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as raw:
        client = GitHubActionsClient(TOKEN, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="disallowed host"):
            client.download_workflow_artifact(REPO, 7)

    assert visited == ["api.github.com"]
