# 프론트엔드 화면 현재 구현

## 1. 기술 구성

| 항목 | 현재 구현 |
|------|-----------|
| 프레임워크 | Svelte 5 |
| 빌드 | Vite |
| 라우터 | `svelte-spa-router` |
| API | native `fetch` |
| SSE | `fetch` + `ReadableStream` |
| 개발 서버 | `localhost:5174` |
| 백엔드 프록시 | `/api` → `http://localhost:8001` |

## 2. 실제 라우트

`App.svelte`의 현재 라우트:

```
/login                                  → Login.svelte
/register                               → Register.svelte
/projects                               → Dashboard.svelte
/projects/:projectId                    → ProjectWorkspace.svelte
/projects/:projectId/chats/:chatId      → ProjectWorkspace.svelte
/logs                                   → Logs.svelte (레거시)
/logs/:sessionId                        → Logs.svelte (레거시)
*                                       → Login.svelte
```

앱 시작 시 `checkAuth()`를 호출하고, 인증되어 있으면 `/projects`, 아니면 `/login`으로 이동한다.

## 3. 주요 화면

### 3.1 로그인 / 회원가입

- `Login.svelte`
- `Register.svelte`
- 중앙 정렬 카드 형태의 간단한 폼
- 로그인 성공 시 JWT를 `localStorage.token`에 저장하고 `/projects`로 이동

### 3.2 프로젝트 대시보드

구현 파일: `Dashboard.svelte`

기능:

- 현재 사용자 이름 표시
- 프로젝트 목록 조회
- 새 프로젝트 생성
- 프로젝트 삭제
- 프로젝트 카드 클릭 시 `/projects/{id}`로 이동
- 카드에 채팅 수와 컨테이너 실행 상태 점 표시

프로젝트 생성 시 백엔드는 기본 채팅 세션도 함께 만든다.

### 3.3 프로젝트 워크스페이스

구현 파일: `ProjectWorkspace.svelte`

```
┌─────────────────────────────────────────────────────────────┐
│ top bar: 프로젝트로 돌아가기 / 프로젝트명 / 사용자명          │
├──────────────┬──────────────────────────┬───────────────────┤
│ 파일 탐색기   │ 파일 뷰어                 │ 채팅 패널           │
│              │                          │                   │
│ 트리 표시     │ 선택 파일 내용             │ 메시지 목록          │
│ 폴더 펼치기   │ 읽기 전용 pre/code         │ 도구 단계 인라인     │
│ 파일 클릭     │                          │ 입력창 + 전송 버튼   │
└──────────────┴──────────────────────────┴───────────────────┘
```

좌측 파일 탐색기:

- `/api/projects/{projectId}/files?path=...`로 디렉토리 로드
- 폴더 클릭 시 lazy loading
- 파일 클릭 시 중앙 뷰어 로드
- `file-changed` 브라우저 이벤트를 받으면 열린 폴더와 선택 파일을 다시 로드

중앙 파일 뷰어:

- `/api/projects/{projectId}/files/content?path=...`로 파일 내용 로드
- 현재는 plain `<pre><code>` 렌더링
- `highlight.js`와 `marked` 의존성은 설치되어 있지만 이 화면에서 적극 사용하지 않는다

우측 채팅 패널:

- 채팅 목록 전환 UI 포함
- 메시지 스트리밍 표시
- `todo_step_updated` 이벤트를 `tool_step` 메시지처럼 인라인 표시
- `status` 이벤트를 헤더 배지로 표시

## 4. 실제 파일 구조

현재 구현은 별도 컴포넌트 디렉토리 없이 route 파일 안에 UI가 들어 있다.

```
frontend/src/
├── App.svelte
├── main.ts
├── lib/
│   ├── api.ts
│   └── sse.ts
├── routes/
│   ├── Login.svelte
│   ├── Register.svelte
│   ├── Dashboard.svelte
│   ├── ProjectWorkspace.svelte
│   ├── Logs.svelte
│   └── Chat.svelte              # 레거시 세션 UI
└── stores/
    ├── auth.ts
    ├── projects.ts
    ├── chatSessions.ts
    ├── chat.ts
    ├── files.ts
    └── sessions.ts              # 레거시 세션 store
```

`Chat.svelte`와 `stores/sessions.ts`는 초기 `/chat/:sessionId` 설계의 흔적이다.
현재 `App.svelte`에는 `/chat` 라우트가 등록되어 있지 않으므로 주 화면에서 사용되지 않는다.

## 5. 상태 관리

### 5.1 auth.ts

| 상태/함수 | 설명 |
|-----------|------|
| `user` | 현재 사용자 |
| `isAuthenticated` | 인증 여부 |
| `login` | `/auth/login` 호출 후 토큰 저장 |
| `register` | `/auth/register` 호출 |
| `checkAuth` | 저장된 토큰으로 `/auth/me` 확인 |
| `logout` | 토큰과 사용자 상태 제거 |

### 5.2 projects.ts

| 상태/함수 | 설명 |
|-----------|------|
| `projects` | 프로젝트 목록 |
| `currentProjectId` | 현재 프로젝트 ID |
| `loadProjects` | 프로젝트 목록 로드 |
| `createProject` | 프로젝트 생성 |
| `deleteProject` | 프로젝트 삭제 |
| `renameProject` | 프로젝트 제목 변경 |

### 5.3 chatSessions.ts

| 상태/함수 | 설명 |
|-----------|------|
| `chatSessions` | 현재 프로젝트의 채팅 목록 |
| `currentChatId` | 현재 채팅 ID |
| `loadChatSessions` | 채팅 목록 로드 |
| `createChatSession` | 채팅 생성 |
| `deleteChatSession` | 채팅 삭제 |
| `renameChatSession` | 채팅 제목 변경 |

### 5.4 chat.ts

| 상태/함수 | 설명 |
|-----------|------|
| `messages` | 화면 메시지 목록 |
| `streaming` | SSE 스트림 진행 여부 |
| `agentStatus` | `idle`, `planning`, `executing` 등 |
| `todoSteps` | 도구 단계 호환 상태 |
| `loadMessages` | 저장된 메시지 로드 |
| `sendMessage` | 사용자 메시지 추가 후 SSE POST |

### 5.5 files.ts

| 상태/함수 | 설명 |
|-----------|------|
| `fileTree` | 파일 트리 |
| `selectedFilePath` | 선택된 파일 |
| `fileContent` | 선택 파일 내용 |
| `fileLanguage` | 백엔드가 추론한 언어 |
| `loadFiles` | 디렉토리 목록 로드 |
| `expandFolder` | 폴더 lazy loading |
| `loadFileContent` | 파일 내용 로드 |
| `reloadAllExpanded` | 열린 폴더 다시 로드 |

## 6. SSE 처리

`lib/sse.ts`의 `streamPost(path, body, onEvent)`가 POST 요청을 보내고 응답 body를 라인 단위로 파싱한다.

현재 처리하는 이벤트:

- `status`
- `message_start`
- `message_delta`
- `message_end`
- `todo_step_updated`
- `file_changed`
- `error`
- `done`

백엔드는 `preview_ready`도 보낼 수 있지만, 현재 프론트 `chat.ts`는 이 이벤트를 별도로 처리하지 않는다.

## 7. 현재 UI 제약

- 데스크톱 3분할 화면 중심
- 파일 편집은 지원하지 않고 읽기 전용 표시만 제공
- 채팅/파일/로그 화면에 이모지 아이콘이 일부 하드코딩되어 있음
- Logs 화면은 아직 새 `Project + ChatSession` 로그 API와 맞지 않는 레거시 구현이다
