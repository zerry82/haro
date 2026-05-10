# src 폴더 구현 정리

작성 기준: 2026-05-06

이 문서는 `src` 폴더의 현재 구현을 빠르게 이해하기 위한 개발자용 요약이다. 기존 `src/plan` 문서의 설계 내용과 실제 코드를 함께 확인해 정리했다.

## 한 줄 요약

`src`는 haro 제품 구현이다. 사용자는 프로젝트를 만들고, 프로젝트마다 물리적인 파일 워크스페이스를 가진다. 각 프로젝트 안에는 여러 채팅이 있고, AI 에이전트는 Gemini 스트리밍 응답과 자체 도구 호출 규약을 이용해 파일 생성/수정/검색, Docker 샌드박스 코드 실행, 웹 프리뷰를 수행한다.

## 폴더 구조

```text
src/
  backend/           FastAPI 백엔드
  frontend/          Svelte 5 + Vite 프론트엔드
  sandbox-runtime/   별도 샌드박스 런타임 서버
  plan/              제품 설계/기획 문서
```

### `src/backend`

FastAPI 기반 API 서버다. 인증, 프로젝트/채팅/파일 API, 메시지 SSE 스트리밍, 에이전트 실행, 워크스페이스 인덱싱, Docker 컨테이너 관리를 담당한다.

### `src/frontend`

Svelte SPA다. 로그인/회원가입, 프로젝트 목록, 프로젝트 작업공간, 채팅, 파일 탐색기, 파일 뷰어/편집기, 디버그 트레이스, 배포/프리뷰 UI를 담당한다.

### `src/sandbox-runtime`

Docker 컨테이너 기반 코드 실행 서버의 독립형 FastAPI 구현이다. 현재 메인 백엔드는 이 서버를 호출하기보다 `backend/app/services/container_manager.py`에서 Docker SDK를 직접 사용한다. 따라서 이 폴더는 분리 런타임 후보 성격이 강하다.

### `src/plan`

프로젝트 설계 문서다. 현재 구현 개요, 에이전트 시스템, API, 데이터 모델, 프론트엔드, SSE, 파일 워크스페이스, 스킬/플러그인, 대화 컨텍스트, 현재 구현 범위를 정리한다.

## 전체 실행 흐름

```text
브라우저
  -> FastAPI /api/auth, /api/projects, /api/projects/{id}/chats
  -> POST /api/projects/{project_id}/chats/{chat_id}/messages
      -> SSEEmitter 생성
  -> run_agent 백그라운드 실행
      -> 사용자 메시지 저장
      -> intent gate 판단
      -> execution policy 결정
      -> Working Context와 시스템 컨텍스트 조립
      -> Gemini 스트리밍 호출
      -> tool_call JSON 블록 파싱
      -> TurnToolState guard 확인
      -> agent_tools 또는 container_manager 실행
      -> 파일/프리뷰/로그/디버그 이벤트 저장
      -> SSE 이벤트를 프론트엔드에 스트리밍
```

주요 SSE 이벤트는 `user_message_saved`, `status`, `message_start`, `message_delta`, `message_end`, `todo_step_updated`, `file_changed`, `preview_ready`, `summary_suggested`, `done`, `error`다.

## 백엔드 구성

### 애플리케이션 시작

핵심 파일: `src/backend/app/main.py`

서버 시작 시 수행하는 일:

- SQLite DB 초기화와 SQLAlchemy 테이블 생성
- 기존 `sessions` 기반 데이터를 `projects` + `chat_sessions` 흐름으로 마이그레이션
- `file_ops` 내장 스킬 시드
- 기본 `SandboxNode` 시드
- 워크스페이스 루트 생성
- 작업 모드 컨테이너 상태 정규화
- 유휴 컨테이너 정리 백그라운드 루프 시작
- 빌드된 프론트엔드 `dist`가 있으면 SPA 정적 파일 서빙

### 설정과 DB

핵심 파일:

- `src/backend/app/config.py`
- `src/backend/app/database.py`
- `src/backend/app/dependencies.py`

주요 설정:

- LLM: `GEMINI_API_KEY`
- 인증: `JWT_SECRET`, `JWT_EXPIRE_MINUTES`
- DB: 기본 `./data/pgdata/haro.db`
- 워크스페이스: 기본 `./data/workspaces`
- 샌드박스 이미지: 기본 `denoland/deno:latest`
- CORS: 기본 `http://localhost:5174`

DB는 `sqlite+aiosqlite`를 사용하며, SQLite `WAL`과 foreign key pragma를 켠다.

### 데이터 모델

핵심 모델:

| 모델 | 테이블 | 역할 |
|---|---|---|
| `User` | `users` | 이메일, 비밀번호 해시, 이름 |
| `Project` | `projects` | 사용자별 프로젝트와 물리 워크스페이스, 샌드박스 상태 |
| `ChatSession` | `chat_sessions` | 프로젝트 안의 개별 채팅과 채팅 폴더 |
| `Message` | `messages` | 사용자/에이전트 메시지 |
| `IntentTurn` | `intent_turns` | 한 사용자 요청의 의도 상태, 선택 도구, 누락 정보 |
| `IntentTurnEvent` | `intent_turn_events` | 게이트/라우터/질문/결과 이벤트 |
| `AgentLog` | `agent_logs` | LLM 요청/응답, 도구 호출/결과, 오류 로그 |
| `AgentDebugTrace` | `agent_debug_traces` | 디버그 모드에서 보는 상세 페이로드 |
| `InstalledSkill` | `installed_skills` | 설치된 스킬과 제공 도구 |
| `SandboxNode` | `sandbox_nodes` | Docker 노드 풀 상태 |
| `Session`, `Todo`, `TodoStep` | `sessions`, `todos`, `todo_steps` | 레거시 호환 모델 |

현재 주 흐름은 `Project` + `ChatSession`이다. `Session` API와 Todo 모델은 초기 구조의 흔적이다.

### API 라우터

| 라우터 | Prefix | 역할 |
|---|---|---|
| `auth.py` | `/api/auth` | 회원가입, 로그인, 현재 사용자 조회 |
| `projects.py` | `/api/projects` | 프로젝트 CRUD, 코드 실행, 프리뷰/배포, 샌드박스 상태 |
| `chats.py` | `/api/projects/{project_id}/chats` | 채팅 CRUD, 채팅 폴더 동기화, 요약, 산출물 export |
| `messages.py` | `/api/projects/{project_id}/chats/{chat_id}/messages` | 메시지 조회, 메시지 전송 SSE, 디버그 트레이스 조회 |
| `files.py` | `/api/projects/{project_id}/files` | 파일 목록, 검색, 폴더 생성, 업로드, 파일 읽기/저장 |
| `skills.py` | `/api/skills` | 설치 스킬 목록 |
| `logs.py` | `/api/projects/{project_id}/chats/{chat_id}/logs` | 에이전트 로그 조회 |
| `preview.py` | `/preview/{project_id}/{path}` | 샌드박스 웹서버 reverse proxy |
| `sessions.py` | `/api/sessions` | 레거시 세션 목록 호환 |

### 에이전트 실행

핵심 파일:

- `src/backend/app/services/agent.py`
- `src/backend/app/services/intent_gate.py`
- `src/backend/app/services/intent_resolution.py`
- `src/backend/app/services/intent_turns.py`
- `src/backend/app/services/execution_policy.py`
- `src/backend/app/services/file_discovery_context.py`
- `src/backend/app/services/agent_response.py`
- `src/backend/app/services/turn_tool_state.py`
- `src/backend/app/services/tool_registry.py`
- `src/backend/app/services/agent_tools.py`

흐름:

1. 사용자 메시지를 `messages`에 저장하고 채팅 `conversation.md`에도 기록한다.
2. `decide_message_gate`가 일반 대화, 새 작업, 기존 intent 이어가기, 산출물 참조, 취소 등을 판단한다.
3. 일반 대화면 `casual_chat.py`가 짧은 응답을 생성한다.
4. 작업이면 `route_intent` 호환층이 `ExecutionPolicyResolver`를 호출해 `read_only`, `file_work`, `workspace_admin`, `research`, `code_or_preview`, `plan_mode` 같은 broad profile을 고른다.
5. source 파일이 반드시 필요하지만 File Discovery 후보가 없으면 `needs_clarification` 상태로 구체적인 경로/재업로드 질문을 한다.
6. 실행 가능하면 `context.py`가 시스템 프롬프트와 하네스 브리핑을 만들고, `agent_response.py`가 Working Context를 compact JSON으로 덧붙인다.
7. Gemini `gemini-3-flash-preview`를 스트리밍 호출한다.
8. 모델 응답의 마지막 fenced block에서 `tool_call` JSON을 파싱한다.
9. 선택된 profile의 broad tool set 밖의 도구를 호출하면 차단하고 intent를 `blocked`로 종료한다.
10. `TurnToolState`가 중복 검색과 읽지 않은 파일에 대한 수정/삭제/이동을 synthetic result로 막아 모델이 먼저 확인하도록 유도한다.
11. 도구 실행 결과를 다시 모델 입력에 붙이고 최대 15라운드까지 반복한다.
12. 완료 시 intent를 `completed`로 기록하고 SSE `done`을 보낸다.

메시지 전송 요청은 선택적으로 `open_file_context`를 포함할 수 있다. 프론트엔드는 현재 선택된 파일의 경로, 언어, 활성 뷰어 탭, dirty 상태, 선택 영역 preview만 전달하며 저장되지 않은 전체 에디터 본문은 보내지 않는다. 백엔드는 이 값을 latest artifact, 최근 대화의 원문 후보, linked files, chat workspace 파일, bounded workspace search 결과와 함께 `File Discovery Context`로 후보화한 뒤 Working Context에 넣는다. active file과 latest artifact가 다르면 executor는 active file을 현재 화면 맥락으로 우선한다.

기존 `intent_router.py`는 semantic router가 아니라 compatibility adapter로 남아 있다. 세부 작업 의미는 router가 확정하지 않고, executor가 Working Context와 도구 결과를 보며 판단한다.

현재 도구 카탈로그:

- `file_create`
- `file_read`
- `file_stats`
- `file_search_content`
- `file_read_range`
- `file_write`
- `file_edit`
- `file_append`
- `file_replace_range`
- `file_delete`
- `file_move`
- `dir_list`
- `dir_create`
- `dir_delete`
- `code_run`
- `web_preview`
- `web_search`
- `file_export`
- `file_search`
- `file_count`

부분 파일 작업은 `partial_file_ops.py`의 순수 텍스트 처리 로직과 `agent_tools.py`의 권한/이벤트/인덱스 갱신 연결로 나뉜다. 기존 파일 일부 수정은 전체 `file_write`보다 `file_stats`/`file_search_content`/`file_read_range`로 범위를 좁힌 뒤 `file_edit` 또는 `file_append`를 우선 사용한다. `file_replace_range`는 줄 범위가 명확한 문서 섹션 교체용 보조 도구다.

### 워크스페이스와 파일 시스템

핵심 파일:

- `src/backend/app/services/harness.py`
- `src/backend/app/services/chat_workspace.py`
- `src/backend/app/services/workspace_file_db.py`
- `src/backend/app/services/workspace_index.py`

프로젝트 생성 시 워크스페이스는 기본적으로 아래 위치에 만들어진다.

```text
./data/workspaces/{user_id}/{project_id}
```

하네스 구조:

```text
clean-room/
  data/
  meta/
playground/
  users/{user_id}/
    00_inbox/
    20_working/
    30_outputs/
    40_rules/
    45_skills/
    50_chats/
90_archive/
.haro/
  db/
  file_summaries/
  git/
  locks/
  context/
```

정책:

- `/clean-room/...`은 읽기 전용이다.
- `/.haro/...` 내부 메타데이터는 사용자 작업 대상이 아니며 API/도구에서 접근을 막는다.
- 명시 경로 없이 파일을 만들면 현재 채팅 폴더의 `outputs` 또는 `working` 아래로 배치한다.

채팅별 작업공간은 대략 아래 형태다.

```text
/playground/users/{user_id}/50_chats/{date}-{title}-{chat_id_prefix}/
  inputs/
  working/
  outputs/
  summaries/
  README.md
  conversation.md
  context.md
  decisions.md
  rule-candidates.md
  agent-log.md
  linked-files.json
  artifacts.json
```

`workspace_file_db.py`는 `/.haro/db/workspace.db`에 워크스페이스 파일 인덱스를 저장한다. 주요 테이블은 `workspace_items`, `workspace_item_relations`, `workspace_file_events`, `workspace_db_meta`이며, 가능하면 FTS5 `workspace_items_fts`도 만든다. 파일 검색, 폴더 페이징, 개수 조회, 요약 snippet 조회가 이 DB를 사용한다.

`workspace_index.py`는 `.haro/workspace.md`와 `.haro/file_summaries`를 관리하는 레거시/보조 인덱스 역할도 한다.

### Docker 샌드박스와 프리뷰

핵심 파일: `src/backend/app/services/container_manager.py`

역할:

- 프로젝트별 Docker 컨테이너 생성/재시작/정지/삭제
- 워크스페이스를 `/workspace`로 bind mount
- TypeScript/JavaScript는 `deno run --allow-all`, Python은 `python3`, 그 외는 `cat`으로 실행
- 작업 모드 컨테이너를 일정 시간 유휴 상태면 정지
- deploy 모드에서는 컨테이너 내부에서 Deno file server를 3000번 포트로 실행
- `/preview/{project_id}/...` 경로를 컨테이너 IP의 3000번 포트로 프록시

Docker가 없어도 로그인, 프로젝트, 파일 API는 가능한 한 살아 있도록 시작 시 Docker reconcile은 의도적으로 수행하지 않는다.

## 프론트엔드 구성

### 라우팅

핵심 파일: `src/frontend/src/App.svelte`

라우트:

- `/login`
- `/register`
- `/projects`
- `/projects/:projectId`
- `/projects/:projectId/chats/:chatId`
- `/logs`
- `/logs/:sessionId`

현재 실제 주 화면은 `ProjectWorkspace.svelte`다. `Chat.svelte`, `sessions.ts`, `/logs/:sessionId`는 이전 세션 기반 흐름의 흔적이 남아 있다.

### 상태 관리

핵심 스토어:

| 파일 | 역할 |
|---|---|
| `stores/auth.ts` | 로그인, 회원가입, 토큰 저장, 현재 사용자 |
| `stores/projects.ts` | 프로젝트 목록/생성/삭제/이름변경, deploy start/stop |
| `stores/chatSessions.ts` | 프로젝트별 채팅 목록/생성/삭제/이름변경, 요약/동기화 |
| `stores/chat.ts` | 메시지 목록, SSE 메시지 전송, 에이전트 상태, 디버그 트레이스 |
| `stores/files.ts` | 파일 트리, 폴더 캐시, 파일 내용, 파일 저장, 검색, 업로드 |

`lib/api.ts`는 `/api` prefix와 JWT Bearer 헤더를 처리한다. `lib/sse.ts`는 `fetch` 응답 body를 직접 읽어 SSE 이벤트를 파싱한다.

### 프로젝트 작업공간 UI

핵심 파일: `src/frontend/src/routes/ProjectWorkspace.svelte`

주요 기능:

- 좌측 사이드 패널: 파일, 스킬, 툴, 데이터소스 탭
- 파일 탐색기: 폴더 lazy load, 페이지네이션, 가상 스크롤, 검색, 업로드, 폴더 생성
- 중앙 뷰어: preview/source/code/editor 탭
- 파일 렌더링: Markdown, HTML iframe preview, CSV table, highlight.js 코드 뷰
- 편집: CodeMirror 기반 텍스트 파일 편집과 저장
- 우측 채팅 패널: 메시지 스트리밍, tool step 표시, 채팅 목록/생성/삭제
- 디버그 모드: 사용자 메시지별 gate/router/LLM/tool trace 조회와 복사
- deploy 토글: 프로젝트 컨테이너를 deploy/work 모드로 전환
- 좌우 패널 리사이즈와 localStorage 저장

`file_changed` SSE 이벤트는 브라우저 `CustomEvent('file-changed')`로 변환되고, 작업공간 화면은 변경된 경로의 부모 폴더 캐시를 dirty 처리한 뒤 필요한 폴더만 새로 읽는다.

## 주요 개발 명령

백엔드:

```bash
cd src/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

백엔드 단위 테스트:

```bash
cd src/backend
pip install -r requirements-dev.txt
pytest
```

프론트엔드:

```bash
cd src/frontend
npm install
npm run dev -- --port 5174
```

프론트엔드 단위 테스트와 빌드:

```bash
cd src/frontend
npm test
npm run build
```

샌드박스/코드 실행/프리뷰 기능에는 Docker가 필요하다. 백엔드 설정의 기본 CORS origin이 `http://localhost:5174`이므로 프론트엔드 개발 서버도 5174 포트를 쓰는 것이 가장 단순하다.

## 구현상 주의점

- 현재 구현은 MCP/FastMCP 플러그인 시스템을 실제 도구 실행 경로로 쓰지 않는다. 실제 도구 호출은 `tool_registry.py`와 `agent_tools.py`에 직접 구현되어 있다.
- `src/sandbox-runtime`은 독립형 런타임이며, 메인 FastAPI 앱의 코드 실행 경로는 `ContainerManager`다.
- `Session`, `Todo`, `Chat.svelte`, `sessions.ts`는 레거시 성격이다. 새 흐름은 `Project` + `ChatSession`이다.
- `files.py`와 `agent_tools.py` 모두 path traversal, `.haro` 보호, Clean Room 쓰기 금지를 처리한다.
- Excel 업로드는 `.xlsx`, `.xlsm`, `.xls` 파일을 CSV 파일들로 변환해 저장한다.
- 메시지 전송 API는 일반 JSON 응답이 아니라 `text/event-stream` 응답이다.
- 에이전트 도구 호출은 한 응답에 하나의 `tool_call` fenced block만 허용하도록 프롬프트와 파서가 설계되어 있다.
- 디버그 모드가 켜져야 `AgentDebugTrace`에 상세 LLM 입력/응답/도구 결과가 저장된다.
