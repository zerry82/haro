from __future__ import annotations

from app.models.mail import MailThreadStaging
from app.services.mail_search import _managed_threads, _merge_thread_rows, rank_mail_threads


def test_rank_mail_threads_matches_korean_sender_particle_query_without_raw_ids() -> None:
    thread = MailThreadStaging(
        id="thread-1",
        run_id="run-1",
        project_id="project-1",
        user_id="user-1",
        source_ref="gmail:secret-source-ref",
        subject="카카오 광고 리포트 공유",
        sender="Kakao Biz <notice@kakao.com>",
        recipients_json='["me@example.com"]',
        received_at="2026-05-12T00:00:00+00:00",
        summary="카카오 캠페인 성과 리포트를 확인해 달라는 메일",
        category="광고/리포트",
        attachments_json='[{"title":"kakao-report.pdf","extension":"pdf","size_bytes":1234,"summary":"캠페인 성과"}]',
        inclusion_decision="allowed",
        metadata_json='{"extracted_actions":[{"text":"리포트 확인"}],"extracted_due_dates":[],"structure_warnings":[]}',
    )

    results = rank_mail_threads([thread], query="카카오에서 온 메일들 요약해줘", limit=10)

    assert len(results) == 1
    assert results[0]["thread_id"] == "thread-1"
    assert "sender" in results[0]["matched_fields"]
    assert results[0]["metadata"]["extracted_actions"] == [{"text": "리포트 확인"}]
    assert "source_ref" not in results[0]


def test_rank_mail_threads_returns_recent_items_for_empty_effective_query() -> None:
    older = _thread("older", "오래된 메일", "2026-05-10T00:00:00+00:00")
    newer = _thread("newer", "새 메일", "2026-05-12T00:00:00+00:00")

    results = rank_mail_threads([older, newer], query="최근 메일 요약", limit=1)

    assert [item["thread_id"] for item in results] == ["newer"]


def test_managed_threads_excludes_management_excluded_rows() -> None:
    managed = _thread("managed", "업무 메일", "2026-05-12T00:00:00+00:00")
    excluded = _thread("excluded", "뉴스레터", "2026-05-12T00:00:00+00:00")
    excluded.metadata_json = '{"management_decision":"excluded"}'

    results = _managed_threads([managed, excluded])

    assert [thread.id for thread in results] == ["managed"]


def test_merge_thread_rows_keeps_source_chain_threads_for_latest_search() -> None:
    old = _thread("old", "기존 메일", "2026-05-10T00:00:00+00:00")
    new = _thread("new", "새 메일", "2026-05-12T00:00:00+00:00")

    results = _merge_thread_rows([old], [new])

    assert [thread.id for thread in results] == ["new", "old"]


def _thread(thread_id: str, subject: str, received_at: str) -> MailThreadStaging:
    return MailThreadStaging(
        id=thread_id,
        run_id="run-1",
        project_id="project-1",
        user_id="user-1",
        source_ref=f"gmail:{thread_id}",
        subject=subject,
        sender="sender@example.com",
        recipients_json="[]",
        received_at=received_at,
        summary=subject,
        category="일반 업무",
        attachments_json="[]",
        inclusion_decision="allowed",
        metadata_json="{}",
    )
