# Web Search Tool Plan

작성일: 2026-05-08

## 개발 실행 순서 요약

이 스펙은 agent가 외부 웹 검색을 명시적 도구로 사용할 수 있게 하는 작업이다. 먼저 tool 계약과 provider abstraction을 추가하고, 그 다음 라우터가 필요한 요청에서 `web_search`를 선택하게 한다.

웹검색은 tool-call 접근을 원칙으로 한다. 라우터가 자동 검색을 실행하지 않고, LLM이 기존 `tool_call` fenced block으로 `web_search`를 호출해야만 provider가 실행된다.

실행 순서:

1. 스펙을 `.specs/draft/web-search-tool/`에서 시작한다.
2. 구현 시작 시 `.specs/work/web-search-tool/`로 이동한다.
3. baseline backend 테스트를 확인한다.
4. web search provider service와 config를 추가한다.
5. tool catalog와 executor에 `web_search`를 추가한다.
6. router prompt와 heuristic에 `web_search` 선택 규칙을 추가한다.
7. tool description에 "검색이 필요하면 반드시 `web_search` tool_call을 호출" 규칙을 추가한다.
8. prompt/tool description에 출처 표시 규칙을 추가한다.
9. provider mock 기반 단위 테스트, router 테스트, tool loop 호출 테스트를 추가한다.
10. backend 전체 테스트와 `git diff --check`를 통과시킨다.

## 1. Baseline

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest
```

## 2. Config와 provider service

목표:

- provider별 HTTP 호출을 agent tool에서 직접 처리하지 않게 한다.
- API key 미설정, timeout, provider 오류를 명확히 분리한다.

예정 변경:

- `app/services/web_search.py` 추가
- 필요한 경우 `app/config.py` 또는 기존 설정 모듈에 env var reader 추가
- `WebSearchResult` dataclass 추가
- `search_web(...)` async helper 추가

검증:

- API key 없음 → unavailable 오류
- provider timeout → timeout 오류
- raw provider result → normalized `WebSearchResult`

## 3. Tool registry와 executor

목표:

- `web_search`가 라우터와 agent loop에서 정상 도구로 인식되게 한다.

예정 변경:

- `TOOL_CATALOG`에 `web_search` 추가
- `_tool_call_example`에 `web_search` 예시 추가
- `execute_tool`에 `web_search` branch 추가
- startup manifest 테스트 갱신

검증:

- `validate_tool_names(["web_search"])`가 valid를 반환한다.
- `execute_tool`이 mock 결과를 numbered text로 반환한다.
- 빈 query가 사용자 친화 validation message를 반환한다.
- `web_search`는 기존 `tool_call` 실행 흐름으로만 호출된다.

## 4. Router와 prompt 정책

목표:

- 최신/외부 정보 요청에서 라우터가 `web_search`를 선택하게 한다.
- 웹 검색 결과를 사용한 답변에는 URL 출처를 포함하게 한다.

예정 변경:

- `intent_router.py` tool selection instruction 갱신
- keyword fast path가 있으면 검색/최신 키워드에 `web_search` 추가
- `build_tool_descriptions`에 웹 검색 출처 표시 규칙 추가
- `build_tool_descriptions`에 웹 검색이 필요하면 설명하지 말고 `web_search` tool_call을 호출하라는 규칙 추가

검증:

- "최신 뉴스 찾아봐" → `web_search`
- "오늘 환율 검색해서 알려줘" → `web_search`
- "이 파일 요약해줘" → `file_read`, not `web_search`
- selected tool에 `web_search`가 있어도 tool_call이 없으면 검색은 실행되지 않는다.
- selected tool에 `web_search`가 없는데 tool_call이 오면 blocked tool 흐름이 실행된다.

## 5. 최종 검증과 문서

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

git diff --check
```

문서:

- `implementation.md`에 구현 결과와 검증 결과 기록
- `commits.md`에 연결 커밋 기록

## 중단 또는 재설계 조건

- 자체 운영 SearXNG endpoint를 준비할 수 없고 유료 provider opt-in도 허용되지 않는 경우
- 검색 provider가 snippet/url/date를 안정적으로 제공하지 않는 경우
- 검색 요청에 민감한 workspace 정보가 자동 포함될 위험이 있는 경우
- router가 너무 자주 `web_search`를 선택해 비용과 latency가 커지는 경우
