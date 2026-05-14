from __future__ import annotations

from app.app_factory import create_app
from app.startup.seeds import BUILTIN_FILE_OPS_TOOLS, builtin_file_ops_manifest


def test_builtin_file_ops_manifest_lists_expected_tools() -> None:
    manifest = builtin_file_ops_manifest()

    assert manifest == {"tools": BUILTIN_FILE_OPS_TOOLS}
    assert {
        "file_create",
        "file_read",
        "file_stats",
        "file_search_content",
        "file_read_range",
        "file_write",
        "file_edit",
        "file_append",
        "file_replace_range",
        "file_search",
        "web_search",
        "mail_search",
        "mail_attachment_read",
    }.issubset(manifest["tools"])


def test_app_factory_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/api/health" in paths
    assert "/api/projects" in paths
    assert "/api/projects/{project_id}/files" in paths
    assert "/api/projects/{project_id}/mail/gmail/status" in paths
    assert "/api/projects/{project_id}/mail/gmail/analysis/{run_id}/search" in paths
    assert "/api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads/{thread_id}/attachments/{attachment_ref}" in paths
    assert "/api/auth/google/gmail/callback" in paths
    assert "/api/projects/{project_id}/context-library/search" in paths
