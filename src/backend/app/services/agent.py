from __future__ import annotations

"""에이전트 오케스트레이션 — 자체 스킬 호출 방식 (POC)"""
import json
import os
import re
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_log import AgentLog
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.project import Project
from app.services.context import build_context, get_recent_messages
from app.services.llm import get_client
from app.services.sse import SSEEmitter
from app.services.workspace_index import META_EXCLUDES, update_file_summary

MAX_TOOL_ROUNDS = 15

TOOL_DESCRIPTIONS = """
사용 가능한 도구 목록:

1. file_create(path, content) - 새 파일 생성
2. file_read(path) - 파일 내용 읽기
3. file_write(path, content) - 기존 파일 덮어쓰기
4. file_delete(path) - 파일 삭제
5. dir_list(path) - 디렉토리 내용 조회 (기본: "/")
6. dir_create(path) - 디렉토리 생성
7. code_run(filename, code) - 코드 실행 (샌드박스 안에서). 기본적으로 TypeScript를 사용하고 filename은 .ts 확장자로 작성.
8. web_preview() - 웹앱 배포모드 활성화, 웹 프리뷰 URL 반환

도구 호출 출력 계약:
- 도구를 사용할 때는 반드시 아래 fenced block 형식만 사용하세요.
- `tool_call`이라는 단어는 반드시 code fence 언어 태그로만 쓰세요.
- code fence 바깥 일반 문장, 제목, 목록, 설명 안에 `tool_call`이라는 단어를 쓰지 마세요.
- 도구 호출 block 뒤에는 어떤 문장도 덧붙이지 말고 즉시 응답을 끝내세요.
- 한 번의 응답에는 정확히 하나의 도구 호출 block만 포함하세요.

허용되는 유일한 형식:
```tool_call
{"tool": "file_read", "args": {"path": "aggregate/combined_view.csv"}}
```

금지되는 형식:
- `tool_call` 다음 줄에 JSON을 쓰는 plain text 형식
- 언어 태그가 `json`인 fenced block
- XML/HTML 태그 안의 도구 호출
- bullet/list 안에 JSON을 넣는 형식
- 한 응답에 여러 개의 tool_call block을 넣는 형식

도구를 사용하지 않고 텍스트만 응답할 때는 일반 텍스트로 응답하세요.
작업 계획을 먼저 설명한 뒤 도구를 호출해야 한다면, 마지막은 반드시 위의 `tool_call` fenced block으로 끝내세요.
code_run을 사용할 때 별도 지시가 없으면 TypeScript 코드와 `.ts` 파일명을 사용하세요.
한 번에 하나의 도구만 호출하세요.
도구 호출 결과를 받은 후 다음 작업을 진행하세요.
"""


def _validate_path(workspace: str, requested: str) -> str:
    full = os.path.realpath(os.path.join(workspace, requested.lstrip("/")))
    if not full.startswith(os.path.realpath(workspace)):
        raise PermissionError("워크스페이스 외부 접근 불가")
    return full


async def execute_tool(workspace: str, tool_name: str, args: dict, emitter: SSEEmitter, db: AsyncSession | None = None, project: Project | None = None) -> str:
    """도구 실행 + SSE 이벤트 발행"""
    try:
        # Sandbox tools (require db + project)
        if tool_name == "code_run":
            if db is None or project is None:
                return "도구 실행 에러: code_run requires sandbox context"
            from app.services.container_manager import ContainerManager
            cm = ContainerManager(db)
            filename = args.get("filename", "script.ts")
            code = args.get("code", "")
            result = await cm.execute_code(project.id, filename, code)
            output_parts = []
            if result["stdout"]:
                output_parts.append(f"[stdout]\n{result['stdout']}")
            if result["stderr"]:
                output_parts.append(f"[stderr]\n{result['stderr']}")
            output_parts.append(f"[exit_code: {result['exit_code']}]")
            return "\n".join(output_parts)

        elif tool_name == "web_preview":
            if db is None or project is None:
                return "도구 실행 에러: web_preview requires sandbox context"
            from app.services.container_manager import ContainerManager
            cm = ContainerManager(db)
            ip = await cm.start_preview(project.id)
            preview_url = f"/preview/{project.id}/"
            emitter.emit("preview_ready", {"url": preview_url, "ip": ip})
            return f"웹 프리뷰 시작됨. URL: {preview_url}"

        path = args.get("path", "/")
        full_path = _validate_path(workspace, path)

        if tool_name == "file_create":
            os.makedirs(os.path.dirname(full_path) or full_path, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(args.get("content", ""))
            emitter.emit("file_changed", {"action": "created", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "created")
            return f"파일 생성 완료: {path}"

        elif tool_name == "file_read":
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()

        elif tool_name == "file_write":
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(args.get("content", ""))
            emitter.emit("file_changed", {"action": "modified", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "modified")
            return f"파일 수정 완료: {path}"

        elif tool_name == "file_delete":
            os.remove(full_path)
            emitter.emit("file_changed", {"action": "deleted", "path": path, "type": "file"})
            await update_file_summary(workspace, path, "deleted")
            return f"파일 삭제 완료: {path}"

        elif tool_name == "dir_list":
            if not os.path.isdir(full_path):
                return f"디렉토리 없음: {path}"
            items = []
            for entry in os.scandir(full_path):
                if entry.name in META_EXCLUDES:
                    continue
                t = "dir" if entry.is_dir() else "file"
                items.append(f"  [{t}] {entry.name}")
            return f"디렉토리 목록 ({path}):\n" + "\n".join(items) if items else f"빈 디렉토리: {path}"

        elif tool_name == "dir_create":
            os.makedirs(full_path, exist_ok=True)
            emitter.emit("file_changed", {"action": "created", "path": path, "type": "directory"})
            return f"디렉토리 생성 완료: {path}"

        else:
            return f"알 수 없는 도구: {tool_name}"

    except Exception as e:
        return f"도구 실행 에러: {str(e)}"


def parse_tool_call(text: str) -> dict | None:
    pattern = r"```tool_call\s*\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


def extract_text_without_tool_call(text: str) -> str:
    pattern = r"```tool_call\s*\n?.*?\n?```"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


async def run_agent(db: AsyncSession, chat_session: ChatSession, project: Project, user_content: str, emitter: SSEEmitter) -> None:
    """에이전트 실행 메인 루프 — 자체 스킬 호출 + 스트리밍"""
    try:
        # 1. 사용자 메시지 저장
        user_msg = Message(chat_session_id=chat_session.id, role="user", content=user_content)
        db.add(user_msg)
        await db.commit()

        emitter.emit("status", {"session_status": "planning", "message": "요청을 분석하고 있습니다..."})

        # 2. 시스템 컨텍스트 조립 (프로젝트의 워크스페이스 사용)
        system_parts = await build_context(db, project)
        system_instruction = "\n".join(system_parts) + "\n" + TOOL_DESCRIPTIONS

        # 3. 최근 대화 히스토리 (채팅 세션의 메시지 사용)
        recent = await get_recent_messages(db, chat_session.id)

        # 4. 대화 히스토리 구성
        contents = []
        for msg in recent:
            contents.append({"role": msg["role"], "parts": [{"text": msg["text"]}]})
        contents.append({"role": "user", "parts": [{"text": user_content}]})

        # 5. Tool calling 루프
        client = get_client()

        for round_num in range(MAX_TOOL_ROUNDS):
            full_text = ""
            msg_id = str(uuid.uuid4())
            started = False
            import asyncio

            # 로그: LLM 요청
            llm_input = contents[-1]["parts"][0]["text"] if contents else ""
            db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="llm_request", content=llm_input[:2000]))
            await db.commit()

            t0 = time.time()
            stream = client.models.generate_content_stream(
                model="gemini-3-flash-preview",
                contents=contents,
                config={"system_instruction": system_instruction, "temperature": 0.7},
            )

            for chunk in stream:
                if not chunk.text:
                    continue
                chunk_text = chunk.text
                full_text += chunk_text

                if "```tool_call" in full_text:
                    if started:
                        # tool_call 앞의 아직 안 보낸 텍스트가 있으면 보내기
                        pre_tool = full_text.split("```tool_call")[0]
                        already_sent_len = len(full_text) - len(chunk_text)
                        remaining = pre_tool[already_sent_len:]
                        if remaining.strip():
                            emitter.emit("message_delta", {"message_id": msg_id, "content": remaining})
                        emitter.emit("message_end", {"message_id": msg_id})
                        started = False
                    continue

                if not started:
                    emitter.emit("message_start", {"message_id": msg_id, "role": "assistant"})
                    started = True
                emitter.emit("message_delta", {"message_id": msg_id, "content": chunk_text})
                await asyncio.sleep(0)

            if started:
                emitter.emit("message_end", {"message_id": msg_id})

            llm_ms = (time.time() - t0) * 1000
            db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="llm_response", content=full_text[:4000], duration_ms=llm_ms))
            await db.commit()

            tool_call = parse_tool_call(full_text)

            if tool_call is None:
                if full_text.strip():
                    assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=full_text.strip())
                    db.add(assistant_msg)
                    await db.commit()
                break

            pre_text = extract_text_without_tool_call(full_text).strip()
            if pre_text:
                assistant_msg = Message(chat_session_id=chat_session.id, role="planner", content=pre_text)
                db.add(assistant_msg)
                await db.commit()

            tool_name = tool_call.get("tool", "")
            tool_args = tool_call.get("args", {})

            emitter.emit("status", {"session_status": "executing", "message": f"{tool_name} 실행 중..."})
            emitter.emit("todo_step_updated", {
                "todo_id": "auto",
                "step": {"description": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)[:80]})", "status": "in_progress"},
            })

            db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="tool_call", content=json.dumps({"tool": tool_name, "args": tool_args}, ensure_ascii=False)[:2000]))
            await db.commit()

            t1 = time.time()
            result = await execute_tool(project.workspace_path, tool_name, tool_args, emitter, db=db, project=project)
            tool_ms = (time.time() - t1) * 1000

            db.add(AgentLog(chat_session_id=chat_session.id, round_index=round_num, event_type="tool_result", content=json.dumps({"tool": tool_name, "result": result[:1000]}, ensure_ascii=False), duration_ms=tool_ms))
            await db.commit()

            emitter.emit("todo_step_updated", {
                "todo_id": "auto",
                "step": {"description": f"{tool_name} 완료", "status": "completed"},
            })

            contents.append({"role": "model", "parts": [{"text": full_text}]})
            contents.append({"role": "user", "parts": [{"text": f"[도구 실행 결과]\n{result}"}]})

        emitter.emit("done", {"summary": "작업이 완료되었습니다."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            db.add(AgentLog(chat_session_id=chat_session.id, round_index=-1, event_type="error", content=str(e)[:2000]))
            await db.commit()
        except Exception:
            pass
        emitter.emit("error", {"code": "AGENT_ERROR", "message": str(e)})
    finally:
        emitter.done()
