# Web Search Tool Spec

작성일: 2026-05-08

## 문제

현재 agent 도구는 workspace 파일, 코드 실행, 웹 프리뷰에 집중되어 있다. 사용자가 최신 정보, 외부 웹 자료, 현재 사건, 제품/가격/규정처럼 로컬 파일과 모델 지식만으로 답하기 어려운 내용을 요청해도 agent가 직접 웹 검색을 수행할 수 없다.

이 때문에 다음 문제가 생긴다.

- 최신 정보 요청에 오래된 모델 지식으로 답할 위험이 있다.
- 사용자가 "검색해줘", "최신", "오늘", "현재"처럼 명시해도 라우터가 실행 가능한 도구를 선택할 수 없다.
- HTML/리포트/대시보드 생성 시 외부 자료 기반 인용과 출처 표시가 어렵다.

## 목표

- agent tool catalog에 `web_search` 도구를 추가한다.
- 웹검색은 모델 내장 기능이나 backend 자동 보강이 아니라 기존 `tool_call` fenced block 계약을 통해서만 실행한다.
- 라우터가 최신/외부 정보가 필요한 요청에 `web_search`를 선택할 수 있게 한다.
- `web_search`는 검색 결과 목록을 반환하고, agent가 필요한 경우 그 결과를 바탕으로 답변이나 산출물을 작성한다.
- 검색 결과에는 title, url, snippet, source, published_at 또는 date hint를 포함한다.
- 사용자-facing 답변에서 웹 검색 결과를 사용한 경우 URL 출처를 함께 표시하도록 prompt 규칙을 추가한다.
- provider 설정이 없거나 실패한 경우 raw backend error 대신 자연스러운 도구 결과를 반환한다.

## 비목표

- v1에서는 웹 페이지 본문 전체를 fetch하거나 요약하지 않는다.
- v1에서는 브라우저 자동화, 로그인 필요한 사이트 접근, 스크래핑 crawler를 만들지 않는다.
- v1에서는 검색 결과를 workspace 파일로 자동 저장하지 않는다.
- v1에서는 웹 검색을 모든 질문의 기본값으로 사용하지 않는다.
- v1에서는 라우터나 backend가 사용자 요청 뒤에서 자동 검색을 실행하지 않는다. 반드시 `selected_tools`에 포함되고 LLM이 `tool_call`로 호출한 경우에만 실행한다.
- v1에서는 의료/법률/금융 자문을 자동으로 확정하지 않고, 출처 기반 요약과 한계 표시까지만 한다.

## 도구 계약

도구 이름: `web_search`

호출 방식:

```tool_call
{"tool": "web_search", "args": {"query": "검색어", "limit": 5}}
```

정책:

- `web_search`는 기존 agent tool loop를 그대로 탄다.
- 라우터는 `selected_tools`에 `web_search`를 넣을 수 있지만, 실제 검색 실행은 LLM의 명시적 `tool_call`이 있을 때만 일어난다.
- `tool_call` 파싱 실패, 선택되지 않은 도구 호출, 반복 교정 실패 처리는 기존 tool-call 정책을 그대로 따른다.

입력:

```json
{
  "query": "검색어",
  "limit": 5,
  "recency_days": 30,
  "domains": ["example.com"]
}
```

필드 정책:

- `query`: required. 빈 문자열이면 validation error를 반환한다.
- `limit`: optional. 기본 5, 최소 1, 최대 10.
- `recency_days`: optional. provider가 지원하지 않으면 best-effort query hint로만 사용한다.
- `domains`: optional. 최대 5개. provider가 지원하지 않으면 `site:` query hint로 변환한다.

출력:

```text
웹 검색 결과 (query):
1. Title
   URL: https://...
   요약: ...
   날짜: 2026-05-08
```

오류 출력:

- 설정 없음: `웹 검색을 사용할 수 없습니다: WEB_SEARCH_API_KEY가 설정되어 있지 않습니다.`
- timeout: `웹 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.`
- 결과 없음: `웹 검색 결과 없음: {query}`

## Provider 정책

v1은 provider abstraction을 둔다.

- 기본 provider는 자체 운영 가능한 `searxng`로 둔다.
- `brave`는 유료 외부 API가 필요할 때 명시적으로 opt-in하는 선택 provider로 둔다.
- 설정 키는 `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_BASE_URL`, `WEB_SEARCH_API_KEY`, `WEB_SEARCH_TIMEOUT_SECONDS`를 사용한다.
- `WEB_SEARCH_PROVIDER=searxng`이면 `WEB_SEARCH_BASE_URL`이 필요하다.
- `WEB_SEARCH_PROVIDER=brave`이면 `WEB_SEARCH_API_KEY`가 필요하다.
- provider가 `disabled`이거나 필수 설정이 없으면 도구는 명확한 unavailable 결과를 반환한다.
- provider API key와 raw response body는 debug trace나 사용자-facing 답변에 노출하지 않는다.

자체 구현의 범위:

- v1의 "자체 구현"은 검색엔진 crawler를 직접 만드는 것이 아니라, 우리가 운영하는 SearXNG endpoint를 호출하는 provider를 뜻한다.
- 검색엔진 HTML 결과를 직접 scraping하지 않는다.
- 로컬 개발 환경에서는 서버 run 스크립트가 Docker 기반 SearXNG 컨테이너를 best-effort로 함께 시작하고 `WEB_SEARCH_BASE_URL`을 주입한다.
- 운영 환경의 SearXNG 배포, rate limit, outbound network policy는 별도 인프라 설정으로 다루며, agent 서버는 `WEB_SEARCH_BASE_URL`로 연결만 한다.

## 라우팅 정책

라우터는 다음 경우 `web_search`를 포함한다.

- 사용자가 "웹검색", "검색해줘", "찾아봐", "최신", "현재", "오늘", "뉴스", "가격", "일정", "규정", "출처"를 명시한 경우
- 로컬 파일이나 최근 대화만으로 답하기 어렵고 외부 현재성이 중요한 경우
- 사용자가 외부 자료 기반 HTML, 리포트, 대시보드를 요청한 경우

라우터는 다음 경우 `web_search`를 포함하지 않는다.

- 최근 대화, linked artifact, workspace 파일만으로 충분한 후속 작업
- 사용자가 명시적으로 인터넷 검색 없이 답하라고 한 경우
- 파일 목록/파일 내용/폴더 개수처럼 workspace DB 도구가 적합한 경우

라우터가 `web_search`를 선택하더라도 검색은 즉시 실행되지 않는다. 선택된 도구 목록은 LLM system prompt의 사용 가능한 도구 목록으로만 전달되고, LLM이 `tool_call` fenced block으로 `web_search`를 호출해야 한다.

## Prompt 정책

- 웹 검색 결과를 사용한 답변에는 가능한 한 URL 출처를 포함한다.
- 검색 결과 snippet은 그대로 긴 복붙하지 않고 요약한다.
- 검색 결과가 불충분하면 "검색 결과 기준" 또는 "확인 가능한 범위"라고 한계를 표시한다.
- 검색 결과를 파일로 저장해야 할 때는 기존 파일 저장 위치 확인 정책을 그대로 따른다.

## 보안과 개인정보

- agent는 사용자 파일 전문이나 민감한 workspace 내용을 검색 query로 자동 전송하지 않는다.
- 사용자가 명시적으로 파일 내용을 바탕으로 웹 검색하라고 한 경우에도 필요한 최소 키워드만 query로 보낸다.
- 내부 canonical path, user id, API key, debug payload는 검색 query와 사용자-facing 결과에 포함하지 않는다.
- 검색 provider timeout과 result cap을 둔다.

## 성공 기준

- `web_search`가 tool catalog와 manifest에 포함된다.
- 라우터가 최신/검색 요청에서 `web_search`를 선택한다.
- 최신/검색 요청에서 LLM이 `web_search` `tool_call`을 생성하면 기존 agent tool loop가 검색을 1회 실행한다.
- `selected_tools`에 없는 `web_search` 호출은 기존 blocked tool 흐름으로 차단된다.
- `execute_tool`이 provider mock으로 검색 결과를 정해진 형식으로 반환한다.
- API key 미설정, timeout, 빈 결과가 사용자 친화 메시지로 처리된다.
- 기존 파일 도구, tool-call 파싱 교정, 비차단 LLM stream 테스트가 깨지지 않는다.
- backend 전체 테스트가 통과한다.
