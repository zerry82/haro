from __future__ import annotations

from app.services.intent_resolution import ResolvedIntentContext
from app.services.intent_router import rule_route


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
