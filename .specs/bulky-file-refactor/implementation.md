# Bulky File Refactor Implementation

작성일: 2026-05-07

## 현재 상태

비대한 파일 리팩토링 2차 패치를 완료했다. 기존 public import 경로와 화면 동작을 유지하면서 백엔드 Facade, 프론트엔드 표시 컴포넌트, 순수 유틸을 추가로 분리했다.

## 주요 라인 수 변화

- `src/backend/app/services/workspace_file_db.py`
  - 약 529줄에서 49줄 facade로 축소
- `src/backend/app/services/intent_turns.py`
  - 약 616줄에서 297줄로 축소
- `src/backend/app/routers/files.py`
  - 400줄대에서 223줄 route facade로 축소
- `src/backend/app/services/chat_workspace.py`
  - 400줄대에서 29줄 public facade로 축소
- `src/backend/app/services/container_manager.py`
  - 400줄대에서 96줄 facade로 축소
- `src/backend/app/main.py`
  - 400줄대에서 5줄 app factory 호출로 축소
- `src/frontend/src/components/WorkspaceSidePanel.svelte`
  - 422줄에서 204줄 side panel shell로 축소
- `src/frontend/src/stores/files.ts`
  - 367줄에서 217줄 store facade로 축소
- `src/frontend/src/routes/ProjectWorkspace.svelte`
  - 약 1,700줄대에서 1,065줄로 축소

## 백엔드 추가 변경

- 파일 API
  - `app/routers/file_models.py`: 파일 API request/response 모델 분리
  - `app/services/file_path_policy.py`: read/write/path/name 정책 분리
  - `app/services/file_conversion.py`: Excel to CSV 변환, 언어 판별, editable 확장자 분리
- Chat workspace
  - `chat_workspace.py`: 기존 public facade 유지
  - `chat_workspace_paths.py`, `chat_workspace_files.py`, `chat_workspace_templates.py`
  - `chat_workspace_lifecycle.py`, `chat_workspace_log.py`
  - `chat_workspace_references.py`, `chat_workspace_summary.py`
- Container sandbox
  - `container_manager.py`: public facade 유지
  - `container_runtime.py`: command/path/status/idle pure helper
  - `container_docker.py`: Docker SDK gateway와 circuit breaker
  - `container_db.py`: project/node/activity DB helper
  - `container_lifecycle.py`, `container_execution.py`, `container_deploy.py`, `container_maintenance.py`
- Startup
  - `app_factory.py`: FastAPI 앱 생성, middleware/router/static mount
  - `startup/lifespan.py`: startup/shutdown 흐름
  - `startup/migrations.py`: SQLite migration
  - `startup/seeds.py`: builtin skill/sandbox node seed
  - `startup/container_tasks.py`: idle cleanup/shutdown container task

## 프론트엔드 추가 변경

- `ActivityRail.svelte`: 왼쪽 activity tab 표시 분리
- `WorkspaceFileExplorer.svelte`: 파일 검색, virtual row, 파일 row, 새 폴더 row 분리
- `WorkspaceSideCatalog.svelte`: 스킬/툴/데이터소스 목록 분리
- `workspaceSidePanelTypes.ts`, `workspaceSidePanelConfig.ts`: side panel 타입/상수 분리
- `debugTraceUtils.ts`: debug trace payload formatting/section/export 분리
- `viewerRenderUtils.ts`: markdown/code/csv rendering helper 분리
- `panelPreferences.ts`: localStorage 기반 패널/디버그 설정 분리
- `workspaceExplorerRows.ts`: tree flattening/virtualization 분리
- `workspacePanelResize.ts`: 패널 resize 제약 계산 분리
- `fileTypes.ts`, `fileTreeUtils.ts`: 파일 store DTO와 tree/path helper 분리

## 테스트 추가

- 백엔드
  - `test_file_conversion.py`
  - `test_file_path_policy.py`
  - `test_chat_workspace_paths.py`
  - `test_chat_workspace_references.py`
  - `test_chat_workspace_summary.py`
  - `test_container_runtime.py`
  - `test_startup_app_factory.py`
- 프론트엔드
  - `debugTraceUtils.test.ts`
  - `viewerRenderUtils.test.ts`
  - `panelPreferences.test.ts`
  - `workspaceExplorerRows.test.ts`
  - `workspacePanelResize.test.ts`
  - `fileTreeUtils.test.ts`

## 검증 결과

- `cd src/backend; .\.venv\Scripts\python.exe -m compileall app tests`
  - 성공
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest`
  - 성공, 51 passed
- `cd src/frontend; npm test`
  - 성공, 24 passed
- `cd src/frontend; npm run build`
  - 성공
- `git diff --check`
  - 성공
  - Windows 줄바꿈 변환 안내만 출력됨

## 남은 판단

- `ProjectWorkspace.svelte`는 아직 1,000줄을 넘지만 현재는 route params, store orchestration, 화면 전체 이벤트 조립 책임이 중심이다. 다만 파일 mutation workflow와 chat lifecycle workflow는 이후 별도 controller/action 모듈로 더 나눌 수 있다.
- `src/backend/app/services/agent.py`는 305줄로 300줄 신호에 걸리지만 주로 에이전트 실행 orchestration이다. 다음 리팩토링에서는 message persistence, SSE event 조립, run loop entry를 더 나눌지 검토한다.
- `Dashboard.svelte`와 `FileViewerPanel.svelte`는 300줄을 조금 넘지만 현재 변경 이유가 비교적 한 화면/한 패널에 묶여 있다. 큰 기능 추가 전에는 다시 SRP 점검을 권장한다.
