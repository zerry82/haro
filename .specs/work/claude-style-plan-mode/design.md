# Claude-Style Plan Mode Design

작성일: 2026-05-09

## 설계 요약

하로에 Claude Code와 같은 Plan Mode를 도입한다. 핵심은 프롬프트 규칙만 추가하는 것이 아니라, 백엔드 상태와 도구 권한으로 실행을 실제로 막는 것이다.

v1 설계는 다음 원칙을 따른다.

- Plan Mode는 채팅 단위 상태다.
- Plan Mode에서는 읽기 도구와 plan 전용 도구만 허용한다.
- plan 파일 외 사용자 파일, 산출물, 코드, 설정 수정은 차단한다.
- 사용자가 plan을 승인해야 실행 단계로 이동한다.
- 승인 후에는 승인된 plan을 기준으로 Execution TODO를 만들고 실행한다.
- TODO는 plan을 대체하지 않고 실행 상태만 추적한다.

## Claude Code 직접 레퍼런스

이 설계는 `study/`에 있는 Claude Code 소스의 다음 구현을 직접 참고한다.

### Plan Mode 진입

레퍼런스:

- `study/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts`
- `study/src/components/permissions/EnterPlanModePermissionRequest/EnterPlanModePermissionRequest.tsx`

참고한 동작:

- EnterPlanMode는 permission mode를 `plan`으로 바꾼다.
- plan mode에서는 read-only 탐색과 plan file 수정만 허용한다.
- 사용자는 UI에서 plan mode 진입을 승인하거나 거절할 수 있다.
- 모델에게 "코드 수정 금지, 계획 작성에 집중"이라는 별도 지침이 주어진다.

하로 반영:

- UI에서 Plan Mode 토글 또는 승인 버튼을 제공한다.
- 라우터가 고위험/복잡 작업이라고 판단하면 Plan Mode 진입을 제안할 수 있다.
- 백엔드는 `PlanSession.status = plan_drafting`인 동안 쓰기 도구를 제한한다.

### Plan Mode 작업 지침

레퍼런스:

- `study/src/utils/messages.ts`

참고한 동작:

- 일반 Plan Mode는 `Initial Understanding -> Design -> Review -> Final Plan -> ExitPlanMode` 흐름이다.
- Interview Plan Mode는 `Explore -> Update plan file -> Ask user` 루프를 반복한다.
- plan file은 유일하게 수정 가능한 파일이다.
- 최종 계획은 간결해야 하며, 변경 파일과 검증 방법을 포함한다.

하로 반영:

- v1은 Claude의 interview workflow를 우선 채택한다.
- 계획 문서는 점진적으로 수정하되, 실제 실행 파일은 승인 전까지 수정하지 않는다.
- 질문이 필요하면 실행하지 않고 `waiting_for_plan_answer` 상태로 멈춘다.

### Plan 승인과 실행 전환

레퍼런스:

- `study/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts`
- `study/src/components/messages/PlanApprovalMessage.tsx`

참고한 동작:

- ExitPlanMode는 plan을 사용자에게 제시하고 승인받는다.
- 승인되면 "이제 코딩 가능" 상태가 된다.
- 거절되면 피드백을 반영해 plan을 고친 뒤 다시 승인 요청한다.

하로 반영:

- 모델은 `plan_approval_request` 도구를 호출해 plan 승인을 요청한다.
- 프론트엔드는 승인/거절 UI를 표시한다.
- 승인/거절은 다음 message turn으로 들어오며, gate가 현재 PlanSession과 연결한다.
- 승인 후에는 `PlanSession.status = plan_approved`로 바꾸고 실행 라우팅을 시작한다.
- 거절 후에는 `PlanSession.status = plan_drafting`으로 되돌리고 피드백을 plan에 반영한다.

### TODO 실행 관리

레퍼런스:

- `study/src/tools/TodoWriteTool/prompt.ts`
- `study/src/tools/TodoWriteTool/TodoWriteTool.ts`
- `study/src/utils/todo/types.ts`

참고한 동작:

- TodoWrite는 복잡한 작업에서 적극 사용된다.
- 새 지시를 받으면 요구사항을 TODO로 즉시 포착한다.
- 동시에 하나의 TODO만 `in_progress`일 수 있다.
- 완료 기준을 충족하지 못하면 `completed`로 표시하지 않는다.
- blocked가 생기면 현재 TODO를 완료 처리하지 않고 해결 항목을 만든다.

하로 반영:

- 승인된 plan을 실행할 때만 Execution TODO를 생성한다.
- TODO는 `pending`, `in_progress`, `done`, `blocked`, `failed` 상태를 가진다.
- 모든 필수 TODO와 검증이 끝나야 최종 완료로 보고한다.

### Plan 파일 저장과 복구

레퍼런스:

- `study/src/utils/plans.ts`

참고한 동작:

- plan은 세션별 파일로 저장된다.
- resume 시 plan 파일을 복구하거나 message history에서 재구성한다.

하로 반영:

- plan은 DB 상태와 물리 파일을 함께 가진다.
- DB에는 plan session 메타데이터를 저장하고, 실제 plan text는 workspace 파일로 저장한다.
- resume 또는 새로고침 후에도 Plan Mode 상태와 plan 파일을 UI에서 복구한다.

## 하로 현재 구조와 연결 지점

현재 관련 파일:

- `src/backend/app/services/agent.py`
- `src/backend/app/services/agent_tool_loop.py`
- `src/backend/app/services/intent_gate.py`
- `src/backend/app/services/intent_router.py`
- `src/backend/app/services/intent_turns.py`
- `src/backend/app/services/tool_registry.py`
- `src/backend/app/services/agent_tools.py`
- `src/backend/app/models/intent_turn.py`
- `src/backend/app/routers/messages.py`
- `src/frontend/src/routes/ProjectWorkspace.svelte`
- `src/frontend/src/components/WorkspaceChatPanel.svelte`
- `src/frontend/src/stores/chat.ts`

현재 흐름은 다음과 같다.

1. `messages.py`가 사용자 메시지를 받아 SSE를 연다.
2. `run_agent()`가 메시지를 저장하고 gate/router를 실행한다.
3. `route_intent()`가 `selected_tools`를 고른다.
4. `run_tool_call_loop()`가 Gemini 응답과 도구 호출을 반복한다.
5. `_execute_tool_call()`이 selected tools 밖 도구를 차단한다.

Plan Mode는 이 흐름 위에 "실행 전 제한 상태"를 추가한다.

## 기존 모드와 충돌 방지

하로에는 이미 여러 종류의 "모드"와 "상태"가 있다. Claude Code 방식의 Plan Mode는 이들과 섞지 않고 별도 네임스페이스로 관리한다.

현재 확인된 기존 상태 축:

- `IntentTurn.status`: `routing`, `needs_clarification`, `executing`, `waiting_review` 등 intent turn 처리 상태
- SSE `session_status`: `routing`, `planning`, `executing` 등 사용자에게 보이는 일시적 진행 표시
- `Project.runtime_mode`: `work`, `deploy` 프로젝트 실행 모드
- `WorkspaceExplorerMode`: `user`, `developer` 파일 탐색 뷰 모드

충돌 방지 원칙:

- 새 Plan Mode는 `agentStatus`나 SSE `session_status=planning`을 재사용하지 않는다.
- Claude Code의 `toolPermissionContext.mode = "plan"`처럼 별도 권한 상태를 둔다.
- 백엔드 영속 상태는 `PlanSession.status`에 저장하되 값은 `plan_*`, `execution_*` 접두어를 사용한다.
- 프론트엔드도 기존 `agentStatus` 대신 별도 `planMode` store로 Plan Mode 상태를 관리한다.
- 기존 `planning`은 "모델이 이번 응답을 준비 중"인 일시 표시로만 남기고, Plan Mode의 계획 작성 상태는 `plan_drafting`으로 부른다.
- 기존 `executing`은 intent/tool loop 진행 표시로만 남기고, 승인된 plan 실행 상태는 `execution_running`으로 부른다.

## 데이터 모델

### PlanSession

새 테이블 `plan_sessions`를 추가한다.

```python
class PlanSession(Base):
    __tablename__ = "plan_sessions"

    id: str
    project_id: str
    chat_session_id: str
    original_message_id: str | None
    intent_turn_id: str | None
    status: str
    trigger_source: str
    plan_file_path: str
    plan_title: str | None
    approved_message_id: str | None
    rejected_message_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
```

`status` 값:

- `plan_drafting`: 계획 작성 중
- `plan_awaiting_approval`: 사용자 승인 대기
- `plan_approved`: 승인됨
- `plan_cancelled`: 사용자가 취소
- `plan_failed`: 계획 단계 시스템 오류
- `execution_running`: 승인된 plan 실행 중
- `execution_completed`: 실행 완료
- `execution_failed`: 실행 단계 복구 불가 오류

`trigger_source` 값:

- `user_explicit`: 사용자가 "계획/스펙/설계 먼저"라고 명시
- `ui_toggle`: UI에서 Plan Mode를 직접 켬
- `router_suggested`: 라우터가 복잡/고위험 작업으로 판단

### PlanEvent

PlanSession이 여러 intent turn을 가로지를 수 있으므로 별도 이벤트 테이블을 둔다.

```python
class PlanEvent(Base):
    __tablename__ = "plan_events"

    id: str
    plan_session_id: str
    message_id: str | None
    event_type: str
    payload_json: str
    created_at: str
```

중요 이벤트는 기존 `IntentTurnEvent`와 debug trace에도 중복 기록한다. PlanEvent는 UI 상태 복구와 plan history 확인용이다.

### ExecutionTodo

기존 `Todo` 모델은 레거시 `sessions` 기반이므로 v1 Plan Mode에서는 새 모델을 둔다.

```python
class ExecutionTodo(Base):
    __tablename__ = "execution_todos"

    id: str
    plan_session_id: str
    intent_turn_id: str | None
    order_index: int
    title: str
    target: str | None
    action: str
    verification: str | None
    status: str
    blocked_reason: str | None
    result_summary: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
```

`status` 값:

- `pending`
- `in_progress`
- `done`
- `blocked`
- `failed`

## Plan File 위치 정책

Plan File은 물리 파일로 저장한다.

기본 위치:

```text
{chat_workspace}/working/plan.md
```

스펙 작성 작업에서 사용자가 `.specs/draft/{spec}/spec.md` 같은 경로를 명시하거나 저장소 지침상 스펙 파일을 만들기로 확정한 경우에는 해당 `spec.md`가 Plan File이 된다.

규칙:

- Plan Mode에서 수정 가능한 파일은 `PlanSession.plan_file_path` 하나뿐이다.
- `spec.md`가 Plan File인 경우에도 같은 폴더의 `design.md`, `plan.md`, `tasks.md`는 승인 전 생성하지 않는다.
- Plan File 경로는 기존 workspace path policy를 통과해야 한다.
- user-facing 응답에는 canonical path 대신 alias path를 사용한다.

## Backend 설계

### app.services.plan_mode

새 서비스 모듈을 추가한다.

책임:

- 진행 중인 PlanSession 조회
- PlanSession 생성
- Plan File 경로 결정
- PlanSession 상태 전이
- PlanEvent 기록
- Plan Mode에서 허용되는 도구 검증
- 승인/거절 메시지 처리

주요 함수:

```python
async def get_current_plan_session(db, chat_session_id) -> PlanSession | None
async def create_plan_session(db, project, chat_session, message, trigger_source, plan_file_path=None) -> PlanSession
async def request_plan_approval(db, plan_session, message_id=None) -> None
async def approve_plan(db, plan_session, message_id) -> None
async def reject_plan(db, plan_session, message_id, feedback) -> None
def is_plan_allowed_tool(tool_name: str) -> bool
def can_write_path_in_plan_mode(plan_session: PlanSession, tool_name: str, path: str | None) -> bool
```

### agent.py 변경

`run_agent()` 초반에 진행 중인 PlanSession을 확인한다.

흐름:

1. 사용자 메시지 저장
2. 진행 중인 PlanSession 조회
3. 진행 중인 PlanSession이 있고 사용자 메시지가 승인/거절이면 PlanSession 상태 전이
4. 진행 중인 PlanSession이 있고 아직 `plan_drafting`이면 plan 전용 라우팅 사용
5. 진행 중인 PlanSession이 `plan_approved`이면 실행 라우팅으로 전환
6. 진행 중인 PlanSession이 없으면 기존 gate/router 흐름

Plan Mode 진입 조건:

- UI payload가 `plan_mode_requested=true`
- gate/router가 `should_enter_plan_mode=true`
- 사용자 메시지가 계획/스펙/설계를 명시

### intent_router.py 변경

RouterDecision에 다음 필드를 추가한다.

```python
should_enter_plan_mode: bool = False
plan_mode_reason: str | None = None
```

라우터 프롬프트에 추가할 원칙:

- 고위험/복잡 작업은 바로 실행하지 말고 Plan Mode를 제안한다.
- PlanSession이 진행 중이면 실행 도구를 선택하지 않는다.
- Plan Mode selected tools는 read-only 도구와 plan 전용 도구로 제한한다.

### tool_registry.py 변경

Plan Mode 전용 도구를 추가한다.

#### plan_file_update

PlanSession의 plan file을 생성 또는 교체한다. path는 받지 않고 현재 PlanSession의 `plan_file_path`를 사용한다.

입력:

```json
{
  "content": "plan markdown"
}
```

#### plan_approval_request

현재 plan file을 사용자에게 승인 요청 상태로 전환한다.

입력:

```json
{
  "summary": "사용자에게 보여줄 짧은 요약"
}
```

도구 실행 결과:

- PlanSession.status를 `plan_awaiting_approval`로 변경
- `plan_approval_requested` SSE 이벤트 emit
- assistant message에 plan summary 저장

Plan Mode에서 허용되는 도구:

- `file_search`
- `file_read`
- `dir_list`
- `file_count`
- `web_search`는 사용자가 외부 자료 조사를 요청했거나 최신 정보가 필요한 경우만 허용
- `plan_file_update`
- `plan_approval_request`

Plan Mode에서 금지되는 도구:

- `file_create`
- `file_write`
- `file_delete`
- `file_move`
- `dir_create`
- `dir_delete`
- `file_export`
- `code_run`
- `web_preview`

예외:

- `plan_file_update`만 plan file을 쓸 수 있다.

### agent_tool_loop.py 변경

`run_tool_call_loop()`에 plan context를 전달한다.

변경점:

- 진행 중인 PlanSession이 있으면 system instruction에 Plan Mode 지침을 추가한다.
- `_execute_tool_call()`에서 selected tools 검증 후 Plan Mode 경로 검증을 추가한다.
- `plan_approval_request` 도구가 호출되면 loop를 종료하고 `plan_awaiting_approval` 상태로 반환한다.
- Plan Mode에서 일반 assistant final text가 나오면 plan 미완료로 간주하고 `plan_drafting` 상태로 저장하되, 승인 대기 상태로 바꾸지 않는다.

반환 상태 추가:

- `plan_drafting`
- `plan_awaiting_approval`
- `plan_approved_for_execution`

### agent_tools.py 변경

`execute_tool()`에 plan 전용 도구 실행을 연결한다.

승인 후 실행 단계의 파일 정리는 `code_run` 우회가 아니라 네이티브 파일 도구를 사용한다.

- `file_move(source_path, target_path)`: 파일 또는 폴더를 실제 workspace 경로에서 이동하고 workspace DB를 갱신한다.
- `dir_delete(path, recursive)`: 정리 후 남은 빈 폴더 또는 명시적으로 recursive 삭제가 허용된 폴더를 삭제하고 workspace DB를 갱신한다.
- `code_run`은 계산/검증용으로만 사용하고, 워크스페이스 파일 생성/수정/이동/삭제 대체 수단으로 쓰지 않는다.

`plan_file_update`:

- `plan_file_path` 부모 폴더를 보장한다.
- content를 plan file에 쓴다.
- workspace index를 갱신한다.
- `plan_file_updated` 이벤트와 SSE를 남긴다.

`plan_approval_request`:

- plan file 내용을 읽는다.
- PlanSession을 `plan_awaiting_approval`로 전환한다.
- SSE `plan_approval_requested`를 emit한다.

## API / SSE 설계

### Message 요청 확장

`POST /api/projects/{project_id}/chats/{chat_id}/messages`

요청 body에 선택 필드를 추가한다.

```json
{
  "content": "사용자 메시지",
  "debug_enabled": false,
  "client_message_id": "...",
  "plan_mode_requested": false,
  "plan_response": null
}
```

`plan_response` 예시:

```json
{
  "plan_session_id": "...",
  "action": "approve",
  "feedback": null
}
```

거절:

```json
{
  "plan_session_id": "...",
  "action": "reject",
  "feedback": "이 부분은 범위를 줄여줘"
}
```

### Plan 상태 조회

새 API:

```text
GET /api/projects/{project_id}/chats/{chat_id}/plan-mode
```

응답:

```json
{
  "plan_mode_active": true,
  "plan_session": {
    "id": "...",
    "status": "plan_awaiting_approval",
    "plan_file_path": "내 폴더/작업 중/plan.md",
    "plan_title": "..."
  },
  "plan_content": "..."
}
```

### SSE 이벤트

새 이벤트:

- `plan_mode_entered`
- `plan_file_updated`
- `plan_approval_requested`
- `plan_approved`
- `plan_rejected`
- `plan_mode_exited`
- `execution_todo_updated`
- `execution_blocked`

`plan_approval_requested` payload:

```json
{
  "plan_session_id": "...",
  "summary": "...",
  "plan_content": "...",
  "plan_file_path": "내 폴더/작업 중/plan.md"
}
```

## Frontend 설계

### WorkspaceChatPanel.svelte

추가 UI:

- Plan Mode 토글 또는 버튼
- Plan Mode badge
- plan approval card
- approve/reject 버튼
- reject feedback input

동작:

- 사용자가 Plan Mode 버튼을 켜고 메시지를 보내면 `plan_mode_requested=true`를 포함한다.
- `plan_approval_requested` SSE를 받으면 메시지 영역에 approval card를 표시한다.
- approve 버튼은 `plan_response.action = approve`로 message endpoint를 호출한다.
- reject 버튼은 feedback과 함께 `plan_response.action = reject`로 호출한다.

### stores/chat.ts

추가 상태:

```ts
export const planMode = writable<PlanModeState | null>(null);
```

SSE 처리 추가:

- `plan_mode_entered`
- `plan_file_updated`
- `plan_approval_requested`
- `plan_approved`
- `plan_rejected`
- `plan_mode_exited`
- `execution_todo_updated`

## Prompt 설계

Plan Mode system instruction은 Claude Code의 interview workflow를 하로에 맞게 축약한다.

핵심 지침:

- 지금은 Plan Mode이며 실행하지 않는다.
- plan file 외에는 쓰지 않는다.
- 먼저 읽고 이해한다.
- 코드에서 찾을 수 있는 것은 사용자에게 묻지 않는다.
- 사용자가 결정해야 하는 것만 질문한다.
- 발견한 내용을 plan file에 점진적으로 반영한다.
- plan이 충분히 수렴하면 `plan_approval_request`를 호출한다.
- approval을 텍스트 질문으로 묻지 않는다.

Execution instruction:

- 승인된 plan을 기준으로 TODO를 만든다.
- TODO는 하나씩 진행한다.
- 검증 실패 또는 blocked는 완료로 처리하지 않는다.
- 최종 보고에 실제 검증 결과를 포함한다.

## 상태 전이

```text
none
  -> plan_drafting            Plan Mode 진입
plan_drafting
  -> plan_awaiting_approval   plan_approval_request
plan_drafting
  -> plan_cancelled           사용자 취소
plan_awaiting_approval
  -> plan_approved            사용자 승인
plan_awaiting_approval
  -> plan_drafting            사용자 거절/피드백
plan_approved
  -> execution_running        실행 시작
execution_running
  -> execution_completed      모든 TODO 완료
execution_running
  -> plan_drafting            실행 중 요구사항 재해석 필요
execution_running
  -> execution_failed         복구 불가 오류
```

## 보안 / 정책

- Plan Mode의 write enforcement는 프롬프트가 아니라 백엔드에서 수행한다.
- selected tools 차단은 유지한다.
- Plan Mode 도구 allowlist를 통과해도 path policy를 다시 검사한다.
- `.haro`, clean-room write 금지는 유지한다.
- 승인 전 `file_write`, `file_create`, `code_run`, `web_preview` 호출은 blocked 처리한다.
- rejected feedback은 다음 Plan Mode prompt에는 포함하되, raw backend error와 canonical path는 사용자-facing 메시지에 노출하지 않는다.

## 테스트 전략

### Unit

- PlanSession 상태 전이 테스트
- 진행 중인 PlanSession 조회 테스트
- Plan Mode 도구 allowlist 테스트
- Plan File 외 경로 쓰기 차단 테스트
- router가 복잡/고위험 작업에 `should_enter_plan_mode`를 반환하는지 테스트
- approval/reject payload 처리 테스트

### Integration

- UI 요청 `plan_mode_requested=true`가 PlanSession을 생성하는지 검증
- Plan Mode에서 `file_write` 호출이 차단되는지 검증
- `plan_file_update`는 plan file만 수정하는지 검증
- `plan_approval_request` 후 SSE 이벤트가 나가는지 검증
- 승인 후 실행 라우팅이 시작되는지 검증
- 거절 후 Plan Mode가 유지되고 feedback이 다음 Plan Mode context에 포함되는지 검증

### Frontend

- Plan Mode 버튼 상태 렌더링
- approval card 렌더링
- approve/reject action payload 생성
- SSE 이벤트별 store 갱신

## 구현 순서 제안

1. `PlanSession`, `PlanEvent`, `ExecutionTodo` 모델과 migration 추가
2. `app.services.plan_mode` facade 추가
3. `tool_registry.py`에 plan 전용 도구 등록
4. `agent_tools.py`에 plan 전용 도구 실행 추가
5. `agent.py`에 진행 중인 PlanSession 상태 전이 연결
6. `agent_tool_loop.py`에 plan context와 write enforcement 연결
7. `messages.py` request schema에 `plan_mode_requested`, `plan_response` 추가
8. frontend store와 chat panel UI 추가
9. debug trace label과 테스트 추가

## 결정 사항

- v1은 Claude Code의 teammate approval, remote plan, multi-agent plan은 도입하지 않는다.
- v1은 Plan Mode를 chat-scoped 상태로 구현한다.
- v1은 plan 전용 쓰기 도구를 두고 기존 `file_write`를 재사용하지 않는다.
- v1은 approval을 별도 REST mutation보다 message endpoint payload로 처리해 SSE 흐름을 유지한다.

## 남은 질문

- 라우터가 자동 Plan Mode를 제안할 때 사용자 승인 없이 바로 PlanSession을 만들지, 먼저 assistant 메시지로 "Plan Mode로 진행할까요?"를 물을지 결정이 필요하다.
- Plan File 기본 경로를 chat workspace `working/plan.md`로 둘지, 사용자에게 더 잘 보이는 `내 폴더/작업 중/계획/{slug}.md` 형태로 둘지 결정이 필요하다.
- 승인 후 바로 실행을 시작할지, 승인 메시지에 사용자가 추가 지시를 함께 넣을 수 있게 할지 결정이 필요하다.
