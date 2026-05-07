# 데이터 모델 현재 구현

## 1. 개요

현재 구현의 주 모델은 다음 구조다.

```
User (1) ──── (N) Project (1) ──── (N) ChatSession (1) ──── (N) Message
                       │                         │
                       │                         └──── (N) AgentLog
                       │
                       ├──── (1) Workspace Directory
                       └──── (0..1) Docker Sandbox Container

SandboxNode (1) ──── (N) Project
InstalledSkill       읽기 전용 스킬 목록
Session/Todo         초기 설계 호환용 레거시 모델
```

## 2. 데이터베이스

문서 초안은 PostgreSQL/pgserver를 가정했지만, 현재 코드는 SQLite를 사용한다.

| 항목 | 현재 구현 |
|------|-----------|
| 드라이버 | `sqlite+aiosqlite` |
| ORM | SQLAlchemy async |
| DB 파일 | `{DB_DATA_DIR}/haro.db` |
| 기본 경로 | `./data/pgdata/haro.db` |
| SQLite 설정 | WAL journal, foreign_keys ON |
| 스키마 생성 | 앱 시작 시 `Base.metadata.create_all` |
| 마이그레이션 | `main.py`의 ad hoc SQLite migration 함수 |

`requirements.txt`에는 PostgreSQL 관련 패키지(`pgserver`, `asyncpg`)가 아직 남아 있으나 현재 `database.py`에서는 사용하지 않는다.

## 3. 테이블

### 3.1 users

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 사용자 ID |
| `email` | String(255), UNIQUE | 이메일 |
| `password_hash` | String(255) | bcrypt 해시 |
| `name` | String(100) | 사용자 이름 |
| `created_at` | String(50) | ISO datetime 문자열 |

### 3.2 projects

프로젝트는 현재 앱의 핵심 작업 단위다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 프로젝트 ID |
| `user_id` | FK `users.id` | 소유자 |
| `title` | String(255) | 프로젝트 제목 |
| `status` | String(20) | 기본값 `idle` |
| `workspace_path` | String(500) | 물리 워크스페이스 경로 |
| `created_at` | String(50) | 생성 시각 |
| `updated_at` | String(50) | 수정 시각 |
| `sandbox_node_id` | FK `sandbox_nodes.id`, nullable | 배정된 샌드박스 노드 |
| `container_id` | String(100), nullable | Docker 컨테이너 ID |
| `container_status` | String(20) | `none`, `creating`, `running`, `stopped`, `error` 등 |
| `last_activity_at` | String(50), nullable | 샌드박스 마지막 활동 시각 |

### 3.3 chat_sessions

하나의 프로젝트 안에서 여러 대화를 분리하기 위한 모델이다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 채팅 ID |
| `project_id` | FK `projects.id` | 소속 프로젝트 |
| `title` | String(255) | 채팅 제목 |
| `created_at` | String(50) | 생성 시각 |
| `updated_at` | String(50) | 수정 시각 |

### 3.4 messages

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 메시지 ID |
| `chat_session_id` | String(36), nullable | 현재 소속 채팅 |
| `session_id` | String(36), nullable | 레거시 세션 호환 컬럼 |
| `role` | String(20) | `user`, `planner`, `executor`, `system` 등 |
| `content` | Text | 메시지 내용 |
| `metadata` | Text, nullable | JSON 문자열 용도 |
| `parent_message_id` | FK `messages.id`, nullable | 부모 메시지 |
| `compressed` | Boolean | 압축 여부. 현재 압축 로직은 미구현 |
| `created_at` | String(50) | 생성 시각 |

현재 에이전트 응답은 주로 `planner` role로 저장된다.
프론트 스트리밍 중 임시로 표시하는 `assistant`, `tool_step` role은 클라이언트 상태용이다.

### 3.5 agent_logs

에이전트 라운드별 관찰 로그.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 로그 ID |
| `chat_session_id` | String(36), nullable | 현재 소속 채팅 |
| `session_id` | String(36), nullable | 레거시 세션 호환 컬럼 |
| `round_index` | Integer | 에이전트 루프 라운드 |
| `event_type` | String(30) | `llm_request`, `llm_response`, `tool_call`, `tool_result`, `error` |
| `content` | Text | 로그 내용 |
| `duration_ms` | Float, nullable | 소요 시간 |
| `created_at` | String(50) | 생성 시각 |

### 3.6 sandbox_nodes

Docker 노드 관리용 모델.
현재 기본 노드 하나를 seed한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 노드 ID |
| `host` | String(500) | Docker host. 기본값 `unix:///var/run/docker.sock` |
| `status` | String(20) | `active`, `draining`, `offline` |
| `max_containers` | Integer | 최대 컨테이너 수 |
| `current_containers` | Integer | 현재 컨테이너 수 |
| `created_at` | String(50) | 생성 시각 |

### 3.7 installed_skills

스킬 목록 API에서 읽는 테이블.
현재는 앱 시작 시 `file_ops` 한 개를 seed한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | String(36), PK | 스킬 ID |
| `name` | String(100), UNIQUE | 스킬 이름 |
| `version` | String(20) | 버전 |
| `type` | String(20) | `builtin` 등 |
| `description` | Text, nullable | 설명 |
| `status` | String(20) | `enabled` 등 |
| `manifest` | Text | JSON 문자열 |
| `config` | Text, nullable | JSON 문자열 |
| `installed_at` | String(50) | 설치 시각 |

### 3.8 sessions

초기 설계의 작업 단위였던 레거시 모델이다.
현재 주요 API는 `projects`와 `chat_sessions`를 사용한다.
앱 시작 시 기존 `sessions` 데이터를 `projects + chat_sessions`로 옮기는 마이그레이션 코드가 있다.

### 3.9 todos / todo_steps

초기 설계의 TODO 저장 모델이다.
현재 에이전트는 DB TODO를 생성하지 않고, SSE `todo_step_updated` 이벤트로 도구 실행 단계를 클라이언트에 보여준다.

## 4. 시작 시 초기화와 마이그레이션

앱 lifespan에서 다음 작업을 수행한다.

1. SQLite 엔진 초기화
2. 워크스페이스 루트 생성
3. SQLAlchemy 모델 기준 테이블 생성
4. 레거시 `sessions` 컬럼 보강
5. 기존 `sessions` 데이터를 `projects + chat_sessions`로 이관
6. `file_ops` 스킬 seed
7. 기본 `SandboxNode` seed
8. DB의 컨테이너 상태와 실제 Docker 상태 reconcile
9. 유휴 컨테이너 정리 백그라운드 태스크 시작
