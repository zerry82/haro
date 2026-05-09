# Nonblocking Agent Runtime Implementation

작성일: 2026-05-08

## 구현 결과

- LLM stream 비차단 helper `stream_llm_chunks_nonblocking(...)`를 추가했다.
- Google GenAI의 동기 `generate_content_stream(...)` 호출과 iterator 순회를 worker thread에서 수행하도록 변경했다.
- `_stream_llm_round`는 worker thread가 전달한 text chunk를 async 쪽에서 소비하며 기존 SSE message_start/message_delta/message_end 동작을 유지한다.
- worker thread에는 model input/config와 sync GenAI 호출만 넘기고, `AsyncSession`, `SSEEmitter`, ORM mutation은 넘기지 않았다.
- `messages.py`의 background task 시작 단계에 top-level 예외 보호를 추가해 agent 시작 전 예외가 SSE hang으로 이어지지 않게 했다.

## 변경 파일

- `src/backend/app/services/agent_tool_loop.py`
- `src/backend/app/routers/messages.py`
- `src/backend/tests/unit/test_agent_tool_loop.py`
- `.specs/work/nonblocking-agent-runtime/spec.md`
- `.specs/work/nonblocking-agent-runtime/plan.md`
- `.specs/work/nonblocking-agent-runtime/tasks.md`

## 검증 결과

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest tests\unit\test_agent_tool_loop.py -q` → 7 passed
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 76 passed, 1 skipped
- `git diff --check` → passed

## 남은 작업

- 커밋 후 `commits.md`에 연결 커밋 기록
