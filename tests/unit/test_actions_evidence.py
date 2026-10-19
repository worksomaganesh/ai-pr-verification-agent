"""Adversarial tests for authenticated Actions evidence ingestion."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

from verification_core.actions_evidence import (
    ActionsEvidenceError,
    AuthenticatedEvidenceArtifact,
    ingest_authenticated_artifact,
)
from verification_core.domain.models import CommitIdentity, VerificationObligation
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


TRUSTED_WORKFLOW = """
name: trusted-ci
on: pull_request
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - name: Upload verification evidence
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: verification-evidence
          path: |
            junit.xml
            coverage-manifest.json
          if-no-files-found: error
"""


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


def ingest(payload: bytes | None = None, **overrides: object) -> AuthenticatedEvidenceArtifact:
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


@pytest.mark.parametrize("payload", [b"", b"not-a-zip-archive"])
def test_archive_reader_rejects_empty_or_malformed_zip(payload: bytes) -> None:
    from verification_core.actions_evidence import _read_zip_members

    with pytest.raises(ActionsEvidenceError, match=r"non-empty bytes|valid ZIP"):
        _read_zip_members(payload)


def test_archive_reader_rejects_too_many_members() -> None:
    from verification_core.actions_evidence import _read_zip_members

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as zip_file:
        for index in range(17):
            zip_file.writestr(f"untrusted-{index}.txt", b"x")
    with pytest.raises(ActionsEvidenceError, match="number of members"):
        _read_zip_members(output.getvalue())


@pytest.mark.parametrize("unsafe_name", ["../junit.xml", "/junit.xml", "folder\\\\junit.xml"])
def test_archive_reader_rejects_unsafe_paths(unsafe_name: str) -> None:
    from verification_core.actions_evidence import _read_zip_members

    with pytest.raises(ActionsEvidenceError, match=r"unsafe member path|path-traversal"):
        _read_zip_members(archive({unsafe_name: JUNIT, "coverage-manifest.json": MANIFEST}))


def test_archive_reader_rejects_duplicate_members() -> None:
    from verification_core.actions_evidence import _read_zip_members

    output = io.BytesIO()
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as zip_file,
    ):
        zip_file.writestr("junit.xml", JUNIT)
        zip_file.writestr("junit.xml", JUNIT)
        zip_file.writestr("coverage-manifest.json", MANIFEST)
    with pytest.raises(ActionsEvidenceError, match="duplicate file names"):
        _read_zip_members(output.getvalue())


def test_archive_reader_rejects_symlink_and_empty_member() -> None:
    from verification_core.actions_evidence import _read_zip_members

    output = io.BytesIO()
    symlink = zipfile.ZipInfo("junit.xml")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as zip_file:
        zip_file.writestr(symlink, b"target")
        zip_file.writestr("coverage-manifest.json", MANIFEST)
    with pytest.raises(ActionsEvidenceError, match="non-regular file"):
        _read_zip_members(output.getvalue())

    empty = archive({"junit.xml": b"", "coverage-manifest.json": MANIFEST})
    with pytest.raises(ActionsEvidenceError, match="empty or exceeds"):
        _read_zip_members(empty)


def test_archive_reader_rejects_large_and_high_ratio_members() -> None:
    from verification_core.actions_evidence import _read_zip_members

    oversized = archive(
        {
            "junit.xml": b"x" * (5 * 1024 * 1024 + 1),
            "coverage-manifest.json": MANIFEST,
        }
    )
    with pytest.raises(ActionsEvidenceError, match="empty or exceeds"):
        _read_zip_members(oversized)

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("junit.xml", JUNIT)
        zip_file.writestr("coverage-manifest.json", b"x" * 600_000)
    with pytest.raises(ActionsEvidenceError, match="compression ratio"):
        _read_zip_members(output.getvalue())


def test_archive_reader_allows_explicit_directory_entries_only_as_containers() -> None:
    from verification_core.actions_evidence import _read_zip_members

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("reports/", b"")
        zip_file.writestr("junit.xml", JUNIT)
        zip_file.writestr("coverage-manifest.json", MANIFEST)
    assert set(_read_zip_members(output.getvalue())) == {"junit.xml", "coverage-manifest.json"}


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
    def __init__(
        self,
        *,
        move_head_after_first_read: bool = False,
        workflow_source: str | None = TRUSTED_WORKFLOW,
    ) -> None:
        self.calls = 0
        self.move_head_after_first_read = move_head_after_first_read
        self.workflow_source = workflow_source

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
        return self.workflow_source


class _FakeActionsReader:
    def __init__(
        self,
        *,
        artifacts: list[dict[str, object]] | None = None,
        change_attempt_after_first_read: bool = False,
    ) -> None:
        self.artifacts = artifacts
        self.run_payload = run()
        self.run_reads = 0
        self.change_attempt_after_first_read = change_attempt_after_first_read

    def get_workflow_run(self, repository: str, run_id: int) -> dict[str, object]:
        assert repository == REPO
        assert run_id == 99
        self.run_reads += 1
        if self.change_attempt_after_first_read and self.run_reads > 1:
            return {**self.run_payload, "run_attempt": 2}
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


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (TRUSTED_WORKFLOW.replace("on: pull_request", "on: push"), "pull_request trigger"),
        (
            TRUSTED_WORKFLOW.replace(
                "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
                "actions/upload-artifact@v4",
            ),
            "full immutable commit SHA",
        ),
        (
            TRUSTED_WORKFLOW.replace("name: verification-evidence", "name: arbitrary-name"),
            "artifact name",
        ),
        (
            TRUSTED_WORKFLOW.replace("coverage-manifest.json", "coverage-*.json"),
            r"exactly junit\.xml and coverage-manifest\.json",
        ),
        (
            TRUSTED_WORKFLOW.replace("if-no-files-found: error", "if-no-files-found: warn"),
            "fail when an evidence file is missing",
        ),
        (
            TRUSTED_WORKFLOW.replace(
                "      - name: Upload verification evidence",
                "      - name: Upload verification evidence\n        if: false",
            ),
            "must not be conditional",
        ),
        (
            TRUSTED_WORKFLOW.replace(
                "        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
                "        run: echo not-an-upload-action",
            ),
            "exactly one required step",
        ),
        (
            TRUSTED_WORKFLOW.replace(
                "          if-no-files-found: error\n",
                "          if-no-files-found: error\n"
                "      - name: Extra uploader\n"
                "        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02\n"
                "        with:\n          name: extra-artifact\n          path: extra.txt\n"
                "          if-no-files-found: error\n",
            ),
            "exactly one required step",
        ),
        ("name: broken\non: [pull_request\njobs: {}", "malformed or ambiguous"),
        (
            "name: duplicate\non: pull_request\njobs:\n  verify: {}\n  verify: {}",
            "malformed or ambiguous",
        ),
        (
            TRUSTED_WORKFLOW.replace(
                "name: Upload verification evidence", "name: Different display name"
            ),
            "exactly one required step",
        ),
    ],
)
def test_phase_three_rejects_unverifiable_base_workflow_contract(source: str, message: str) -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    with pytest.raises(EvidenceIngestionServiceError, match=message):
        ingest_pull_request_run(
            github=_FakePRReader(workflow_source=source),
            actions=_FakeActionsReader(),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )


@pytest.mark.parametrize(
    ("workflow_source", "required_step_name", "artifact_name", "message"),
    [
        ("", "Upload verification evidence", "verification-evidence", "source is missing"),
        (
            "name: safe",
            "Upload verification evidence",
            "verification-evidence",
            "pull_request trigger",
        ),
        (
            TRUSTED_WORKFLOW,
            "",
            "verification-evidence",
            "Required evidence step name is invalid",
        ),
        (
            TRUSTED_WORKFLOW,
            "Upload verification evidence",
            "",
            "Expected evidence artifact name is invalid",
        ),
        (
            "name: oversized\\n" + " " * (256 * 1024),
            "Upload verification evidence",
            "verification-evidence",
            "size limit",
        ),
    ],
)
def test_phase_three_trusted_workflow_input_validation(
    workflow_source: str, required_step_name: str, artifact_name: str, message: str
) -> None:
    from verification_core.phase_three import (
        EvidenceIngestionServiceError,
        _validate_trusted_workflow_upload_contract,
    )

    with pytest.raises(EvidenceIngestionServiceError, match=message):
        _validate_trusted_workflow_upload_contract(
            workflow_source,
            required_step_name=required_step_name,
            expected_artifact_name=artifact_name,
        )


def test_phase_three_workflow_source_size_is_bounded() -> None:
    from verification_core.phase_three import (
        EvidenceIngestionServiceError,
        _validate_trusted_workflow_upload_contract,
    )

    with pytest.raises(EvidenceIngestionServiceError, match="size limit"):
        _validate_trusted_workflow_upload_contract(
            "x" * (256 * 1024 + 1),
            required_step_name="Upload verification evidence",
            expected_artifact_name="verification-evidence",
        )


def test_phase_three_service_rejects_missing_or_ambiguous_artifacts() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    data = archive()
    one = metadata(data)
    with pytest.raises(EvidenceIngestionServiceError, match="exactly one"):
        ingest_pull_request_run(
            github=_FakePRReader(),
            actions=_FakeActionsReader(artifacts=[]),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )
    with pytest.raises(EvidenceIngestionServiceError, match="exactly one"):
        ingest_pull_request_run(
            github=_FakePRReader(),
            actions=_FakeActionsReader(artifacts=[one, {**one, "id": 56}]),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
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


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("id", 100),
        ("workflow_id", 101),
        ("path", ".github/workflows/other.yml"),
        ("event", "push"),
        ("status", "in_progress"),
        ("conclusion", "cancelled"),
        ("head_sha", "e" * 40),
        ("run_attempt", 2),
    ],
)
def test_phase_three_rejects_each_workflow_run_identity_change(
    field: str, replacement: object
) -> None:
    from verification_core.phase_three import (
        EvidenceIngestionServiceError,
        _assert_workflow_run_unchanged,
    )

    actions = _FakeActionsReader()
    original = actions.run_payload
    actions.run_payload = {**original, field: replacement}
    with pytest.raises(EvidenceIngestionServiceError, match="identity or attempt changed"):
        _assert_workflow_run_unchanged(actions, REPO, 99, original)


def test_phase_three_rejects_invalid_original_workflow_attempt() -> None:
    from verification_core.phase_three import (
        EvidenceIngestionServiceError,
        _assert_workflow_run_unchanged,
    )

    actions = _FakeActionsReader()
    original = {**actions.run_payload, "run_attempt": True}
    with pytest.raises(EvidenceIngestionServiceError, match="attempt is missing or invalid"):
        _assert_workflow_run_unchanged(actions, REPO, 99, original)


@pytest.mark.parametrize("invalid_run_id", [0, -1, True])
def test_phase_three_rejects_invalid_workflow_run_identifiers(invalid_run_id: int) -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    with pytest.raises(EvidenceIngestionServiceError, match="positive integer"):
        ingest_pull_request_run(
            github=_FakePRReader(),
            actions=_FakeActionsReader(),
            commit=identity(),
            workflow_run_id=invalid_run_id,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )


def test_phase_three_rejects_empty_trusted_workflow_policy() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    with pytest.raises(EvidenceIngestionServiceError, match="policy is empty"):
        ingest_pull_request_run(
            github=_FakePRReader(),
            actions=_FakeActionsReader(),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )


@pytest.mark.parametrize(
    ("path", "workflow_source", "message"),
    [
        (None, TRUSTED_WORKFLOW, "path is missing"),
        (
            ".github/workflows/not-trusted.yml@refs/heads/main",
            TRUSTED_WORKFLOW,
            "not present in the trusted base policy",
        ),
        (".github/workflows/ci.yml@refs/heads/main", None, "does not exist at the exact base SHA"),
    ],
)
def test_phase_three_rejects_missing_or_untrusted_workflow_source(
    path: str | None, workflow_source: str | None, message: str
) -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    actions = _FakeActionsReader()
    actions.run_payload = {**actions.run_payload, "path": path}
    with pytest.raises(EvidenceIngestionServiceError, match=message):
        ingest_pull_request_run(
            github=_FakePRReader(workflow_source=workflow_source),
            actions=actions,
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )


@pytest.mark.parametrize("bad_digest", ["", "D" * 64, "x" * 64, "d" * 63])
def test_ingested_evidence_requires_lowercase_sha256_workflow_digest(bad_digest: str) -> None:
    from verification_core.phase_three import IngestedPullRequestEvidence

    with pytest.raises(ValueError, match="lowercase SHA-256 digest"):
        IngestedPullRequestEvidence(ingest(), bad_digest)


def test_phase_three_rejects_closed_pull_request_before_actions_reads() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    class ClosedPRReader(_FakePRReader):
        def get_pull_request(self, repository: str, pr_number: int) -> dict[str, object]:
            return {"state": "closed", "base": {"sha": BASE}, "head": {"sha": HEAD}}

    actions = _FakeActionsReader()
    with pytest.raises(EvidenceIngestionServiceError, match="no longer open"):
        ingest_pull_request_run(
            github=ClosedPRReader(),
            actions=actions,
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )
    assert actions.run_reads == 0


def test_phase_three_service_rejects_attempt_change_during_ingestion() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    with pytest.raises(EvidenceIngestionServiceError, match="identity or attempt changed"):
        ingest_pull_request_run(
            github=_FakePRReader(),
            actions=_FakeActionsReader(change_attempt_after_first_read=True),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
        )


def test_phase_three_service_persists_evidence_as_inconclusive_and_idempotently(
    tmp_path: Path,
) -> None:
    from verification_core.evidence_ledger import SQLAlchemyEvidenceLedger
    from verification_core.phase_three import ingest_pull_request_run

    ledger = SQLAlchemyEvidenceLedger(f"sqlite:///{tmp_path / 'evidence.sqlite3'}")
    first = ingest_pull_request_run(
        github=_FakePRReader(),
        actions=_FakeActionsReader(),
        commit=identity(),
        workflow_run_id=99,
        trusted_workflow_paths=(".github/workflows/ci.yml",),
        harness_sensitive_paths=(".github/workflows/", "conftest.py"),
        changed_paths=("src/auth.py",),
        evidence_ledger=ledger,
        ledger_now=10,
    )
    second = ingest_pull_request_run(
        github=_FakePRReader(),
        actions=_FakeActionsReader(),
        commit=identity(),
        workflow_run_id=99,
        trusted_workflow_paths=(".github/workflows/ci.yml",),
        harness_sensitive_paths=(".github/workflows/", "conftest.py"),
        changed_paths=("src/auth.py",),
        evidence_ledger=ledger,
        ledger_now=10,
    )
    assert first.ledger_record_key is not None
    assert second.ledger_record_key == first.ledger_record_key
    row = ledger.get_record(first.ledger_record_key)
    assert row is not None
    assert row["reconciliation_status"] == "INCONCLUSIVE"
    ledger.close()


class _RecordingEvidenceLedger:
    def __init__(self) -> None:
        self.calls = 0

    def record_ingestion(
        self,
        *,
        commit: CommitIdentity,
        evidence: AuthenticatedEvidenceArtifact,
        workflow_definition_sha256: str,
        now: float | None = None,
    ) -> str:
        self.calls += 1
        return "f" * 64


def test_stale_pr_is_rejected_before_persisting_evidence() -> None:
    from verification_core.phase_three import EvidenceIngestionServiceError, ingest_pull_request_run

    ledger = _RecordingEvidenceLedger()
    with pytest.raises(EvidenceIngestionServiceError, match="changed during"):
        ingest_pull_request_run(
            github=_FakePRReader(move_head_after_first_read=True),
            actions=_FakeActionsReader(),
            commit=identity(),
            workflow_run_id=99,
            trusted_workflow_paths=(".github/workflows/ci.yml",),
            harness_sensitive_paths=(".github/workflows/", "conftest.py"),
            changed_paths=("src/auth.py",),
            evidence_ledger=ledger,
        )
    assert ledger.calls == 0


def test_reconciliation_never_trusts_artifact_assertion_claim_alone() -> None:
    from verification_core.domain.enums import ObligationSource, ObligationStatus, Severity
    from verification_core.domain.models import VerificationObligation
    from verification_core.domain.state_machine import schedule_obligation
    from verification_core.phase_three import (
        IngestedPullRequestEvidence,
        reconcile_authenticated_obligation,
    )

    commit = identity()
    proposed = VerificationObligation.propose(
        obligation_id="OBL-AUTH-1",
        category="authorization",
        description="A caller must not access another tenant's data.",
        severity=Severity.HIGH,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/auth.py",),
        candidate_test_id="tests.test_auth::test_access",
    )
    scheduled = schedule_obligation(proposed)
    ingested = IngestedPullRequestEvidence(ingest(), "d" * 64)
    result = reconcile_authenticated_obligation(
        ingested=ingested,
        obligation=scheduled,
        expected_commit=commit,
        target_lines={"src/auth.py": {10}},
        target_branches={"src/auth.py": {"10:0"}},
        trusted_assertion_bindings={},
    )
    assert result.status is ObligationStatus.INCONCLUSIVE
    assert result.evidence is not None
    assert not result.evidence.behavioral_assertion_verified


def test_reconciliation_pass_requires_trusted_assertion_binding() -> None:
    from verification_core.domain.enums import ObligationSource, ObligationStatus, Severity
    from verification_core.domain.models import VerificationObligation
    from verification_core.domain.state_machine import schedule_obligation
    from verification_core.phase_three import (
        IngestedPullRequestEvidence,
        reconcile_authenticated_obligation,
    )

    commit = identity()
    proposed = VerificationObligation.propose(
        obligation_id="OBL-AUTH-2",
        category="authorization",
        description="A caller must not access another tenant's data.",
        severity=Severity.HIGH,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/auth.py",),
        candidate_test_id="tests.test_auth::test_access",
    )
    scheduled = schedule_obligation(proposed)
    ingested = IngestedPullRequestEvidence(ingest(), "d" * 64)
    result = reconcile_authenticated_obligation(
        ingested=ingested,
        obligation=scheduled,
        expected_commit=commit,
        target_lines={"src/auth.py": {10}},
        target_branches={"src/auth.py": {"10:0"}},
        trusted_assertion_bindings={"OBL-AUTH-2": "tests.test_auth::test_access"},
    )
    assert result.status is ObligationStatus.PASSED
    assert result.evidence is not None
    assert result.evidence.behavioral_assertion_verified


def test_reconciliation_missing_target_coverage_stays_inconclusive() -> None:
    from verification_core.domain.enums import ObligationSource, ObligationStatus, Severity
    from verification_core.domain.models import VerificationObligation
    from verification_core.domain.state_machine import schedule_obligation
    from verification_core.phase_three import (
        IngestedPullRequestEvidence,
        reconcile_authenticated_obligation,
    )

    proposed = VerificationObligation.propose(
        obligation_id="OBL-AUTH-3",
        category="authorization",
        description="A caller must not access another tenant's data.",
        severity=Severity.HIGH,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/auth.py",),
        candidate_test_id="tests.test_auth::test_access",
    )
    result = reconcile_authenticated_obligation(
        ingested=IngestedPullRequestEvidence(ingest(), "d" * 64),
        obligation=schedule_obligation(proposed),
        expected_commit=identity(),
        target_lines={"src/auth.py": {11}},
        target_branches={"src/auth.py": {"11:0"}},
        trusted_assertion_bindings={"OBL-AUTH-3": "tests.test_auth::test_access"},
    )
    assert result.status is ObligationStatus.INCONCLUSIVE


class _FakeCheckPublisher(_FakePRReader):
    def __init__(self, *, stale: bool = False) -> None:
        super().__init__()
        self.stale = stale
        self.published: list[dict[str, object]] = []

    def get_pull_request(self, repository: str, pr_number: int) -> dict[str, object]:
        if self.stale:
            return {
                "state": "open",
                "base": {"sha": BASE},
                "head": {"sha": "3" * 40},
                "html_url": "https://github.com/acme/service/pull/7",
            }
        return {
            "state": "open",
            "base": {"sha": BASE},
            "head": {"sha": HEAD},
            "html_url": "https://github.com/acme/service/pull/7",
        }

    def publish_check_run(self, **kwargs: object) -> int:
        self.published.append(kwargs)
        return 123


def _scheduled_high_obligation(
    obligation_id: str = "OBL-PUBLISH-1",
) -> VerificationObligation:
    from verification_core.domain.enums import ObligationSource, Severity
    from verification_core.domain.state_machine import schedule_obligation

    return schedule_obligation(
        VerificationObligation.propose(
            obligation_id=obligation_id,
            category="authorization",
            description="A caller must not access another tenant's data.",
            severity=Severity.HIGH,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/auth.py",),
            candidate_test_id="tests.test_auth::test_access",
        )
    )


def test_publication_rejects_stale_pr_before_any_check_run() -> None:
    from verification_core.phase_three import (
        EvidenceIngestionServiceError,
        publish_reconciled_verification,
    )

    publisher = _FakeCheckPublisher(stale=True)
    with pytest.raises(EvidenceIngestionServiceError, match="commits changed"):
        publish_reconciled_verification(
            github=publisher,
            commit=identity(),
            obligations=(_scheduled_high_obligation(),),
        )
    assert publisher.published == []


def test_publication_uses_state_machine_conclusion_for_unverified_obligations() -> None:
    from verification_core.domain.enums import GitHubCheckConclusion
    from verification_core.phase_three import publish_reconciled_verification

    publisher = _FakeCheckPublisher()
    result = publish_reconciled_verification(
        github=publisher,
        commit=identity(),
        obligations=(_scheduled_high_obligation(),),
    )
    assert result.evaluation.github_conclusion is GitHubCheckConclusion.ACTION_REQUIRED
    assert result.check_run_id == 123
    assert publisher.published[0]["conclusion"] == "action_required"
    assert publisher.published[0]["head_sha"] == HEAD


def test_publication_passes_only_from_a_passed_phase_one_obligation() -> None:
    from verification_core.domain.enums import GitHubCheckConclusion
    from verification_core.phase_three import (
        IngestedPullRequestEvidence,
        publish_reconciled_verification,
        reconcile_authenticated_obligation,
    )

    commit = identity()
    scheduled = _scheduled_high_obligation("OBL-PUBLISH-PASS")
    passed = reconcile_authenticated_obligation(
        ingested=IngestedPullRequestEvidence(ingest(), "d" * 64),
        obligation=scheduled,
        expected_commit=commit,
        target_lines={"src/auth.py": {10}},
        target_branches={"src/auth.py": {"10:0"}},
        trusted_assertion_bindings={"OBL-PUBLISH-PASS": "tests.test_auth::test_access"},
    )
    result = publish_reconciled_verification(
        github=_FakeCheckPublisher(),
        commit=commit,
        obligations=(passed,),
    )
    assert result.evaluation.github_conclusion is GitHubCheckConclusion.SUCCESS
    assert result.check_run_id == 123


def test_contradictory_coverage_result_is_never_turned_into_a_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import verification_core.phase_three as phase_three
    from verification_core.coverage import ReconciledTestEvidence
    from verification_core.domain.enums import (
        EvidenceSufficiency,
        ExecutionOutcome,
        ObligationStatus,
    )

    monkeypatch.setattr(
        phase_three,
        "reconcile_test_coverage",
        lambda **_kwargs: ReconciledTestEvidence(
            node_id="tests.test_auth::test_access",
            outcome=ExecutionOutcome.PASSED,
            target_lines_exercised=True,
            target_branches_exercised=True,
            behavioral_assertion_verified=True,
            sufficiency=EvidenceSufficiency.CONTRADICTORY,
        ),
    )
    result = phase_three.reconcile_authenticated_obligation(
        ingested=phase_three.IngestedPullRequestEvidence(ingest(), "d" * 64),
        obligation=_scheduled_high_obligation("OBL-CONTRADICTORY"),
        expected_commit=identity(),
        target_lines={"src/auth.py": {10}},
        target_branches={"src/auth.py": {"10:0"}},
        trusted_assertion_bindings={"OBL-CONTRADICTORY": "tests.test_auth::test_access"},
    )
    assert result.status is ObligationStatus.FAILED


class _RecordingDecisionLedger:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def record_reconciliation(
        self,
        record_key: str,
        *,
        status: str,
        reason: str,
        decision_sha256: str,
        now: float | None = None,
    ) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("ledger unavailable")


class _FailingCheckPublisher(_FakeCheckPublisher):
    def publish_check_run(self, **kwargs: object) -> int:
        raise RuntimeError("Check Run API unavailable")


def _passed_obligation_for_publication() -> VerificationObligation:
    from verification_core.phase_three import (
        IngestedPullRequestEvidence,
        reconcile_authenticated_obligation,
    )

    scheduled = _scheduled_high_obligation("OBL-PUBLISH-LEDGER")
    return reconcile_authenticated_obligation(
        ingested=IngestedPullRequestEvidence(ingest(), "d" * 64),
        obligation=scheduled,
        expected_commit=identity(),
        target_lines={"src/auth.py": {10}},
        target_branches={"src/auth.py": {"10:0"}},
        trusted_assertion_bindings={"OBL-PUBLISH-LEDGER": "tests.test_auth::test_access"},
    )


def test_publication_failure_does_not_write_terminal_ledger_decision() -> None:
    from verification_core.phase_three import publish_reconciled_verification

    ledger = _RecordingDecisionLedger()
    with pytest.raises(RuntimeError, match="Check Run API unavailable"):
        publish_reconciled_verification(
            github=_FailingCheckPublisher(),
            commit=identity(),
            obligations=(_passed_obligation_for_publication(),),
            decision_ledger=ledger,
            ledger_record_key="f" * 64,
        )
    assert ledger.calls == 0


def test_publication_reports_failed_post_publish_ledger_persistence() -> None:
    from verification_core.phase_three import publish_reconciled_verification

    publisher = _FakeCheckPublisher()
    ledger = _RecordingDecisionLedger(fail=True)
    result = publish_reconciled_verification(
        github=publisher,
        commit=identity(),
        obligations=(_passed_obligation_for_publication(),),
        decision_ledger=ledger,
        ledger_record_key="f" * 64,
    )
    assert len(publisher.published) == 1
    assert ledger.calls == 1
    assert result.ledger_persisted is False
