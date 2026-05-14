# 대화 히스토리와 컨텍스트 현재 구현

## 1. 개요

LLM에 전달되는 정보:

1. explicit cache 대상인 stable system prompt
2. 현재 turn마다 바뀌는 runtime context
3. 현재 채팅 세션의 최근 메시지 20개
4. 방금 입력한 사용자 메시지
5. 도구 실행 결과 메시지

구현 위치:

- `backend/app/services/context.py`
- `backend/app/services/prompt_bundle.py`
- `backend/app/services/prompt_cache.py`
- `backend/app/services/workspace_index.py`
- `backend/app/services/agent_tool_loop.py`
- `backend/app/services/tool_registry.py`

## 2. 시스템 프롬프트

시스템 프롬프트는 `PromptBundle`로 stable 영역과 runtime 영역을 나눈다.

Stable 영역:

- 기본 에이전트 역할과 공통 규칙
- 프로젝트 지침 파일에서 온 정책
- 도구 호출 문법, 한 번에 하나의 도구만 호출하는 규칙, workspace 안전 규칙 같은 stable tool-call contract

Runtime 영역:

- 이번 turn에서 선택된 도구 목록과 도구별 상세 설명
- route context
- 하네스 브리핑, Working Context, 현재 채팅/파일 맥락
- Plan Mode 또는 승인된 execution plan 지시

Gemini explicit cache가 성공하면 stable 영역은 `cached_content`로 참조하고, runtime 영역은 첫 synthetic user message로 전달한다. cache 생성/조회 실패 시에는 stable + runtime 전체 prompt를 기존처럼 `system_instruction`에 넣어 fallback한다.

## 3. 최근 메시지

`RECENT_MESSAGE_COUNT = 20`

`get_recent_messages(db, chat_session_id)`는 현재 채팅 세션에서 `compressed == False`인 최근 메시지 20개를 가져온 뒤 오래된 순서로 반환한다.

role 변환:

| DB role | Gemini role |
|---------|-------------|
| `planner` | `model` |
| `executor` | `model` |
| `system` | `model` |
| `user` | `user` |

현재 압축 실행 로직은 없으므로 대부분의 메시지는 `compressed = False` 상태로 남는다.

## 4. 대화 요약

`context.py`는 `.haro` 디렉토리에서 `summary_v*.md` 파일을 찾아 가장 최신 파일을 읽을 수 있다.

```
{workspace}/.haro/summary_v3.md
```

하지만 현재 코드에는 요약 파일을 생성하거나 메시지를 압축하는 백그라운드 작업이 없다.
따라서 이 기능은 수동으로 요약 파일이 있을 때만 컨텍스트에 포함되는 수준이다.

## 5. 워크스페이스 컨텍스트

파일 도구가 파일을 생성/수정/삭제하면 `workspace_index.py`가 `.haro/workspace.md`를 갱신한다.

```
{workspace}/.haro/
├── workspace.md
└── file_summaries/
    └── src__main.ts.md
```

`workspace.md`는 다음 정보를 포함한다.

- 파일 트리
- 파일별 간단 요약

현재 파일별 요약은 LLM 없이 생성한다.

```text
- {line_count}줄, 첫 줄: `{first_line}`
```

## 6. LLM 호출 시 실제 조립

현재 흐름:

```python
context_sections = await build_context_sections(db, project, chat_session)
prompt_bundle = _build_prompt_bundle(context_sections, selected_tools, route)
cache_result = await ensure_gemini_prompt_cache(prompt_bundle, "gemini-3-flash-preview")

recent = await get_recent_messages(db, chat_session.id)
contents = build_model_contents(recent, user_content)

if cache_result.use_cached_content:
    contents = prompt_bundle.model_contents(contents, include_runtime_context=True)
```

이후 Gemini 스트리밍 호출에 전달한다.

```python
client.models.generate_content_stream(
    model="gemini-3-flash-preview",
    contents=contents,
    config=cache_result.generation_config(prompt_bundle.text, temperature=0.7),
)
```

explicit cache 성공 시 config는 `{"cached_content": cache_name, "temperature": 0.7}` 형태이며, `system_instruction`을 다시 보내지 않는다. fallback 시 config는 `{"system_instruction": prompt_bundle.text, "temperature": 0.7}` 형태다.

## 7. 도구 결과 컨텍스트

LLM이 `tool_call` 블록을 반환하면 백엔드가 도구를 실행하고, 결과를 다음 라운드의 사용자 메시지처럼 추가한다.

```python
contents.append({"role": "model", "parts": [{"text": full_text}]})
contents.append({
    "role": "user",
    "parts": [{"text": f"[도구 실행 결과]\n{result}"}],
})
```

이 방식으로 모델은 이전 도구 호출 결과를 보고 다음 도구를 호출하거나 최종 답변을 만든다.

## 8. 현재 미구현 사항

초기 설계에 있었지만 현재 코드에는 없는 기능:

- 메시지 수 기준 자동 압축
- LLM 기반 긴 파일 요약
- 압축된 메시지 `compressed=true` 마킹
- 요약 파일 버전 관리/정리
- 파일 요약 디바운스

## 9. 향후 확장 방향

현재 구조를 유지하면서 확장하려면 다음 순서가 자연스럽다.

1. 메시지 수가 임계값을 넘을 때 오래된 메시지를 요약
2. 요약을 `.haro/summary_v{n}.md`에 저장
3. 요약된 메시지를 `compressed=true`로 표시
4. 긴 파일은 LLM 요약으로 `file_summaries` 품질 개선
5. 프로젝트 단위 요약과 채팅 단위 요약을 분리
