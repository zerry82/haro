from __future__ import annotations

import json

from app.services.intent_resolution import ResolvedIntentContext
from app.services.intent_text_rules import (
    as_bool,
    as_list,
    has_count_signal,
    has_create_signal,
    has_explicit_scope,
    has_list_signal,
    has_period_or_target,
    has_read_signal,
    has_search_signal,
    normalize,
    parse_json_object,
)
from app.services.intent_types import RouterDecision
from app.services.llm import get_client
from app.services.tool_registry import DEFAULT_TASK_TOOLS, build_tool_catalog, validate_tool_names


async def llm_route(resolved: ResolvedIntentContext) -> RouterDecision | None:
    context = resolved.to_prompt_dict()
    prompt = f"""
사용자 요청을 haro 작업 라우팅 JSON으로 분류하세요.
실행하지 말고 도구 선택만 판단합니다.

현재 턴은 아래 resolved_intent_context를 기준으로 판단합니다.
clarification 답변인 경우 current_user_message만 보지 말고 previous_intent, clarification_question, routing_text를 함께 보세요.

도구 카탈로그:
{build_tool_catalog()}

resolved_intent_context:
{json.dumps(context, ensure_ascii=False, indent=2)}

도구 선택 지침:
- selected_tools에는 실행 중 필요할 가능성이 있는 모든 도구를 포함하세요.
- resolved_intent_context와 최근 대화만으로 답할 수 있으면 selected_tools를 빈 배열로 두고 can_execute=true로 판단하세요.
- 사용자가 파일/폴더 개수, 통계, 집계를 요구하면 file_count를 포함하세요.
- 의미 있는 파일을 찾아야 하면 file_search를 포함하고, 실제 내용 확인이 필요하면 file_read도 포함하세요.
- gate_context.artifact_action이 summarize_artifact이고 artifact_path가 있으면, 최신 assistant 요약을 반복하지 말고 원천 산출물 확인이 필요한지 판단하세요. 실제 파일 내용 기준 요약이면 file_read를 포함하세요.
- gate_context.artifact_action이 followup_task이고 최근 산출물의 실제 내용 확인이 필요하면 file_read를 포함하세요.
- HTML/Markdown/대시보드/리포트 등 새 산출물을 저장해야 하면 file_create를 포함하세요.
- selected_tools는 도구 카탈로그 name 값만 사용하세요.

반드시 JSON만 반환하세요.
필드:
intent, confidence, can_execute, selected_tools, selected_skills, missing_info, risk_level, question, reason
정보가 부족하면 can_execute=false와 question을 반환하세요.
"""
    try:
        client = get_client()
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config={"temperature": 0.1},
        )
        text = getattr(response, "text", "") or ""
        data = parse_json_object(text)
        if not data:
            return None
        raw_tools = as_list(data.get("selected_tools"))
        selected_tools, invalid_tools = validate_tool_names(raw_tools)
        return RouterDecision(
            intent=str(data.get("intent") or "general_task"),
            confidence=float(data.get("confidence") or 0.5),
            can_execute=as_bool(data.get("can_execute"), default=False),
            selected_tools=selected_tools,
            selected_skills=as_list(data.get("selected_skills")),
            missing_info=as_list(data.get("missing_info")),
            risk_level=str(data.get("risk_level") or "low"),
            question=data.get("question"),
            reason=str(data.get("reason") or ""),
            source="llm",
            invalid_tools=invalid_tools,
            routing_context=context,
        )
    except Exception:
        return None


def rule_route(resolved: ResolvedIntentContext) -> RouterDecision | None:
    normalized = normalize(resolved.routing_text)
    context = resolved.to_prompt_dict()

    if has_count_signal(normalized):
        return RouterDecision(
            intent="file_count",
            confidence=0.92,
            can_execute=True,
            selected_tools=["file_count"],
            reason="개수 조회 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if has_search_signal(normalized):
        return RouterDecision(
            intent="file_search",
            confidence=0.88,
            can_execute=True,
            selected_tools=["file_search", "file_read"],
            reason="파일/폴더 검색 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if has_list_signal(normalized):
        if not has_explicit_scope(normalized):
            return RouterDecision(
                intent="dir_list",
                confidence=0.72,
                can_execute=False,
                selected_tools=[],
                missing_info=["조회할 폴더 경로"],
                question="어느 폴더의 목록을 볼까요? 루트(`/`) 기준으로 볼지, 현재 채팅 작업공간 기준으로 볼지 알려주세요.",
                reason="목록 조회 대상 경로가 명확하지 않습니다.",
                source="fallback_rule",
                routing_context=context,
            )
        return RouterDecision(
            intent="dir_list",
            confidence=0.84,
            can_execute=True,
            selected_tools=["dir_list"],
            reason="디렉토리 목록 조회 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if has_read_signal(normalized):
        return RouterDecision(
            intent="file_read",
            confidence=0.86,
            can_execute=True,
            selected_tools=["file_search", "file_read"],
            reason="파일 읽기 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if has_create_signal(normalized):
        return RouterDecision(
            intent="file_create",
            confidence=0.82,
            can_execute=True,
            selected_tools=["file_search", "file_read", "file_create"],
            reason="파일 생성/저장 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if "웹앱" in normalized or "프리뷰" in normalized or "preview" in normalized:
        return RouterDecision(
            intent="web_preview",
            confidence=0.9,
            can_execute=True,
            selected_tools=["web_preview"],
            reason="웹앱 프리뷰 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if "코드" in normalized and ("실행" in normalized or "돌려" in normalized):
        return RouterDecision(
            intent="code_run",
            confidence=0.86,
            can_execute=True,
            selected_tools=["code_run"],
            reason="코드 실행 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if "리포트" in normalized and ("정리" in normalized or "요약" in normalized):
        if not has_period_or_target(normalized):
            return RouterDecision(
                intent="report_summary",
                confidence=0.78,
                can_execute=False,
                selected_tools=[],
                missing_info=["대상 리포트 또는 기간"],
                question="어떤 리포트를 정리할까요? 기간이나 파일 위치를 알려주세요.",
                reason="리포트 대상이 부족합니다.",
                source="fallback_rule",
                routing_context=context,
            )
        return RouterDecision(
            intent="report_summary",
            confidence=0.78,
            can_execute=True,
            selected_tools=["file_search", "file_read", "file_create"],
            reason="리포트 정리 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if "자동화" in normalized or "스킬" in normalized:
        return RouterDecision(
            intent="skill_discovery",
            confidence=0.74,
            can_execute=False,
            selected_tools=[],
            missing_info=["자동화할 업무 입력", "원하는 출력"],
            question="어떤 업무를 자동화하고 싶으세요? 입력 자료와 최종 결과물을 한 가지씩 알려주세요.",
            reason="스킬 제작 대화는 업무 이해가 먼저 필요합니다.",
            source="fallback_rule",
            routing_context=context,
        )
    return None


def fallback_router_decision(resolved: ResolvedIntentContext) -> RouterDecision:
    return RouterDecision(
        intent="general_task",
        confidence=0.55,
        can_execute=True,
        selected_tools=DEFAULT_TASK_TOOLS,
        risk_level="low",
        reason="라우터 fallback: 일반 파일 기반 작업으로 처리합니다.",
        source="fallback",
        routing_context=resolved.to_prompt_dict(),
    )
