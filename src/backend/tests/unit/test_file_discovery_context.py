from __future__ import annotations

from types import SimpleNamespace

from app.services.file_discovery_context import (
    build_file_discovery_context,
    sanitize_open_file_context,
)
from app.services.intent_turns import apply_file_discovery_constraints
from app.services.intent_resolution import ResolvedIntentContext
from app.services.intent_types import RouterDecision


def _chat() -> SimpleNamespace:
    return SimpleNamespace(id="chat-1", folder_path="/playground/users/u1/50_chats/chat-1")


def test_active_file_is_top_candidate_for_current_file_reference(tmp_path) -> None:
    active_path = "/playground/users/u1/30_outputs/report.md"

    context = build_file_discovery_context(
        workspace=str(tmp_path),
        user_id="u1",
        chat_session=_chat(),
        current_message="이 파일 기준으로 요약해줘",
        routing_text="이 파일 기준으로 요약해줘",
        open_file_context={
            "active_file_path": active_path,
            "opened_file_paths": [active_path],
            "language": "markdown",
            "active_viewer_tab": "editor",
            "dirty": False,
        },
    )

    assert context is not None
    first = context["candidates"][0]
    assert first["path"] == active_path
    assert first["alias_path"] == "내 폴더/결과/report.md"
    assert first["confidence"] >= 0.9
    assert first["source"] == "open_file_context"


def test_weather_trace_separates_target_artifact_from_missing_source(tmp_path) -> None:
    target_path = "/playground/users/u1/30_outputs/날씨_브리핑/서울_날씨_대시보드_20260509.html"

    context = build_file_discovery_context(
        workspace=str(tmp_path),
        user_id="u1",
        chat_session=_chat(),
        current_message="이미 파일로 추가했었어",
        routing_text=(
            "이전 사용자 요청: 서울 날씨 브리핑에서 현재 html을 건들지 말고, "
            "아래 5.10일 내용을 추가해줘.\n현재 사용자 답변: 이미 파일로 추가했었어"
        ),
        latest_artifact={"path": target_path, "kind": "outputs"},
    )

    assert context is not None
    assert context["requires_source_content"] is True
    assert context["source_content_missing"] is True
    assert context["candidates"][0]["role"] == "target_artifact"
    assert context["candidates"][0]["path"] == target_path
    assert "파일 경로" in context["recommended_user_question"]


def test_existing_written_text_uses_recent_conversation_as_source(tmp_path) -> None:
    context = build_file_discovery_context(
        workspace=str(tmp_path),
        user_id="u1",
        chat_session=_chat(),
        current_message="기존에 작성했었어.",
        routing_text="현재 사용자 답변: 기존에 작성했었어.",
        recent_messages=[
            {
                "id": "m1",
                "role": "user",
                "content": "5월 10일 서울 날씨: 오전에는 흐리고 오후에는 비 가능성이 있습니다. 낮 최고기온은 22도입니다.",
            },
            {"id": "m2", "role": "user", "content": "기존에 작성했었어."},
        ],
    )

    assert context is not None
    assert context["requires_source_content"] is True
    assert context["source_content_missing"] is False
    first = context["candidates"][0]
    assert first["role"] == "source_content"
    assert first["source"] == "recent_messages"
    assert first["path"] == "conversation://messages/m1"
    assert "5월 10일 서울 날씨" in first["content_preview"]


def test_status_conversation_messages_do_not_hide_missing_source(tmp_path) -> None:
    context = build_file_discovery_context(
        workspace=str(tmp_path),
        user_id="u1",
        chat_session=_chat(),
        current_message="기존에 작성했었어.",
        routing_text="현재 사용자 답변: 기존에 작성했었어.",
        recent_messages=[
            {
                "id": "m1",
                "role": "planner",
                "content": "주인님, 파일을 찾아보겠습니다. 먼저 작업공간에서 관련 파일을 검색해 보겠습니다.",
            },
            {"id": "m2", "role": "user", "content": "기존에 작성했었어."},
        ],
    )

    assert context is not None
    assert context["source_content_missing"] is True
    assert context["candidates"] == []


def test_selection_preview_is_limited_and_dirty_content_is_not_copied() -> None:
    long_selection = "가" * 2500

    context = sanitize_open_file_context(
        {
            "active_file_path": "내 폴더/결과/report.md",
            "opened_file_paths": ["내 폴더/결과/report.md"],
            "language": "markdown",
            "active_viewer_tab": "editor",
            "dirty": True,
            "content": "저장되지 않은 전체 본문",
            "selection": {
                "start_line": 3,
                "end_line": 9,
                "text_preview": long_selection,
            },
        },
        "u1",
    )

    assert context is not None
    assert context["active_file_path"] == "/playground/users/u1/30_outputs/report.md"
    assert context["dirty"] is True
    assert len(context["selection"]["text_preview"]) == 2000
    assert "content" not in context


def test_source_missing_discovery_turns_route_into_question() -> None:
    resolved = ResolvedIntentContext(
        current_message="이미 파일로 추가했어",
        routing_text="현재 사용자 답변: 이미 파일로 추가했어",
        chat_workspace=None,
        gate_context=None,
        is_clarification_answer=True,
        previous_intent=None,
        clarification_question=None,
        latest_artifact=None,
        latest_preview=None,
        file_discovery_context={
            "source_content_missing": True,
            "missing_info": ["추가할 원문 파일 경로 또는 재업로드"],
            "recommended_user_question": "파일 경로를 알려주세요.",
        },
        latest_assistant_message=None,
        recent_messages=[],
        recent_intents=[],
    )
    route = RouterDecision(
        intent="file_partial_modify",
        confidence=0.8,
        can_execute=True,
        selected_tools=["file_search", "file_read", "file_edit"],
    )

    constrained = apply_file_discovery_constraints(route, resolved)

    assert constrained.can_execute is False
    assert constrained.selected_tools == []
    assert constrained.question == "파일 경로를 알려주세요."
    assert constrained.missing_info == ["추가할 원문 파일 경로 또는 재업로드"]
