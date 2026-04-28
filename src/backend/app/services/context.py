from __future__ import annotations

"""대화 컨텍스트 윈도우 관리"""
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.project import Project
from app.services.workspace_index import load_workspace_context

RECENT_MESSAGE_COUNT = 20

SYSTEM_PROMPT = """당신은 Mini Open Claw AI 에이전트입니다.
사용자의 요청을 분석하고, 도구를 사용하여 파일을 생성·수정·삭제하며 작업을 수행합니다.

역할:
1. 사용자 의도를 분석합니다.
2. 필요한 작업을 계획합니다.
3. 도구를 호출하여 실제 작업을 수행합니다.
4. 애매한 부분이 있으면 사용자에게 질문합니다.

규칙:
- 파일 작업 시 반드시 제공된 도구를 사용하세요.
- 작업 전 dir_list로 현재 파일 구조를 확인하세요.
- 한국어로 응답하세요.
- 작업 계획을 먼저 설명한 후 도구를 호출하세요.
- 도구 호출이 필요하면 응답의 마지막을 반드시 언어 태그가 `tool_call`인 fenced block으로 끝내세요.
- `tool_call`이라는 단어를 code fence 바깥 일반 텍스트로 출력하지 마세요.
- 한 번에 하나의 도구만 호출하세요.
"""


async def build_context(db: AsyncSession, project: Project) -> list[str]:
    """LLM에 전달할 시스템 컨텍스트를 하나의 문자열 리스트로 조립."""
    parts = [SYSTEM_PROMPT]

    # 워크스페이스 컨텍스트 (프로젝트의 워크스페이스 경로 사용)
    ws_ctx = load_workspace_context(project.workspace_path)
    if ws_ctx:
        parts.append(f"\n[현재 워크스페이스 상태]\n{ws_ctx}")

    # 대화 요약
    summary = _load_latest_summary(project.workspace_path)
    if summary:
        parts.append(f"\n[이전 대화 요약]\n{summary}")

    return parts


async def get_recent_messages(db: AsyncSession, chat_session_id: str) -> list[dict]:
    """최근 N개 메시지를 Gemini 대화 형식으로 반환 (채팅 세션 기준)"""
    stmt = (
        select(Message)
        .where(Message.chat_session_id == chat_session_id, Message.compressed == False)
        .order_by(Message.created_at.desc())
        .limit(RECENT_MESSAGE_COUNT)
    )
    result = await db.execute(stmt)
    recent = list(reversed(result.scalars().all()))

    messages = []
    for msg in recent:
        role = "model" if msg.role in ("planner", "executor", "system") else "user"
        messages.append({"role": role, "text": msg.content})
    return messages


def _load_latest_summary(workspace_path: str) -> str | None:
    openclaw = os.path.join(workspace_path, ".openclaw")
    if not os.path.exists(openclaw):
        return None
    summaries = sorted(
        [f for f in os.listdir(openclaw) if f.startswith("summary_v") and f.endswith(".md")],
        reverse=True,
    )
    if summaries:
        with open(os.path.join(openclaw, summaries[0]), "r", encoding="utf-8") as f:
            return f.read()
    return None
