# 에이전트 시스템 현재 구현

## 1. 개요

PoC에서는 팀장/팀원 에이전트를 분리하지 않는다.
하나의 에이전트가 사용자 의도 분석, 작업 계획 설명, 도구 호출, 결과 보고를 모두 담당한다.

구현 위치:

- `backend/app/services/agent.py`
- `backend/app/services/context.py`
- `backend/app/services/llm.py`

## 2. 실행 흐름

```
POST /api/projects/{project_id}/chats/{chat_id}/messages
    ↓
SSEEmitter 생성
    ↓
run_agent(db, chat_session, project, user_content, emitter)
    ↓
사용자 메시지 DB 저장
    ↓
시스템 컨텍스트 조립
    ├─ 기본 시스템 프롬프트
    ├─ .openclaw/workspace.md
    └─ .openclaw/summary_v*.md 중 최신 파일(있을 때)
    ↓
최근 메시지 20개 로드
    ↓
Gemini 스트리밍 호출
    ↓
응답에 tool_call 블록이 있으면 도구 실행
    ↓
도구 결과를 대화에 다시 넣고 다음 라운드 진행
```

최대 도구 라운드는 `MAX_TOOL_ROUNDS = 15`이다.

## 3. LLM 연동

현재 코드는 Google GenAI 클라이언트를 직접 생성한다.

```python
client = genai.Client(api_key=settings.gemini_api_key)
```

에이전트 호출은 스트리밍 API를 사용한다.

```python
client.models.generate_content_stream(
    model="gemini-3-flash-preview",
    contents=contents,
    config={
        "system_instruction": system_instruction,
        "temperature": 0.7,
    },
)
```

## 4. 도구 호출 방식

Gemini native function calling이나 MCP tools 파라미터를 쓰지 않는다.
현재 PoC는 모델에게 아래 fenced block 형식으로 응답하도록 지시하고, 백엔드가 정규식으로 파싱한다.

````markdown
```tool_call
{"tool": "file_create", "args": {"path": "/README.md", "content": "..."}}
```
````

규칙:

- 한 번에 하나의 도구만 호출한다.
- 도구 호출 전 일반 텍스트가 있으면 메시지로 저장/스트리밍한다.
- 도구 실행 결과를 `[도구 실행 결과]` 사용자 메시지 형태로 다음 LLM 라운드에 전달한다.

## 5. 현재 내장 도구

| 도구 | 설명 | 주요 인자 |
|------|------|-----------|
| `file_create` | 워크스페이스에 파일 생성 | `path`, `content` |
| `file_read` | 파일 내용 읽기 | `path` |
| `file_write` | 파일 덮어쓰기 | `path`, `content` |
| `file_delete` | 파일 삭제 | `path` |
| `dir_list` | 디렉토리 목록 조회 | `path` |
| `dir_create` | 디렉토리 생성 | `path` |
| `code_run` | Docker 샌드박스 안에서 코드 실행 | `filename`, `code` |
| `web_preview` | 샌드박스 웹 파일 서버 시작 | 없음 |

파일 도구는 프로젝트 워크스페이스 안에서만 동작하도록 경로를 검증한다.
`code_run`과 `web_preview`는 `ContainerManager`를 통해 프로젝트에 연결된 Docker 컨테이너를 사용한다.

## 6. 상태와 로그

에이전트는 실행 중 다음 이벤트를 DB와 SSE로 남긴다.

| 이벤트 | 저장/전송 위치 | 설명 |
|--------|----------------|------|
| `llm_request` | `agent_logs` | LLM 라운드 입력 일부 |
| `llm_response` | `agent_logs` | LLM 응답 일부와 소요 시간 |
| `tool_call` | `agent_logs` | 호출한 도구명과 인자 |
| `tool_result` | `agent_logs` | 도구 결과와 소요 시간 |
| `status` | SSE | planning/executing 상태 |
| `todo_step_updated` | SSE | 도구 실행 단계를 UI에 표시 |
| `file_changed` | SSE | 파일 탐색기/뷰어 갱신 트리거 |
| `preview_ready` | SSE | 웹 프리뷰 URL 전달 |
| `done` | SSE | 작업 종료 |
| `error` | SSE + `agent_logs` | 예외 발생 |

## 7. 현재 구현과 향후 확장

현재 구현은 PoC를 빠르게 검증하기 위한 직접 도구 호출 구조다.
초기 설계의 팀장/팀원 분리, MCP 기반 SkillManager, Gemini function declaration 변환은 아직 구현되어 있지 않다.
Phase 2에서 추가하려면 `run_agent`의 도구 목록/호출 부분을 SkillManager로 교체하고, 역할 분리는 오케스트레이션 레이어에서 나누면 된다.
