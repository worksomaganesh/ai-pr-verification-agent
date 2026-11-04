"""HTTP-boundary tests for the authenticated GitHub Actions client."""

from __future__ import annotations

import httpx
import pytest

from verification_core.github_actions import GitHubActionsAPIError, GitHubActionsClient
from verification_core.github_app import GitHubResponseTooLarge

REPO = "acme/service"
INSTALLATION_FIXTURE = "fixture-value"


def test_get_workflow_run_uses_authenticated_api_and_checks_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/repos/{REPO}/actions/runs/99"
        assert request.headers["Authorization"] == f"Bearer {INSTALLATION_FIXTURE}"
        return httpx.Response(200, json={"id": 99, "event": "pull_request"})

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        assert client.get_workflow_run(REPO, 99)["id"] == 99


def test_get_workflow_run_rejects_mismatched_response_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 100})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="requested ID"):
            client.get_workflow_run(REPO, 99)


def test_workflow_run_listing_filters_exact_head_and_paginates() -> None:
    sha = "a" * 40
    requests: list[httpx.Request] = []
    pages = {
        1: [{"id": 1, "head_sha": sha}, {"id": 2, "head_sha": sha}],
        2: [{"id": 3, "head_sha": sha}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == f"/repos/{REPO}/actions/runs"
        assert request.url.params["head_sha"] == sha
        assert request.url.params["event"] == "pull_request"
        return httpx.Response(
            200,
            json={
                "total_count": 3,
                "workflow_runs": pages[int(request.url.params["page"])],
            },
        )

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        result = client.list_pull_request_workflow_runs(REPO, sha)
    assert [item["id"] for item in result] == [1, 2, 3]
    assert [int(request.url.params["page"]) for request in requests] == [1, 2]


def test_workflow_run_listing_rejects_wrong_head_and_bad_sha() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "workflow_runs": [{"id": 1, "head_sha": "b" * 40}],
            },
        )

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="different head SHA"):
            client.list_pull_request_workflow_runs(REPO, "a" * 40)
        with pytest.raises(ValueError, match="head_sha"):
            client.list_pull_request_workflow_runs(REPO, "BAD")


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ([{"total_count": "1", "workflow_runs": []}], "invalid total_count"),
        ([{"total_count": -1, "workflow_runs": []}], "invalid total_count"),
        ([{"total_count": 1, "workflow_runs": {}}], "malformed"),
        ([{"total_count": 1, "workflow_runs": [None]}], "malformed item"),
        (
            [{"total_count": 1, "workflow_runs": [{"id": 0, "head_sha": "a" * 40}]}],
            "invalid ID",
        ),
        (
            [
                {
                    "total_count": 2,
                    "workflow_runs": [
                        {"id": 5, "head_sha": "a" * 40},
                        {"id": 5, "head_sha": "a" * 40},
                    ],
                }
            ],
            "duplicate IDs",
        ),
        (
            [
                {"total_count": 2, "workflow_runs": [{"id": 1, "head_sha": "a" * 40}]},
                {"total_count": 3, "workflow_runs": [{"id": 2, "head_sha": "a" * 40}]},
            ],
            "pagination changed",
        ),
        ([{"total_count": 1, "workflow_runs": []}], "ended before"),
    ],
    ids=(
        "text-total",
        "negative-total",
        "non-list-runs",
        "non-object-run",
        "non-positive-run-id",
        "duplicate-run-id",
        "changing-pagination-total",
        "missing-page-items",
    ),
)
def test_workflow_run_listing_rejects_malformed_or_incomplete_api_responses(
    responses: list[dict[str, object]], message: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json=responses[min(page - 1, len(responses) - 1)])

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match=message):
            client.list_pull_request_workflow_runs(REPO, "a" * 40)


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
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
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
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="pagination changed"):
            client.list_workflow_run_jobs(REPO, 99)

    def missing_items(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_count": 1, "jobs": []})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(missing_items)
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
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
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
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
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        assert client.download_workflow_artifact(REPO, 7) == archive_bytes

    assert seen == [
        ("api.github.com", f"Bearer {INSTALLATION_FIXTURE}"),
        ("pipelines.actions.githubusercontent.com", None),
    ]


def test_artifact_download_rejects_untrusted_redirect_and_oversize_body() -> None:
    def bad_redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/archive"})

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(bad_redirect)
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="disallowed host"):
            client.download_workflow_artifact(REPO, 7)

    def large_body(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"12345")

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(large_body)
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw, max_archive_bytes=4)
        with pytest.raises(GitHubResponseTooLarge):
            client.download_workflow_artifact(REPO, 7)


def test_client_rejects_invalid_ids_and_repository_paths() -> None:
    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"id": 1})),
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
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
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="disallowed host"):
            client.download_workflow_artifact(REPO, 7)

    assert visited == ["api.github.com"]


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (403, "rejected"),
        (429, "rejected"),
        (404, "download failed"),
        (500, "download failed"),
    ],
    ids=("forbidden", "rate-limited", "not-found", "server-error"),
)
def test_artifact_download_rejects_github_error_statuses(status: int, message: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "untrusted error body"})

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match=message):
            client.download_workflow_artifact(REPO, 7)


def test_artifact_download_rejects_missing_redirect_and_failed_signed_download() -> None:
    def no_location(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302)

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(no_location),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="disallowed host"):
            client.download_workflow_artifact(REPO, 7)

    signed_url = "https://pipelines.actions.githubusercontent.com/signed/archive"

    def failed_signed_download(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"Location": signed_url})
        return httpx.Response(503)

    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(failed_signed_download),
        follow_redirects=False,
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        with pytest.raises(GitHubActionsAPIError, match="signed artifact download failed"):
            client.download_workflow_artifact(REPO, 7)


@pytest.mark.parametrize(
    ("token", "limit"),
    [
        ("", 10),
        ("  ", 10),
        (INSTALLATION_FIXTURE, 0),
        (INSTALLATION_FIXTURE, 20 * 1024 * 1024 + 1),
        (INSTALLATION_FIXTURE, True),
    ],
    ids=("empty-token", "whitespace-token", "zero-limit", "oversized-limit", "boolean-limit"),
)
def test_client_constructor_rejects_unsafe_configuration(token: str, limit: int) -> None:
    with pytest.raises(ValueError):
        GitHubActionsClient(token, max_archive_bytes=limit)


def test_client_rejects_malformed_repository_names() -> None:
    with httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"id": 1})),
    ) as raw:
        client = GitHubActionsClient(INSTALLATION_FIXTURE, http_client=raw)
        for repository in (
            "../acme/service",
            "acme//service",
            "acme/service?query",
            "acme/../service",
            "acme/service#fragment",
        ):
            with pytest.raises(GitHubActionsAPIError, match="owner/name"):
                client.get_workflow_run(repository, 1)
