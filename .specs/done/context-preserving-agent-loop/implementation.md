# Context-Preserving Agent Loop Implementation

작성일: 2026-05-11
상태: done

## 구현 결과

- `.specs/draft/context-preserving-agent-loop`를 `.specs/work/context-preserving-agent-loop`로 이동했다.
- `ExecutionPolicyResolver`를 추가해 기존 semantic router 대신 broad execution profile을 선택하도록 했다.
- `intent_router.py`는 삭제하지 않고 compatibility adapter로 축소했다. `llm_route()`는 더 이상 의미 판단을 수행하지 않고, `rule_route()`/`fallback_router_decision()`은 execution policy를 `RouterDecision`으로 변환한다.
- `RouterDecision`은 호환을 위해 유지하되 `execution_policy`, context/target/source/operation confidence 필드를 추가했다.
- Working Context 문구를 "현재 턴 라우팅 맥락"에서 "현재 작업 맥락"으로 바꾸고, execution policy와 File Discovery Context를 compact하게 포함한다.
- 시스템 프롬프트에 active file 우선, B2B confidence/risk 확인 정책, 반복 검색/정정 진단 정책을 추가했다.
- `TurnToolState`를 추가해 한 턴 안의 검색 signature, 확인한 파일/폴더, write guard 결과를 추적한다.
- `agent_tool_loop`에 `TurnToolState`를 연결해 동일 검색 반복과 읽지 않은 대상에 대한 수정/삭제/이동을 synthetic result로 차단한다.
- `doc/src/README.md`의 에이전트 실행 설명을 새 policy/working-context/tool-state 흐름에 맞게 갱신했다.

## 검증

실행 완료:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest tests/unit/test_file_discovery_context.py tests/unit/test_agent_response.py tests/unit/test_intent_router.py tests/unit/test_agent_tool_loop.py

.\.venv\Scripts\python.exe -m pytest

cd ../frontend
npm run build
```

결과:

- 44 passed
- 133 passed, 1 skipped
- frontend build passed

## 남은 관찰 항목

- 실제 Gemini 루프에서 weather/date-section 회귀 시나리오는 다음 대화형 스모크 테스트에서 추가 관찰한다.
