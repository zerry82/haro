from __future__ import annotations

import asyncio

from app.services.intent_resolution import ResolvedIntentContext
from app.services.intent_router import fallback_router_decision, llm_route, rule_route


def _resolved(
    text: str,
    *,
    latest_artifact: dict | None = None,
    file_discovery_context: dict | None = None,
) -> ResolvedIntentContext:
    return ResolvedIntentContext(
        current_message=text,
        routing_text=text,
        chat_workspace=None,
        gate_context=None,
        is_clarification_answer=False,
        previous_intent=None,
        clarification_question=None,
        latest_artifact=latest_artifact,
        latest_preview=None,
        file_discovery_context=file_discovery_context,
        latest_assistant_message=None,
        recent_messages=[],
        recent_intents=[],
    )


def test_llm_route_is_disabled_for_context_preserving_loop() -> None:
    route = asyncio.run(llm_route(_resolved("파일 찾아줘")))

    assert route is None


def test_rule_route_selects_research_profile_for_latest_external_info() -> None:
    route = rule_route(_resolved("오늘 환율 검색해서 알려줘"))

    assert route.intent == "research"
    assert route.execution_policy == "research"
    assert "web_search" in route.selected_tools


def test_rule_route_selects_read_only_profile_for_file_requests() -> None:
    route = rule_route(_resolved("파일 검색해줘"))

    assert route.intent == "read_only"
    assert route.execution_policy == "read_only"
    assert "file_search" in route.selected_tools
    assert "file_read" in route.selected_tools


def test_rule_route_selects_mail_search_for_mail_requests() -> None:
    route = rule_route(_resolved("카카오에서 온 메일들 요약해줘"))

    assert route.intent == "mail_read"
    assert route.execution_policy == "mail_read"
    assert "mail_search" in route.selected_tools
    assert "file_search" not in route.selected_tools


def test_rule_route_uses_workspace_admin_profile_for_folder_cleanup() -> None:
    route = rule_route(_resolved("폴더들이 너무 지저분하다. 정리좀 부탁해"))

    assert route.intent == "workspace_admin"
    assert route.execution_policy == "workspace_admin"
    assert "file_move" in route.selected_tools
    assert "dir_delete" in route.selected_tools
    assert "code_run" not in route.selected_tools


def test_rule_route_selects_file_work_profile_for_existing_file_modify() -> None:
    route = rule_route(_resolved("기존 문서 일부를 수정하고 분량을 3배 늘려줘"))

    assert route.intent == "file_work"
    assert route.execution_policy == "file_work"
    assert "file_stats" in route.selected_tools
    assert "file_search_content" in route.selected_tools
    assert "file_read_range" in route.selected_tools
    assert "file_edit" in route.selected_tools
    assert "file_append" in route.selected_tools
    assert "code_run" not in route.selected_tools


def test_rule_route_marks_explicit_plan_request_for_plan_mode() -> None:
    route = fallback_router_decision(_resolved("새 대시보드 구현 계획을 먼저 세워줘"))

    assert route.intent == "plan_mode"
    assert route.execution_policy == "plan_mode"
    assert route.should_enter_plan_mode is True
    assert route.plan_mode_reason


def test_rule_route_does_not_force_plan_mode_for_simple_create() -> None:
    route = rule_route(_resolved("간단한 메모 파일 만들어줘"))

    assert route.intent == "file_work"
    assert route.execution_policy == "file_work"
    assert route.should_enter_plan_mode is False


def test_active_file_context_raises_context_confidence() -> None:
    route = rule_route(_resolved(
        "지금 뭐가 보여?",
        latest_artifact={"path": "/playground/users/u1/30_outputs/weather.html"},
        file_discovery_context={
            "open_file_context": {
                "active_file_path": "/playground/users/u1/30_outputs/data.csv",
            },
            "candidates": [
                {
                    "path": "/playground/users/u1/30_outputs/data.csv",
                    "role": "context_file",
                    "confidence": 0.92,
                }
            ],
        },
    ))

    assert route.execution_policy == "read_only"
    assert route.context_confidence and route.context_confidence >= 0.9
    assert route.routing_context["execution_policy"]["profile"] == "read_only"
