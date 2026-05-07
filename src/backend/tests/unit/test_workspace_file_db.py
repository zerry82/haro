from pathlib import Path

from app.services.workspace_file_db import (
    count_workspace_items,
    list_workspace_directory_page,
    search_workspace_files,
    _full_path,
)


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "docs").mkdir(parents=True)
    (workspace / "data").mkdir()
    (workspace / ".haro").mkdir()
    (workspace / ".openclaw").mkdir()
    (workspace / "clean-room" / "data").mkdir(parents=True)

    (workspace / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (workspace / "data" / "report.csv").write_text("name,value\nA,1\n", encoding="utf-8")
    (workspace / "clean-room" / "data" / "source.txt").write_text("raw\n", encoding="utf-8")
    (workspace / ".haro" / "hidden.txt").write_text("hidden\n", encoding="utf-8")
    (workspace / ".openclaw" / "legacy.txt").write_text("legacy\n", encoding="utf-8")
    return workspace


def test_list_workspace_directory_page_indexes_root_without_meta_dirs(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    page = list_workspace_directory_page(str(workspace), "/", limit=10)

    names = [item["name"] for item in page["items"]]
    assert names == ["clean-room", "data", "docs"]
    assert page["total"] == 3
    assert page["has_more"] is False


def test_list_workspace_directory_page_supports_pagination(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    page = list_workspace_directory_page(str(workspace), "/", limit=2, offset=1)

    assert [item["name"] for item in page["items"]] == ["data", "docs"]
    assert page["total"] == 3
    assert page["has_more"] is False


def test_search_workspace_files_finds_indexed_paths(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    results = search_workspace_files(str(workspace), "guide")

    assert [item["path"] for item in results] == ["/docs/guide.md"]
    assert results[0]["item_type"] == "file"
    assert results[0]["language"] == "markdown"


def test_count_workspace_items_ignores_workspace_metadata(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    assert count_workspace_items(str(workspace), "/", item_type="directory") == 3
    assert count_workspace_items(str(workspace), "/", recursive=True, item_type="file") == 3


def test_full_path_normalizes_traversal_inside_workspace(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    assert _full_path(str(workspace), "../outside.txt") == str(workspace / "outside.txt")
