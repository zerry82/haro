# Workspace Folder View Modes Plan

작성일: 2026-05-07

## 개발 실행 순서 요약

이 스펙은 backend 정책을 먼저 고정한 뒤 frontend view mode를 연결한다. 사용자 모드는 backend가 필터링한 안전한 결과를 받아 alias view로 보여주고, 개발자 모드는 모든 사용자가 raw tree를 볼 수 있게 한다.

구현 중 실제 진행 체크는 `tasks.md`를 기준으로 한다. `plan.md`는 단계별 방향과 검증 게이트를 설명하고, `tasks.md`는 실행 항목을 체크리스트로 관리한다.

실행 순서:

1. 스펙을 `draft`에서 `work`로 이동하고 baseline 테스트를 확인한다.
2. workspace root, path safety, 초기화 정책을 backend 기준으로 먼저 고정한다.
3. backend visibility policy, alias resolver, `include_hidden`, 사용자 모드 allowlist 검색을 구현하고 단위 테스트를 통과시킨다.
4. frontend developer mode 상태, mode별 cache key, alias/canonical resolver, 사용자 모드 root view를 구현하고 단위 테스트를 통과시킨다.
5. 파일 생성/업로드/rename/move/delete target이 backend resolver를 거쳐 canonical path로 처리되는지 통합 검증한다.
6. 필요 시 GitHub checkpoint 이후 기존 개발/테스트 workspace를 안전 초기화하고 harness 구조를 재생성한다.
7. 전체 backend/frontend 테스트와 build를 통과시킨 뒤 문서와 커밋 기록을 동기화한다.

검증 게이트:

- Backend gate: path safety, dot-prefix validation, visibility filtering, alias resolver, search allowlist 테스트가 통과해야 frontend 연결로 넘어간다.
- Frontend gate: developer mode state, cache 분리, alias root, alias/canonical 변환 테스트가 통과해야 mutation 연결로 넘어간다.
- Integration gate: `pytest`, `npm test`, `npm run build`, `git diff --check`가 통과해야 스펙 완료 후보가 된다.

## 0. 구현 시작 준비

- 스펙을 `.specs/draft/workspace-folder-view-modes/`에서 `.specs/work/workspace-folder-view-modes/`로 이동한다.
- backend/frontend 현재 테스트 상태를 확인한다.
- 기존 workspace는 migration하지 않고 초기화 가능하다는 전제를 확인한다.
- 초기화가 필요한 경우, 실행 전에 현재 변경을 커밋하고 GitHub 원격에 push한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd src/frontend
npm test
npm run build
```

## 1. 시스템 물리 구조와 alias mapping 확정

목표:

- 물리 구조는 UX 이름이 아니라 system design을 따르도록 확정한다.
- 사용자 모드의 `팀 폴더`, `내 폴더` alias prefix가 어떤 canonical prefix를 가리키는지 정한다.
- 사용자 모드 UI에는 내부 user id 기반 canonical prefix가 직접 노출되지 않도록 alias mapping을 정의한다.

예정 파일:

- `src/backend/app/services/harness.py`
- `src/backend/app/services/context.py`
- `src/backend/app/services/tool_registry.py`
- `src/backend/app/services/chat_workspace_paths.py`
- `src/frontend/src/lib/workspaceUtils.ts`
- 신규 alias mapping helper

검증:

- alias root가 `팀 폴더`, `내 폴더`로 구성된다.
- alias prefix가 canonical prefix로 1:1 resolve된다.
- 물리 구조 변경이 필요한 경우에도 그 이유가 system design에 근거한다.

## 2. 안전한 workspace 초기화 절차 추가

목표:

- 기존 workspace를 migration하지 않고 현재 system design 구조로 재생성하는 절차를 명시하거나 helper/script로 만든다.
- 초기화 전 GitHub commit/push checkpoint를 필수 조건으로 둔다.
- 초기화 대상 path가 workspace root 하위인지 반드시 검증한다.
- workspace DB/index는 초기화 후 재생성한다.
- workspace root를 프로젝트 루트 하위 runtime data 경로로 옮긴다.

예정 파일:

- `src/backend/app/config.py`
- `src/backend/.env.example`
- `.gitignore`
- `scripts/` 하위 reset helper 또는 backend service helper
- 필요 시 문서

검증:

- 초기화 전 `git status`와 upstream push 상태를 확인한다.
- 잘못된 path나 workspace root 밖 path는 초기화가 차단된다.
- 초기화 후 `ensure_harness_structure`가 시스템 물리 구조를 만든다.
- workspace root가 `src/backend` 하위가 아니라 project root 하위 `runtime/workspaces`로 resolve된다.
- 초기화 절차가 source code, `.specs`, repo root, `src/backend`를 건드리지 않는다.
- `runtime/`은 gitignore 대상이다.

## 3. Hidden/System Path 정책 helper 추가

목표:

- backend에서 dot-prefixed/system hidden path를 판별하는 helper를 만든다.
- `.haro`, `.openclaw`, dot-prefixed 항목을 기본 숨김 대상으로 정의한다.

예정 파일:

- `src/backend/app/services/workspace_visibility_policy.py`
- backend tests

검증:

- `/docs/.cache`
- `/.haro`
- `/.openclaw`
- `/playground/users/u1/20_working/a.md`
- `/clean-room/data/10_sources/source.csv`

각 경로가 숨김/표시 대상으로 올바르게 분류되는지 테스트한다.

## 4. Directory/Search API에 include_hidden 추가

목표:

- `GET /files`와 `GET /files/search`에 `include_hidden` query를 추가한다.
- `include_hidden=false`일 때 SQL WHERE에서 숨김 항목을 제외한다.
- 사용자 모드에서는 alias allowlist에 포함된 canonical prefix 범위로 directory/search 결과를 제한한다.
- 개발자 모드에서는 모든 사용자가 `include_hidden=true` raw tree를 볼 수 있게 하되, 기존 파일 권한과 path safety guard는 유지한다.
- pagination total과 `has_more`가 필터 이후 기준이 되게 한다.

예정 파일:

- `src/backend/app/routers/files.py`
- `src/backend/app/services/workspace_file_queries.py`
- 관련 backend tests

검증:

- hidden 항목이 list/search에서 제외되는지 확인
- `include_hidden=true`에서는 raw 항목이 보이는지 확인
- 사용자 모드 search가 alias allowlist 밖 canonical path를 반환하지 않는지 확인
- limit/offset이 hidden filter와 함께 정상 동작하는지 확인

## 4.5 Backend path safety guard 점검

목표:

- 모든 backend filesystem 작업이 canonical path resolve 이후 workspace root 내부에서만 수행되도록 점검한다.
- `..`, absolute path injection, Windows drive prefix, UNC path, symlink/mount traversal을 차단한다.
- EFS mount 또는 symlink를 쓰더라도 configured workspace root 정책을 벗어나지 않게 한다.

예정 파일:

- `src/backend/app/services/file_path_policy.py`
- `src/backend/app/routers/files.py`
- 관련 backend tests

검증:

- workspace root 밖 path read/write/create/delete가 실패한다.
- symlink 또는 resolved absolute path가 workspace root 밖이면 실패한다.
- 기존 Clean Room 권한과 internal metadata content guard가 유지된다.

## 5. Frontend 개발자 모드 상태 추가

목표:

- topbar에 개발자 모드 토글을 추가한다.
- `developerMode`를 user-specific localStorage에 저장한다.
- 채팅 debug mode와 상태를 분리한다.

예정 파일:

- `src/frontend/src/components/WorkspaceTopBar.svelte`
- `src/frontend/src/routes/ProjectWorkspace.svelte`
- `src/frontend/src/lib/panelPreferences.ts` 또는 신규 preference helper
- frontend tests

검증:

- 개발자 모드 저장 key가 사용자별로 분리되는지 테스트
- build에서 topbar props 타입이 깨지지 않는지 확인

## 6. 사용자 모드 filtered alias view model 추가

목표:

- 사용자 모드 root를 `팀 폴더`, `내 폴더`로 구성한다.
- alias path와 canonical path의 prefix resolver를 만든다.
- 사용자 모드에서 user id가 UI 경로에 노출되지 않도록 한다.

예정 파일:

- `src/frontend/src/lib/workspaceFolderView.ts`
- `src/frontend/src/lib/workspaceFolderView.test.ts`
- `src/frontend/src/lib/workspaceExplorerRows.ts`
- `src/frontend/src/components/WorkspaceFileExplorer.svelte`

검증:

- alias root가 기대한 표시 이름으로 생성되는지 테스트
- `내 폴더/작업 중` alias path가 system-defined canonical path로 변환되는지 테스트
- alias path에서 user id가 제거되는지 테스트

## 7. API 호출 mode 연결

목표:

- 개발자 모드에서는 `include_hidden=true`로 directory/search를 호출한다.
- 사용자 모드에서는 `include_hidden=false`로 directory/search를 호출한다.
- cache key가 mode에 따라 충돌하지 않도록 한다.

주의:

- 현재 `folderCache` key가 path만 쓰는 구조면, 같은 path를 다른 hidden 정책으로 로드할 때 충돌할 수 있다.
- 충돌 가능성이 있으면 cache key에 visibility mode를 포함하거나 mode 전환 시 cache를 reload한다.

검증:

- mode 전환 후 root/explorer가 stale cache를 보여주지 않는지 테스트 또는 수동 확인한다.

## 8. 파일 mutation target 연결

목표:

- 사용자 모드 alias node에서 새 폴더/업로드 target을 canonical path로 resolve한다.
- read-only 팀 폴더에서는 기존 guard를 유지한다.

검증:

- `내 폴더/받은 파일`에서 생성 요청이 실제 inbox canonical path로 들어가는지 테스트한다.
- `팀 폴더/데이터`에서 생성/업로드가 차단되는지 확인한다.

## 9. Legacy path 참조 점검

목표:

- 코드와 문서에서 사용자 모드에 노출되는 legacy path 참조를 제거하거나 alias mapping으로 감싼다.
- system design상 남아야 하는 canonical path 참조는 유지하되 사용자 표시 경로로 직접 사용하지 않는다.

검증:

```powershell
rg "clean-room|playground/users|90_archive|00_inbox|20_working|30_outputs" src/backend src/frontend/src
rg "src/backend/data|data/workspaces|WORKSPACE_ROOT" src/backend .specs AGENTS.md
```

남아도 되는 참조는 system canonical path, legacy compatibility, test fixture 중 하나임을 명확히 한다.

## 10. 최종 검증과 문서 동기화

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd src/frontend
npm test
npm run build

git diff --check
```

문서:

- `implementation.md`에 구현 결과와 검증 결과 기록
- `commits.md`에 연결 커밋 기록
- 완료 시 `.specs/done/workspace-folder-view-modes/`로 이동

## 중단 또는 재설계 조건

- workspace 초기화가 workspace root 밖 path를 건드릴 위험이 있는 경우
- 초기화 전 GitHub checkpoint를 만들 수 없는 경우
- workspace root가 project root 하위 runtime 경로로 안정적으로 resolve되지 않는 경우
- backend pagination과 frontend alias root가 충돌해 empty page를 만들 경우
- alias path와 canonical path resolver가 불일치해 파일 저장/업로드 target이 잘못될 경우
- user id가 사용자 모드 UI에 계속 노출될 경우
- 사용자 모드 search가 alias allowlist 밖 canonical path를 반환하는 경우
- backend filesystem 작업이 workspace root 밖 path를 처리할 가능성이 있는 경우
- 물리 구조를 UX 이름에 맞추기 위해 system design을 훼손해야 하는 경우
