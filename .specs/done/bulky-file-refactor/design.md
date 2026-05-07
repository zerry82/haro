# Bulky File Refactor Design

작성일: 2026-05-07

## 설계 원칙

- 기존 public import 경로를 facade로 보존한다.
- Svelte 컴포넌트는 표시와 사용자 입력 이벤트만 맡기고, 데이터 로딩과 상태 전이는 기존 route가 계속 조립한다.
- 백엔드 모듈은 `types/helpers/router/facade` 순서로 의존 방향을 고정한다.
- 새 테스트는 이동한 순수 로직을 중심으로 추가한다.

## 프론트엔드 분리

```text
src/frontend/src/components/
  WorkspaceTopBar.svelte
  WorkspaceChatPanel.svelte
  FileViewerPanel.svelte
  DebugTraceModal.svelte
  ActivityRail.svelte
  WorkspaceFileExplorer.svelte
  WorkspaceSideCatalog.svelte

src/frontend/src/lib/
  debugTraceUtils.ts
  viewerRenderUtils.ts
  panelPreferences.ts
  workspaceExplorerRows.ts
  workspacePanelResize.ts
  workspaceSidePanelConfig.ts

src/frontend/src/stores/
  fileTypes.ts
  fileTreeUtils.ts
```

`ProjectWorkspace.svelte`는 다음 책임을 유지한다.

- route params와 store orchestration
- workspace/file/chat 상태 전이
- resize, drag/drop, persistence 같은 화면 전체 이벤트

분리 컴포넌트는 다음 책임만 가진다.

- `WorkspaceTopBar.svelte`: 프로젝트명, runtime/container 상태, deploy toggle, preview link
- `WorkspaceChatPanel.svelte`: 채팅 목록/메시지/input/debug toggle 표시와 callback 호출
- `WorkspaceSidePanel.svelte`: side panel shell과 header action 조립
- `ActivityRail.svelte`: 왼쪽 activity tab 표시
- `WorkspaceFileExplorer.svelte`: 파일 검색, tree virtualization, 새 폴더 row, 파일 row 표시
- `WorkspaceSideCatalog.svelte`: 스킬/툴/데이터소스 목록 표시

순수 유틸은 다음 책임을 가진다.

- `debugTraceUtils.ts`: debug payload formatting, section 구성, label 매핑, export JSON 생성
- `viewerRenderUtils.ts`: markdown/code/csv viewer 렌더링 helper
- `panelPreferences.ts`: localStorage 기반 패널/디버그 설정 저장
- `workspaceExplorerRows.ts`: file tree flattening과 virtual row 계산
- `workspacePanelResize.ts`: 패널 resize 제약 계산
- `fileTreeUtils.ts`: 파일 store의 path/tree 변환 helper

## 백엔드 intent 분리

```text
src/backend/app/services/
  intent_turns.py          # DB 상태 전이 facade
  intent_types.py          # dataclass/constants
  intent_text_rules.py     # text/json helper와 signal 판별
  intent_router.py         # LLM route와 fallback rule route
```

`intent_turns.py`는 외부에서 쓰던 `GateDecision`, `RouterDecision` import를 계속 지원하기 위해 해당 이름을 import/re-export한다.

## 백엔드 workspace DB 분리

```text
src/backend/app/services/
  workspace_file_db.py          # 기존 public facade
  workspace_file_connection.py  # sqlite connect, lock, atomic write
  workspace_file_lifecycle.py   # ensure/rebuild/sync/delete/summary/relation
  workspace_file_queries.py     # list/search/count/briefing
```

`workspace_file_db.py`는 기존 router/service가 import하던 함수명을 그대로 제공한다.

## 백엔드 추가 Facade 분리

```text
src/backend/app/routers/
  files.py              # 파일 API route facade
  file_models.py        # 파일 API request/response 모델

src/backend/app/services/
  file_path_policy.py        # 파일 API read/write/path/name 정책
  file_conversion.py         # Excel 업로드 CSV 변환과 언어 판별
  chat_workspace.py          # 기존 public facade
  chat_workspace_paths.py
  chat_workspace_files.py
  chat_workspace_templates.py
  chat_workspace_lifecycle.py
  chat_workspace_log.py
  chat_workspace_references.py
  chat_workspace_summary.py
  container_manager.py       # Docker sandbox facade
  container_runtime.py
  container_docker.py
  container_db.py
  container_lifecycle.py
  container_execution.py
  container_deploy.py
  container_maintenance.py
  app/startup/*              # main.py startup/migration/seed/lifespan 분리
```

추가 분리에서도 기존 public import 경로는 유지한다. `chat_workspace.py`, `container_manager.py`, `workspace_file_db.py`는 외부 호출자가 보는 Facade로 남긴다.

## 검증

- `cd src/backend; .\.venv\Scripts\python.exe -m compileall app tests`
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest`
- `cd src/frontend; npm test`
- `cd src/frontend; npm run build`
- `git diff --check`
