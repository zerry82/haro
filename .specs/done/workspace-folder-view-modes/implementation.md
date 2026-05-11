# Workspace Folder View Modes Implementation

작성일: 2026-05-07

## 현재 상태

구현 완료 상태다. 적용 확인과 연결 커밋 기록을 마쳤으며 스펙은 `.specs/done/workspace-folder-view-modes/`로 이동한다.

## 주요 변경 파일

- `src/backend/app/config.py`
- `src/backend/.env.example`
- `src/backend/app/services/file_path_policy.py`
- `src/backend/app/services/workspace_aliases.py`
- `src/backend/app/services/workspace_instruction_files.py`
- `src/backend/app/services/workspace_visibility_policy.py`
- `src/backend/app/services/workspace_file_queries.py`
- `src/backend/app/routers/files.py`
- `.gitignore`
- `src/backend/tests/unit/test_file_path_policy.py`
- `src/backend/tests/unit/test_chat_workspace_paths.py`
- `src/backend/tests/unit/test_workspace_file_db.py`
- `src/backend/tests/unit/test_workspace_instruction_files.py`
- `src/frontend/src/routes/ProjectWorkspace.svelte`
- `src/frontend/src/components/FileViewerPanel.svelte`
- `src/frontend/src/components/WorkspaceChatPanel.svelte`
- `src/frontend/src/components/WorkspaceTopBar.svelte`
- `src/frontend/src/components/WorkspaceFileExplorer.svelte`
- `src/frontend/src/components/WorkspaceSidePanel.svelte`
- `src/frontend/src/components/workspaceSidePanelTypes.ts`
- `src/frontend/src/lib/chatDisplay.ts`
- `src/frontend/src/lib/chatDisplay.test.ts`
- `src/frontend/src/lib/workspaceFolderView.ts`
- `src/frontend/src/lib/workspaceFolderView.test.ts`
- `src/frontend/src/lib/workspaceFileActions.ts`
- `src/frontend/src/lib/workspaceFileActions.test.ts`
- `src/frontend/src/lib/workspaceUtils.ts`
- `src/frontend/src/lib/workspaceUtils.test.ts`
- `src/frontend/src/stores/fileTypes.ts`
- `src/frontend/src/stores/files.ts`
- `src/frontend/src/stores/files.test.ts`

## 구현 결과

- Backend workspace root 기본값을 project-root `runtime/workspaces`로 변경하고 `runtime/`을 Git 추적 제외 대상으로 추가했다.
- Backend path safety를 강화해 `..`, drive prefix, UNC path, symlink traversal, workspace root 밖 resolved path를 차단한다.
- Backend alias/canonical resolver와 visibility policy를 추가했다.
- Directory/search API에 `include_hidden`을 연결하고, 사용자 모드 query는 alias allowlist canonical prefix 범위로 제한했다.
- 파일 생성, 업로드, content read/write 경로에서 backend resolver와 mutation validation을 거치도록 연결했다.
- Frontend topbar에 developer mode toggle을 추가하고 chat debug mode와 별도 key로 저장한다.
- Frontend user mode root를 `팀 폴더`, `내 폴더` virtual node로 구성하고, display path는 alias로 표시한다.
- Frontend folder cache는 explorer mode와 canonical path를 함께 key로 사용한다.
- 기존 rename/move/delete API는 없으므로 새로 만들지 않았다.
- Runtime workspace 초기화는 필요하지 않아 실행하지 않았다.
- 사용자별 `.HARO.md`와 `AGENTS.md` instruction 파일을 하네스에 추가했다.
- Agent 프롬프트에 `.HARO.md`, `AGENTS.md`를 순서대로 포함하도록 연결했다.
- `.HARO.md`는 시스템 관리 파일로 read/write API에서 차단하고, `AGENTS.md`는 사용자에게 보이고 수정 가능하게 했다.
- `AGENTS.md`는 사용자 모드 `내 폴더/AGENTS.md` 파일 노드와 backend alias/search allowlist에 포함했다.
- 개발자 모드 raw tree에서도 instruction 파일이 보이도록 하네스 생성 파일을 workspace DB에 sync하고, 개발자 모드 진입 시 directory cache를 강제 갱신하게 했다.
- 프로젝트 생성에서도 같은 하네스 동기화 함수를 사용하도록 연결해 신규 프로젝트의 instruction 파일이 생성 즉시 listing DB에 반영되게 했다.
- 사용자 모드 채팅 렌더링에서 canonical path를 alias path로 치환하고 tool step은 간단한 상태 문구로 표시한다.
- `.HARO.md`, `AGENTS.md` instruction context가 agent system prompt 초반에 포함되도록 보정하고, 명시적인 파일 저장 기본 위치에서 채팅 날짜/제목/id 기반 폴더를 제거했다.
- `file_create`, `file_write`에서 파일명만 전달되거나 `outputs/...` 같은 채팅 작업공간 상대 경로가 전달되면 자동 저장하지 않고 저장 위치 확인 필요 메시지를 반환한다.
- 명시적인 `내 폴더/결과/...` alias path는 사용자 결과 폴더로 resolve한다. 채팅 `outputs/working`은 임시/중간 파일 용도로만 사용한다.
- 이미 생성된 `2026-05-07-새-채팅-21ece926` 런타임 결과 폴더는 사용자 결정에 따라 이동하거나 삭제하지 않았다.

## 구현 기록

- 2026-05-07: 폴더/파일 표시 정책, 사용자/개발자 explorer 모드, backend hidden query 설계 스펙을 작성했다.
- 2026-05-07: 사용자 모드는 필터링된 폴더 조회 view이고, 실제 물리 구조는 system design을 따른다는 전제를 반영했다.
- 2026-05-07: migration 없이 기존 워크스페이스 초기화를 허용하는 전제를 반영했다.
- 2026-05-07: 초기화 전 GitHub commit/push checkpoint와 project-root runtime workspace root 방향을 반영했다.
- 2026-05-07: backend 정책을 먼저 고정하고 frontend view mode를 연결하는 개발 실행 순서와 검증 게이트를 `plan.md`에 정리했다.
- 2026-05-07: 실제 구현 진행을 추적하기 위한 체크리스트를 `tasks.md`로 분리했다.
- 2026-05-07: 스펙을 `draft`에서 `work`로 이동했다.
- 2026-05-07: backend path safety, alias/canonical resolver, hidden query, user-mode allowlist search를 구현했다.
- 2026-05-07: frontend developer/user explorer mode, user-mode alias root, mode별 cache, alias display path를 구현했다.
- 2026-05-07: legacy canonical path 참조를 검토하고 사용자 모드 UI 표시 경로를 alias display로 감쌌다.
- 2026-05-07: runtime workspace 초기화는 실행하지 않고, 안전 초기화 정책은 스펙/디자인 문서에 남겼다.
- 2026-05-07: alias shortcut과 실제 하위 폴더가 같은 canonical path를 가리킬 때 Svelte keyed each가 중복 key로 실패하는 버그를 수정했다.
- 2026-05-07: 사용자별 `.HARO.md`, `AGENTS.md` instruction 파일과 사용자 친화 채팅 경로 표시를 구현했다.
- 2026-05-07: 신규 프로젝트 사용자 모드에서 `AGENTS.md`가 보이지 않는 문제를 수정해 `내 폴더/AGENTS.md`로 노출했다.
- 2026-05-07: 개발자 모드 raw tree에서 `AGENTS.md`가 누락되는 문제를 수정했다.
- 2026-05-07: 기존 로컬 워크스페이스 15개에 instruction 파일 보정을 실행했다. `test7`, `test8` 포함.
- 2026-05-08: agent system prompt에 instruction context가 빠지는 문제를 보강하고, 기본 파일 저장 위치를 사용자 결과 폴더로 바꿨다.
- 2026-05-08: 최종 산출물 파일이 실제로 생성되고 파일 row도 있지만 새 중간 폴더 row가 workspace DB에 없어 사용자 모드 UI에 보이지 않는 문제를 수정했다. `update_workspace_item_summary`와 stale 처리에서 부모 폴더까지 sync하고, frontend file_changed refresh가 조상 폴더 cache도 갱신하도록 보강했다.
- 2026-05-08: `test8`의 `내 폴더/결과/세종대왕-대시보드` 인덱스를 보정해 `dashboard.html`, `dashboard.tsx`가 UI listing 기준으로 조회되게 했다.

## 검증 기록

- 2026-05-07 baseline:
  - `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 51 passed
  - `cd src/frontend; npm test -- --run` → 37 passed
  - `cd src/frontend; npm run build` → passed
- 2026-05-07 final:
  - `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 65 passed, 1 skipped
  - `cd src/frontend; npm test -- --run` → 47 passed
  - `cd src/frontend; npm run build` → passed
  - `git diff --check` → passed

## 남은 작업

- 없음. 적용 확인 및 연결 커밋 기록 후 `done`으로 이동한다.

## 남은 위험

- 기존 `50_chats`, `40_rules`, `45_skills` 같은 폴더는 사용자 기능인지 시스템 내부인지 추가 분류가 필요하다.
- `src/backend/data/workspaces`에는 ignored 처리된 legacy runtime data가 남아 있다. 이번 스펙은 새 기본 root를 `runtime/workspaces`로 옮기지만 기존 runtime data 삭제나 migration은 실행하지 않았다.
- 기존 workspace는 migration하지 않고 초기화하므로, 보존해야 할 실제 사용자 데이터가 있으면 구현 전 별도 백업/내보내기 판단이 필요하다.
- GitHub checkpoint는 코드/스펙 복구 지점일 뿐 runtime workspace 데이터 백업은 아니다.
- `WORKSPACE_ROOT`는 project root 기준으로 resolve하도록 구현했다. 운영 환경에서는 절대 경로도 사용할 수 있다.
- symlink escape 테스트는 환경에 따라 skip될 수 있다. 코드 경로는 `realpath + commonpath` 검증을 사용한다.
- 브라우저 수동 확인은 아직 수행하지 않았다.
