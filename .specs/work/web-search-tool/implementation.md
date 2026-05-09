# Web Search Tool Implementation

작성일: 2026-05-09

## 구현 결과

- `web_search`를 기존 `tool_call` 기반 agent 도구로 추가했다.
- 기본 provider는 SearXNG이며 `WEB_SEARCH_BASE_URL`로 자체 운영 endpoint를 연결한다.
- 선택 provider로 Brave Search API를 지원하되, `WEB_SEARCH_API_KEY`가 있을 때만 동작한다.
- `execute_tool("web_search", ...)`는 검색 결과를 title/url/snippet/date/source 형태의 numbered text로 반환한다.
- 라우터 fallback은 최신/뉴스/환율/가격/출처 등 외부 정보 요청에서 `web_search`를 선택하고, 파일 검색 요청은 기존 `file_search`를 유지한다.
- `web_search`는 자동 실행되지 않고, selected tool에 포함된 뒤 LLM이 명시적 `tool_call`을 생성해야 실행된다.
- `scripts/start-searxng.ps1`을 추가해 로컬 개발 서버 실행 시 Docker 기반 SearXNG 컨테이너를 best-effort로 함께 시작한다.
- VS Code `dev: backend (8001)` task와 `scripts/start-backend.ps1`은 SearXNG base URL을 backend process 환경 변수로 주입한다.

## 변경 파일

- `src/backend/app/services/web_search.py`
- `src/backend/app/services/agent_tools.py`
- `src/backend/app/services/tool_registry.py`
- `src/backend/app/services/intent_router.py`
- `src/backend/app/services/intent_text_rules.py`
- `src/backend/app/config.py`
- `src/backend/.env.example`
- `src/backend/app/startup/seeds.py`
- `src/backend/tests/unit/test_web_search.py`
- `src/backend/tests/unit/test_agent_tools_result_location.py`
- `src/backend/tests/unit/test_intent_router.py`
- `src/backend/tests/unit/test_agent_tool_loop.py`
- `src/backend/tests/unit/test_startup_app_factory.py`
- `scripts/start-searxng.ps1`
- `scripts/run-backend-dev.ps1`
- `scripts/searxng-settings.yml`
- `.vscode/tasks.json`
- `AGENTS.md`

## 검증 결과

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest tests\unit\test_web_search.py tests\unit\test_agent_tools_result_location.py tests\unit\test_intent_router.py tests\unit\test_agent_tool_loop.py tests\unit\test_startup_app_factory.py -q` → 20 passed
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 86 passed, 1 skipped
- PowerShell script parse + `.vscode/tasks.json` JSON parse → passed
- `git diff --check` → passed

## 남은 작업

- 커밋 후 `commits.md`에 연결 커밋 기록
