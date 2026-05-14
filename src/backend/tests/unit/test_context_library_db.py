from types import SimpleNamespace

from app.services.context_library_db import promote_mail_threads, search_context_library


def test_staging_threads_are_not_searchable_until_promoted(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = SimpleNamespace(
        id="staging-1",
        inclusion_decision="allowed",
        source_ref="gmail-thread-secret-123",
        subject="A client weekly report",
        sender="Manager <manager@client.com>",
        recipients_json='["owner@agency.com"]',
        received_at="2026-05-01T01:00:00+00:00",
        summary="Client asked for the weekly performance report.",
        category="보고/리포트",
        attachments_json='[{"title":"report.xlsx","extension":"xlsx","size_bytes":1000,"summary":"weekly metrics"}]',
    )

    before = search_context_library(str(workspace), "weekly")
    promoted = promote_mail_threads(str(workspace), [staging])
    after = search_context_library(str(workspace), "weekly")

    assert before["items"] == []
    assert len(promoted) == 1
    assert promoted[0]["staging_id"] == "staging-1"
    assert after["items"][0]["title"] == "A client weekly report"

    summary_path = workspace / promoted[0]["clean_room_path"].lstrip("/")
    summary = summary_path.read_text(encoding="utf-8")
    assert "Client asked for the weekly performance report." in summary
    assert "gmail-thread-secret-123" not in summary


def test_denied_staging_threads_are_not_promoted(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = SimpleNamespace(
        id="staging-1",
        inclusion_decision="denied",
        source_ref="gmail-thread-secret-123",
        subject="Newsletter",
        sender="news@vendor.com",
        recipients_json="[]",
        received_at="2026-05-01T01:00:00+00:00",
        summary="Vendor newsletter.",
        category="뉴스레터",
        attachments_json="[]",
    )

    promoted = promote_mail_threads(str(workspace), [staging])
    result = search_context_library(str(workspace), "newsletter")

    assert promoted == []
    assert result["items"] == []

