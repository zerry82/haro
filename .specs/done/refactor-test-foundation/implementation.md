# Refactor Test Foundation Implementation

작성일: 2026-05-07

## 현재 상태

스펙의 주요 잔여 작업을 완료했다. 백엔드에는 단위 테스트 기반을 추가하고, `agent.py`와 `workspace_file_db.py`에 몰려 있던 책임을 작게 분리했다. 프론트엔드에는 Vitest 기반 테스트를 추가하고, `ProjectWorkspace.svelte`의 순수 helper, 디버그 모달, 파일 뷰어 패널을 별도 모듈/컴포넌트로 분리했다.

프론트 빌드에서 남아 있던 `Logs.svelte`의 Svelte 경고와 큰 chunk 경고도 정리했다. `ProjectWorkspace.svelte` 자체는 여전히 큰 편이지만, 이번 스펙에서 목표로 삼은 테스트 기반과 안전한 1차 분리, 명시된 잔여 경고 정리는 완료 상태다.

## 백엔드 구현

- `src/backend/requirements-dev.txt`
  - 백엔드 개발 테스트 의존성으로 `pytest`를 추가했다.
- `src/backend/pytest.ini`
  - `pythonpath = .`와 `tests` 실행 기준을 정의했다.
- `src/backend/app/services/agent_response.py`
  - tool call 파싱, tool call 제거, 차단 메시지, compact helper를 분리했다.
- `src/backend/app/services/agent_events.py`
  - debug trace 저장과 assistant 메시지 저장/emit helper를 분리했다.
- `src/backend/app/services/agent_tool_loop.py`
  - LLM round 실행, tool call 검증/실행, tool loop 진행을 `run_agent` 밖으로 분리했다.
- `src/backend/app/services/agent.py`
  - gate, message 저장, 최종 orchestration 중심으로 축소했다.
- `src/backend/app/services/workspace_file_helpers.py`
  - 워크스페이스 경로 정규화, 메타 경로 판별, path classification, 검색 query escape, snippet helper를 분리했다.
- `src/backend/app/services/workspace_file_schema.py`
  - SQLite schema 초기화와 meta read/write 책임을 분리했다.
- `src/backend/app/services/workspace_file_indexer.py`
  - index rebuild, item upsert, FTS sync, event 기록 책임을 분리했다.
- `src/backend/app/services/workspace_file_db.py`
  - 공개 API/facade 역할을 유지하고 내부 세부 작업은 분리 모듈로 위임했다.

## 백엔드 테스트

- `src/backend/tests/unit/test_agent_response.py`
  - tool call JSON 파싱, fenced block 처리, 잘못된 JSON, 차단 메시지, compact 동작을 고정했다.
- `src/backend/tests/unit/test_agent_tool_loop.py`
  - LLM 요청 content 구성의 핵심 변환을 검증했다.
- `src/backend/tests/unit/test_workspace_file_db.py`
  - 임시 워크스페이스 기반 목록, `.haro` 제외, 검색, 카운트 동작을 검증했다.
- `src/backend/tests/unit/test_workspace_file_helpers.py`
  - 경로/검색 helper의 순수 동작을 검증했다.

## 프론트엔드 구현

- `src/frontend/package.json`, `src/frontend/package-lock.json`
  - Vitest dev dependency와 `npm test` script를 추가했다.
- `src/frontend/src/lib/workspaceUtils.ts`
  - 경로, 파일 타입, viewer 탭, HTML escape helper를 분리했다.
- `src/frontend/src/lib/workspaceUtils.test.ts`
  - DOM 없는 순수 유틸 단위 테스트를 추가했다.
- `src/frontend/src/components/DebugTraceModal.svelte`
  - `ProjectWorkspace.svelte`의 debug trace 모달 UI를 컴포넌트로 분리했다.
- `src/frontend/src/components/FileViewerPanel.svelte`
  - 파일 viewer, preview, CSV table/editor, text editor 패널을 컴포넌트로 분리했다.
- `src/frontend/src/routes/ProjectWorkspace.svelte`
  - workspace helper와 분리 컴포넌트를 사용하도록 변경했다.
  - `highlight.js` 전체 번들 import를 core + 필요한 language 등록 방식으로 바꿨다.
- `src/frontend/src/routes/Logs.svelte`
  - 초기 session id 참조를 함수로 감싸 `state_referenced_locally` 경고를 제거했다.
- `src/frontend/src/App.svelte`
  - route component를 동적 import로 전환해 초기 번들을 줄였다.
- `src/frontend/vite.config.ts`
  - `manualChunks`를 지정해 CodeMirror, viewer vendor, Svelte vendor, icon chunk를 분리했다.

## 문서 동기화

- `AGENTS.md`
  - 백엔드/프론트엔드 테스트 실행 명령과 단위 테스트 원칙을 반영했다.
- `doc/src/README.md`
  - 주요 개발 명령에 백엔드/프론트엔드 테스트와 빌드 명령을 반영했다.
- `.specs/refactor-test-foundation/implementation.md`
  - 실제 구현 결과와 검증 결과를 최신화했다.
- `.specs/refactor-test-foundation/commits.md`
  - 현재 브랜치와 아직 커밋되지 않은 상태를 기록했다.

## 검증 결과

- `cd src/backend; .\.venv\Scripts\python.exe -m compileall app tests`
  - 성공
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest`
  - 성공, 22 passed
- `cd src/frontend; npm test`
  - 성공, 9 passed
- `cd src/frontend; npm run build`
  - 성공
  - `Logs.svelte` Svelte 경고 제거됨
  - 큰 chunk 경고 제거됨
- `git diff --check`
  - 성공
  - Windows 줄바꿈 변환 안내만 출력됨

## 후속 개선 후보

- `ProjectWorkspace.svelte`는 `FileExplorerPanel`, `ChatPanel`, `WorkspaceTopBar` 단위로 더 나눌 수 있다.
- `workspace_file_db.py`는 공개 API facade로 남겼지만 아직 300줄을 넘으므로 추가 축소 후보로 남는다.
- `agent_tool_loop.py`는 tool loop 책임을 분리했지만, 추후 LLM client adapter와 tool execution facade를 더 세분화할 수 있다.
