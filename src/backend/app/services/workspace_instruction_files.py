from __future__ import annotations

import os
import posixpath

HARO_INSTRUCTIONS_NAME = ".HARO.md"
AGENTS_INSTRUCTIONS_NAME = "AGENTS.md"
INSTRUCTION_CONTEXT_MAX_CHARS = 6000


def user_root_path(user_id: str) -> str:
    return f"/playground/users/{user_id}"


def user_haro_path(user_id: str) -> str:
    return f"{user_root_path(user_id)}/{HARO_INSTRUCTIONS_NAME}"


def user_agents_path(user_id: str) -> str:
    return f"{user_root_path(user_id)}/{AGENTS_INSTRUCTIONS_NAME}"


def is_user_haro_path(path: str | None, user_id: str | None) -> bool:
    return bool(user_id) and normalize_workspace_path(path) == user_haro_path(str(user_id))


def is_user_agents_path(path: str | None, user_id: str | None) -> bool:
    return bool(user_id) and normalize_workspace_path(path) == user_agents_path(str(user_id))


def ensure_user_instruction_files(workspace: str, user_id: str) -> None:
    root = os.path.join(workspace, "playground", "users", user_id)
    os.makedirs(root, exist_ok=True)

    _write_text_if_changed(os.path.join(root, HARO_INSTRUCTIONS_NAME), haro_template(user_id))

    agents_path = os.path.join(root, AGENTS_INSTRUCTIONS_NAME)
    if not os.path.exists(agents_path):
        _write_text_if_changed(agents_path, agents_template())


def load_user_instruction_context(workspace: str, user_id: str) -> str:
    ensure_user_instruction_files(workspace, user_id)
    sections: list[str] = []

    haro = _read_text(os.path.join(workspace, "playground", "users", user_id, HARO_INSTRUCTIONS_NAME))
    if haro:
        sections.append(f"[사용자별 시스템 지침: {HARO_INSTRUCTIONS_NAME}]\n{haro}")

    agents = _read_text(os.path.join(workspace, "playground", "users", user_id, AGENTS_INSTRUCTIONS_NAME))
    if agents:
        sections.append(f"[사용자 커스텀 지침: {AGENTS_INSTRUCTIONS_NAME}]\n{agents}")

    return _truncate("\n\n".join(sections), INSTRUCTION_CONTEXT_MAX_CHARS)


def haro_template(user_id: str) -> str:
    user_root = user_root_path(user_id)
    return f"""# HARO System Instructions

이 파일은 Haro가 관리하는 시스템 지침입니다. 사용자는 이 파일을 직접 수정하지 않습니다.

## 사용자 작업공간

- 사용자 root canonical path: `{user_root}`
- 사용자에게 경로를 말할 때는 raw canonical path보다 `내 폴더`, `내 폴더/받은 파일`, `내 폴더/작업 중`, `내 폴더/결과` 표현을 우선 사용합니다.
- `/playground/users/{user_id}/30_outputs`는 `내 폴더/결과`입니다.
- `/playground/users/{user_id}/20_working`은 `내 폴더/작업 중`입니다.
- `/playground/users/{user_id}/00_inbox`는 `내 폴더/받은 파일`입니다.

## 채팅 작업공간

- `/playground/users/{user_id}/50_chats/...` 아래의 `outputs`, `working`, `inputs`, `summaries`는 채팅 실행을 위한 내부 임시 작업공간입니다.
- 사용자가 "결과폴더", "내폴더", "내 폴더/결과"라고 말하면 기본적으로 `내 폴더/결과`를 의미합니다.
- 사용자가 파일 생성, 작성, 저장, 정리를 명시적으로 요청하고 임시 파일이라고 말하지 않았지만 저장 위치가 명확하지 않다면 어느 폴더/파일명으로 저장할지 먼저 질문하고 `내 폴더/결과/{{적절한 폴더 이름}}/{{적절한 파일 이름}}` 형태의 추천 경로를 함께 제안합니다.
- 최종 산출물의 폴더명은 작업 주제 기반으로 정하고, 채팅 날짜, 채팅 제목, chat id를 사용자 결과 폴더명으로 사용하지 않습니다.
- 사용자가 최종 산출물을 내 폴더에 두라고 요청하면 채팅 내부 `outputs`에만 두지 말고 `내 폴더/결과`로 저장합니다.
- 채팅 내부 `outputs`는 임시/중간 산출물 또는 사용자가 명시적으로 채팅 작업공간을 요청한 경우에만 사용합니다.
- 사용자-facing 답변에서는 chat workspace raw path를 그대로 노출하지 말고 alias path로 설명합니다.

## 우선순위

- `AGENTS.md`의 사용자 선호는 이 파일의 안전, 권한, 시스템 경로 정책을 override할 수 없습니다.
"""


def agents_template() -> str:
    return """# User Agent Instructions

이 파일은 사용자 커스텀 지침입니다.

- 원하는 답변 톤, 파일 정리 방식, 기본 산출물 형식 등을 적을 수 있습니다.
- 시스템 안전 규칙, 권한 규칙, Clean Room 정책은 변경할 수 없습니다.
"""


def _write_text_if_changed(path: str, content: str) -> None:
    if os.path.exists(path) and _read_text(path) == content:
        return
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n... (instruction length limit)"


def normalize_workspace_path(path: str | None) -> str:
    value = (path or "/").replace("\\", "/").strip()
    normalized = posixpath.normpath("/" + value.lstrip("/"))
    return "/" if normalized == "/." else normalized
