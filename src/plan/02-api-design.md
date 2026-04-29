# API 엔드포인트 현재 구현

기본 prefix는 `/api`이다.
인증이 필요한 엔드포인트는 `Authorization: Bearer {token}` 헤더를 사용한다.

## 1. 인증 API

### POST `/api/auth/register`

회원가입.

**Request**

```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "홍길동"
}
```

**Response `201`**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "홍길동",
  "created_at": "2026-04-22T00:00:00+00:00"
}
```

### POST `/api/auth/login`

로그인.

**Request**

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response `200`**

```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "홍길동",
    "created_at": "2026-04-22T00:00:00+00:00"
  }
}
```

### GET `/api/auth/me`

현재 사용자 정보.

## 2. 프로젝트 API

현재 주 리소스는 `Project`이다.
프로젝트는 하나의 물리 워크스페이스와 하나의 Docker 샌드박스 상태를 가진다.

### GET `/api/projects`

사용자의 프로젝트 목록 조회.

**Response `200`**

```json
{
  "projects": [
    {
      "id": "uuid",
      "title": "Python 프로젝트",
      "status": "idle",
      "container_status": "running",
      "created_at": "2026-04-22T00:00:00+00:00",
      "updated_at": "2026-04-22T01:00:00+00:00",
      "chat_session_count": 1
    }
  ]
}
```

### POST `/api/projects`

새 프로젝트 생성.
서버는 워크스페이스 디렉토리와 기본 채팅 세션을 만들고, 가능한 경우 Docker 샌드박스 컨테이너를 생성한다.

**Request**

```json
{
  "title": "새 프로젝트"
}
```

**Response `201`**

`ProjectResponse`와 동일하다.

### PATCH `/api/projects/{project_id}`

프로젝트 제목 변경.

**Request**

```json
{
  "title": "변경된 이름"
}
```

### DELETE `/api/projects/{project_id}`

프로젝트 삭제.
연결된 샌드박스 컨테이너, 채팅, 메시지, 에이전트 로그, 워크스페이스 디렉토리를 함께 정리한다.

## 3. 프로젝트 샌드박스 API

### POST `/api/projects/{project_id}/execute`

프로젝트의 Docker 샌드박스에서 코드를 실행한다.
코드는 먼저 워크스페이스 파일로 저장된 뒤 컨테이너 안에서 실행된다.

**Request**

```json
{
  "filename": "script.ts",
  "code": "console.log('hello')"
}
```

**Response `200`**

```json
{
  "stdout": "hello\n",
  "stderr": "",
  "exit_code": 0
}
```

### POST `/api/projects/{project_id}/preview`

컨테이너 안에서 Deno 파일 서버를 시작하고 프리뷰 프록시 URL을 반환한다.

**Response `200`**

```json
{
  "preview_url": "/preview/{project_id}/",
  "status": "running"
}
```

### GET `/api/projects/{project_id}/sandbox`

샌드박스 상태 조회.

**Response `200`**

```json
{
  "container_status": "running",
  "container_id": "docker-container-id",
  "sandbox_node_id": "uuid"
}
```

## 4. 채팅 API

프로젝트 하나에 여러 채팅 세션을 둘 수 있다.

### GET `/api/projects/{project_id}/chats`

프로젝트의 채팅 목록 조회.

**Response `200`**

```json
{
  "chats": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "title": "기본 채팅",
      "created_at": "2026-04-22T00:00:00+00:00",
      "updated_at": "2026-04-22T00:00:00+00:00",
      "message_count": 3
    }
  ]
}
```

### POST `/api/projects/{project_id}/chats`

채팅 세션 생성.

**Request**

```json
{
  "title": "새 채팅"
}
```

### PATCH `/api/projects/{project_id}/chats/{chat_id}`

채팅 제목 변경.

### DELETE `/api/projects/{project_id}/chats/{chat_id}`

채팅 삭제.
프로젝트에는 최소 하나의 채팅이 남아야 한다.

## 5. 메시지 API

### GET `/api/projects/{project_id}/chats/{chat_id}/messages`

채팅 메시지 목록 조회.

**Query Params**

| 이름 | 기본값 | 설명 |
|------|--------|------|
| `limit` | `50` | 오래된 순으로 반환할 최대 메시지 수 |

**Response `200`**

```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "README 만들어줘",
      "metadata": null,
      "created_at": "2026-04-22T00:00:00+00:00"
    },
    {
      "id": "uuid",
      "role": "planner",
      "content": "README를 생성했습니다.",
      "metadata": null,
      "created_at": "2026-04-22T00:00:01+00:00"
    }
  ]
}
```

### POST `/api/projects/{project_id}/chats/{chat_id}/messages`

사용자 메시지를 보내고 SSE 스트림을 받는다.

**Request**

```json
{
  "content": "간단한 TypeScript 예제 만들어서 실행해줘"
}
```

**Response**

`text/event-stream`.
실제 이벤트는 `05-sse-protocol.md`를 따른다.

## 6. 파일 API

파일 API는 프로젝트 워크스페이스 기준 상대 경로를 사용한다.

### GET `/api/projects/{project_id}/files`

디렉토리 목록 조회.

**Query Params**

| 이름 | 기본값 | 설명 |
|------|--------|------|
| `path` | `/` | 조회할 디렉토리 |

**Response `200`**

```json
{
  "path": "/",
  "items": [
    {
      "name": "src",
      "type": "directory",
      "size": null,
      "children_count": 2
    },
    {
      "name": "README.md",
      "type": "file",
      "size": 1024,
      "children_count": null
    }
  ]
}
```

`.haro`로 시작하는 파일/디렉토리는 목록에서 제외한다.

### GET `/api/projects/{project_id}/files/content`

파일 내용 조회.

**Query Params**

| 이름 | 필수 | 설명 |
|------|------|------|
| `path` | 예 | 조회할 파일 경로 |

**Response `200`**

```json
{
  "path": "/README.md",
  "content": "# Title\n",
  "size": 8,
  "language": "markdown"
}
```

## 7. 스킬 API

### GET `/api/skills`

설치된 스킬 목록 조회.
현재는 시작 시 seed되는 `file_ops` 목록을 읽기 전용으로 보여준다.

**Response `200`**

```json
{
  "skills": [
    {
      "name": "file_ops",
      "version": "1.0.0",
      "type": "builtin",
      "status": "enabled",
      "description": "파일 시스템 도구 — 파일/디렉토리 생성, 읽기, 수정, 삭제",
      "tools": ["file_create", "file_read", "file_write", "file_delete", "dir_list", "dir_create"]
    }
  ]
}
```

스킬 설치/삭제/활성화 API는 현재 구현되어 있지 않다.

## 8. 로그 API

### GET `/api/projects/{project_id}/chats/{chat_id}/logs`

에이전트 실행 로그 조회.

**Response `200`**

```json
{
  "logs": [
    {
      "id": "uuid",
      "round_index": 0,
      "event_type": "tool_call",
      "content": "{\"tool\":\"file_create\"}",
      "duration_ms": null,
      "created_at": "2026-04-22T00:00:00+00:00"
    }
  ]
}
```

## 9. 프리뷰 프록시

### GET `/preview/{project_id}/{path:path}`

FastAPI가 프로젝트 컨테이너의 `http://{container_ip}:3000/{path}`로 프록시한다.
이 경로는 `/api` prefix를 쓰지 않는다.

## 10. 레거시 엔드포인트

### GET `/api/sessions`

초기 `Session` 모델 호환을 위한 목록 조회만 남아 있다.
현재 주요 프론트 흐름은 이 엔드포인트를 사용하지 않는다.

## 11. 공통 에러 형식

FastAPI 기본 오류 형식을 사용한다.

```json
{
  "detail": "에러 메시지"
}
```
