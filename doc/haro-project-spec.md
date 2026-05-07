# haro 프로젝트 스펙

Updated: 2026-04-28

## 1. 제품 개요

haro는 프로젝트별 워크스페이스를 만들고, AI 에이전트가 파일을 읽고 수정하며, 사용자가 브라우저 UI에서 파일을 탐색, 미리보기, 편집, 업로드할 수 있는 제품 개발 환경이다.

핵심 목표는 다음과 같다.

- 프로젝트별 독립 워크스페이스 제공
- 채팅 기반 AI 작업 요청 및 도구 실행
- 파일 트리 탐색, 파일 미리보기, 텍스트/CSV 편집
- Docker 샌드박스를 필요한 시점에만 사용하는 작업모드
- 웹앱을 명시적으로 활성화할 때만 유지되는 배포모드

## 2. 기술 스택

### Backend

- Python
- FastAPI
- SQLAlchemy async
- SQLite 기본 개발 DB
- Docker SDK
- Google Gemini API
- `python-multipart` 파일 업로드
- `openpyxl`, `xlrd` Excel 업로드 CSV 변환

### Frontend

- Svelte 5
- Vite
- Svelte SPA Router
- CodeMirror 6
- `marked` Markdown 렌더링
- `highlight.js` 코드 하이라이트
- `papaparse` CSV 파싱/직렬화
- `lucide-svelte` 아이콘

## 3. 주요 화면

### Dashboard

- 프로젝트 목록 표시
- 프로젝트 생성
- 프로젝트별 `작업모드 / 배포모드` 표시
- 컨테이너 상태 표시

### Project Workspace

Workspace는 크게 세 영역으로 구성된다.

- 왼쪽: VSCode 스타일 Activity Bar + 사이드 패널
- 가운데: 파일 뷰어 / 프리뷰 / 에디터
- 오른쪽: 채팅 패널

## 4. 왼쪽 사이드 패널

Activity Bar 탭은 다음 네 가지다.

- 폴더
- 스킬
- 툴
- 데이터소스

### 폴더 탭

지원 기능:

- 파일/폴더 트리 탐색
- 폴더 lazy load
- 파일 선택
- Explorer 포커스 상태 관리
- 새 폴더 생성
- 파일 업로드
- 다중 파일 업로드
- 드래그앤드랍 업로드
- 중복 파일 업로드 시 사용자 확인 후 덮어쓰기

업로드 위치 규칙:

- 폴더가 포커스된 상태: 해당 폴더 안
- 파일이 포커스된 상태: 해당 파일의 부모 폴더 안
- 포커스가 없으면 현재 선택 파일의 부모 폴더, 없으면 루트
- 드래그앤드랍 시 폴더 위에 drop하면 해당 폴더 안
- 드래그앤드랍 시 파일 위에 drop하면 해당 파일의 부모 폴더 안

Excel 업로드 규칙:

- `.xlsx`, `.xlsm`, `.xls` 파일은 원본 Excel로 저장하지 않는다.
- 업로드 시 시트별 CSV로 변환해 저장한다.
- 저장 구조:

```text
/업로드위치/엑셀파일명/시트명.csv
```

예:

```text
/report/Summary.csv
/report/Detail.csv
```

### 스킬 탭

- 기존 `GET /api/skills` API를 사용한다.
- 스킬명, 상태, 타입, 버전, 설명, 도구 목록을 표시한다.
- v1에서는 표시 전용이다.

### 툴 탭

현재 에이전트 도구 카탈로그를 표시한다.

- `file_create`
- `file_read`
- `file_write`
- `file_delete`
- `dir_list`
- `dir_create`
- `code_run`
- `web_preview`

v1에서는 클릭 실행 기능은 없다.

### 데이터소스 탭

- 현재는 “연결된 데이터소스 없음” 빈 상태만 표시한다.
- 데이터소스 연결 CRUD/API는 추후 범위다.

## 5. 파일 뷰어와 에디터

가운데 파일 패널은 선택 파일 확장자에 따라 탭 구성이 달라진다.

### Markdown

대상:

- `.md`

탭:

- 프리뷰
- 에디터
- 원본

동작:

- 기본 탭은 프리뷰
- `marked`로 Markdown HTML 렌더링
- 에디터 draft 기준으로 프리뷰 갱신

### HTML

대상:

- `.html`

탭:

- 프리뷰
- 에디터
- 원본

동작:

- 기본 탭은 프리뷰
- `iframe srcdoc`으로 Docker 없이 HTML 미리보기
- `sandbox="allow-scripts"`로 HTML 내부 script 실행 허용
- `allow-same-origin`은 사용하지 않는다.
- HTML 내용/path/revision 기반 key로 iframe을 강제 remount해 script 초기화 누락을 줄인다.
- 프리뷰 새로고침 버튼 제공

### TypeScript / JavaScript / JSON

대상:

- `.ts`
- `.js`
- `.json`

탭:

- 코드
- 에디터

동작:

- 기본 탭은 코드
- `highlight.js`로 syntax highlight
- 에디터는 CodeMirror 사용

### CSV

대상:

- `.csv`

탭:

- 프리뷰
- 에디터
- 원본

동작:

- 기본 탭은 에디터
- 프리뷰는 읽기 전용 테이블
- 에디터는 셀 단위 편집 테이블
- `Papa.parse`로 파싱
- `Papa.unparse`로 저장 문자열 생성
- 첫 번째 행은 헤더처럼 강조하지만 편집 가능하다.
- 행/열 추가, 삭제, 정렬, 필터는 v1 범위 밖이다.

### 기타 텍스트 파일

대상:

- `.txt`
- `.css`
- `.py`
- `.yaml`
- `.yml`
- `.svg`

탭:

- 에디터
- 원본

### 저장 정책

- 자동 저장 없음
- 저장 버튼 또는 `Ctrl+S`로 저장
- 저장 전 변경사항이 있으면 `수정됨` 상태 표시
- 다른 파일 선택 시 미저장 변경사항이 있으면 confirm 표시
- SSE `file_changed`가 현재 파일에 들어왔을 때 로컬 수정 중이면 덮어쓰지 않고 `외부 변경 있음` 표시

## 6. Backend 파일 API

Base path:

```text
/api/projects/{project_id}/files
```

### 파일 목록

```http
GET /api/projects/{project_id}/files?path=/
```

응답:

```json
{
  "path": "/",
  "items": [
    {
      "name": "src",
      "type": "directory",
      "children_count": 3
    }
  ]
}
```

### 파일 읽기

```http
GET /api/projects/{project_id}/files/content?path=/path/file.md
```

응답:

```json
{
  "path": "/path/file.md",
  "content": "...",
  "size": 123,
  "language": "markdown"
}
```

### 파일 저장

```http
PUT /api/projects/{project_id}/files/content?path=/path/file.md
```

요청:

```json
{
  "content": "..."
}
```

제한:

- 기존 파일만 수정 가능
- 허용 확장자만 수정 가능
- workspace 밖 경로 접근은 `403`

### 폴더 생성

```http
POST /api/projects/{project_id}/files/directories
```

요청:

```json
{
  "path": "/target/new-folder"
}
```

정책:

- 이미 존재하면 `409`
- 부모 폴더가 없으면 `404`
- workspace 밖 경로는 `403`
- 성공 후 workspace index 갱신

### 파일 업로드

```http
POST /api/projects/{project_id}/files/upload?path=/target&overwrite=false
```

요청:

- multipart form-data
- field name: `files`
- 다중 파일 허용

정책:

- 기본적으로 중복 파일은 `409`
- `overwrite=true`이면 기존 파일 덮어쓰기
- 기존 폴더와 같은 이름은 항상 `409`
- Excel 파일은 CSV로 변환 저장
- 성공 후 파일 요약과 workspace index 갱신

## 7. 프로젝트와 런타임 모드

Project 모델 주요 필드:

- `id`
- `user_id`
- `title`
- `status`
- `runtime_mode`
- `workspace_path`
- `sandbox_node_id`
- `container_id`
- `container_status`
- `last_activity_at`

### 작업모드

값:

```text
runtime_mode = "work"
```

정책:

- 프로젝트 생성 시 기본 모드
- Docker 컨테이너를 즉시 생성하지 않는다.
- 파일 작업, 일반 HTML srcdoc preview, 채팅은 Docker 없이 가능하다.
- `code_run`이 필요할 때만 샌드박스를 lazy 생성/시작한다.
- 작업모드 컨테이너는 idle timeout 이후 자동 중지 대상이다.

### 배포모드

값:

```text
runtime_mode = "deploy"
```

정책:

- 사용자가 “웹앱 활성화”를 누르면 전환된다.
- Docker 컨테이너를 생성/시작하고 `/workspace` 파일 서버를 실행한다.
- `/preview/{project_id}/`로 접근한다.
- 배포모드 컨테이너는 idle cleanup 대상에서 제외된다.
- “웹앱 비활성화” 시 컨테이너를 중지하고 작업모드로 돌아간다.

### 관련 API

```http
POST /api/projects/{project_id}/execute
POST /api/projects/{project_id}/preview
POST /api/projects/{project_id}/deploy/start
POST /api/projects/{project_id}/deploy/stop
GET  /api/projects/{project_id}/sandbox
```

## 8. AI 에이전트 스펙

### 시스템 기본 규칙

에이전트는 haro AI 에이전트로 동작한다.

주요 규칙:

- 한국어로 응답
- 파일 작업 시 제공된 도구 사용
- 작업 전 `dir_list`로 현재 파일 구조 확인
- 작업 계획을 먼저 설명한 후 도구 호출
- 한 번에 하나의 도구만 호출
- 코드 실행이 필요하면 기본적으로 TypeScript 사용
- `code_run`의 filename은 기본적으로 `.ts` 확장자 사용

### 도구 호출 출력 계약

정상 도구 호출은 반드시 다음 fenced block 형식이어야 한다.

````markdown
```tool_call
{"tool": "file_read", "args": {"path": "aggregate/combined_view.csv"}}
```
````

금지 형식:

- fence 없는 `tool_call` plain text
- 언어 태그가 `json`인 fenced block
- XML/HTML 태그 기반 도구 호출
- bullet/list 안 JSON
- 한 응답 안 여러 tool call
- 도구 호출 block 뒤 추가 문장

### 지원 도구

- `file_create(path, content)`
- `file_read(path)`
- `file_write(path, content)`
- `file_delete(path)`
- `dir_list(path)`
- `dir_create(path)`
- `code_run(filename, code)`
- `web_preview()`

### code_run

- Docker 샌드박스 안에서 실행
- `.ts`, `.js`는 Deno로 실행
- `.py`는 Python으로 실행
- 별도 지시가 없으면 TypeScript를 사용한다.

## 9. Workspace Index

프로젝트 워크스페이스 아래 `.haro` 디렉토리에 인덱스 정보를 유지한다.
기존 구현에서 생성된 `.openclaw` 디렉토리는 읽기 fallback으로 지원하지만, 신규 인덱스는 `.haro`에 기록한다.

주요 파일:

```text
.haro/workspace.md
.haro/file_summaries/*.md
```

동작:

- 파일 생성/수정/삭제 후 파일 요약 갱신
- 폴더 생성 후 workspace index 재생성
- 업로드 후 파일별 요약 갱신
- 에이전트 시스템 컨텍스트에 현재 워크스페이스 상태로 포함

## 10. SSE 이벤트

에이전트 실행 중 UI에 상태를 전달한다.

주요 이벤트:

- `status`
- `message_start`
- `message_delta`
- `message_end`
- `todo_step_updated`
- `file_changed`
- `preview_ready`
- `done`
- `error`

프론트는 `file_changed` 이벤트를 받으면 파일 트리를 갱신하고, 현재 파일이 로컬 수정 중인지에 따라 재로드 또는 외부 변경 표시를 수행한다.

## 11. 인증과 프로젝트 격리

- API는 현재 사용자 기준으로 프로젝트를 조회한다.
- 프로젝트는 사용자별 workspace path를 가진다.
- 파일 API는 workspace 밖 path traversal을 차단한다.
- 프로젝트 삭제 시 Docker sandbox 제거와 workspace 삭제를 시도한다.

## 12. 현재 알려진 제한과 다음 과제

### 대량 파일/폴더

현재 폴더 트리는 lazy load지만, 한 폴더에 파일이 2,000개 이상 있으면 응답과 렌더링이 무거워질 수 있다.

권장 다음 작업:

- 파일/폴더 검색 전용 API 추가
- 결과 limit/pagination 적용
- `node_modules`, `dist`, `.git`, `.venv` 등 ignore 규칙 체계화
- workspace index 생성 시 파일 수/depth 제한 명확화

예상 API:

```http
GET /api/projects/{project_id}/files/search?q=dashboard&limit=100
```

### CSV 에디터

현재 CSV 셀 편집은 기존 셀 값 수정 중심이다.

추후 후보:

- 행/열 추가
- 행/열 삭제
- 정렬
- 필터
- 대용량 CSV 가상 스크롤

### 데이터소스

현재 데이터소스 탭은 빈 상태 표시만 제공한다.

추후 후보:

- 데이터소스 연결 모델/API
- 연결 테스트
- Credential 저장 정책
- 에이전트 도구와 데이터소스 연결

### Tool Calling

현재는 prompt 기반 fenced block parsing을 사용한다.

운영 품질 후보:

- 파서 관대화 또는 malformed output 처리
- Gemini native function calling 전환
- MCP tool schema 전환
- 도구 호출 로그/재시도 정책 강화

## 13. 개발 및 검증 명령

Frontend build:

```powershell
cd src/frontend
npm run build
```

Backend compile check:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m py_compile app\routers\files.py app\services\agent.py app\services\context.py
```

Backend dev server:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Frontend dev server:

```powershell
cd src/frontend
npm run dev -- --host 0.0.0.0 --port 5174
```
