# 프로젝트 개요: haro

## 1. 프로젝트 비전

ChatGPT와 유사한 대화형 AI 서비스이되, **프로젝트마다 독립된 물리적 파일 작업 공간**을 제공한다.
사용자는 하나의 프로젝트 안에서 여러 채팅을 이어갈 수 있고, AI 에이전트는 해당 프로젝트의 파일/폴더를 직접 생성·수정·삭제하며 작업을 수행한다.

## 2. 핵심 차별점

- 프로젝트 = 독립된 파일 작업 공간
- 프로젝트 안에 여러 채팅 세션을 둘 수 있음
- AI가 단순 답변이 아니라 파일 작업, 코드 실행, 웹 프리뷰 같은 도구를 사용해 실제 산출물을 만듦
- PoC에서는 팀장/팀원 분리 없이 단일 에이전트가 계획과 실행을 모두 담당

## 3. 현재 PoC 아키텍처

```
사용자 메시지
    ↓
[단일 에이전트] ← Gemini 3 Flash Preview 스트리밍 호출
    │
    ├─ 일반 텍스트 응답 → SSE message_* 이벤트로 프론트에 표시
    │
    └─ ```tool_call JSON``` 응답
          ↓
       백엔드 내장 도구 실행
          ├─ file_create / file_write / file_delete / dir_list ...
          ├─ code_run       → Docker 샌드박스에서 실행
          └─ web_preview    → 샌드박스 파일 서버 프록시
          ↓
       file_changed / todo_step_updated / preview_ready SSE 이벤트
          ↓
       프론트엔드 3분할 화면 갱신
```

## 4. 기술 스택

| 영역 | 현재 구현 |
|------|-----------|
| 백엔드 | FastAPI (Python) |
| 프론트엔드 | Svelte 5 + Vite + svelte-spa-router |
| 실시간 통신 | POST 응답 SSE (`fetch` + `ReadableStream`) |
| 인증 | JWT Bearer Token, bcrypt 비밀번호 해시 |
| LLM | Google Gemini API, `gemini-3-flash-preview` |
| 데이터 저장 | SQLite + SQLAlchemy async (`./data/pgdata/haro.db`) |
| 파일 저장 | 로컬 파일시스템 (`./data/workspaces/{user_id}/{project_id}`) |
| 코드 실행 | Docker SDK + `denoland/deno:latest` 컨테이너 |
| 웹 프리뷰 | 컨테이너 내부 Deno file_server + FastAPI 프록시 |

## 5. 구현 범위

1. 회원가입 / 로그인
2. 프로젝트 목록, 생성, 삭제, 이름 변경
3. 프로젝트별 채팅 목록, 생성, 삭제, 이름 변경
4. 프로젝트 워크스페이스 3분할 화면
   - 좌측: 파일 탐색기
   - 중앙: 선택된 파일 뷰어
   - 우측: 채팅 인터페이스
5. 단일 에이전트의 파일 작업 및 Docker 샌드박스 코드 실행
6. SSE 기반 메시지 스트리밍, 작업 단계 표시, 파일 변경 반영
7. 에이전트 라운드별 로그 조회 API

## 6. 구현상 남아 있는 레거시

- 초기 설계의 `Session` 모델과 `/api/sessions` 일부 코드는 마이그레이션/호환용으로 남아 있다.
- 현재 주 흐름은 `Project` + `ChatSession`이다.
- MCP/FastMCP 기반 스킬 시스템은 문서상 미래 확장 방향이며, 현재 PoC의 도구 호출은 `app/services/agent.py` 내부 함수로 직접 처리한다.

## 7. 문서 구성

| 파일 | 내용 |
|------|------|
| `01-agent-system.md` | 현재 단일 에이전트와 도구 호출 루프 |
| `02-api-design.md` | 실제 FastAPI 엔드포인트 |
| `03-data-model.md` | 현재 SQLAlchemy 모델 |
| `04-frontend-design.md` | 실제 Svelte 라우트와 스토어 |
| `05-sse-protocol.md` | 현재 SSE 이벤트 |
| `06-file-workspace.md` | 프로젝트 워크스페이스와 파일 인덱스 |
| `07-skill-plugin-system.md` | 현재 스킬 목록 API와 향후 MCP 확장 |
| `08-conversation-context.md` | 현재 컨텍스트 조립 방식 |
| `09-poc-scope.md` | 현재 PoC 범위 |
