from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_debug_trace import AgentDebugTrace
from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.project import Project
from app.services.chat_workspace import append_conversation_message
from app.services.sse import SSEEmitter


async def record_debug_trace(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession,
    turn_message_id: str,
    round_index: int,
    event_type: str,
    payload: object,
    duration_ms: float | None = None,
) -> None:
    try:
        db.add(AgentDebugTrace(
            project_id=project.id,
            chat_session_id=chat_session.id,
            turn_message_id=turn_message_id,
            round_index=round_index,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            duration_ms=duration_ms,
        ))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        try:
            db.add(AgentLog(
                chat_session_id=chat_session.id,
                round_index=round_index,
                event_type="debug_trace_error",
                content=str(exc)[:2000],
            ))
            await db.commit()
        except Exception:
            await db.rollback()


async def emit_and_save_assistant(
    db: AsyncSession,
    chat_session: ChatSession,
    workspace: str,
    emitter: SSEEmitter,
    content: str,
) -> Message:
    assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=content)
    db.add(assistant_msg)
    await db.commit()
    emitter.emit("message_start", {"message_id": assistant_msg.id, "role": "assistant"})
    emitter.emit("message_delta", {"message_id": assistant_msg.id, "content": content})
    emitter.emit("message_end", {"message_id": assistant_msg.id})
    append_conversation_message(workspace, chat_session, "planner", content, assistant_msg.created_at)
    return assistant_msg
