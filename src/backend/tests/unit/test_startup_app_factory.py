from __future__ import annotations

from app.app_factory import create_app
from app.startup.seeds import BUILTIN_FILE_OPS_TOOLS, builtin_file_ops_manifest


def test_builtin_file_ops_manifest_lists_expected_tools() -> None:
    manifest = builtin_file_ops_manifest()

    assert manifest == {"tools": BUILTIN_FILE_OPS_TOOLS}
    assert {"file_create", "file_read", "file_write", "file_search"}.issubset(manifest["tools"])


def test_app_factory_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/api/health" in paths
    assert "/api/projects" in paths
    assert "/api/projects/{project_id}/files" in paths
