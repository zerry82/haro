from __future__ import annotations

"""대화 컨텍스트 윈도우 관리"""
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.project import Project
from app.models.chat_session import ChatSession
from app.services.chat_workspace import load_chat_context
from app.services.workspace_file_db import read_workspace_briefing_counts
from app.services.workspace_index import LEGACY_META_DIR, META_DIR

RECENT_MESSAGE_COUNT = 20
HARNESS_BRIEFING_MAX_CHARS = 4000
CHAT_CONTEXT_MAX_CHARS = 2400
PREVIOUS_SUMMARY_MAX_CHARS = 2000

SYSTEM_PROMPT = """당신은 haro AI 에이전트입니다.
사용자의 요청을 분석하고, 도구를 사용하여 파일을 생성·수정·삭제하며 작업을 수행합니다.

역할:
1. 사용자 의도를 분석합니다.
2. 필요한 작업을 계획합니다.
3. 도구를 호출하여 실제 작업을 수행합니다.
4. 애매한 부분이 있으면 사용자에게 질문합니다.

규칙:
- 파일 작업 시 반드시 제공된 도구를 사용하세요.
- 파일 구조 확인이 필요한 작업에는 이번 턴에 제공된 디렉토리/파일 DB 도구만 사용하세요.
- 파일/폴더 검색, 개수, 요약 기반 탐색에는 이번 턴에 제공된 SQLite 파일 DB 도구만 사용하세요.
- 개수만 묻는 질문에는 이번 턴에 개수 조회 도구가 제공된 경우 우선 사용하고, 요청하지 않은 폴더를 추가로 조회하지 마세요.
- 전체 파일 트리는 컨텍스트에 제공되지 않습니다. 파일 목록을 추측하지 말고 필요한 범위만 도구로 조회하세요.
- 한국어로 응답하세요.
- 작업 계획을 먼저 설명한 후 도구를 호출하세요.
- 코드 실행 도구가 제공된 경우 기본적으로 TypeScript를 사용하고 filename은 `.ts` 확장자로 작성하세요.
- 사용자가 파일 저장 위치를 명확히 말하지 않았다면 현재 채팅 작업공간에 저장하세요.
- 사용자가 `/playground/...`처럼 명시한 합법 경로는 그대로 따르세요.
- Clean Room과 `.haro` 내부 메타데이터는 직접 수정하지 마세요.
- 사용자가 파일 생성/저장/수정/삭제를 명시적으로 요청하지 않은 질문에는 파일 변경 도구를 호출하지 말고 텍스트로만 답하세요.
- 도구 호출이 필요하면 응답의 마지막을 반드시 언어 태그가 `tool_call`인 fenced block으로 끝내세요.
- `tool_call`이라는 단어를 code fence 바깥 일반 텍스트로 출력하지 마세요.
- 한 번에 하나의 도구만 호출하세요.
"""


async def build_context(db: AsyncSession, project: Project, chat_session: ChatSession | None = None) -> list[str]:
    """LLM에 전달할 시스템 컨텍스트를 하나의 문자열 리스트로 조립."""
    parts = [SYSTEM_PROMPT]
    parts.append(build_harness_briefing(project, chat_session))

    # 대화 요약
    summary = _load_latest_summary(project.workspace_path)
    if summary:
        parts.append(f"\n[이전 대화 요약]\n{_truncate_text(summary, PREVIOUS_SUMMARY_MAX_CHARS)}")

    return parts


def build_harness_briefing(project: Project, chat_session: ChatSession | None = None) -> str:
    """Return a compact workspace map without embedding the recursive file tree."""
    user_root = f"/playground/users/{project.user_id}"
    chat_path = chat_session.folder_path if chat_session else None
    counts = read_workspace_briefing_counts(project.workspace_path, chat_path)

    lines = [
        "\n[현재 하네스 브리핑]",
        "## 하네스 지도",
        "- /clean-room/data: 팀 공식 데이터 공간입니다. 읽기만 가능하며 직접 수정하지 않습니다.",
        "- /clean-room/meta: 공식 규칙, 스킬, 스키마, validator, trigger, hook, policy 공간입니다. 읽기만 가능하며 직접 수정하지 않습니다.",
        f"- {user_root}: 현재 사용자의 Playground 작업공간입니다.",
        "- /90_archive: 보관 공간입니다.",
        "- /.haro: haro 시스템 메타데이터 공간입니다. 목록 조회, 읽기, 쓰기 모두 사용자 작업 대상이 아닙니다.",
        "",
        "## 현재 작업 위치",
    ]

    if chat_path:
        lines.extend([
            f"- 현재 채팅 작업공간: {chat_path}",
            f"- 명시 경로가 없는 새 파일은 {chat_path}/outputs 또는 {chat_path}/working 아래에 저장합니다.",
            "- 다른 Playground 폴더로 보내야 할 때는 사용자의 명시 요청과 내보내기 절차가 필요합니다.",
        ])
    else:
        lines.append("- 현재 채팅 작업공간이 아직 지정되지 않았습니다.")

    lines.extend([
        "",
        "## 탐색 규칙",
        "- 전체 파일 트리와 전체 파일별 요약은 이 컨텍스트에 포함되지 않습니다.",
        "- 디렉토리 목록은 필요한 경로에 대해서만, 이번 턴에 제공된 목록 조회 도구로 조회하세요.",
        "- 파일명, 경로, 요약 텍스트 검색은 이번 턴에 제공된 검색 도구로 조회하세요.",
        "- 파일/폴더 개수만 묻는 질문에는 이번 턴에 제공된 개수 조회 도구를 우선 사용하세요.",
        "- 사용자가 요구하지 않은 다른 폴더나 채팅 작업공간을 추가로 조회하지 마세요.",
        "",
        "## 상태 요약",
    ])

    if counts:
        lines.extend([
            f"- DB 인덱스 기준 전체 폴더: {counts.get('total_dirs', 0)}개",
            f"- DB 인덱스 기준 전체 파일: {counts.get('total_files', 0)}개",
            f"- 루트 하위 폴더: {counts.get('root_dirs', 0)}개",
        ])
        if chat_path:
            lines.extend([
                f"- 현재 채팅 작업공간 하위 폴더: {counts.get('chat_dirs', 0)}개",
                f"- 현재 채팅 작업공간 하위 파일: {counts.get('chat_files', 0)}개",
            ])
        if counts.get("needs_rescan") == "true":
            lines.append("- 파일 DB 인덱스가 재스캔 필요 상태입니다. 탐색 결과가 오래되었을 수 있습니다.")
    else:
        lines.append("- 파일 DB 상태 요약은 아직 준비되지 않았습니다. 필요한 경우 도구로 조회하세요.")

    if chat_session:
        chat_ctx = load_chat_context(project.workspace_path, chat_session)
        lines.extend(["", "## 현재 채팅 압축 맥락"])
        if chat_ctx:
            lines.append(_truncate_text(chat_ctx, CHAT_CONTEXT_MAX_CHARS))
        else:
            lines.append("아직 압축된 채팅 맥락이 없습니다.")

    return _truncate_text("\n".join(lines), HARNESS_BRIEFING_MAX_CHARS)


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
    for meta_name in [META_DIR, LEGACY_META_DIR]:
        meta_dir = os.path.join(workspace_path, meta_name)
        if not os.path.exists(meta_dir):
            continue
        summaries = sorted(
            [f for f in os.listdir(meta_dir) if f.startswith("summary_v") and f.endswith(".md")],
            reverse=True,
        )
        if summaries:
            with open(os.path.join(meta_dir, summaries[0]), "r", encoding="utf-8") as f:
                return f.read()
    return None


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n... (길이 제한으로 일부 생략됨)"
