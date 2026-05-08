from pathlib import Path

from app.services.workspace_file_db import (
    count_workspace_items,
    ensure_workspace_file_db,
    list_workspace_directory_page,
    search_workspace_files,
    update_workspace_item_summary,
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


def test_list_workspace_directory_page_filters_hidden_items_before_pagination(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    (workspace / ".cache").mkdir()
    (workspace / ".cache" / "secret.txt").write_text("secret\n", encoding="utf-8")

    raw_page = list_workspace_directory_page(str(workspace), "/", include_hidden=True, limit=10)
    filtered_page = list_workspace_directory_page(str(workspace), "/", include_hidden=False, limit=10)

    assert ".cache" in [item["name"] for item in raw_page["items"]]
    assert ".cache" not in [item["name"] for item in filtered_page["items"]]
    assert raw_page["total"] == filtered_page["total"] + 1


def test_search_workspace_files_finds_indexed_paths(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    results = search_workspace_files(str(workspace), "guide")

    assert [item["path"] for item in results] == ["/docs/guide.md"]
    assert results[0]["item_type"] == "file"
    assert results[0]["language"] == "markdown"


def test_search_workspace_files_filters_hidden_and_alias_allowlist(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    (workspace / "playground" / "users" / "u1" / "20_working").mkdir(parents=True)
    (workspace / "playground" / "users" / "u2" / "20_working").mkdir(parents=True)
    (workspace / "docs").mkdir(exist_ok=True)
    (workspace / ".cache").mkdir()

    (workspace / "playground" / "users" / "u1" / "20_working" / "visible-needle.md").write_text("ok\n", encoding="utf-8")
    (workspace / "playground" / "users" / "u2" / "20_working" / "other-needle.md").write_text("no\n", encoding="utf-8")
    (workspace / "docs" / "public-needle.md").write_text("no\n", encoding="utf-8")
    (workspace / ".cache" / "hidden-needle.md").write_text("no\n", encoding="utf-8")

    raw_results = search_workspace_files(str(workspace), "needle", include_hidden=True)
    user_results = search_workspace_files(str(workspace), "needle", include_hidden=False, user_id="u1")

    assert {item["path"] for item in raw_results} >= {
        "/playground/users/u1/20_working/visible-needle.md",
        "/playground/users/u2/20_working/other-needle.md",
        "/docs/public-needle.md",
        "/.cache/hidden-needle.md",
    }
    assert [item["path"] for item in user_results] == ["/playground/users/u1/20_working/visible-needle.md"]


def test_search_workspace_files_includes_user_agents_md_in_alias_allowlist(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    user_root = workspace / "playground" / "users" / "u1"
    user_root.mkdir(parents=True)
    (user_root / "AGENTS.md").write_text("custom preference\n", encoding="utf-8")

    results = search_workspace_files(str(workspace), "AGENTS", include_hidden=False, user_id="u1")

    assert [item["path"] for item in results] == ["/playground/users/u1/AGENTS.md"]


def test_update_workspace_item_summary_syncs_new_parent_directories(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ensure_workspace_file_db(str(workspace))

    nested_file = workspace / "playground" / "users" / "u1" / "30_outputs" / "report" / "dashboard.html"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("<!doctype html>\n", encoding="utf-8")

    update_workspace_item_summary(
        str(workspace),
        "/playground/users/u1/30_outputs/report/dashboard.html",
        "html dashboard",
    )

    page = list_workspace_directory_page(
        str(workspace),
        "/playground/users/u1/30_outputs",
        include_hidden=False,
        user_id="u1",
    )

    assert [item["name"] for item in page["items"]] == ["report"]
    assert page["items"][0]["type"] == "directory"


def test_count_workspace_items_ignores_workspace_metadata(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    assert count_workspace_items(str(workspace), "/", item_type="directory") == 3
    assert count_workspace_items(str(workspace), "/", recursive=True, item_type="file") == 3


def test_full_path_normalizes_traversal_inside_workspace(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)

    assert _full_path(str(workspace), "../outside.txt") == str(workspace / "outside.txt")
