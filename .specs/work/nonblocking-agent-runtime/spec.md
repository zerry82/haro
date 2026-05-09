# Nonblocking Agent Runtime Spec

작성일: 2026-05-08

## 문제

현재 채팅 라우트는 FastAPI `async` endpoint와 SSE `StreamingResponse`를 사용한다. 하지만 실제 LLM 응답 생성 단계에서 Google GenAI의 동기 스트리밍 iterator를 이벤트 루프 안에서 직접 순회한다.

이 때문에 채팅 응답을 기다리는 동안 같은 서버 프로세스의 다른 요청도 지연될 수 있다.

- 파일 트리 조회, health check, preview 관련 요청이 채팅 스트리밍 중 늦게 응답한다.
- `asyncio.create_task()`로 agent 실행 task를 만들더라도, task 내부에서 동기 네트워크 iterator가 이벤트 루프를 점유하면 전체 서버 반응성이 떨어진다.
- 원인은 "FastAPI가 비동기가 아님"이 아니라 "동기 LLM 스트림이 이벤트 루프 안에서 실행됨"이다.

## 목표

- 기존 message send API와 SSE 이벤트 계약은 유지한다.
- LLM 스트리밍 호출과 chunk iterator 소비를 이벤트 루프 밖 worker thread에서 실행한다.
- async 쪽 consumer만 SSE emit, DB 저장, trace 기록을 수행한다.
- 채팅 스트리밍 중에도 파일 목록, health check, preview 관련 요청이 응답 가능해야 한다.
- tool-call 파싱/교정, 파일 저장 위치 정책, 기존 agent tool 선택 정책은 변경하지 않는다.

## 비목표

- Celery, RQ, 외부 queue, 별도 worker process를 도입하지 않는다.
- Google SDK stream을 강제 취소하는 복잡한 cancellation 계층을 만들지 않는다.
- `file_read`, `file_write`, `file_create` 같은 짧은 동기 파일 작업까지 이번 범위에서 모두 thread offload하지 않는다.
- SSE payload shape, message schema, frontend consume 로직을 변경하지 않는다.
- 모델, prompt, tool selection 정책을 변경하지 않는다.

## 현재 구조

- `messages.py::send_message`는 `asyncio.create_task(_run())`로 agent 실행을 시작하고 `SSEEmitter.stream()`을 반환한다.
- `agent_tool_loop.py::_stream_llm_round`는 `get_client().models.generate_content_stream(...)`을 호출한 뒤 `for chunk in stream`으로 동기 iterator를 직접 순회한다.
- `await asyncio.sleep(0)`은 chunk가 나온 뒤에만 양보하므로, 동기 iterator가 네트워크 응답을 기다리는 동안에는 이벤트 루프가 막힐 수 있다.

## 대상 동작

LLM round는 다음 흐름으로 바꾼다.

1. async 함수가 LLM request log와 debug trace를 기존처럼 기록한다.
2. worker thread가 `generate_content_stream(...)` 호출과 동기 iterator 순회를 담당한다.
3. worker thread는 text chunk, error, done 이벤트만 event-loop-safe queue로 전달한다.
4. async consumer가 queue를 읽어 `full_text`를 조립하고 기존 SSE message_start/message_delta/message_end 규칙을 유지한다.
5. async consumer가 LLM response log, duration, debug trace를 기존처럼 기록한다.

## Thread 경계

worker thread로 넘겨도 되는 값:

- model name
- contents
- generation config
- sync GenAI client 호출
- chunk text 또는 exception 정보

worker thread로 넘기지 않는 값:

- SQLAlchemy `AsyncSession`
- `SSEEmitter`
- ORM model mutation
- intent status mutation
- workspace file DB mutation
- debug trace DB write

## 오류 처리

- worker thread에서 예외가 발생하면 async consumer가 예외를 받아 기존 agent 실패 흐름으로 전파한다.
- `messages.py`의 background task는 top-level 예외를 잡아 사용자-facing error SSE와 done 이벤트를 emit한다.
- 클라이언트 연결이 끊긴 경우 async consumer는 종료하고 이후 worker 결과는 best-effort로 무시한다.
- Google SDK stream 자체 취소는 v1에서는 best-effort로만 처리한다.

## 성공 기준

- LLM stream fake가 `time.sleep()`으로 blocking하더라도 이벤트 루프 heartbeat가 지연되지 않는다.
- 채팅 스트리밍 중 `/api/health` 또는 파일 목록 API가 timeout 없이 응답한다.
- 기존 SSE 이벤트 순서와 최종 done 이벤트가 유지된다.
- 기존 tool-call 파싱/교정 테스트가 통과한다.
- 외부 API, SSE payload, frontend 사용 방식이 바뀌지 않는다.
- backend 전체 테스트가 통과한다.

