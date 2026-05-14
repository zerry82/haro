from __future__ import annotations

"""대화 컨텍스트 윈도우 관리"""
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.project import Project
from app.models.chat_session import ChatSession
from app.services.chat_workspace import load_chat_context
from app.services.chat_workspace_paths import user_result_root_path
from app.services.harness import ensure_harness_structure_synced
from app.services.prompt_bundle import PromptSection
from app.services.workspace_file_db import read_workspace_briefing_counts
from app.services.workspace_index import LEGACY_META_DIR, META_DIR
from app.services.workspace_instruction_files import load_user_instruction_context

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
- 워크스페이스 파일 생성/수정/이동/삭제를 code_run으로 우회하지 말고 전용 파일/폴더 도구만 사용하세요.
- 파일 구조 확인이 필요한 작업에는 이번 턴에 제공된 디렉토리/파일 DB 도구만 사용하세요.
- 파일/폴더 검색, 개수, 요약 기반 탐색에는 이번 턴에 제공된 SQLite 파일 DB 도구만 사용하세요.
- 개수만 묻는 질문에는 이번 턴에 개수 조회 도구가 제공된 경우 우선 사용하고, 요청하지 않은 폴더를 추가로 조회하지 마세요.
- 전체 파일 트리는 컨텍스트에 제공되지 않습니다. 파일 목록을 추측하지 말고 필요한 범위만 도구로 조회하세요.
- 한국어로 응답하세요.
- 작업 계획을 먼저 설명한 후 도구를 호출하세요.
- 별도 라우터가 작업 의미를 확정하지 않습니다. 현재 작업 맥락, 열린 파일, 최근 산출물, 대화, 도구 결과를 종합해 직접 판단하세요.
- "여기", "아래", "오늘", "방금", "이 파일" 같은 지시어는 현재 열린 파일과 직전 도구 결과를 우선 근거로 해석하세요.
- active file과 latest artifact가 다르면 active file을 현재 화면으로 우선하고, 두 대상을 혼동하지 말고 구분해서 설명하세요.
- 낮은 위험의 읽기/요약/확인 요청은 맥락 확신도가 높으면 불필요하게 되묻지 말고 진행하세요.
- 파일 수정/삭제/이동처럼 되돌리기 어려운 작업에서 대상 파일, source 파일, 작업 단위가 모호하면 후보와 이유를 들어 구체적으로 확인하세요.
- 파일 작업 실패, 중복 검색, 사용자 정정("응?", "아니", "그게 맞아?")이 나오면 같은 행동을 반복하지 말고 직전 판단과 도구 결과를 먼저 진단하세요.
- 코드 실행 도구가 제공된 경우 기본적으로 TypeScript를 사용하고 filename은 `.ts` 확장자로 작성하세요.
- 사용자가 파일 생성, 작성, 저장, 정리를 명시적으로 요청했지만 위치를 말하지 않았다면 어느 폴더/파일명으로 저장할지 먼저 질문하고 `내 폴더/결과/{적절한 폴더}/{적절한 파일명}` 형태의 추천 경로를 함께 제안하세요.
- 현재 채팅 작업공간의 `outputs`, `working`은 임시/중간 산출물에만 사용하세요.
- 사용자가 `/playground/...`처럼 명시한 합법 경로는 그대로 따르세요.
- Clean Room과 `.haro` 내부 메타데이터는 직접 수정하지 마세요.
- 사용자가 파일 생성/저장/수정/삭제를 명시적으로 요청하지 않은 질문에는 파일 변경 도구를 호출하지 말고 텍스트로만 답하세요.
- 도구 호출이 필요하면 응답의 마지막을 반드시 언어 태그가 `tool_call`인 fenced block으로 끝내세요.
- `tool_call`이라는 단어를 code fence 바깥 일반 텍스트로 출력하지 마세요.
- 도구 호출 JSON이 유효하지 않으면 실행되지 않고 교정 요청을 받습니다.
- JSON 문자열 안의 백슬래시는 반드시 유효하게 escape하세요. CSS/HTML content에 불필요한 `\\ ` 조합을 넣지 마세요.
- 한 번에 하나의 도구만 호출하세요.
"""


async def build_context_sections(
    db: AsyncSession,
    project: Project,
    chat_session: ChatSession | None = None,
) -> list[PromptSection]:
    """Return prompt sections ordered for Gemini explicit cache reuse."""
    ensure_harness_structure_synced(project.workspace_path, project.user_id, initialize_git=False)
    sections = [
        PromptSection(
            id="system_prompt.static_core",
            kind="static_core",
            text=SYSTEM_PROMPT,
            cache_scope="static",
        )
    ]
    instruction_context = load_user_instruction_context(project.workspace_path, project.user_id)
    if instruction_context:
        sections.append(
            PromptSection(
                id="system_prompt.project_policy",
                kind="project_policy",
                text=instruction_context,
                cache_scope="project",
            )
        )

    runtime_parts = [build_harness_briefing(project, chat_session)]

    # 대화 요약
    summary = _load_latest_summary(project.workspace_path)
    if summary:
        runtime_parts.append(f"\n[이전 대화 요약]\n{_truncate_text(summary, PREVIOUS_SUMMARY_MAX_CHARS)}")

    sections.append(
        PromptSection(
            id="system_prompt.runtime_context",
            kind="runtime_context",
            text="\n".join(runtime_parts),
            cache_scope="runtime",
        )
    )

    return sections


async def build_context(db: AsyncSession, project: Project, chat_session: ChatSession | None = None) -> list[str]:
    """LLM에 전달할 시스템 컨텍스트를 하나의 문자열 리스트로 조립."""
    return [section.text for section in await build_context_sections(db, project, chat_session)]


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
        result_path = user_result_root_path(project.user_id)
        lines.extend([
            f"- 현재 채팅 작업공간: {chat_path}",
            f"- 사용자 결과 폴더 root는 {result_path} 입니다.",
            "- 최종 산출물 저장 위치가 명확하지 않으면 저장 전에 사용자에게 확인 질문을 하세요. 추천 경로는 `내 폴더/결과/{주제}/{파일명}`처럼 주제 기반 이름을 사용합니다.",
            "- 채팅 날짜, 채팅 제목, chat id를 사용자 결과 폴더명으로 사용하지 마세요.",
            f"- {chat_path}/outputs 또는 {chat_path}/working은 임시/중간 파일이 필요할 때만 사용합니다.",
            "- 사용자가 \"결과 폴더\", \"결과폴더\", \"내 폴더/결과\"라고 말하면 현재 사용자 결과 폴더를 의미합니다.",
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
