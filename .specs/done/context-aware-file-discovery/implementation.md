# Context-Aware File Discovery Implementation

작성일: 2026-05-10
상태: done

## 구현 요약

- 메시지 API와 프론트 `sendMessage` payload에 optional `open_file_context`를 추가했다.
- `CodeEditor` 선택 영역 변경을 상위 컴포넌트로 전달하고, 메시지 전송 시 현재 선택 파일의 경로/언어/탭/dirty 상태와 선택 preview만 포함한다.
- 백엔드에 내부 `file_discovery_context` 서비스를 추가해 active file, latest artifact, 최근 대화의 원문 후보, linked files, artifacts metadata, chat workspace 폴더, bounded workspace search 후보를 랭킹한다.
- "기존에 작성했었어" 같은 답변은 최근 대화 메시지의 `content_preview`를 `conversation_message` source 후보로 만들며, 진행 상황 안내 메시지는 원문 후보로 오인하지 않도록 제외한다.
- `ResolvedIntentContext`와 `routing_context`에 discovery 결과를 포함하고, source content가 없으면 라우터 결과를 즉시 clarification 질문으로 전환한다.
- 실행 루프에서 `file_search`, `dir_list`, `file_search_content`의 동일 normalized args 반복 호출을 synthetic result로 생략한다.

## 검증

- `src/backend/.venv/Scripts/python.exe -m pytest tests/unit/test_file_discovery_context.py tests/unit/test_agent_response.py tests/unit/test_intent_router.py tests/unit/test_agent_tool_loop.py`
  - 2026-05-10 추가 검증: 41 passed
- `cd src/frontend && npm run build`

## 후속 확장 후보

- 실제 다중 열린 탭 목록은 현재 UI 상태 모델이 생긴 뒤 확장한다.
- prompt packaging/cache 개편은 별도 스펙으로 분리한다.
