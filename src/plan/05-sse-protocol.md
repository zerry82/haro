# SSE 통신 프로토콜 현재 구현

## 1. 개요

사용자가 메시지를 전송하면 서버는 `text/event-stream` 응답을 반환한다.
브라우저 `EventSource`는 GET만 지원하므로, 프론트는 `fetch`와 `ReadableStream`으로 POST 응답 스트림을 직접 읽는다.

현재 메시지 전송 엔드포인트:

```
POST /api/projects/{project_id}/chats/{chat_id}/messages
Content-Type: application/json
Authorization: Bearer {token}

{"content": "README 만들어줘"}
```

응답:

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

## 2. 서버 구현

`SSEEmitter`가 문자열 큐를 가지고 있다.

```python
event: {event_name}
data: {json}

```

`run_agent`가 작업 중 `emitter.emit(...)`을 호출하고, 마지막에 `emitter.done()`으로 스트림을 닫는다.

## 3. 현재 이벤트 타입

### 3.1 `status`

에이전트 상태를 표시한다.

```text
event: status
data: {"session_status":"planning","message":"요청을 분석하고 있습니다..."}
```

현재 사용하는 상태:

- `planning`
- `executing`
- 프론트에서는 스트림 종료 후 `idle`로 되돌림

### 3.2 `message_start`

어시스턴트 메시지 시작.

```text
event: message_start
data: {"message_id":"uuid","role":"assistant"}
```

### 3.3 `message_delta`

어시스턴트 메시지 조각.

```text
event: message_delta
data: {"message_id":"uuid","content":"파일을 생성하겠습니다."}
```

### 3.4 `message_end`

어시스턴트 메시지 종료.

```text
event: message_end
data: {"message_id":"uuid"}
```

### 3.5 `todo_step_updated`

현재 구현은 DB TODO를 만들지 않는다.
대신 도구 실행 전후를 단계 이벤트로 보내 UI에 인라인 표시한다.

```text
event: todo_step_updated
data: {
  "todo_id": "auto",
  "step": {
    "description": "file_create({\"path\":\"/README.md\"})",
    "status": "in_progress"
  }
}
```

도구 실행 후:

```text
event: todo_step_updated
data: {
  "todo_id": "auto",
  "step": {
    "description": "file_create 완료",
    "status": "completed"
  }
}
```

### 3.6 `file_changed`

파일 또는 디렉토리 변경 알림.
프론트는 이 이벤트를 브라우저 `CustomEvent('file-changed')`로 바꿔 파일 트리를 다시 로드한다.

```text
event: file_changed
data: {"action":"created","path":"/README.md","type":"file"}
```

현재 action:

- `created`
- `modified`
- `deleted`

현재 type:

- `file`
- `directory`

### 3.7 `preview_ready`

`web_preview` 도구가 성공했을 때 전송한다.

```text
event: preview_ready
data: {"url":"/preview/{project_id}/","ip":"172.17.0.2"}
```

현재 프론트는 이 이벤트를 별도로 렌더링하지 않는다.

### 3.8 `error`

에이전트 실행 중 예외가 발생했을 때 전송한다.

```text
event: error
data: {"code":"AGENT_ERROR","message":"에러 메시지"}
```

프론트는 시스템 메시지 형태로 표시한다.

### 3.9 `done`

작업 종료.

```text
event: done
data: {"summary":"작업이 완료되었습니다."}
```

프론트는 `agentStatus`를 `idle`로 되돌린다.

## 4. 전체 흐름 예시

```
사용자: "README 만들어줘"

→ status(planning)
→ message_start
→ message_delta("README를 생성하겠습니다.")
→ message_end
→ status(executing)
→ todo_step_updated(file_create in_progress)
→ file_changed(created /README.md)
→ todo_step_updated(file_create 완료)
→ message_start
→ message_delta("README 파일을 만들었습니다.")
→ message_end
→ done
```

## 5. 프론트 처리

`frontend/src/lib/sse.ts`는 스트림을 줄 단위로 파싱한다.

```typescript
await streamPost(
  `/projects/${projectId}/chats/${chatId}/messages`,
  { content },
  (event, data) => {
    // chat.ts switch(event)
  },
);
```

현재 구현은 `event:` 라인 다음의 `data:` 한 줄 JSON을 기대한다.
멀티라인 data, reconnect, event id, retry 필드는 구현하지 않았다.

## 6. 문서상 제거된 과거 이벤트

초기 설계에 있던 아래 이벤트는 현재 코드에서 발행하지 않는다.

- `thinking`
- `clarification`
- `todo_created`
- `todo_updated`
