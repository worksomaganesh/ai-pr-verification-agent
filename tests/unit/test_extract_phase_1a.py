"""Regression tests for the legacy Phase 1A extractor's overwrite safeguards."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from extract_phase_1a import PHASE_1A_FILES, extract_and_bundle


def test_conflicting_files_are_refused_before_any_write(tmp_path: Path) -> None:
    existing = tmp_path / "pyproject.toml"
    existing.write_text("current Phase 1B project configuration", encoding="utf-8")

    with pytest.raises(FileExistsError, match="legacy Phase 1A snapshot"):
        extract_and_bundle(tmp_path, "bootstrap.zip", create_zip=False)

    assert existing.read_text(encoding="utf-8") == "current Phase 1B project configuration"
    assert not (tmp_path / "src").exists()


def test_zip_name_cannot_escape_target_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="filename"):
        extract_and_bundle(tmp_path / "target", "../outside.zip")

    assert not (tmp_path / "target").exists()
    assert not (tmp_path.parent / "outside.zip").exists()


def test_existing_zip_is_refused_before_extracting_files(tmp_path: Path) -> None:
    archive = tmp_path / "bootstrap.zip"
    archive.write_bytes(b"keep existing archive")

    with pytest.raises(FileExistsError, match="bootstrap.zip"):
        extract_and_bundle(tmp_path, "bootstrap.zip")

    assert archive.read_bytes() == b"keep existing archive"
    assert not (tmp_path / "src").exists()


def test_clean_target_extracts_files_and_builds_archive(tmp_path: Path) -> None:
    extract_and_bundle(tmp_path, "bootstrap.zip")

    for relative_path, expected_content in PHASE_1A_FILES.items():
        assert (tmp_path / relative_path).read_text(encoding="utf-8") == expected_content

    with zipfile.ZipFile(tmp_path / "bootstrap.zip") as archive:
        assert set(archive.namelist()) == set(PHASE_1A_FILES)
        assert archive.read("pyproject.toml").decode("utf-8") == PHASE_1A_FILES["pyproject.toml"]


def test_overwrite_requires_explicit_opt_in(tmp_path: Path) -> None:
    existing = tmp_path / "pyproject.toml"
    existing.write_text("deliberately different", encoding="utf-8")

    extract_and_bundle(tmp_path, "bootstrap.zip", create_zip=False, overwrite=True)

    assert existing.read_text(encoding="utf-8") == PHASE_1A_FILES["pyproject.toml"]
