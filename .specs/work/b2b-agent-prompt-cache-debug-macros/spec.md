# B2B Agent Prompt Cache Debug Macros

## 문제

에이전트 tool loop는 Gemini 호출 round마다 동일한 대형 `system_instruction`을 반복해서 사용한다. 1차 구현으로 debug JSON에서는 system prompt를 macro로 1회만 노출하도록 정리했지만, Gemini implicit cache는 best-effort라서 같은 turn 안에서도 `cached_content_token_count`가 0인 round가 발생한다.

또한 현재 full system prompt 안에는 selected tools, route, 현재 하네스/채팅 맥락처럼 자주 바뀌는 runtime 정보가 섞여 있다. 이 때문에 검증2/검증3처럼 라우팅 결과가 달라지면 full prompt hash가 달라지고, cache 재사용성이 낮아진다.

## 목표

- Claude Code처럼 안정적인 prompt boundary를 만든다.
- Gemini 제약에 맞춰 stable system prompt는 explicit `cached_content`로 전달한다.
- selected tools, route, 현재 작업공간/채팅 맥락, plan/execution context는 runtime content로 분리한다.
- cache name은 파일 store에 best-effort로 저장하고, 기본 TTL은 300초로 둔다.
- cache 생성/조회 실패 시 기존 full `system_instruction` 호출로 fallback해 에이전트 실행을 막지 않는다.
- debug trace는 `system_prompt.full`, `system_prompt.cached_system`, `system_prompt.runtime_context` macro를 최상단에 1회 노출한다.

## 비목표

- keyword 기반 route 로직 자체를 교체하지 않는다.
- Anthropic/OpenAI provider adapter를 실제로 구현하지 않는다. 단, provider별 확장이 가능하도록 경계 이름은 열어 둔다.
- Gemini cache 파일 store를 강한 일관성 저장소로 만들지 않는다. 동시 요청 중복 cache 생성은 허용한다.

## 설계

Prompt sections:

- `cached_system`: `static_core`, `project_policy`, stable tool-call contract.
- `runtime_context`: 하네스 브리핑, 채팅 압축 맥락, selected tools, route, plan/execution instruction.
- `full`: 사람이 보는 전체 조립 prompt이며 `cached_system + runtime_context`로 구성한다.

Gemini explicit cache:

1. `cached_system_hash`로 cache key를 만든다.
2. 파일 store에서 TTL 안의 `cache_name`을 찾는다.
3. 있으면 `client.caches.get(name=cache_name)`로 best-effort 검증한다.
4. 없거나 만료/실패하면 `client.caches.create(model, system_instruction=cached_system, ttl="300s")`를 호출한다.
5. 생성 요청에는 `GenerateContentConfig(cached_content=cache.name, temperature=0.7)`만 넣고 `system_instruction`은 다시 넣지 않는다.
6. runtime context는 `contents` 첫 synthetic user message로 전달한다.

Fallback:

- cache create/get 실패 시 `cache_state="failed_fallback"`을 debug에 기록한다.
- fallback 요청은 기존처럼 `system_instruction=full_prompt`를 사용하고, runtime synthetic message는 추가하지 않는다.

## 성공 기준

- selected tools가 달라도 `cached_system_hash`가 같으면 같은 cache key를 사용한다.
- `llm_request.payload.config`는 explicit cache 성공 시 `cached_content`를 포함하고 `system_instruction`은 포함하지 않는다.
- fallback 시 기존 full `system_instruction` 동작을 유지한다.
- debug trace에는 system prompt 원문이 macro 최상단에만 있고, request body에는 macro reference가 표시된다.
- Gemini usage metadata의 `cached_content_token_count`와 cache state를 함께 확인할 수 있다.
