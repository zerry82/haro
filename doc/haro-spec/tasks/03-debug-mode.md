# 3번째 개발 주기: Debug Mode

## 목표

채팅 턴별로 LLM 교신 과정을 확인할 수 있는 디버그 모드를 구현한다.

사용자는 디버그 모드를 켠 뒤 메시지를 보내고, 자신이 보낸 채팅 블럭을 클릭해 중앙 모달에서 LLM 요청/응답/tool call/result를 확인할 수 있어야 한다.

이번 주기는 문제 재현과 개발 품질 개선을 위한 개발 주기다.
일반 사용자용 설명 UI나 민감정보 마스킹 자동화는 후속 주기로 둔다.

## 구현 범위

- 서비스 DB에 `agent_debug_traces` 테이블을 추가한다.
- 메시지 전송 요청에 `debug_enabled` 값을 추가한다.
- 디버그 on 턴에서만 full trace를 저장한다.
- 사용자 메시지 저장 직후 SSE `user_message_saved` 이벤트를 보낸다.
- 사용자 메시지 id 기준 trace 조회 API를 추가한다.
- 채팅 패널 헤더에 `디버그` 토글을 추가한다.
- 사용자 메시지 클릭 시 중앙 모달로 trace를 표시한다.

상세 제품 스펙은 [15-debug-mode-spec.md](../15-debug-mode-spec.md)를 따른다.

## DB 변경

새 테이블:

```text
agent_debug_traces
```

컬럼:

| column | type | description |
| --- | --- | --- |
| `id` | TEXT PK | 내부 UUID |
| `project_id` | TEXT | 프로젝트 id |
| `chat_session_id` | TEXT | 채팅 세션 id |
| `turn_message_id` | TEXT | 사용자가 보낸 메시지 id |
| `round_index` | INTEGER | LLM/tool loop round |
| `event_type` | TEXT | `llm_request`, `llm_response`, `tool_call`, `tool_result`, `error` |
| `payload_json` | TEXT | 원문 전체 payload |
| `duration_ms` | REAL NULL | 처리 시간 |
| `created_at` | TEXT | 생성 시각 |

마이그레이션:

- startup migration에서 테이블이 없으면 생성한다.
- 기존 `agent_logs` 테이블은 변경하지 않는다.
- 기존 메시지/채팅 데이터는 backfill하지 않는다.

## API 변경

메시지 전송 request:

```json
{
  "content": "질문 내용",
  "debug_enabled": true
}
```

SSE 추가 이벤트:

```text
user_message_saved
```

payload:

```json
{
  "client_message_id": "optional-client-id",
  "message_id": "server-message-id",
  "debug_enabled": true
}
```

Trace 조회:

```http
GET /api/projects/{project_id}/chats/{chat_id}/messages/{message_id}/debug-trace
```

응답:

```json
{
  "message_id": "server-message-id",
  "has_trace": true,
  "events": []
}
```

## 백엔드 구현 체크리스트

- [x] `AgentDebugTrace` 모델을 추가한다.
- [x] startup create_all 흐름에서 `agent_debug_traces` 테이블이 생성되게 한다.
- [x] `SendMessageRequest`에 `debug_enabled`와 선택적 `client_message_id`를 추가한다.
- [x] `run_agent`가 user message id와 debug flag를 인자로 받도록 조정한다.
- [x] LLM 요청 직전 full `system_instruction`, `contents`, config를 저장한다.
- [x] LLM 응답 원문 전체를 저장한다.
- [x] tool call과 tool result 원문 전체를 저장한다.
- [x] error 발생 시 error trace를 저장한다.
- [x] 기존 `agent_logs` 저장은 유지한다.
- [x] trace 조회 API에서 프로젝트/채팅/message 소유권을 검증한다.

## 프론트엔드 구현 체크리스트

- [x] 채팅 헤더에 `디버그` 토글을 추가한다.
- [x] 토글 상태를 사용자별 `localStorage`에 저장한다.
- [x] 메시지 전송 시 `debug_enabled`와 `client_message_id`를 함께 보낸다.
- [x] `user_message_saved` 이벤트를 받아 optimistic user message id를 서버 id로 교체한다.
- [x] 디버그 대상 사용자 메시지에 클릭 가능 스타일을 적용한다.
- [x] 사용자 메시지 클릭 시 trace 조회 API를 호출한다.
- [x] 중앙 모달에 round별 trace를 표시한다.
- [x] trace 없는 메시지는 빈 상태 안내를 표시한다.
- [x] payload 복사 버튼을 제공한다.

## 검증 체크리스트

- [ ] 디버그 off 상태에서 메시지를 보내면 `agent_debug_traces`가 생성되지 않는다.
- [ ] 디버그 on 상태에서 메시지를 보내면 `turn_message_id` 기준 trace가 저장된다.
- [ ] LLM request trace에 system instruction과 contents가 포함된다.
- [ ] LLM response trace에 원문 응답 전체가 포함된다.
- [ ] tool call/result가 발생한 턴은 round 순서대로 표시된다.
- [ ] 사용자 메시지 블럭 클릭 시 중앙 모달이 열린다.
- [ ] trace가 없는 과거 메시지는 “이 메시지는 디버그 기록이 없습니다.”를 보여준다.
- [ ] 다른 프로젝트/채팅의 message id로 trace를 조회할 수 없다.
- [ ] 기존 `agent_logs`와 Logs 화면이 그대로 동작한다.
- [x] `python -m py_compile app/main.py app/routers/messages.py app/models/agent_debug_trace.py app/services/agent.py`
- [x] `npm run build`

## 제외 항목

- 자동 민감정보 마스킹
- 팀/관리자 정책 기반 디버그 설정
- trace 자동 만료 구현
- trace 삭제 UI
- trace를 파일로 export하는 기능
- 외부 hook으로 debug trace를 보내는 기능

## 구현 메모

- full trace는 크기가 커질 수 있으므로 `agent_logs`와 분리한다.
- v1은 디버그 모드가 켜진 턴만 저장한다.
- 기존 메시지에는 trace를 backfill하지 않는다.
- UI는 중앙 모달로 시작한다.
- trace 저장 실패가 에이전트 실행 전체를 망가뜨리지 않도록 하되, 최소한 `agent_logs`에는 error를 남긴다.
