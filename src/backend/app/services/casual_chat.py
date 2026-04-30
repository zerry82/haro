from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.project import Project
from app.services.intent_resolution import build_resolved_intent_context
from app.services.llm import get_client


async def generate_casual_reply(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    content: str,
    *,
    gate_reason: str | None = None,
) -> str | None:
    resolved = await build_resolved_intent_context(
        db,
        project,
        chat_session,
        content,
        gate_context={
            "decision": "casual_chat",
            "reason": gate_reason,
        },
    )
    prompt = f"""
사용자의 casual_chat 메시지에 답하세요.

역할:
- 업무 실행, 도구 호출, 작업 계획을 하지 않습니다.
- 최근 대화 맥락을 자연스럽게 반영해 한국어로 1~2문장만 답합니다.
- 사용자가 감사/격려/수고 인사를 하면, 직전 작업 맥락에 맞게 짧게 응답합니다.
- 새 요청처럼 보이는 내용을 만들어내거나 산출물 상태를 새로 단정하지 않습니다.

context:
{json.dumps(_prompt_context(resolved.to_prompt_dict()), ensure_ascii=False, indent=2, default=str)}

응답 본문만 반환하세요.
"""
    try:
        response = get_client().models.generate_content(
            model="gemini-3-flash-preview",
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config={"temperature": 0.4},
        )
        return _clean_reply(getattr(response, "text", "") or "")
    except Exception:
        return None


def _prompt_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_user_message": context.get("current_user_message"),
        "gate_context": context.get("gate_context"),
        "latest_assistant_message": context.get("latest_assistant_message"),
        "latest_artifact": context.get("latest_artifact"),
        "latest_preview": context.get("latest_preview"),
        "recent_intents": context.get("recent_intents"),
        "recent_messages": context.get("recent_messages"),
    }


def _clean_reply(text: str) -> str | None:
    reply = text.strip()
    if not reply or "```tool_call" in reply:
        return None
    if len(reply) > 600:
        reply = reply[:600].rstrip()
    return reply
