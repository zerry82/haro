from __future__ import annotations

from app.services.intent_resolution import ResolvedIntentContext
from app.services.intent_text_rules import (
    has_count_signal,
    has_create_signal,
    has_list_signal,
    has_modify_signal,
    has_read_signal,
    has_search_signal,
    has_web_search_signal,
    normalize,
)
from app.services.intent_types import ExecutionPolicyDecision, RouterDecision
from app.services.plan_mode import PLAN_MODE_SELECTED_TOOLS, should_enter_plan_mode_for_text
from app.services.tool_registry import normalize_tool_names


READ_ONLY_TOOLS = [
    "file_search",
    "dir_list",
    "file_count",
    "file_read",
    "file_stats",
    "file_search_content",
    "file_read_range",
]

FILE_WORK_TOOLS = [
    "file_search",
    "dir_list",
    "file_count",
    "file_read",
    "file_stats",
    "file_search_content",
    "file_read_range",
    "file_create",
    "file_write",
    "file_edit",
    "file_append",
    "file_replace_range",
    "web_preview",
]

WORKSPACE_ADMIN_TOOLS = [
    "file_search",
    "dir_list",
    "file_count",
    "file_read",
    "file_stats",
    "dir_create",
    "file_move",
    "file_delete",
    "dir_delete",
]

RESEARCH_TOOLS = [
    "web_search",
    "file_search",
    "file_read",
    "file_create",
    "file_edit",
    "file_append",
]

CODE_OR_PREVIEW_TOOLS = [
    "file_search",
    "file_read",
    "code_run",
    "web_preview",
]

MAIL_READ_TOOLS = [
    "mail_search",
    "mail_attachment_read",
]


def resolve_execution_policy(resolved: ResolvedIntentContext) -> ExecutionPolicyDecision:
    text = resolved.routing_text or resolved.current_message
    normalized = normalize(text)
    should_plan, plan_reason = should_enter_plan_mode_for_text(text)
    if _execution_requested(normalized):
        should_plan = False
        plan_reason = None

    if should_plan:
        return ExecutionPolicyDecision(
            profile="plan_mode",
            confidence=0.9,
            selected_tools=PLAN_MODE_SELECTED_TOOLS,
            risk_level="low",
            reason=plan_reason or "사용자가 승인 전 계획 수립을 요청했습니다.",
            should_enter_plan_mode=True,
            plan_mode_reason=plan_reason,
            context_confidence=_context_confidence(resolved),
            target_confidence=_target_confidence(resolved),
            source_confidence=_source_confidence(resolved),
            operation_confidence=0.8,
        )

    if _has_workspace_admin_signal(normalized):
        return _decision(
            "workspace_admin",
            WORKSPACE_ADMIN_TOOLS,
            "파일/폴더 이동, 삭제, 정리 같은 workspace 관리 작업입니다.",
            risk_level="high" if _has_delete_signal(normalized) else "medium",
            resolved=resolved,
            operation_confidence=0.82,
        )

    if _has_mail_read_signal(normalized, resolved):
        return _decision(
            "mail_read",
            MAIL_READ_TOOLS,
            "Gmail 분석 결과에서 메일 thread를 검색하거나 요약하는 작업입니다.",
            risk_level="low",
            resolved=resolved,
            operation_confidence=0.86,
        )

    if has_web_search_signal(normalized):
        return _decision(
            "research",
            RESEARCH_TOOLS,
            "외부 최신 정보 또는 출처 확인이 필요한 작업입니다.",
            risk_level="medium",
            resolved=resolved,
            operation_confidence=0.84,
        )

    if _has_code_or_preview_signal(normalized):
        return _decision(
            "code_or_preview",
            CODE_OR_PREVIEW_TOOLS,
            "코드 실행 또는 웹 프리뷰 확인 작업입니다.",
            risk_level="medium",
            resolved=resolved,
            operation_confidence=0.82,
        )

    if has_modify_signal(normalized) or has_create_signal(normalized):
        return _decision(
            "file_work",
            FILE_WORK_TOOLS,
            "파일 생성 또는 수정이 필요한 작업입니다.",
            risk_level="medium",
            resolved=resolved,
            operation_confidence=0.78,
        )

    if _has_read_only_signal(normalized):
        return _decision(
            "read_only",
            READ_ONLY_TOOLS,
            "파일, 폴더, 현재 화면, 산출물 상태 확인 작업입니다.",
            risk_level="low",
            resolved=resolved,
            operation_confidence=0.84,
        )

    if _looks_like_agentic_task(normalized, resolved):
        return _decision(
            "file_work",
            FILE_WORK_TOOLS,
            "일반 파일 기반 작업으로 executor가 맥락을 보존하며 판단합니다.",
            risk_level="medium",
            resolved=resolved,
            operation_confidence=0.62,
        )

    return _decision(
        "chat_only",
        [],
        "도구 없이 답변 가능한 대화로 판단했습니다.",
        risk_level="low",
        resolved=resolved,
        operation_confidence=0.72,
    )


def policy_to_router_decision(policy: ExecutionPolicyDecision, resolved: ResolvedIntentContext) -> RouterDecision:
    return RouterDecision(
        intent=policy.profile,
        confidence=policy.confidence,
        can_execute=policy.can_execute,
        selected_tools=normalize_tool_names(policy.selected_tools),
        selected_skills=policy.selected_skills,
        missing_info=policy.missing_info,
        risk_level=policy.risk_level,
        question=policy.question,
        reason=policy.reason,
        source=policy.source,
        routing_context={
            **resolved.to_prompt_dict(),
            "execution_policy": {
                "profile": policy.profile,
                "confidence": policy.confidence,
                "risk_level": policy.risk_level,
                "reason": policy.reason,
                "context_confidence": policy.context_confidence,
                "target_confidence": policy.target_confidence,
                "source_confidence": policy.source_confidence,
                "operation_confidence": policy.operation_confidence,
            },
        },
        should_enter_plan_mode=policy.should_enter_plan_mode,
        plan_mode_reason=policy.plan_mode_reason,
        execution_policy=policy.profile,
        context_confidence=policy.context_confidence,
        target_confidence=policy.target_confidence,
        source_confidence=policy.source_confidence,
        operation_confidence=policy.operation_confidence,
    )


def _decision(
    profile: str,
    tools: list[str],
    reason: str,
    *,
    risk_level: str,
    resolved: ResolvedIntentContext,
    operation_confidence: float,
) -> ExecutionPolicyDecision:
    return ExecutionPolicyDecision(
        profile=profile,
        confidence=0.86 if profile != "file_work" else 0.78,
        selected_tools=tools,
        risk_level=risk_level,
        reason=reason,
        context_confidence=_context_confidence(resolved),
        target_confidence=_target_confidence(resolved),
        source_confidence=_source_confidence(resolved),
        operation_confidence=operation_confidence,
    )


def _context_confidence(resolved: ResolvedIntentContext) -> float:
    discovery = resolved.file_discovery_context or {}
    open_file = discovery.get("open_file_context") or {}
    if open_file.get("active_file_path"):
        return 0.92
    if resolved.latest_artifact:
        return 0.78
    if resolved.previous_intent or resolved.recent_messages:
        return 0.68
    return 0.45


def _target_confidence(resolved: ResolvedIntentContext) -> float:
    for candidate in _discovery_candidates(resolved):
        if candidate.get("role") == "target_artifact":
            try:
                return float(candidate.get("confidence") or 0.8)
            except (TypeError, ValueError):
                return 0.8
    if resolved.latest_artifact:
        return 0.72
    return 0.45


def _source_confidence(resolved: ResolvedIntentContext) -> float:
    discovery = resolved.file_discovery_context or {}
    if discovery.get("requires_source_content") and discovery.get("source_content_missing"):
        return 0.2
    for candidate in _discovery_candidates(resolved):
        if candidate.get("role") == "source_content":
            try:
                return float(candidate.get("confidence") or 0.8)
            except (TypeError, ValueError):
                return 0.8
    return 0.55


def _discovery_candidates(resolved: ResolvedIntentContext) -> list[dict]:
    discovery = resolved.file_discovery_context or {}
    candidates = discovery.get("candidates")
    return candidates if isinstance(candidates, list) else []


def _has_read_only_signal(normalized: str) -> bool:
    return (
        has_read_signal(normalized)
        or has_search_signal(normalized)
        or has_list_signal(normalized)
        or has_count_signal(normalized)
        or any(signal in normalized for signal in ("보여", "보이는", "확인", "요약", "읽어", "뭐가"))
    )


def _has_workspace_admin_signal(normalized: str) -> bool:
    admin_words = ("정리", "정돈", "분류", "통합", "이동", "옮겨", "삭제", "rename", "move", "organize", "clean")
    scope_words = ("파일", "폴더", "디렉토리", "folder", "directory")
    return any(word in normalized for word in admin_words) and any(word in normalized for word in scope_words)


def _has_delete_signal(normalized: str) -> bool:
    return any(word in normalized for word in ("삭제", "지워", "delete", "remove", "dir_delete"))


def _has_code_or_preview_signal(normalized: str) -> bool:
    return (
        "프리뷰" in normalized
        or "preview" in normalized
        or ("코드" in normalized and ("실행" in normalized or "돌려" in normalized))
    )


def _has_mail_read_signal(normalized: str, resolved: ResolvedIntentContext) -> bool:
    mail_targets = ("메일", "이메일", "gmail", "지메일", "받은메일", "받은 메일", "보낸사람", "스레드", "thread", "첨부")
    mail_actions = ("요약", "정리", "찾", "검색", "보여", "온", "보낸", "받은", "마감", "요청", "첨부")
    if any(target in normalized for target in mail_targets) and any(action in normalized for action in mail_actions):
        return True
    mail_context = resolved.mail_context or {}
    if mail_context.get("active") and _has_read_only_signal(normalized):
        return True
    return False


def _looks_like_agentic_task(normalized: str, resolved: ResolvedIntentContext) -> bool:
    if resolved.gate_context and resolved.gate_context.get("decision") not in {None, "casual_chat"}:
        return True
    return any(
        signal in normalized
        for signal in ("해줘", "만들", "작성", "추가", "수정", "반영", "업데이트", "저장", "고쳐", "구현")
    )


def _execution_requested(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in ("please implement", "implement this plan", "구현해", "진행해", "실행해")
    )
