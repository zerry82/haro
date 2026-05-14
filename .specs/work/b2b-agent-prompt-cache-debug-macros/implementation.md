# Implementation Notes

## 구현 결과

- `PromptBundle`을 stable cached system prompt와 runtime context로 분리했다.
- Gemini explicit cache store를 추가했다. cache key는 `provider + model + cache_version + cached_system_hash`이고, 기본 TTL은 300초다.
- explicit cache 성공 시 Gemini generate config에는 `cached_content`만 넣고, runtime context는 첫 synthetic user message로 전달한다.
- cache 생성/조회 실패 시 `cache_state="failed_fallback"`을 기록하고 기존 full `system_instruction` 호출로 fallback한다.
- 도구 프롬프트를 stable contract와 dynamic tool context로 분리해 selected tools 변화가 cached system hash를 흔들지 않게 했다.
- debug trace의 `prompt_macros`에는 `system_prompt.full`, `system_prompt.cached_system`, `system_prompt.runtime_context`를 1회 노출한다.
- `llm_request` debug payload에는 prompt macro reference, prompt cache state, cached/runtime/full prompt hash와 chars를 저장한다.

## 변경 파일

- Backend
  - `src/backend/app/services/prompt_bundle.py`
  - `src/backend/app/services/prompt_cache.py`
  - `src/backend/app/services/agent_tool_loop.py`
  - `src/backend/app/services/tool_registry.py`
  - `src/backend/app/routers/messages.py`
  - `src/backend/app/services/context.py`
- Frontend
  - `src/frontend/src/components/DebugTraceModal.svelte`
  - `src/frontend/src/lib/debugTraceUtils.ts`
  - `src/frontend/src/stores/chat.ts`
- Tests
  - `src/backend/tests/unit/test_prompt_cache.py`
  - `src/backend/tests/unit/test_agent_tool_loop.py`
  - `src/backend/tests/unit/test_debug_trace_macros.py`
  - `src/frontend/src/lib/debugTraceUtils.test.ts`
- Docs
  - `doc/src/README.md`
  - `src/plan/08-conversation-context.md`

## 검증

- `src/backend/.venv/Scripts/python.exe -m pytest src/backend/tests/unit/test_prompt_cache.py src/backend/tests/unit/test_agent_tool_loop.py src/backend/tests/unit/test_debug_trace_macros.py`
- `npm test -- --run src/lib/debugTraceUtils.test.ts`
- `src/backend/.venv/Scripts/python.exe -m pytest`
- `npm test`
- `npm run build`
- Backend dev server restarted on `http://127.0.0.1:8001`; `/api/health` returned 200.

## 남은 확인

- 실제 Gemini 응답에서 `usage_metadata.cached_content_token_count`가 기록되는지는 live API 호출로 확인해야 한다.
- 파일 store는 best-effort이며 동시 요청의 중복 cache 생성은 v1/v2 범위에서 허용한다.
