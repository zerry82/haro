from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.plan_mode import PlanEvent, PlanSession
from app.models.project import Project
from app.services.chat_workspace_paths import full_path
from app.services.harness import normalize_workspace_path
from app.services.workspace_aliases import alias_path_for_canonical_path


PLAN_DRAFTING = "plan_drafting"
REQUIREMENTS_CLARIFYING = "requirements_clarifying"
PLAN_AWAITING_APPROVAL = "plan_awaiting_approval"
PLAN_APPROVED = "plan_approved"
PLAN_CANCELLED = "plan_cancelled"
PLAN_FAILED = "plan_failed"
EXECUTION_RUNNING = "execution_running"
EXECUTION_COMPLETED = "execution_completed"
EXECUTION_FAILED = "execution_failed"

CURRENT_PLAN_STATUSES = {
    REQUIREMENTS_CLARIFYING,
    PLAN_DRAFTING,
    PLAN_AWAITING_APPROVAL,
    PLAN_APPROVED,
    EXECUTION_RUNNING,
}
TERMINAL_PLAN_STATUSES = {
    PLAN_CANCELLED,
    PLAN_FAILED,
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
}

PLAN_READ_TOOLS = {
    "file_search",
    "file_read",
    "file_stats",
    "file_search_content",
    "file_read_range",
    "dir_list",
    "file_count",
    "web_search",
}
PLAN_WRITE_TOOLS = {"plan_file_update", "plan_approval_request"}
PLAN_ALLOWED_TOOLS = PLAN_READ_TOOLS | PLAN_WRITE_TOOLS
PLAN_MODE_SELECTED_TOOLS = [
    "file_search",
    "file_read",
    "file_stats",
    "file_search_content",
    "file_read_range",
    "dir_list",
    "file_count",
    "web_search",
    "plan_file_update",
    "plan_approval_request",
]

PLAN_SECTION_ALIASES = {
    "requirements": ("requirements", "요구사항"),
    "open_questions": ("open questions", "남은 질문", "확인 질문", "미해결 질문"),
    "evidence_ledger": ("evidence ledger", "근거 목록", "근거 수집", "출처 목록", "증거 목록"),
    "execution_plan": ("execution plan", "실행 계획", "작업 계획"),
    "acceptance_checks": ("acceptance checks", "검증 기준", "성공 기준", "완료 기준"),
}

EVIDENCE_REQUIRED_KEYWORDS = (
    "리서치",
    "보고서",
    "리포트",
    "팩트체크",
    "투자",
    "시장 분석",
    "기업 분석",
    "대시보드",
    "통계",
    "최신",
    "현재",
    "실시간",
    "뉴스",
    "주가",
    "가격",
    "매출",
    "점유율",
    "컨센서스",
    "전망",
    "분기",
    "출처",
    "research",
    "report",
    "dashboard",
    "market",
    "investment",
    "financial",
    "quarterly",
    "revenue",
    "forecast",
    "consensus",
    "latest",
    "current",
)
WORKSPACE_ORGANIZATION_SUBJECT_KEYWORDS = (
    "폴더",
    "디렉토리",
    "파일",
    "경로",
    "내 폴더",
    "결과",
    "30_outputs",
    "workspace",
    "folder",
    "directory",
    "file",
    "path",
)
WORKSPACE_ORGANIZATION_ACTION_KEYWORDS = (
    "정리",
    "정돈",
    "분류",
    "통합",
    "이동",
    "옮기",
    "삭제",
    "구조",
    "대분류",
    "하위",
    "rename",
    "move",
    "organize",
    "clean",
    "delete",
    "merge",
)
EXTERNAL_EVIDENCE_INTENT_KEYWORDS = (
    "웹 검색",
    "web search",
    "외부 자료",
    "외부 데이터",
    "검색해서",
    "검색하여",
    "출처",
    "url",
    "http://",
    "https://",
    "최신",
    "실시간",
    "뉴스",
    "주가",
    "가격",
    "매출",
    "점유율",
    "컨센서스",
    "전망",
    "분기",
    "best practice",
    "latest",
    "news",
    "source",
)

EVIDENCE_NEGATION_MARKERS = ("해당 없음", "없음", "n/a", "not applicable")
OPEN_QUESTION_CLEAR_MARKERS = ("없음", "해당 없음", "n/a", "없습니다", "none")
UNCLEAR_MARKERS = ("?", "？", "미정", "확인 필요", "추후 결정", "todo", "tbd")


@dataclass(frozen=True)
class PlanValidationResult:
    ok: bool
    reason: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlanResponseAction:
    plan_session_id: str
    action: str
    feedback: str | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_plan_file_path(chat_session: ChatSession) -> str:
    if not chat_session.folder_path:
        raise ValueError("Chat workspace folder path is not initialized")
    return normalize_workspace_path(f"{chat_session.folder_path}/working/plan.md")


def is_plan_allowed_tool(tool_name: str) -> bool:
    return tool_name in PLAN_ALLOWED_TOOLS


def can_write_path_in_plan_mode(plan_session: PlanSession, tool_name: str, path: str | None) -> bool:
    if tool_name == "plan_file_update":
        return True
    if tool_name == "plan_approval_request":
        return True
    if tool_name in PLAN_READ_TOOLS:
        return True
    return False


def plan_mode_blocked_message(tool_name: str) -> str:
    return (
        f"Plan Mode에서는 `{tool_name}` 도구를 실행할 수 없습니다. "
        "계획 파일 작성과 승인 전에는 실제 파일/코드/프리뷰 변경이 차단됩니다."
    )


def should_enter_plan_mode_for_text(text: str, *, selected_tools: list[str] | None = None, risk_level: str | None = None) -> tuple[bool, str | None]:
    normalized = " ".join((text or "").lower().split())
    selected = set(selected_tools or [])
    if any(phrase in normalized for phrase in ("please implement", "implement this plan", "구현해", "진행해", "실행해")):
        return False, None

    explicit_signals = (
        "스펙",
        "spec",
        "계획",
        "plan mode",
        "plan-mode",
        "설계",
        "어떻게 할지",
        "어떻게 진행",
        "먼저 계획",
        "먼저 설계",
    )
    if any(signal in normalized for signal in explicit_signals):
        return True, "사용자가 계획/스펙/설계를 먼저 요구했습니다."

    complex_signals = (
        "api",
        "sse",
        "데이터 모델",
        "라우팅",
        "도구 실행",
        "워크스페이스 정책",
        "프론트",
        "백엔드",
        "리서치",
        "보고서",
        "리포트",
        "팩트체크",
        "투자 분석",
        "시장 분석",
        "기업 분석",
        "대시보드",
    )
    write_tools = {
        "file_create",
        "file_write",
        "file_edit",
        "file_append",
        "file_replace_range",
        "file_delete",
        "file_move",
        "dir_create",
        "dir_delete",
        "file_export",
        "code_run",
        "web_preview",
    }
    if selected & write_tools and any(signal in normalized for signal in complex_signals):
        return True, "복잡하거나 되돌리기 어려운 변경으로 판단했습니다."

    if risk_level in {"high", "critical"}:
        return True, "고위험 작업으로 판단했습니다."

    return False, None


async def get_current_plan_session(db: AsyncSession, chat_session_id: str) -> PlanSession | None:
    result = await db.execute(
        select(PlanSession)
        .where(
            PlanSession.chat_session_id == chat_session_id,
            PlanSession.status.in_(CURRENT_PLAN_STATUSES),
        )
        .order_by(desc(PlanSession.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_plan_session(db: AsyncSession, chat_session_id: str, plan_session_id: str) -> PlanSession | None:
    result = await db.execute(
        select(PlanSession).where(
            PlanSession.id == plan_session_id,
            PlanSession.chat_session_id == chat_session_id,
        )
    )
    return result.scalar_one_or_none()


async def create_plan_session(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    message: Message,
    *,
    trigger_source: str,
    plan_file_path: str | None = None,
    intent_turn_id: str | None = None,
    reason: str | None = None,
) -> PlanSession:
    plan_session = PlanSession(
        project_id=project.id,
        chat_session_id=chat_session.id,
        original_message_id=message.id,
        intent_turn_id=intent_turn_id,
        status=REQUIREMENTS_CLARIFYING,
        trigger_source=trigger_source,
        plan_file_path=normalize_workspace_path(plan_file_path or default_plan_file_path(chat_session)),
        plan_title=message.content[:120],
    )
    db.add(plan_session)
    await db.commit()
    await db.refresh(plan_session)
    await record_plan_event(
        db,
        plan_session,
        "plan_mode_entered",
        {"trigger_source": trigger_source, "reason": reason, "plan_file_path": plan_session.plan_file_path},
        message_id=message.id,
    )
    return plan_session


def is_evidence_required_text(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    if _is_workspace_organization_text(normalized) and not _has_external_evidence_intent(normalized):
        return False
    return any(keyword in normalized for keyword in EVIDENCE_REQUIRED_KEYWORDS)


def is_evidence_required_plan(plan_session: PlanSession, plan_content: str) -> bool:
    requirements = _section_body(plan_content, PLAN_SECTION_ALIASES["requirements"])
    execution_plan = _section_body(plan_content, PLAN_SECTION_ALIASES["execution_plan"])
    scoped_content = "\n".join(
        part
        for part in (plan_session.plan_title or "", requirements or "", execution_plan or "")
        if part
    )
    return is_evidence_required_text(scoped_content or plan_content)


def analyze_plan_requirements(plan_session: PlanSession, plan_content: str) -> dict[str, Any]:
    sections = {
        key: _section_body(plan_content, aliases)
        for key, aliases in PLAN_SECTION_ALIASES.items()
    }
    evidence_required = is_evidence_required_plan(plan_session, plan_content)
    requirements_body = sections["requirements"]
    open_questions_body = sections["open_questions"]
    evidence_body = sections["evidence_ledger"]
    acceptance_body = sections["acceptance_checks"]
    as_of_date = _find_as_of_date(plan_content)
    return {
        "requirements": _extract_requirement_lines(requirements_body, plan_session.plan_title or ""),
        "sections_present": {key: body is not None for key, body in sections.items()},
        "open_questions_clear": _open_questions_are_clear(open_questions_body),
        "evidence_required": evidence_required,
        "evidence_ledger_has_sources": _evidence_ledger_has_sources(evidence_body),
        "as_of_date": as_of_date,
        "acceptance_checks_present": bool((acceptance_body or "").strip()),
    }


def validate_plan_for_approval(
    plan_session: PlanSession,
    plan_content: str,
    *,
    has_successful_evidence: bool = False,
) -> PlanValidationResult:
    snapshot = analyze_plan_requirements(plan_session, plan_content)
    missing_sections = [
        key
        for key, present in snapshot["sections_present"].items()
        if not present
    ]
    if missing_sections:
        return PlanValidationResult(
            ok=False,
            reason=(
                "계획 승인 전 요구사항 명확화 섹션이 부족합니다: "
                + ", ".join(missing_sections)
                + ". Plan File에 Requirements, Open Questions, Evidence Ledger, Execution Plan, Acceptance Checks를 포함하세요."
            ),
            payload={**snapshot, "missing_sections": missing_sections},
        )
    if not snapshot["requirements"]:
        return PlanValidationResult(
            ok=False,
            reason="Requirements 섹션에 확정된 요구사항이 없습니다.",
            payload=snapshot,
        )
    if not snapshot["open_questions_clear"]:
        return PlanValidationResult(
            ok=False,
            reason="Open Questions가 남아 있어 계획 승인을 요청할 수 없습니다. 먼저 사용자에게 요구사항을 명확히 확인하세요.",
            payload=snapshot,
        )
    if not snapshot["acceptance_checks_present"]:
        return PlanValidationResult(
            ok=False,
            reason="Acceptance Checks 섹션에 실행 후 검증 기준이 없습니다.",
            payload=snapshot,
        )
    if snapshot["evidence_required"]:
        if not has_successful_evidence:
            return PlanValidationResult(
                ok=False,
                reason="리서치/보고서/투자 분석 계획에는 성공한 web_search 근거가 필요합니다.",
                payload=snapshot,
            )
        if not snapshot["evidence_ledger_has_sources"]:
            return PlanValidationResult(
                ok=False,
                reason="Evidence Ledger에 URL 또는 출처가 포함되어 있지 않습니다.",
                payload=snapshot,
            )
        if not snapshot["as_of_date"]:
            return PlanValidationResult(
                ok=False,
                reason="Evidence Ledger 또는 계획 본문에 기준일(YYYY-MM-DD)을 명시해야 합니다.",
                payload=snapshot,
            )
    return PlanValidationResult(ok=True, payload=snapshot)


async def plan_has_successful_evidence(db: AsyncSession, plan_session: PlanSession) -> bool:
    result = await db.execute(
        select(PlanEvent)
        .where(
            PlanEvent.plan_session_id == plan_session.id,
            PlanEvent.event_type == "evidence_collected",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _extract_requirement_lines(requirements_body: str | None, fallback: str) -> list[dict[str, Any]]:
    body = (requirements_body or "").strip()
    lines = [
        re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        for line in body.splitlines()
        if line.strip()
    ]
    if not lines and fallback.strip():
        lines = [fallback.strip()]
    return [
        {
            "source_text": line,
            "interpreted_requirement": line,
            "category": "data" if is_evidence_required_text(line) else "content",
            "acceptance_check": "Acceptance Checks 섹션 기준",
            "status": "confirmed",
            "evidence_required": is_evidence_required_text(line),
        }
        for line in lines
    ]


def _is_workspace_organization_text(normalized: str) -> bool:
    return (
        any(keyword in normalized for keyword in WORKSPACE_ORGANIZATION_SUBJECT_KEYWORDS)
        and any(keyword in normalized for keyword in WORKSPACE_ORGANIZATION_ACTION_KEYWORDS)
    )


def _has_external_evidence_intent(normalized: str) -> bool:
    return any(keyword in normalized for keyword in EXTERNAL_EVIDENCE_INTENT_KEYWORDS)


def _section_body(content: str, aliases: tuple[str, ...]) -> str | None:
    lines = content.splitlines()
    start_index: int | None = None
    start_level = 0
    alias_patterns = [re.escape(alias.lower()) for alias in aliases]
    pattern = re.compile(r"^\s*(#{1,6})\s*(" + "|".join(alias_patterns) + r")\b", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            start_index = index + 1
            start_level = len(match.group(1))
            break
    if start_index is None:
        return None
    body: list[str] = []
    heading_pattern = re.compile(r"^\s*(#{1,6})\s+")
    for line in lines[start_index:]:
        match = heading_pattern.match(line)
        if match and len(match.group(1)) <= start_level:
            break
        body.append(line)
    return "\n".join(body).strip()


def _open_questions_are_clear(body: str | None) -> bool:
    if body is None:
        return False
    normalized = " ".join(body.lower().split())
    if not normalized:
        return False
    if any(marker in normalized for marker in OPEN_QUESTION_CLEAR_MARKERS):
        return True
    return not any(marker in normalized for marker in UNCLEAR_MARKERS)


def _evidence_ledger_has_sources(body: str | None) -> bool:
    if body is None:
        return False
    normalized = " ".join(body.lower().split())
    if not normalized:
        return False
    if any(marker in normalized for marker in EVIDENCE_NEGATION_MARKERS):
        return False
    return "http://" in normalized or "https://" in normalized or "url:" in normalized or "출처:" in normalized


def _find_as_of_date(content: str) -> str | None:
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", content)
    return match.group(0) if match else None


async def record_plan_event(
    db: AsyncSession,
    plan_session: PlanSession,
    event_type: str,
    payload: dict[str, Any],
    *,
    message_id: str | None = None,
) -> PlanEvent:
    event = PlanEvent(
        plan_session_id=plan_session.id,
        message_id=message_id,
        event_type=event_type,
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def request_plan_approval(db: AsyncSession, plan_session: PlanSession, *, message_id: str | None = None, summary: str | None = None) -> None:
    plan_session.status = PLAN_AWAITING_APPROVAL
    plan_session.updated_at = now()
    await db.commit()
    await record_plan_event(
        db,
        plan_session,
        "plan_approval_requested",
        {"summary": summary, "plan_file_path": plan_session.plan_file_path},
        message_id=message_id,
    )


async def approve_plan(db: AsyncSession, plan_session: PlanSession, *, message_id: str | None) -> None:
    plan_session.status = PLAN_APPROVED
    plan_session.approved_message_id = message_id
    plan_session.updated_at = now()
    await db.commit()
    await record_plan_event(db, plan_session, "plan_approved", {}, message_id=message_id)


async def reject_plan(db: AsyncSession, plan_session: PlanSession, *, message_id: str | None, feedback: str | None) -> None:
    plan_session.status = PLAN_DRAFTING
    plan_session.rejected_message_id = message_id
    plan_session.updated_at = now()
    await db.commit()
    await record_plan_event(db, plan_session, "plan_rejected", {"feedback": feedback}, message_id=message_id)


async def set_plan_status(db: AsyncSession, plan_session: PlanSession, status: str, *, event_type: str | None = None, payload: dict[str, Any] | None = None) -> None:
    plan_session.status = status
    plan_session.updated_at = now()
    if status in TERMINAL_PLAN_STATUSES:
        plan_session.completed_at = now()
    await db.commit()
    if event_type:
        await record_plan_event(db, plan_session, event_type, payload or {})


def read_plan_file(workspace: str, plan_session: PlanSession) -> str:
    full = full_path(workspace, plan_session.plan_file_path)
    if not os.path.exists(full):
        return ""
    with open(full, "r", encoding="utf-8") as file:
        return file.read()


def plan_file_display_path(plan_session: PlanSession, user_id: str) -> str:
    return alias_path_for_canonical_path(plan_session.plan_file_path, user_id)


def build_plan_mode_instruction(plan_session: PlanSession, *, feedback: str | None = None) -> str:
    feedback_block = f"\n사용자 피드백:\n{feedback}\n" if feedback else ""
    return f"""

[Plan Mode]
지금은 Claude Code 방식의 Plan Mode입니다.
- 실제 산출물, 코드, 설정, 프리뷰, 사용자 파일을 수정하지 마세요.
- 사용할 수 있는 쓰기 도구는 plan_file_update 뿐이며, 대상은 현재 Plan File 하나입니다.
- 먼저 읽고 이해하세요. 코드/파일에서 확인할 수 있는 내용은 사용자에게 묻지 마세요.
- Plan Mode는 `요구사항 명확화 -> 근거 수집 -> 계획 승인` 순서로 진행하세요.
- 요구사항이 모호하거나 충돌하면 plan_approval_request를 호출하지 말고 사용자에게 확인 질문을 하세요.
- 최신/현재/외부 데이터가 요구사항이나 계획의 전제라면 plan_approval_request 전에 web_search로 확인하세요.
- web_search가 실패하거나 사용할 수 없으면 내부 지식 기반 계획으로 조용히 대체하지 말고 blocked 상태로 멈춰 사용자 피드백을 요청하세요.
- 외부 사실, 최신 데이터, 출처 기반 리서치/보고서/투자 분석/대시보드 계획은 Evidence Ledger에 기준일(YYYY-MM-DD), URL 출처, 확인한 핵심 수치를 적기 전에는 승인 요청하지 마세요.
- Plan File에는 반드시 다음 섹션을 포함하세요: Requirements, Open Questions, Evidence Ledger, Execution Plan, Acceptance Checks.
- Open Questions가 남아 있으면 계획 승인 요청 대신 질문을 하세요. 질문이 없으면 `없음`이라고 명시하세요.
- 계획이 충분히 수렴하면 plan_approval_request를 호출하세요.
- approval을 일반 텍스트 질문으로 묻지 말고 반드시 plan_approval_request 도구를 사용하세요.
- Plan File 경로: {plan_session.plan_file_path}
{feedback_block}
""".strip()


def build_execution_instruction(plan_content: str) -> str:
    return f"""
[Approved Plan Execution]
아래 사용자가 승인한 plan을 기준으로 실제 실행을 진행하세요.
- 승인된 plan 범위 밖의 작업을 임의로 추가하지 마세요.
- 필요한 도구가 선택되지 않았으면 실행하지 말고 blocked로 멈추세요.
- 파일/폴더 생성, 수정, 이동, 삭제는 전용 파일 도구로만 실행하세요. code_run으로 워크스페이스 파일을 직접 조작하지 마세요.
- `[x] Research` 같은 텍스트 체크박스만으로 근거 수집이 끝났다고 보지 마세요. Evidence Ledger와 출처를 기준으로 실행하세요.
- 외부 사실, 최신 데이터, 출처 기반 리서치/보고서/투자 분석 산출물은 기준일, URL 출처, 한계를 포함하세요.
- 완료 보고에는 파일 생성 여부가 아니라 Acceptance Checks별 실제 검증 결과를 포함하세요.

승인된 plan:
{plan_content}
""".strip()
