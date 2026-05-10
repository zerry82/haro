from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.intent_resolution import ResolvedIntentContext
import app.services.intent_router as intent_router
from app.services.intent_router import fallback_router_decision, llm_route, rule_route


def _resolved(text: str) -> ResolvedIntentContext:
    return ResolvedIntentContext(
        current_message=text,
        routing_text=text,
        chat_workspace=None,
        gate_context=None,
        is_clarification_answer=False,
        previous_intent=None,
        clarification_question=None,
        latest_artifact=None,
        latest_preview=None,
        latest_assistant_message=None,
        recent_messages=[],
        recent_intents=[],
    )


def test_rule_route_selects_web_search_for_latest_external_info() -> None:
    route = rule_route(_resolved("오늘 환율 검색해서 알려줘"))

    assert route is not None
    assert route.intent == "web_search"
    assert route.selected_tools == ["web_search"]


def test_rule_route_keeps_file_search_for_file_requests() -> None:
    route = rule_route(_resolved("파일 검색해줘"))

    assert route is not None
    assert route.intent == "file_search"
    assert route.selected_tools == ["file_search", "file_read"]


def test_rule_route_uses_native_tools_for_folder_cleanup() -> None:
    route = rule_route(_resolved("폴더들이 너무 지저분하다. 정리좀 부탁해"))

    assert route is not None
    assert route.intent == "folder_organization"
    assert "file_move" in route.selected_tools
    assert "dir_delete" in route.selected_tools
    assert "code_run" not in route.selected_tools


def test_rule_route_selects_partial_tools_for_existing_file_modify() -> None:
    route = rule_route(_resolved("기존 문서 일부를 수정하고 분량을 3배 늘려줘"))

    assert route is not None
    assert route.intent == "file_partial_modify"
    assert "file_stats" in route.selected_tools
    assert "file_search_content" in route.selected_tools
    assert "file_read_range" in route.selected_tools
    assert "file_edit" in route.selected_tools
    assert "file_append" in route.selected_tools
    assert "code_run" not in route.selected_tools


def test_llm_route_replaces_code_run_for_folder_cleanup(monkeypatch) -> None:
    class _Models:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                text='{"intent":"folder_organization","confidence":0.9,"can_execute":true,"selected_tools":["code_run"],"selected_skills":[],"missing_info":[],"risk_level":"low","question":null,"reason":"cleanup","should_enter_plan_mode":false,"plan_mode_reason":null}'
            )

    monkeypatch.setattr(intent_router, "get_client", lambda: SimpleNamespace(models=_Models()))

    route = asyncio.run(llm_route(_resolved("폴더들을 이동해서 정리하고 빈 폴더는 삭제해줘")))

    assert route is not None
    assert "file_move" in route.selected_tools
    assert "dir_delete" in route.selected_tools
    assert "code_run" not in route.selected_tools


def test_rule_route_marks_explicit_plan_request_for_plan_mode() -> None:
    route = fallback_router_decision(_resolved("새 대시보드 구현 계획을 먼저 세워줘"))

    assert route is not None
    assert route.should_enter_plan_mode is True
    assert route.plan_mode_reason


def test_rule_route_does_not_force_plan_mode_for_simple_create() -> None:
    route = rule_route(_resolved("간단한 메모 파일 만들어줘"))

    assert route is not None
    assert route.intent == "file_create"
    assert route.should_enter_plan_mode is False
