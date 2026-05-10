from __future__ import annotations

from pathlib import Path

import pytest

from app.services.partial_file_ops import (
    ChecksumMismatchError,
    PartialFileOperationError,
    append_text,
    edit_text,
    file_stats,
    read_range,
    replace_range,
    search_content,
)


def test_file_stats_counts_text_and_sha256(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("첫 줄입니다.\nsecond line words\n", encoding="utf-8")

    stats = file_stats(str(path))

    assert stats["lines"] == 2
    assert stats["words"] == 5
    assert stats["korean_eojeol_estimate"] == 5
    assert stats["chars"] == len(path.read_bytes().decode("utf-8"))
    assert len(stats["sha256"]) == 64
    assert stats["estimated_speech_minutes"]["normal"] == 1


def test_read_range_returns_only_requested_lines_and_checksum(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    result = read_range(str(path), start_line=2, line_count=2)

    assert result["start_line"] == 2
    assert result["end_line"] == 3
    assert result["total_lines"] == 3
    assert result["content"].replace("\r\n", "\n") == "two\nthree\n"
    assert len(result["sha256"]) == 64


def test_search_content_supports_file_folder_glob_and_modes(tmp_path: Path) -> None:
    workspace = tmp_path
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("alpha\nneedle here\n", encoding="utf-8")
    (tmp_path / "docs" / "b.txt").write_text("needle elsewhere\n", encoding="utf-8")

    content = search_content(
        str(tmp_path / "docs"),
        workspace=str(workspace),
        query="needle",
        glob="*.md",
        output_mode="content",
        context_lines=1,
    )
    files = search_content(
        str(tmp_path / "docs"),
        workspace=str(workspace),
        query="needle",
        output_mode="files_with_matches",
    )
    count = search_content(
        str(tmp_path / "docs"),
        workspace=str(workspace),
        query="needle",
        output_mode="count",
    )

    assert content["total_matches"] == 1
    assert content["matches"][0]["path"] == "/docs/a.md"
    assert content["matches"][0]["line"] == 2
    assert files["total_files"] == 2
    assert count["match_count"] == 2


def test_file_edit_replaces_unique_string_and_reports_diff(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("hello old world\n", encoding="utf-8")
    before_sha = file_stats(str(path))["sha256"]

    result = edit_text(
        str(path),
        old_string="old world",
        new_string="new world",
        expected_sha256=before_sha,
    )
    assert result["new_content"].replace("\r\n", "\n") == "hello new world\n"
    assert result["matched_count"] == 1
    assert result["replaced_count"] == 1
    assert "new world" in result["diff_preview"]


def test_file_edit_rejects_missing_duplicate_noop_and_checksum_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("same same\n", encoding="utf-8")

    with pytest.raises(PartialFileOperationError, match="찾지 못했습니다"):
        edit_text(str(path), old_string="missing", new_string="new")
    with pytest.raises(PartialFileOperationError, match="여러 번"):
        edit_text(str(path), old_string="same", new_string="new")
    with pytest.raises(PartialFileOperationError, match="같아"):
        edit_text(str(path), old_string="same", new_string="same")
    with pytest.raises(ChecksumMismatchError):
        edit_text(str(path), old_string="same same", new_string="new", expected_sha256="bad")


def test_append_text_adds_separator_newline_and_checks_checksum(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("first", encoding="utf-8")
    before_sha = file_stats(str(path))["sha256"]

    result = append_text(str(path), content="second", expected_sha256=before_sha)

    assert result["new_content"] == "first\nsecond"
    assert result["appended_chars"] == len("\nsecond")
    with pytest.raises(ChecksumMismatchError):
        append_text(str(path), content="third", expected_sha256="bad")


def test_replace_range_replaces_inclusive_line_range(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    result = replace_range(str(path), start_line=2, end_line=3, content="TWO\nTHREE\n")

    assert result["new_content"].replace("\r\n", "\n") == "one\nTWO\nTHREE\nfour\n"
    assert result["old_line_count"] == 2
    assert result["new_line_count"] == 2


def test_binary_or_non_utf8_files_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "binary.bin"
    path.write_bytes(b"abc\x00def")

    with pytest.raises(PartialFileOperationError, match="바이너리"):
        file_stats(str(path))
