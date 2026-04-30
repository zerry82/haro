from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.intent_turn import IntentTurn, IntentTurnEvent
from app.models.message import Message
from app.models.project import Project
from app.services.chat_workspace import get_latest_chat_output_reference
from app.services.intent_gate import LlmGateResult, decide_gate_with_llm
from app.services.intent_resolution import build_resolved_intent_context, ResolvedIntentContext
from app.services.llm import get_client
from app.services.tool_registry import DEFAULT_TASK_TOOLS, build_tool_catalog, normalize_tool_names, validate_tool_names

ACTIVE_INTENT_STATUSES = {"routing", "needs_clarification", "executing", "waiting_review"}
RECENT_INTENT_LIMIT = 5


@dataclass
class GateDecision:
    decision: str
    reason: str
    intent_turn: IntentTurn | None = None
    candidates: list[IntentTurn] = field(default_factory=list)
    artifact_path: str | None = None
    artifact_kind: str | None = None
    artifact_url: str | None = None
    artifact_action: str | None = None
    confidence: float | None = None
    source: str = "llm"


@dataclass
class RouterDecision:
    intent: str
    confidence: float
    can_execute: bool
    selected_tools: list[str] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    risk_level: str = "low"
    question: str | None = None
    reason: str = ""
    source: str = "rule"
    invalid_tools: list[str] = field(default_factory=list)
    routing_context: dict[str, Any] | None = None


async def decide_message_gate(
    db: AsyncSession,
    chat_session: ChatSession,
    content: str,
    *,
    workspace: str | None = None,
) -> GateDecision:
    normalized = _normalize(content)
    waiting = await _get_waiting_intent(db, chat_session.id)
    recent = await get_recent_intent_turns(db, chat_session.id)
    resolved = await build_resolved_intent_context(
        db,
        None,
        chat_session,
        content,
        workspace=workspace,
        previous_turn=waiting,
        recent_turns=recent,
    )

    llm_gate = await decide_gate_with_llm(resolved)
    if llm_gate:
        return _gate_decision_from_llm(llm_gate, waiting, recent, resolved)

    return _fallback_gate_decision(normalized, waiting, recent, workspace, chat_session)


async def route_intent(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    content: str,
    *,
    previous_turn: IntentTurn | None = None,
    gate_context: dict[str, Any] | None = None,
) -> RouterDecision:
    resolved = await build_resolved_intent_context(
        db,
        project,
        chat_session,
        content,
        previous_turn=previous_turn,
        gate_context=gate_context,
    )

    llm_decision = await _llm_route(resolved)
    if llm_decision:
        return llm_decision

    shortcut = _rule_route(resolved)
    if shortcut:
        return shortcut

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


def gate_context_payload(gate: GateDecision) -> dict[str, Any]:
    return {
        "decision": gate.decision,
        "reason": gate.reason,
        "source": gate.source,
        "confidence": gate.confidence,
        "artifact_path": gate.artifact_path,
        "artifact_kind": gate.artifact_kind,
        "artifact_url": gate.artifact_url,
        "artifact_action": gate.artifact_action,
        "intent_turn_id": gate.intent_turn.id if gate.intent_turn else None,
    }


def casual_response(content: str) -> str:
    normalized = _normalize(content)
    if "누구" in normalized or "정체" in normalized:
        return "저는 haro입니다. 파일, 채팅 작업공간, 도구를 이용해 반복 업무를 정리하고 실행을 도와주는 AI 에이전트예요."
    if "뭐 할 수" in normalized or "무엇을 할 수" in normalized:
        return "파일 찾기, 폴더 확인, 문서/리포트 초안 작성, 코드 실행, 웹앱 미리보기 같은 일을 도울 수 있어요. 필요한 작업을 말해주면 먼저 범위를 확인하고 진행할게요."
    if "고마" in normalized or "감사" in normalized:
        return "천만에요. 필요하면 바로 이어서 도와드릴게요."
    return "안녕하세요. 필요한 업무나 확인할 파일이 있으면 편하게 말해주세요."


async def create_intent_turn(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    user_msg: Message,
    *,
    parent_intent_turn_id: str | None = None,
) -> IntentTurn:
    turn = IntentTurn(
        project_id=project.id,
        chat_session_id=chat_session.id,
        status="routing",
        original_message_id=user_msg.id,
        parent_intent_turn_id=parent_intent_turn_id,
        summary=_summarize_text(user_msg.content),
    )
    db.add(turn)
    await db.commit()
    await db.refresh(turn)
    return turn


async def update_intent_turn_from_route(db: AsyncSession, turn: IntentTurn, route: RouterDecision, status: str) -> None:
    now = _now()
    turn.status = status
    turn.current_intent = route.intent
    turn.confidence = route.confidence
    turn.risk_level = route.risk_level
    turn.selected_tools_json = json.dumps(route.selected_tools, ensure_ascii=False)
    turn.selected_skills_json = json.dumps(route.selected_skills, ensure_ascii=False)
    turn.missing_info_json = json.dumps(route.missing_info, ensure_ascii=False)
    turn.updated_at = now
    if status in {"completed", "blocked", "failed", "cancelled", "abandoned"}:
        turn.completed_at = now
    await db.commit()


async def set_intent_status(db: AsyncSession, turn: IntentTurn, status: str) -> None:
    now = _now()
    turn.status = status
    turn.updated_at = now
    if status in {"completed", "blocked", "failed", "cancelled", "abandoned"}:
        turn.completed_at = now
    await db.commit()


async def record_intent_event(
    db: AsyncSession,
    turn: IntentTurn,
    event_type: str,
    payload: dict[str, Any],
    *,
    message_id: str | None = None,
    debug_payload: dict[str, Any] | None = None,
) -> IntentTurnEvent:
    event = IntentTurnEvent(
        intent_turn_id=turn.id,
        message_id=message_id,
        event_type=event_type,
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        debug_payload_json=json.dumps(debug_payload, ensure_ascii=False, default=str) if debug_payload else None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_recent_intent_turns(db: AsyncSession, chat_session_id: str, limit: int = RECENT_INTENT_LIMIT) -> list[IntentTurn]:
    result = await db.execute(
        select(IntentTurn)
        .where(IntentTurn.chat_session_id == chat_session_id)
        .order_by(desc(IntentTurn.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def find_intent_turns_for_message(db: AsyncSession, chat_session_id: str, message_id: str) -> list[IntentTurn]:
    event_turn_ids = (
        select(IntentTurnEvent.intent_turn_id)
        .where(IntentTurnEvent.message_id == message_id)
    )
    result = await db.execute(
        select(IntentTurn)
        .where(
            IntentTurn.chat_session_id == chat_session_id,
            or_(IntentTurn.original_message_id == message_id, IntentTurn.id.in_(event_turn_ids)),
        )
        .order_by(IntentTurn.created_at.asc())
    )
    return list(result.scalars().all())


def selected_tools_from_turn(turn: IntentTurn | None) -> list[str]:
    if not turn:
        return []
    try:
        return normalize_tool_names(json.loads(turn.selected_tools_json))
    except Exception:
        return []


def clarification_question(route: RouterDecision) -> str:
    if route.question:
        return route.question
    if route.missing_info:
        return f"{route.missing_info[0]} 정보가 필요합니다. 어떤 기준으로 진행할까요?"
    return "진행하기 전에 작업 범위를 조금만 더 알려주세요."


def ambiguous_reference_question(candidates: list[IntentTurn]) -> str:
    lines = ["아까 말씀하신 작업이 어떤 건가요?"]
    for index, turn in enumerate(candidates[:3], start=1):
        lines.append(f"{index}. {turn.summary or turn.current_intent or '이전 작업'}")
    return "\n".join(lines)


async def _get_waiting_intent(db: AsyncSession, chat_session_id: str) -> IntentTurn | None:
    result = await db.execute(
        select(IntentTurn)
        .where(
            IntentTurn.chat_session_id == chat_session_id,
            IntentTurn.status.in_(["needs_clarification", "waiting_review"]),
        )
        .order_by(desc(IntentTurn.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _gate_decision_from_llm(
    result: LlmGateResult,
    waiting: IntentTurn | None,
    recent: list[IntentTurn],
    resolved: ResolvedIntentContext,
) -> GateDecision:
    candidates = _reference_candidates(recent)
    by_id = {turn.id: turn for turn in recent}
    if waiting:
        by_id[waiting.id] = waiting
    intent_turn = by_id.get(result.intent_turn_id or "")

    decision = result.decision
    if decision == "continue_intent":
        if waiting:
            intent_turn = waiting
        elif intent_turn:
            decision = "revive_intent"
        else:
            decision = "new_task"

    if decision == "cancel_intent" and not waiting:
        decision = "casual_chat"
        intent_turn = None

    if decision == "revive_intent":
        if not intent_turn and len(candidates) == 1:
            intent_turn = candidates[0]
        elif not intent_turn and len(candidates) > 1:
            decision = "ambiguous_reference"

    artifact_path = result.artifact_path or _latest_artifact_path(resolved)
    artifact_url = result.artifact_url or _latest_preview_url(resolved)
    artifact_kind = result.artifact_kind or _latest_artifact_kind(resolved)
    artifact_action = result.artifact_action if decision == "artifact_reference" else None

    if decision == "artifact_reference":
        if not intent_turn and candidates:
            intent_turn = candidates[0]
        if not artifact_path and not artifact_url:
            return GateDecision(
                "missing_artifact_reference",
                "LLM gate가 최근 산출물 참조로 판단했지만 사용할 산출물/프리뷰 정보가 없습니다.",
                intent_turn,
                candidates[:3],
                artifact_action=artifact_action,
                confidence=result.confidence,
                source="llm",
            )

    return GateDecision(
        decision,
        result.reason,
        intent_turn,
        candidates[:3],
        artifact_path=artifact_path if decision == "artifact_reference" else None,
        artifact_kind=artifact_kind if decision == "artifact_reference" else None,
        artifact_url=artifact_url if decision == "artifact_reference" else None,
        artifact_action=artifact_action,
        confidence=result.confidence,
        source="llm",
    )


def _fallback_gate_decision(
    normalized: str,
    waiting: IntentTurn | None,
    recent: list[IntentTurn],
    workspace: str | None,
    chat_session: ChatSession,
) -> GateDecision:
    if waiting:
        if _is_cancel(normalized):
            return GateDecision("cancel_intent", "LLM gate 실패 후 fallback: 취소 요청입니다.", waiting, source="fallback")
        return GateDecision("continue_intent", "LLM gate 실패 후 fallback: 진행 중인 질문에 대한 답변으로 처리합니다.", waiting, source="fallback")

    if _is_casual_chat(normalized):
        return GateDecision("casual_chat", "LLM gate 실패 후 fallback: 일반 대화입니다.", source="fallback")

    if _looks_like_artifact_reference(normalized):
        candidates = _reference_candidates(recent)
        artifact = get_latest_chat_output_reference(workspace, chat_session) if workspace else None
        if artifact:
            return GateDecision(
                "artifact_reference",
                "LLM gate 실패 후 fallback: 최근 산출물 참조 요청입니다.",
                candidates[0] if candidates else None,
                candidates[:3],
                artifact_path=artifact.get("path"),
                artifact_kind=artifact.get("kind"),
                artifact_action="unknown",
                source="fallback",
            )
        return GateDecision(
            "missing_artifact_reference",
            "LLM gate 실패 후 fallback: 참조할 최근 산출물이 없습니다.",
            candidates[0] if len(candidates) == 1 else None,
            candidates[:3],
            source="fallback",
        )

    if _looks_like_reference(normalized):
        candidates = _reference_candidates(recent)
        if len(candidates) == 1:
            return GateDecision("revive_intent", "LLM gate 실패 후 fallback: 최근 작업 후속 요청입니다.", candidates[0], candidates, source="fallback")
        if len(candidates) > 1:
            return GateDecision("ambiguous_reference", "LLM gate 실패 후 fallback: 참조 후보가 여러 개입니다.", None, candidates[:3], source="fallback")

    return GateDecision("new_task", "LLM gate 실패 후 fallback: 업무로 처리해 맥락 손실을 피합니다.", source="fallback")


def _latest_artifact_path(resolved: ResolvedIntentContext) -> str | None:
    artifact = resolved.latest_artifact or {}
    path = artifact.get("path")
    return str(path) if path else None


def _latest_artifact_kind(resolved: ResolvedIntentContext) -> str | None:
    artifact = resolved.latest_artifact or {}
    preview = resolved.latest_preview or {}
    kind = artifact.get("kind") or preview.get("kind")
    return str(kind) if kind else None


def _latest_preview_url(resolved: ResolvedIntentContext) -> str | None:
    preview = resolved.latest_preview or {}
    url = preview.get("url")
    return str(url) if url else None


def _rule_route(resolved: ResolvedIntentContext) -> RouterDecision | None:
    normalized = _normalize(resolved.routing_text)
    context = resolved.to_prompt_dict()

    if _has_count_signal(normalized):
        return RouterDecision(
            intent="file_count",
            confidence=0.92,
            can_execute=True,
            selected_tools=["file_count"],
            reason="개수 조회 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if _has_search_signal(normalized):
        return RouterDecision(
            intent="file_search",
            confidence=0.88,
            can_execute=True,
            selected_tools=["file_search", "file_read"],
            reason="파일/폴더 검색 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if _has_list_signal(normalized):
        if not _has_explicit_scope(normalized):
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
    if _has_read_signal(normalized):
        return RouterDecision(
            intent="file_read",
            confidence=0.86,
            can_execute=True,
            selected_tools=["file_search", "file_read"],
            reason="파일 읽기 요청입니다.",
            source="fallback_rule",
            routing_context=context,
        )
    if _has_create_signal(normalized):
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
        if not _has_period_or_target(normalized):
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


async def _llm_route(resolved: ResolvedIntentContext) -> RouterDecision | None:
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
        data = _parse_json_object(text)
        if not data:
            return None
        raw_tools = _as_list(data.get("selected_tools"))
        selected_tools, invalid_tools = validate_tool_names(raw_tools)
        return RouterDecision(
            intent=str(data.get("intent") or "general_task"),
            confidence=float(data.get("confidence") or 0.5),
            can_execute=_as_bool(data.get("can_execute"), default=False),
            selected_tools=selected_tools,
            selected_skills=_as_list(data.get("selected_skills")),
            missing_info=_as_list(data.get("missing_info")),
            risk_level=str(data.get("risk_level") or "low"),
            question=data.get("question"),
            reason=str(data.get("reason") or ""),
            source="llm",
            invalid_tools=invalid_tools,
            routing_context=context,
        )
    except Exception:
        return None


def _parse_json_object(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def _normalize(content: str) -> str:
    return " ".join(content.strip().lower().split())


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "가능", "실행"}:
            return True
        if normalized in {"false", "no", "n", "0", "불가", "불가능"}:
            return False
    return default


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _is_casual_chat(text: str) -> bool:
    casual_signals = ["안녕", "하이", "hello", "hi", "누구", "뭐 할 수", "무엇을 할 수", "고마", "감사"]
    return any(signal in text for signal in casual_signals) and not _looks_like_task(text)


def _looks_like_task(text: str) -> bool:
    task_signals = [
        "파일", "폴더", "찾", "검색", "읽", "보여", "만들", "생성", "수정", "삭제",
        "정리", "요약", "자동화", "메일", "리포트", "보고서", "실행", "웹앱", "프리뷰",
        "몇 개", "몇개", "개수", "저장", "업로드",
    ]
    return any(signal in text for signal in task_signals)


def _looks_like_new_task(text: str) -> bool:
    return _looks_like_task(text)


def _looks_like_strong_new_task(text: str) -> bool:
    return _looks_like_task(text) and not _looks_like_reference(text)


def _has_abandon_signal(text: str) -> bool:
    return any(signal in text for signal in ["됐고", "그건 됐", "아니", "새로", "새 프로젝트", "새 작업", "다른"])


def _is_cancel(text: str) -> bool:
    return text in {"취소", "그만", "중단", "멈춰"} or "취소해" in text or "그만해" in text


def _looks_like_reference(text: str) -> bool:
    return any(signal in text for signal in ["아까", "방금", "그거", "그 파일", "그 리포트", "이전", "전에"])


def _looks_like_artifact_reference(text: str) -> bool:
    path_signals = [
        "풀패스", "풀 패스", "full path", "전체 경로", "절대 경로", "경로", "위치",
        "어디 저장", "어디다 저장", "어디에 저장", "어디 있", "어디있", "파일명",
    ]
    if not any(signal in text for signal in path_signals):
        return False
    if any(signal in text for signal in ["말해", "알려", "뭐야", "무엇", "어디", "저장"]):
        return True
    return len(text) <= 30


def _reference_candidates(recent: list[IntentTurn]) -> list[IntentTurn]:
    return [
        turn for turn in recent
        if turn.status in {"completed", "failed", "needs_clarification", "waiting_review"}
    ]


def _has_count_signal(text: str) -> bool:
    return any(signal in text for signal in ["몇 개", "몇개", "개수", "수가", "몇 명"]) and any(
        target in text for target in ["파일", "폴더", "디렉토리", "루트", "전체"]
    )


def _has_search_signal(text: str) -> bool:
    return any(signal in text for signal in ["찾", "검색", "어디 있", "찾아"])


def _has_list_signal(text: str) -> bool:
    return any(signal in text for signal in [
        "목록", "뭐 있어", "무엇이 있어", "어떤 파일", "어떤 폴더",
        "파일 있어", "폴더 있어", "보여줘", "나열",
    ])


def _has_read_signal(text: str) -> bool:
    return any(signal in text for signal in ["읽어", "열어", "내용", "확인해"])


def _has_create_signal(text: str) -> bool:
    return any(signal in text for signal in [
        "만들어", "만들어줘", "생성해", "생성해줘", "작성해", "작성해줘",
        "저장해", "저장해줘", "파일로 만들어", "파일로 저장",
    ])


def _has_period_or_target(text: str) -> bool:
    return any(signal in text for signal in ["지난", "이번", "월", "주", "일", ".csv", ".xlsx", ".md", ".html", "/"])


def _has_explicit_scope(text: str) -> bool:
    return any(signal in text for signal in ["루트", "전체", "현재", "여기", "채팅", "clean-room", "playground", "/"])


def _summarize_text(text: str) -> str:
    return text.strip().replace("\n", " ")[:120]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
