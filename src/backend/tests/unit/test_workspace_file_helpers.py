from pathlib import Path

from app.services.workspace_file_helpers import (
    classify_path,
    db_path,
    escape_like,
    fts_phrase,
    full_path,
    is_meta_path,
    language_for_extension,
    make_snippet,
    parent_path,
    workspace_path_from_full,
)


def test_classify_path_identifies_workspace_rooms() -> None:
    assert classify_path("/") == ("root", "writable", None)
    assert classify_path("/clean-room/data/source.csv") == ("clean_room_data", "read_only", None)
    assert classify_path("/clean-room/meta/rules.md") == ("clean_room_meta", "read_only", None)
    assert classify_path("/playground/users/user-1/00_inbox/a.txt") == ("playground", "writable", "user-1")
    assert classify_path("/90_archive/old.txt") == ("archive", "read_only", None)


def test_language_for_extension_maps_known_text_types() -> None:
    assert language_for_extension(".py") == "python"
    assert language_for_extension(".md") == "markdown"
    assert language_for_extension(".unknown") is None


def test_search_helpers_escape_fts_and_like_queries() -> None:
    assert fts_phrase('a "quoted" value') == '"a ""quoted"" value"'
    assert escape_like(r"100%_done\path") == r"100\%\_done\\path"


def test_path_helpers_normalize_workspace_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    nested = workspace / "docs" / "guide.md"
    nested.parent.mkdir()
    nested.write_text("hello", encoding="utf-8")

    assert parent_path("/docs/guide.md") == "/docs"
    assert workspace_path_from_full(str(workspace), str(nested)) == "/docs/guide.md"
    assert full_path(str(workspace), "/docs/../guide.md") == str(workspace / "guide.md")
    assert db_path(str(workspace)) == str(workspace / ".haro" / "db" / "workspace.db")


def test_meta_path_detection_covers_current_and_legacy_dirs() -> None:
    assert is_meta_path("/.haro/db/workspace.db") is True
    assert is_meta_path("/.openclaw/file_summaries/a.md") is True
    assert is_meta_path("/docs/.haro-note.md") is False


def test_make_snippet_returns_nearby_query_context() -> None:
    summary = "alpha " * 40 + "needle " + "omega " * 40

    snippet = make_snippet(summary, "needle")

    assert "needle" in snippet
    assert snippet.startswith("...")
    assert snippet.endswith("...")
