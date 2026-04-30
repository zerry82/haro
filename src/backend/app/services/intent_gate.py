from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.services.intent_resolution import ResolvedIntentContext
from app.services.llm import get_client


VALID_GATE_DECISIONS = {
    "casual_chat",
    "continue_intent",
    "revive_intent",
    "new_task",
    "artifact_reference",
    "ambiguous_reference",
    "cancel_intent",
}


@dataclass
class LlmGateResult:
    decision: str
    reason: str
    confidence: float
    intent_turn_id: str | None = None
    artifact_path: str | None = None
    artifact_kind: str | None = None
    artifact_url: str | None = None
    artifact_action: str | None = None


async def decide_gate_with_llm(resolved: ResolvedIntentContext) -> LlmGateResult | None:
    """Use the LLM as the primary semantic gate.

    This function intentionally does not select tools. It only decides whether
    the current message is casual chat, a new task, or a follow-up to recent
    intent/artifact context.
    """
    prompt = f"""
haro 게이트 판단만 수행하세요. 도구 선택이나 작업 계획은 하지 마세요.
현재 사용자 메시지를 단독으로 보지 말고, resolved_intent_context의 최근 대화/산출물/intent 상태를 함께 보고 의미적으로 판단하세요.

허용 decision:
- casual_chat: 업무나 이전 산출물/intent와 무관한 일반 대화
- continue_intent: 진행 중인 clarification/waiting_review에 대한 답변
- revive_intent: 완료되었거나 최근에 중단된 intent를 이어가는 후속 요청
- new_task: 새 업무 요청
- artifact_reference: 최근 산출물, 파일 경로, preview, 방금 안내한 결과물에 대한 질문/문제 제기
- ambiguous_reference: 사용자가 이전 것을 가리키지만 후보 intent가 여럿이라 특정할 수 없음
- cancel_intent: 진행 중인 intent 취소

판단 원칙:
- "안보이는데?", "어디야?", "그거 안됨"처럼 짧은 말도 최근 assistant 응답, latest_artifact, latest_preview가 있으면 그 맥락으로 해석하세요.
- 최근 산출물/preview가 있는데 사용자가 경로, 위치, 확인 불가, 안 보임, 링크 문제를 말하면 artifact_reference로 판단하세요.
- artifact_reference로 판단했다면 artifact_action을 반드시 고르세요:
  - path_lookup: 사용자가 전체 경로, 위치, 파일명, preview URL 자체를 묻는 경우
  - location_explanation: 사용자가 산출물이 왜 그 위치/중첩 폴더에 저장됐는지 이유를 묻는 경우
  - preview_issue: 사용자가 preview나 HTML 결과가 보이지 않거나 열리지 않는 문제를 말하는 경우
  - summarize_artifact: 사용자가 최근 산출물이나 최근 작업 결과를 요약해 달라고 하는 경우
  - followup_task: 최근 산출물을 바탕으로 수정, 재생성, 변환 같은 추가 작업을 요청하는 경우
  - unknown: 최근 산출물 관련은 맞지만 위 범주를 자신 있게 고르기 어려운 경우
- 산출물/preview 맥락이 없고 사용자의 참조 대상이 불명확하면 casual_chat 대신 ambiguous_reference 또는 new_task/continue_intent 중 가장 안전한 판단을 고르세요.
- 일반 인사나 감사처럼 업무 실행 의미가 없고 최근 artifact 문제도 아니면 casual_chat입니다.

resolved_intent_context:
{json.dumps(resolved.to_prompt_dict(), ensure_ascii=False, indent=2)}

반드시 JSON만 반환하세요.
필드:
decision, reason, confidence, intent_turn_id, artifact_path, artifact_kind, artifact_url, artifact_action

intent_turn_id는 recent_intents 또는 previous_intent의 id 중 하나이거나 null입니다.
artifact_path는 latest_artifact.path를 참조할 때만 채우고, artifact_url은 latest_preview.url을 참조할 때만 채우세요.
artifact_action은 artifact_reference일 때만 채우고, 다른 decision에서는 null로 두세요.
"""
    try:
        client = get_client()
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config={"temperature": 0.05},
        )
        data = _parse_json_object(getattr(response, "text", "") or "")
        if not data:
            return None
        decision = str(data.get("decision") or "").strip()
        if decision not in VALID_GATE_DECISIONS:
            return None
        return LlmGateResult(
            decision=decision,
            reason=str(data.get("reason") or "LLM gate decision"),
            confidence=_as_float(data.get("confidence"), default=0.5),
            intent_turn_id=_optional_str(data.get("intent_turn_id")),
            artifact_path=_optional_str(data.get("artifact_path")),
            artifact_kind=_optional_str(data.get("artifact_kind")),
            artifact_url=_optional_str(data.get("artifact_url")),
            artifact_action=_optional_str(data.get("artifact_action")),
        )
    except Exception:
        return None


def _parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except Exception:
            return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def _as_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
