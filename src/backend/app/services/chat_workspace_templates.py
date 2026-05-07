from __future__ import annotations

from datetime import datetime, timezone

from app.models.chat_session import ChatSession


def readme_template(chat: ChatSession) -> str:
    return f"""# {chat.title}

status: active
created_at: {chat.created_at}
last_activity_at: {chat.updated_at}
chat_id: {chat.id}

## 목적

이 채팅에서 진행하는 작업의 목적을 기록합니다.

## 현재 상태

- 아직 정리된 상태가 없습니다.

## 주요 산출물

- 아직 연결된 산출물이 없습니다.
"""


def context_template(chat: ChatSession) -> str:
    return f"""# Current Chat Context

chat_id: {chat.id}
updated_at: {datetime.now(timezone.utc).isoformat()}

아직 압축된 맥락이 없습니다.
"""
