# Debug Mode 스펙

## 1. 목적

haro의 채팅형 에이전트는 사용자 메시지 하나를 처리하기 위해 여러 번 LLM을 호출하고, 중간에 도구를 실행하고, 다시 LLM에게 결과를 전달한다.

일반 사용자는 최종 답변만 보면 된다.
하지만 개발 중이거나 업무 자동화 규칙을 다듬는 단계에서는 다음 질문에 답할 수 있어야 한다.

- haro가 LLM에게 어떤 system instruction을 보냈는가?
- 사용자의 질문은 어떤 최근 대화 맥락과 함께 전달되었는가?
- LLM이 실제로 어떤 응답을 만들었는가?
- 어떤 tool call이 발생했고, 그 결과는 무엇이었는가?
- 잘못된 답변이 프롬프트 문제인지, 도구 결과 문제인지, LLM 해석 문제인지 어디에서 갈라졌는가?

디버그 모드는 이 과정을 채팅 턴 단위로 추적하는 기능이다.

## 2. 제품 원칙

1. 디버그 모드는 기본적으로 꺼져 있다.
2. 디버그 모드가 켜진 턴에만 원문 전체 trace를 저장한다.
3. 기존 `agent_logs`는 운영 로그로 유지하고, 원문 전체 디버그 기록은 별도 trace로 분리한다.
4. 사용자는 자신이 보낸 채팅 블럭을 클릭해 해당 턴의 LLM 교신 기록을 볼 수 있다.
5. 디버그 trace는 문제 해결과 품질 개선용이지, 일반 업무 산출물이 아니다.
6. Project Fork, Clean Room, workspace 파일 인덱스에는 디버그 trace를 포함하지 않는다.

## 3. 디버그 모드 단위

v1의 디버그 모드는 사용자별 local preference로 시작한다.

```text
사용자 A: 디버그 on
사용자 B: 디버그 off
프로젝트: 동일
결과: 사용자 A가 보낸 턴만 full trace 저장
```

이 설정은 v1에서 브라우저 `localStorage`에 저장한다.
서버는 메시지 전송 요청의 `debug_enabled` 값을 보고 해당 턴 trace 저장 여부를 결정한다.

후속 단계에서는 사용자 프로필 설정이나 팀 정책으로 이동할 수 있다.

## 4. 저장 모델

서비스 DB에 `agent_debug_traces` 테이블을 추가한다.

`agent_logs`는 현재처럼 요약/절삭 로그를 유지한다.
`agent_debug_traces`는 디버그 모드가 켜진 턴의 원문 전체 payload를 저장한다.

| column | type | description |
| --- | --- | --- |
| `id` | TEXT PK | 내부 UUID |
| `project_id` | TEXT | 프로젝트 id |
| `chat_session_id` | TEXT | 채팅 세션 id |
| `turn_message_id` | TEXT | 사용자가 보낸 메시지 id |
| `round_index` | INTEGER | LLM/tool loop round |
| `event_type` | TEXT | `llm_request`, `llm_response`, `tool_call`, `tool_result`, `error` |
| `payload_json` | TEXT | 원문 전체 payload |
| `duration_ms` | REAL NULL | 해당 이벤트 처리 시간 |
| `created_at` | TEXT | 생성 시각 |

권장 인덱스:

```sql
CREATE INDEX idx_agent_debug_trace_turn
ON agent_debug_traces(project_id, chat_session_id, turn_message_id, round_index);

CREATE INDEX idx_agent_debug_trace_chat
ON agent_debug_traces(chat_session_id, created_at);
```

## 5. 저장 대상

### `llm_request`

LLM 호출 직전의 입력을 저장한다.

포함 대상:

- `model`
- `system_instruction`
- `contents`
- `temperature` 등 generation config
- 현재 채팅 id와 round index

### `llm_response`

LLM이 반환한 원문 응답 전체를 저장한다.

포함 대상:

- 원문 text
- duration
- tool call parsing 전/후 상태

### `tool_call`

LLM이 요청한 도구 호출을 저장한다.

포함 대상:

- tool name
- args 원문
- parsing 결과

### `tool_result`

도구 실행 결과를 저장한다.

포함 대상:

- tool name
- result 원문
- duration
- 성공/실패 상태

### `error`

에이전트 실행 중 발생한 예외를 저장한다.

포함 대상:

- error message
- traceback 요약
- round index

## 6. 메시지 연결

v1 디버그 조회 기준은 `turn_message_id`다.

`turn_message_id`는 사용자가 보낸 메시지 DB id다.
하나의 사용자 메시지는 여러 round의 LLM/tool trace를 가질 수 있다.

```text
messages.id = user message id
  -> agent_debug_traces.turn_message_id
    -> round 0 llm_request
    -> round 0 llm_response
    -> round 0 tool_call
    -> round 0 tool_result
    -> round 1 llm_request
    -> round 1 llm_response
```

`messages.parent_message_id`는 assistant/tool 표시 연결에 활용할 수 있지만, v1의 디버그 조회 기준으로 사용하지 않는다.

## 7. API 초안

### 메시지 전송

```http
POST /api/projects/{project_id}/chats/{chat_id}/messages
```

Request:

```json
{
  "content": "현재 폴더가 몇 개야?",
  "debug_enabled": true
}
```

동작:

- `debug_enabled=false` 또는 생략 시 기존 `agent_logs`만 저장한다.
- `debug_enabled=true`면 해당 사용자 메시지 턴의 full trace를 `agent_debug_traces`에 저장한다.

### SSE 이벤트

사용자 메시지가 DB에 저장되면 서버는 다음 이벤트를 보낸다.

```text
event: user_message_saved
data: {"client_message_id":"...", "message_id":"...", "debug_enabled":true}
```

프론트는 optimistic user message id를 서버 message id로 교체한다.
이 id가 이후 debug trace 조회 기준이 된다.

### 디버그 trace 조회

```http
GET /api/projects/{project_id}/chats/{chat_id}/messages/{message_id}/debug-trace
```

Response:

```json
{
  "message_id": "user-message-id",
  "has_trace": true,
  "events": [
    {
      "id": "trace-id",
      "round_index": 0,
      "event_type": "llm_request",
      "payload": {},
      "duration_ms": null,
      "created_at": "2026-04-30T12:00:00+09:00"
    }
  ]
}
```

권한:

- 프로젝트 소유 사용자가 아니면 조회할 수 없다.
- 해당 채팅에 속하지 않는 message id는 404 또는 `has_trace=false`로 처리한다.

## 8. UI

채팅 패널 헤더에 `디버그` 토글을 추가한다.

기본 상태:

- off
- localStorage에 사용자별 저장

디버그 on 상태에서 보낸 사용자 메시지는 클릭 가능한 상태로 표시한다.

사용자 메시지 블럭 클릭 시 중앙 모달을 연다.

모달 구성:

- 상단: 사용자 질문, 생성 시각, trace 저장 여부
- 본문: round별 접힘 블럭
- 각 round 안에 `LLM 요청`, `LLM 응답`, `Tool Call`, `Tool Result`, `Error` 영역
- 각 payload 영역에는 복사 버튼 제공
- trace가 없으면 “이 메시지는 디버그 기록이 없습니다.” 표시

기술 용어가 많으므로 모달 안에서는 다음 라벨을 사용한다.

| 내부 이벤트 | UI 라벨 |
| --- | --- |
| `llm_request` | LLM에게 보낸 내용 |
| `llm_response` | LLM이 돌려준 내용 |
| `tool_call` | 실행하려 한 도구 |
| `tool_result` | 도구 실행 결과 |
| `error` | 오류 |

## 9. 보안과 보존

원문 전체 trace는 민감정보를 포함할 수 있다.

따라서 v1에서는 다음 원칙을 둔다.

- 기본값 off
- 디버그 on 턴만 저장
- 해당 프로젝트 사용자만 조회
- Project Fork 제외
- Clean Room 승격 제외
- workspace file DB 색인 제외
- 외부 hook 전송 금지

v1에서는 삭제/보존 기간 UI를 만들지 않는다.
다만 후속 구현에서는 다음 기능을 추가한다.

- 사용자별 디버그 trace 전체 삭제
- 채팅별 디버그 trace 삭제
- 일정 기간 이후 자동 만료
- 민감정보 마스킹 옵션

## 10. 기존 로그와의 관계

`agent_logs`는 계속 유지한다.

역할:

- 일반 운영 로그
- Logs 화면 표시
- 짧은 이벤트 추적
- 디버그 off 상태에서도 최소한의 실행 이력 보존

`agent_debug_traces`는 디버그 모드 전용이다.

역할:

- 원문 전체 LLM payload 저장
- 채팅 턴별 문제 재현
- 프롬프트/도구/응답 품질 분석

두 저장소를 합치지 않는 이유:

- 운영 로그는 항상 가볍게 유지되어야 한다.
- 원문 trace는 민감하고 크기가 커질 수 있다.
- 디버그 trace는 보존/삭제 정책이 별도로 필요하다.

## 11. 성공 기준

- 디버그 off 상태에서는 full trace가 저장되지 않는다.
- 디버그 on 상태에서 보낸 사용자 메시지는 `turn_message_id` 기준 trace를 가진다.
- 사용자 메시지 블럭을 클릭하면 중앙 모달에서 LLM 요청/응답/tool 기록을 볼 수 있다.
- 여러 round가 발생해도 순서대로 표시된다.
- trace가 없는 과거 메시지는 빈 상태 안내가 나온다.
- 기존 `agent_logs`와 Logs 화면은 깨지지 않는다.
- 디버그 trace는 프로젝트 fork, Clean Room, workspace file DB 검색에 포함되지 않는다.
