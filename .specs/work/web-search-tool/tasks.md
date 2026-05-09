# Web Search Tool Tasks

작성일: 2026-05-08

## 0. 스펙과 baseline

- [x] `.specs/draft/web-search-tool/` 스펙 폴더를 만든다.
- [x] `spec.md`에 문제, 목표, 비목표, 성공 기준을 기록한다.
- [x] `design.md`에 도구 계약, provider, router 정책을 기록한다.
- [x] `plan.md`에 구현 순서와 검증 게이트를 기록한다.
- [x] `tasks.md`에 실행 체크리스트를 만든다.
- [x] 구현 시작 시 `.specs/work/web-search-tool/`로 이동한다.
- [x] backend baseline 테스트를 실행한다.

## 1. Provider service

- [x] `WebSearchResult` dataclass를 추가한다.
- [x] `search_web(...)` async helper를 추가한다.
- [x] `WEB_SEARCH_PROVIDER` 설정을 읽는다.
- [x] `WEB_SEARCH_BASE_URL` 설정을 읽는다.
- [x] `WEB_SEARCH_API_KEY` 설정을 읽는다.
- [x] `WEB_SEARCH_TIMEOUT_SECONDS` 설정을 읽는다.
- [x] provider disabled 또는 필수 설정 없음 오류를 정의한다.
- [x] timeout 오류를 정의한다.
- [x] SearXNG provider raw response를 normalized result로 변환한다.
- [x] Brave provider raw response를 normalized result로 변환한다.

완료 조건:

- [x] provider mock으로 정상 결과, 빈 결과, 설정 없음, timeout을 테스트할 수 있다.

## 2. Tool catalog와 executor

- [x] `TOOL_CATALOG`에 `web_search`를 추가한다.
- [x] `_tool_call_example`에 `web_search` 예시를 추가한다.
- [x] tool description에 웹 검색은 반드시 `web_search` `tool_call`로 실행하라고 명시한다.
- [x] `execute_tool`에 `web_search` branch를 추가한다.
- [x] query 빈 값 validation을 추가한다.
- [x] limit clamp를 적용한다.
- [x] domains 최대 개수를 제한한다.
- [x] result를 numbered text로 포맷한다.
- [x] startup manifest 또는 registry 테스트를 갱신한다.

완료 조건:

- [x] `web_search`가 selected tools로 허용된다.
- [x] provider 오류가 raw backend error로 노출되지 않는다.

## 3. Router와 prompt

- [x] `intent_router.py`에 최신/외부 정보 요청 시 `web_search` 선택 규칙을 추가한다.
- [x] 검색 관련 keyword fast path에 `web_search`를 추가한다.
- [x] 파일 기반 후속 작업은 기존 파일 도구를 우선하도록 규칙을 유지한다.
- [x] `build_tool_descriptions`에 웹 검색 결과 출처 표시 규칙을 추가한다.
- [x] 라우터가 검색을 직접 실행하지 않고 selected tool만 정한다는 정책을 문서와 prompt에 반영한다.
- [x] 웹 검색 query에 민감한 workspace 내용을 자동 포함하지 말라는 규칙을 추가한다.

완료 조건:

- [x] 검색/최신 요청은 `web_search`를 선택한다.
- [x] workspace 파일 요약 요청은 `web_search`를 선택하지 않는다.

## 4. 테스트

- [x] provider service 정상 결과 테스트를 추가한다.
- [x] provider service 설정 없음 테스트를 추가한다.
- [x] provider service timeout 테스트를 추가한다.
- [x] `execute_tool("web_search", ...)` 포맷 테스트를 추가한다.
- [x] router가 검색/최신 키워드에서 `web_search`를 선택하는 테스트를 추가한다.
- [x] tool loop가 `web_search` `tool_call`을 기존 도구 흐름으로 실행하는 테스트를 추가한다.
- [x] 선택되지 않은 `web_search` `tool_call`이 blocked tool 흐름으로 차단되는 테스트를 추가한다.
- [x] 기존 tool-call parse recovery 테스트가 통과하는지 확인한다.

## 5. 최종 검증과 문서 동기화

- [x] backend 전체 테스트를 실행한다.
- [x] `git diff --check`를 실행한다.
- [x] 구현 결과와 검증 결과를 `implementation.md`에 기록한다.
- [x] 서버 run 시 로컬 SearXNG가 함께 시작되도록 dev script와 VS Code task를 연결한다.
- [ ] 연결 커밋을 `commits.md`에 기록한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

git diff --check
```

검증 결과:

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest tests\unit\test_web_search.py tests\unit\test_agent_tools_result_location.py tests\unit\test_intent_router.py tests\unit\test_agent_tool_loop.py tests\unit\test_startup_app_factory.py -q` → 20 passed
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 86 passed, 1 skipped
- `git diff --check` → passed
