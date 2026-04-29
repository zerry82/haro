# POC 범위 현재 기준

## 1. POC 목표

"사용자가 프로젝트 채팅으로 요청하면 AI 에이전트가 파일을 생성/수정하고, 3분할 화면에서 실시간으로 확인할 수 있다."

현재 구현은 여기에 Docker 샌드박스 코드 실행과 웹 프리뷰까지 일부 포함한다.

## 2. 포함된 기능

| 기능 | 현재 상태 | 비고 |
|------|-----------|------|
| 회원가입 / 로그인 | 구현됨 | JWT, bcrypt |
| 프로젝트 CRUD | 구현됨 | 생성, 목록, 삭제, 이름 변경 |
| 프로젝트별 채팅 CRUD | 구현됨 | 프로젝트당 최소 1개 채팅 유지 |
| 3분할 워크스페이스 UI | 구현됨 | 파일 탐색기 + 파일 뷰어 + 채팅 |
| 단일 에이전트 | 구현됨 | 계획/실행 통합 |
| 파일 도구 | 구현됨 | `agent.py` 직접 실행 |
| SSE 스트리밍 | 구현됨 | 메시지, 도구 단계, 파일 변경 |
| 워크스페이스 인덱스 | 구현됨 | `.haro/workspace.md` |
| 최근 대화 히스토리 | 구현됨 | 최근 20개 메시지 |
| 스킬 목록 조회 | 구현됨 | `GET /api/skills`, 읽기 전용 |
| 에이전트 로그 | 구현됨 | 채팅별 `agent_logs` |
| Docker 샌드박스 | 구현됨 | Deno 컨테이너, 코드 실행 |
| 웹 프리뷰 | 구현됨 | 컨테이너 file_server 프록시 |

## 3. 현재 미구현 또는 레거시 상태

| 기능 | 현재 상태 |
|------|-----------|
| 팀장/팀원 에이전트 분리 | 미구현 |
| MCP/FastMCP 도구 호출 | 미구현. 직접 함수 호출 사용 |
| 스킬 설치/삭제 UI/API | 미구현 |
| Gemini native function calling | 미구현. fenced `tool_call` JSON 파싱 사용 |
| 대화 자동 압축 | 미구현. 요약 파일 로드는 가능 |
| LLM 기반 파일 요약 | 미구현. 단순 줄 수/첫 줄 요약 |
| 사용자 파일 편집 | 미구현. 뷰어는 읽기 전용 |
| 작업 중단/취소 | 미구현 |
| 프론트 Logs 화면 최신화 | 레거시 `/api/sessions` 기준 |
| `/chat` 세션 UI | 레거시. 현재 라우터에 등록되지 않음 |

## 4. 현재 에이전트

```
사용자 메시지
    ↓
[단일 에이전트] (gemini-3-flash-preview)
    │
    ├─ 일반 텍스트 스트리밍
    ├─ fenced tool_call JSON 파싱
    ├─ 파일 도구 직접 실행
    ├─ Docker 코드 실행
    ├─ 웹 프리뷰 시작
    └─ 결과 보고
```

시스템 프롬프트는 팀장+팀원 역할을 하나로 합친 형태다.
Phase 2에서 분리하려면 `run_agent` 바깥에 오케스트레이션 레이어를 추가한다.

## 5. 에러 처리

현재 구현:

- 도구 실행 중 예외는 대부분 문자열 `"도구 실행 에러: ..."`로 반환된다.
- 이 결과가 다음 LLM 라운드에 전달되므로 모델이 다른 도구 호출을 시도할 수 있다.
- 에이전트 전체 예외는 `AGENT_ERROR` SSE 이벤트와 `agent_logs`에 기록된다.
- 명시적인 `MAX_RETRIES = 3` 재시도 루프는 구현되어 있지 않다.

## 6. 환경 설정

현재 `.env.example` 기준:

```env
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET=your_jwt_secret_change_this
JWT_EXPIRE_MINUTES=1440

DB_DATA_DIR=./data/pgdata
WORKSPACE_ROOT=./data/workspaces

HOST=0.0.0.0
PORT=8001
CORS_ORIGINS=http://localhost:5174

SANDBOX_IMAGE=denoland/deno:latest
SANDBOX_MEM_LIMIT=256m
SANDBOX_CPU_QUOTA=50000
SANDBOX_CPU_PERIOD=100000
SANDBOX_IDLE_TIMEOUT_MINUTES=30
SANDBOX_EXEC_TIMEOUT=30
SANDBOX_DEFAULT_NODE_HOST=unix:///var/run/docker.sock
SANDBOX_DEFAULT_NODE_MAX_CONTAINERS=10
```

## 7. 현재 프로젝트 구조

```
src/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py              # SQLite + SQLAlchemy async
│   │   ├── dependencies.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── chat_session.py
│   │   │   ├── message.py
│   │   │   ├── agent_log.py
│   │   │   ├── sandbox_node.py
│   │   │   ├── skill.py
│   │   │   ├── session.py           # legacy
│   │   │   └── todo.py              # legacy
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── chats.py
│   │   │   ├── messages.py
│   │   │   ├── files.py
│   │   │   ├── skills.py
│   │   │   ├── logs.py
│   │   │   ├── preview.py
│   │   │   └── sessions.py          # legacy
│   │   └── services/
│   │       ├── agent.py
│   │       ├── auth.py
│   │       ├── container_manager.py
│   │       ├── context.py
│   │       ├── llm.py
│   │       ├── sse.py
│   │       └── workspace_index.py
│   ├── data/                        # 로컬 런타임 산출물
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.svelte
│   │   ├── routes/
│   │   │   ├── Login.svelte
│   │   │   ├── Register.svelte
│   │   │   ├── Dashboard.svelte
│   │   │   ├── ProjectWorkspace.svelte
│   │   │   ├── Logs.svelte          # legacy
│   │   │   └── Chat.svelte          # legacy
│   │   ├── stores/
│   │   └── lib/
│   ├── package.json
│   └── vite.config.ts
├── plan/
└── sandbox-poc/                     # 별도 Docker 샌드박스 실험 코드
```

## 8. SSE 구현 방식

```typescript
await streamPost(
  `/projects/${projectId}/chats/${chatId}/messages`,
  { content },
  onEvent,
);
```

주요 이벤트:

- `status`
- `message_start`
- `message_delta`
- `message_end`
- `todo_step_updated`
- `file_changed`
- `preview_ready`
- `error`
- `done`

## 9. 데모 시나리오

```
1. 회원가입 → 로그인
2. "새 프로젝트" 생성
3. 기본 채팅으로 진입
4. "TypeScript로 간단한 계산기 코드 만들고 실행해줘" 입력
5. 에이전트가 dir_list 후 파일 생성
6. file_changed 이벤트로 파일 탐색기 갱신
7. code_run 도구로 Docker 샌드박스에서 실행
8. 결과를 채팅에 보고
9. 파일 탐색기에서 생성 파일을 열어 내용 확인
```

웹 프리뷰 데모:

```
1. HTML/CSS/JS 파일 생성 요청
2. 에이전트가 파일 생성
3. web_preview 도구 호출
4. /preview/{project_id}/ 경로로 결과 확인
```
