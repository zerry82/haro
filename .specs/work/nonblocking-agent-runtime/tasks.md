# Nonblocking Agent Runtime Tasks

작성일: 2026-05-08

## 0. 스펙과 baseline

- [x] `.specs/draft/nonblocking-agent-runtime/` 스펙 폴더를 만든다.
- [x] 구현 시작에 맞춰 스펙을 `.specs/work/nonblocking-agent-runtime/`로 이동한다.
- [x] `spec.md`에 문제, 목표, 비목표, 성공 기준을 기록한다.
- [x] `plan.md`에 구현 순서와 검증 게이트를 기록한다.
- [x] `tasks.md`에 실행 체크리스트를 만든다.
- [x] `git status --short`로 작업트리 상태를 확인한다.
- [x] backend baseline 테스트를 실행한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest
```

## 1. LLM stream helper

- [x] `stream_llm_chunks_nonblocking(...)` helper를 추가한다.
- [x] helper가 worker thread에서 `generate_content_stream(...)`을 호출하게 한다.
- [x] helper가 worker thread에서 동기 stream iterator를 순회하게 한다.
- [x] helper가 text chunk를 async consumer로 순서대로 전달하게 한다.
- [x] helper가 worker thread 예외를 async consumer로 전달하게 한다.
- [x] helper가 done 신호를 async consumer로 전달하게 한다.

완료 조건:

- [x] 동기 LLM stream 호출이 이벤트 루프 안에서 직접 실행되지 않는다.
- [x] `AsyncSession`, `SSEEmitter`, ORM object가 worker thread로 넘어가지 않는다.

## 2. `_stream_llm_round` 연결

- [x] `_stream_llm_round`의 직접 stream 순회를 제거한다.
- [x] `_stream_llm_round`가 새 helper를 async consume하게 한다.
- [x] 기존 `message_start`, `message_delta`, `message_end` SSE 동작을 유지한다.
- [x] tool_call 블록 감지 후 사용자-facing delta를 중단하는 기존 동작을 유지한다.
- [x] LLM request/response `AgentLog` 기록을 유지한다.
- [x] debug trace payload를 유지한다.

완료 조건:

- [x] 정상 텍스트 응답이 기존처럼 스트리밍된다.
- [x] tool_call 응답이 일반 planner 메시지로 잘못 노출되지 않는다.

## 3. Message background task 보호

- [x] `messages.py` background `_run`에 top-level 예외 처리를 추가한다.
- [x] 예외 발생 시 사용자-facing error SSE를 emit한다.
- [x] 예외 발생 시 stream이 종료되도록 done 처리를 보장한다.
- [x] 정상 flow에서 done 중복이 frontend를 깨지 않는지 확인한다.

완료 조건:

- [x] agent 내부 예외가 SSE stream hang으로 이어지지 않는다.

## 4. 테스트

- [x] blocking fake stream 중 event loop heartbeat가 진행되는 테스트를 추가한다.
- [x] fake stream 예외가 async helper에서 다시 raise되는 테스트를 추가한다.
- [x] chunk 순서 보존 테스트를 추가한다.
- [x] `_stream_llm_round` service-level 회귀 테스트를 추가하거나 기존 tool loop 테스트에 helper 단위 검증을 연결한다.
- [x] 기존 tool-call parse recovery 테스트가 통과하는지 확인한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest
```

## 5. 최종 검증과 문서 동기화

- [x] backend 전체 테스트를 실행한다.
- [x] `git diff --check`를 실행한다.
- [x] 구현 결과와 검증 결과를 `implementation.md`에 기록한다.
- [ ] 연결 커밋을 `commits.md`에 기록한다.
- [ ] 완료 시 `.specs/work/nonblocking-agent-runtime/` 또는 `.specs/done/nonblocking-agent-runtime/` 이동 여부를 결정한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

git diff --check
```

검증 결과:

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest tests\unit\test_agent_tool_loop.py -q` → 7 passed
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 76 passed, 1 skipped
- `git diff --check` → passed
