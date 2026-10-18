"""Adversarial tests for authenticated Actions evidence ingestion."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from verification_core.actions_evidence import ActionsEvidenceError, ingest_authenticated_artifact
from verification_core.domain.models import CommitIdentity
from verification_core.github_actions import _artifact_redirect_is_allowed

BASE = "1" * 40
HEAD = "2" * 40
POLICY = "a" * 64
REPO = "acme/service"
JUNIT = (
    b'<testsuite tests="1"><testcase classname="tests.test_auth" name="test_access"/></testsuite>'
)
NODE = "tests.test_auth::test_access"
MANIFEST = json.dumps(
    {
        "version": 1,
        "head_sha": HEAD,
        "tests": [
            {
                "node_id": NODE,
                "outcome": "passed",
                "lines": {"src/auth.py": [10]},
                "branches": {"src/auth.py": ["10:0"]},
                "behavioral_assertion_verified": True,
            }
        ],
    }
).encode()


def identity() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name=REPO,
        pr_number=7,
        base_sha=BASE,
        head_sha=HEAD,
        policy_sha256=POLICY,
    )


def archive(files: dict[str, bytes] | None = None) -> bytes:
    files = files or {"junit.xml": JUNIT, "coverage-manifest.json": MANIFEST}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return output.getvalue()


def metadata(payload: bytes, *, digest: str | None = None) -> dict[str, object]:
    return {
        "id": 55,
        "name": "verification-evidence",
        "expired": False,
        "size_in_bytes": len(payload),
        "digest": "sha256:" + (digest or hashlib.sha256(payload).hexdigest()),
        "workflow_run": {"id": 99, "repository_id": 123},
    }


def run(
    *, head: str = HEAD, path: str = ".github/workflows/ci.yml@refs/heads/main"
) -> dict[str, object]:
    return {
        "id": 99,
        "workflow_id": 12,
        "run_attempt": 1,
        "path": path,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "head_sha": head,
        "repository": {"full_name": REPO, "id": 123},
        "pull_requests": [{"number": 7, "base": {"sha": BASE}, "head": {"sha": head}}],
    }


def jobs() -> list[dict[str, object]]:
    return [
        {
            "status": "completed",
            "conclusion": "success",
            "steps": [
                {
                    "name": "Upload verification evidence",
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
        }
    ]


def ingest(payload: bytes | None = None, **overrides: object):
    data = payload or archive()
    args: dict[str, object] = {
        "commit": identity(),
        "run_payload": run(),
        "jobs": jobs(),
        "artifact_metadata": metadata(data),
        "archive_bytes": data,
        "trusted_workflow_paths": [".github/workflows/ci.yml"],
        "harness_sensitive_paths": [
            ".github/workflows/",
            ".verification-policy.yml",
            "conftest.py",
        ],
        "changed_paths": ["src/auth.py"],
    }
    args.update(overrides)
    return ingest_authenticated_artifact(**args)  # type: ignore[arg-type]


def test_ingest_binds_run_artifact_and_reports_to_exact_commit() -> None:
    result = ingest()
    assert result.workflow_run_id == 99
    assert result.artifact_id == 55
    assert result.head_sha == HEAD
    assert result.provenance.is_authentic_and_trusted(identity())
    assert result.junit_report.total_tests == 1
    assert result.coverage_manifest.head_sha == HEAD


@pytest.mark.parametrize(
    "payload",
    [
        run(head="3" * 40),
        run(path=".github/workflows/untrusted.yml@refs/heads/main"),
        {**run(), "event": "push"},
        {**run(), "conclusion": "failure"},
    ],
)


def test_rejects_stale_untrusted_or_unsuccessful_workflow(payload: dict[str, object]) -> None:
    with pytest.raises(ActionsEvidenceError):
        ingest(run_payload=payload)


def test_rejects_harness_changes_and_missing_evidence_step() -> None:
    with pytest.raises(ActionsEvidenceError, match="harness-sensitive"):
        ingest(changed_paths=[".github/workflows/ci.yml"])
    with pytest.raises(ActionsEvidenceError, match="evidence-upload step"):
        ingest(jobs=[])


def test_rejects_forged_digest_wrong_run_or_stale_manifest() -> None:
    data = archive()
    with pytest.raises(ActionsEvidenceError, match="SHA-256 digest"):
        ingest(artifact_metadata=metadata(data, digest="0" * 64))
    wrong_run = metadata(data)
    wrong_run["workflow_run"] = {"id": 100, "repository_id": 123}
    with pytest.raises(ActionsEvidenceError, match="different workflow run"):
        ingest(artifact_metadata=wrong_run)
    stale = archive(
        {"junit.xml": JUNIT, "coverage-manifest.json": MANIFEST.replace(HEAD.encode(), b"3" * 40)}
    )
    with pytest.raises(ActionsEvidenceError, match=r"SHA-256 digest|stale"):
        ingest(stale)


def test_rejects_extra_files_traversal_and_contradictory_reports() -> None:
    extra = archive({"junit.xml": JUNIT, "coverage-manifest.json": MANIFEST, "../evil": b"x"})
    with pytest.raises(ActionsEvidenceError):
        ingest(extra)
    contradictory = MANIFEST.replace(b'"outcome": "passed"', b'"outcome": "failed"')
    with pytest.raises(ActionsEvidenceError, match="contradict"):
        ingest(archive({"junit.xml": JUNIT, "coverage-manifest.json": contradictory}))


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example/artifact",
        "https://user:pass@githubusercontent.com/artifact",
        "https://evil.example/artifact",
        "https://githubusercontent.com:444/artifact",
        "//githubusercontent.com/artifact",
    ],
)


def test_artifact_redirect_rejects_untrusted_urls(url: str) -> None:
    assert not _artifact_redirect_is_allowed(url)


def test_artifact_redirect_allows_https_signed_storage_url() -> None:
    assert _artifact_redirect_is_allowed(
        "https://pipelines.actions.githubusercontent.com/signed/path"
    )


def test_rejects_archive_size_that_disagrees_with_api_metadata() -> None:
    data = archive()
    artifact = metadata(data)
    artifact["size_in_bytes"] = len(data) + 1
    with pytest.raises(ActionsEvidenceError, match="size does not match"):
        ingest(artifact_metadata=artifact)


class _FakePRReader:
    def __init__(self, *, move_head_after_first_read: bool = False) -> None:
        self.calls = 0
        self.move_head_after_first_read = move_head_after_first_read

    def get_pull_request(self, repository: str, pr_number: int) -> dict[str, object]:
        assert repository == REPO
        assert pr_number == 7
        self.calls += 1
        head = HEAD
        if self.move_head_after_first_read and self.calls > 1:
            head = "3" * 40
        return {"state": "open", "base": {"sha": BASE}, "head": {"sha": head}}

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        assert repository == REPO
        assert path == ".github/workflows/ci.yml"
        assert ref == BASE
        return "name: trusted-ci\non: pull_request\njobs: {}\n"


class _FakeActionsReader:
    def __init__(self, *, artifacts: list[dict[str, object]] | None = None) -> None:
        self.artifacts = artifacts
        self.run_payload = run()

    def get_workflow_run(self, repository: str, run_id: int) -> dict[str, object]:
        assert repository == REPO
        assert run_id == 99
        return self.run_payload

    def list_workflow_run_jobs(self, repository: str, run_id: int) -> tuple[dict[str, object], ...]:
        return tuple(jobs())

    def list_workflow_run_artifacts(
        self, repository: str, run_id: int
    ) -> tuple[dict[str, object], ...]:
        data = archive()
        return tuple(self.artifacts) if self.artifacts is not None else (metadata(data),)

    def download_workflow_artifact(self, repository: str, artifact_id: int) -> bytes:
        assert repository == REPO
        assert artifact_id == 55
        return archive()


def test_phase_three_service_binds_base_workflow_and_rechecks_pr() -> None:
    from verification_core.phase_three import ingest_pull_request_run

    pr_reader = _FakePRReader()
    result = ingest_pull_request_run(
        github=pr_reader,
        actions=_FakeActionsReader(),
        commit=identity(),
        workflow_run_id=99,
        trusted_workflow_paths=(".github/workflows/ci.yml",),
        harness_sensitive_paths=(
            ".github/workflows/",
            ".verification-policy.yml",
            "conftest.py",
        ),
        changed_paths=("src/auth.py",),
    )
    assert result.evidence.workflow_run_id == 99
    assert result.evidence.artifact_id == 55
    assert len(result.workflow_definition_sha256) == 64
    assert pr_reader.calls == 2


def test_phase_three_service_rejects_missing_or_ambiguous_artifacts() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    data = archive()
    one = metadata(data)
    common = {
        "github": _FakePRReader(),
        "commit": identity(),
        "workflow_run_id": 99,
        "trusted_workflow_paths": (".github/workflows/ci.yml",),
        "harness_sensitive_paths": (".github/workflows/", "conftest.py"),
        "changed_paths": ("src/auth.py",),
    }
    with pytest.raises(EvidenceIngestionServiceError, match="exactly one"):
        ingest_pull_request_run(**common, actions=_FakeActionsReader(artifacts=[]))
    with pytest.raises(EvidenceIngestionServiceError, match="exactly one"):
        ingest_pull_request_run(
            **common,
            actions=_FakeActionsReader(artifacts=[one, {**one, "id": 56}]),
        )


def test_phase_three_service_rejects_pr_head_moving_during_ingestion() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    with pytest.raises(EvidenceIngestionServiceError, match="changed during"):
        ingest_pull_request_run(
            github=_FakePRReader(move_head_after_first_read=True),
            actions=_FakeActionsReader(),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )
