# Nonblocking Agent Runtime Plan

작성일: 2026-05-08

## 개발 실행 순서 요약

이 스펙은 agent LLM 스트리밍만 먼저 비차단화한다. API/SSE 계약은 유지하고, DB/SSE side effect는 이벤트 루프에 남긴다.

실행 순서:

1. 스펙을 `.specs/draft/nonblocking-agent-runtime/`에서 시작한다.
2. backend baseline 테스트를 확인한다.
3. LLM 동기 stream을 worker thread에서 소비하는 helper를 추가한다.
4. `_stream_llm_round`가 새 helper를 통해 chunk를 async consume하도록 바꾼다.
5. `messages.py` background task에 top-level 예외 보호를 추가한다.
6. blocking fake stream 단위 테스트와 기존 tool loop 회귀 테스트를 추가한다.
7. backend 전체 테스트와 `git diff --check`를 통과시킨다.

## 1. Baseline 확인

목표:

- 현재 backend 테스트 상태를 확인한다.
- 기존 tool-call parse recovery 테스트가 통과하는지 확인한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest
```

## 2. LLM stream bridge 추가

목표:

- Google GenAI 동기 stream 호출과 iterator 순회를 이벤트 루프 밖에서 실행한다.
- async consumer가 기존 `_stream_llm_round` 동작을 유지한다.

예정 변경:

- `agent_tool_loop.py`에 내부 helper `stream_llm_chunks_nonblocking(...)`를 추가한다.
- helper는 현재 event loop를 캡처하고 worker thread를 `asyncio.to_thread(...)`로 실행한다.
- worker thread는 `get_client().models.generate_content_stream(...)`을 호출하고 chunk text를 queue로 전달한다.
- queue item은 최소한 `chunk`, `error`, `done` 타입을 구분한다.
- async consumer는 queue를 읽으며 text chunk만 기존 SSE 처리 경로로 넘긴다.

주의:

- `AsyncSession`, `SSEEmitter`, ORM object는 worker thread에서 사용하지 않는다.
- worker thread 예외는 async consumer에서 다시 raise한다.
- chunk 순서는 원래 stream 순서를 유지한다.

## 3. `_stream_llm_round` 연결

목표:

- 기존 LLM request/response log, duration, debug trace를 유지한다.
- 기존 tool_call 블록 감지 시 SSE delta를 멈추는 동작을 유지한다.

예정 변경:

- `stream = get_client().models.generate_content_stream(...)`와 `for chunk in stream` 직접 순회를 제거한다.
- `async for chunk_text in stream_llm_chunks_nonblocking(...)` 형태로 변경한다.
- `full_text`, `message_start`, `message_delta`, `message_end` 로직은 기존 기준으로 보존한다.

검증:

- 정상 stream에서 chunk 순서가 유지된다.
- tool_call 블록이 포함된 응답은 사용자-facing message로 끝까지 노출되지 않는다.
- LLM response log와 duration이 계속 기록된다.

## 4. Message background task 보호

목표:

- agent task 내부 예외가 SSE stream을 영원히 열어두지 않게 한다.

예정 변경:

- `messages.py::_run`을 `try/except/finally`로 감싼다.
- 예외 발생 시 raw backend detail 대신 자연스러운 error event를 emit한다.
- finally에서 `emitter.done()`이 보장되게 한다.
- 기존 `run_agent` 내부 done emit과 중복되지 않도록 `SSEEmitter.done()`은 idempotent하게 만들거나 `_run`에서 중복 done이 안전한지 확인한다.

검증:

- agent 예외 시 SSE stream이 종료된다.
- 정상 성공 flow의 done 이벤트 순서가 깨지지 않는다.

## 5. 테스트 추가

단위 테스트:

- blocking fake stream이 `time.sleep()` 후 chunk를 반환해도 `asyncio.sleep()` heartbeat가 먼저 실행된다.
- fake stream이 예외를 던지면 async helper가 같은 예외를 async 쪽에 전달한다.
- 여러 chunk가 순서대로 반환된다.

통합 또는 service-level 테스트:

- `_stream_llm_round`가 fake blocking stream을 사용할 때 event loop를 막지 않는지 검증한다.
- 기존 invalid tool_call repair 테스트가 그대로 통과하는지 확인한다.

## 6. 최종 검증

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

git diff --check
```

프론트엔드 코드는 변경하지 않으므로 `npm test`와 `npm run build`는 이번 스펙의 필수 검증에서 제외한다.

## 중단 또는 재설계 조건

- Google GenAI client가 thread에서 안전하게 사용할 수 없다는 문제가 확인되는 경우
- queue bridge가 chunk 순서나 예외 전파를 불안정하게 만드는 경우
- SSE done 이벤트가 중복되어 frontend 상태가 깨지는 경우
- 비차단화 후에도 health/file API가 채팅 중 계속 지연되는 경우
- 해결하려면 tool execution 전체 offload 또는 별도 job queue가 필요하다고 확인되는 경우

