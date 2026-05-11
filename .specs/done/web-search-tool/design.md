# Web Search Tool Design

작성일: 2026-05-08

## 아키텍처

웹 검색 도구는 기존 agent tool 구조에 맞춰 세 계층으로 나눈다.

1. Tool catalog: `web_search`를 선택 가능한 도구로 노출한다.
2. Provider service: 외부 검색 API 호출을 감싼다.
3. Tool executor: provider 결과를 agent가 읽기 쉬운 텍스트로 포맷한다.

기존 agent loop, SSE 계약, tool-call fenced block 계약은 유지한다.

핵심 결정:

- 웹검색은 숨은 자동 단계가 아니라 명시적 `tool_call` 도구다.
- 라우터는 `web_search`를 선택 가능한 도구 목록에 넣는 역할까지만 한다.
- 실제 외부 검색은 LLM 응답에 유효한 `web_search` `tool_call` 블록이 있을 때만 실행된다.
- 선택되지 않은 `web_search` 호출은 기존 blocked tool 흐름으로 차단한다.

## 내부 인터페이스

신규 service helper:

```python
@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str
    source: str | None = None
    published_at: str | None = None

async def search_web(
    query: str,
    *,
    limit: int = 5,
    recency_days: int | None = None,
    domains: list[str] | None = None,
) -> list[WebSearchResult]:
    ...
```

구현 원칙:

- HTTP 호출은 async client를 사용한다.
- provider timeout은 config에서 읽고 기본값은 10초로 둔다.
- result는 최대 10개로 clamp한다.
- provider별 raw response는 helper 내부에서 normalize한다.

## Tool catalog 변경

`TOOL_CATALOG`에 추가한다.

- name: `web_search`
- purpose: 웹 검색
- required_args: `query`
- description: `web_search(query, limit, recency_days, domains) - 외부 웹 검색 결과 조회.`

도구 설명에는 다음 제약을 포함한다.

- 웹 검색이 필요하면 설명 텍스트로 검색했다고 말하지 말고 반드시 `web_search` `tool_call`을 호출한다.
- 검색 결과를 받은 뒤 다음 LLM round에서 답변 또는 산출물을 작성한다.

`_tool_call_example`에 다음 예시를 추가한다.

```json
{"tool": "web_search", "args": {"query": "대한민국 청개구리 개체수 최신 연구", "limit": 5}}
```

## Tool executor 변경

`execute_tool`에 `web_search` branch를 추가한다.

동작:

- `query`를 검증한다.
- `limit`, `recency_days`, `domains`를 정규화한다.
- `search_web(...)`를 호출한다.
- 결과를 numbered text로 반환한다.
- 결과가 없으면 `웹 검색 결과 없음: {query}`를 반환한다.
- provider 설정 없음, timeout, provider 오류는 사용자 친화 메시지로 반환한다.

SSE:

- 기존 tool 실행 상태 emit 흐름을 그대로 사용한다.
- 별도 파일 변경 이벤트는 emit하지 않는다.

Tool loop:

- 별도 web search 전용 loop를 만들지 않는다.
- `run_tool_call_loop`의 기존 selected tool 검증, debug trace, tool result append 흐름을 그대로 사용한다.
- 검색 결과는 `[도구 실행 결과]` user message로 다음 LLM round에 전달된다.

## Provider 선택

v1 기본 provider는 자체 운영 가능한 SearXNG endpoint로 설계한다. Brave Search API는 유료 외부 API가 필요한 환경에서 opt-in으로 둔다.

환경 변수:

- `WEB_SEARCH_PROVIDER=searxng|brave|disabled`
- `WEB_SEARCH_BASE_URL`
- `WEB_SEARCH_API_KEY`
- `WEB_SEARCH_TIMEOUT_SECONDS=10`

Provider별 요구 설정:

- `searxng`: `WEB_SEARCH_BASE_URL` required. 예: `https://search.example.com`
- `brave`: `WEB_SEARCH_API_KEY` required.
- `disabled`: 항상 unavailable 결과를 반환한다.

Provider abstraction을 둬서 나중에 다른 검색 API로 교체할 수 있게 하되, v1에서는 provider plugin system이나 runtime UI 설정은 만들지 않는다.

자체 구현 경계:

- agent 서버는 검색 provider adapter만 구현한다.
- 자체 검색 index, crawler, search ranking engine은 만들지 않는다.
- 외부 검색엔진 HTML을 직접 scraping하지 않는다.
- 로컬 개발 실행은 `scripts/start-searxng.ps1`로 Docker 기반 SearXNG 컨테이너를 best-effort로 시작한다.
- 운영 환경의 SearXNG 배포, rate limit, outbound network policy는 별도 인프라 설정으로 다룬다.

## Router 변경

`intent_router.py`의 system instruction에 다음 규칙을 추가한다.

- 최신/현재/외부 웹 정보가 필요한 경우 `selected_tools`에 `web_search`를 포함한다.
- 파일 기반 후속 작업이면 기존 `file_search`/`file_read`를 우선한다.
- 웹 검색 결과를 파일로 저장해야 하면 `web_search`와 `file_create` 또는 `file_write`를 함께 선택한다.
- 라우터는 검색을 직접 실행하지 않는다. `selected_tools`만 정한다.

Heuristic fast path가 있다면 다음 키워드에 `web_search`를 포함한다.

- `웹검색`
- `검색`
- `찾아봐`
- `최신`
- `현재`
- `오늘`
- `뉴스`
- `가격`
- `출처`

## Debug/Trace

Debug trace에는 다음만 남긴다.

- query
- normalized args
- result count
- result urls
- provider name
- duration

남기지 않는다.

- API key
- raw provider response body
- 사용자 파일 전문

## 테스트 전략

- provider service는 HTTP client mock 또는 provider function monkeypatch로 테스트한다.
- `execute_tool("web_search", ...)`는 provider mock으로 결과 포맷, 빈 결과, 오류를 테스트한다.
- `tool_registry` 테스트에서 `web_search`가 catalog/manifest에 포함되는지 확인한다.
- router 테스트에서 최신/검색 키워드가 `web_search`를 선택하는지 확인한다.
- tool loop 테스트에서 `selected_tools=["web_search"]`이고 LLM이 `web_search` tool_call을 반환하면 executor가 호출되는지 확인한다.
- tool loop 테스트에서 `selected_tools=[]`인데 LLM이 `web_search` tool_call을 반환하면 blocked tool 흐름이 유지되는지 확인한다.
- 기존 backend 전체 테스트를 통과시킨다.
