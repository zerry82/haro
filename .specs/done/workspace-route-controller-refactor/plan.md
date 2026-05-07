# Workspace Route Controller Refactor Plan

작성일: 2026-05-07

## 가정

- 이번 스펙은 frontend route인 `src/frontend/src/routes/ProjectWorkspace.svelte`를 대상으로 한다.
- backend API, SSE 이벤트명, Svelte store public API, UI 레이아웃은 변경하지 않는다.
- 구현을 시작할 때 이 스펙은 `.specs/draft/`에서 `.specs/work/`로 이동한다.
- 구현 중 각 단계는 작은 단위로 완료하고, 가능한 한 Vitest를 함께 추가한다.

## 현재 책임 묶음

`ProjectWorkspace.svelte`에 남아 있는 workspace route 책임은 다음 묶음으로 다룬다.

- 파일 변경 refresh: `queueExplorerRefresh`, `flushExplorerRefreshes`, `handleFileChanged`
- 파일 저장/재로드: `handleSaveFile`, `handleReloadCurrentFile`
- 폴더 생성: `beginCreateFolder`, `submitCreateFolder`
- 업로드와 drag/drop: `triggerUpload`, `uploadSelectedFiles`, `handleFileDragOver`, `handleFileDragLeave`, `handleFileDrop`
- explorer interaction: `getExplorerTargetDir`, `getNodeTargetDir`, `handleNodeClick`, `handleSearchResultClick`

채팅, deploy, preview/editor tab workflow는 이번 계획의 직접 구현 범위에서 제외한다.

## 단계별 계획

### 0. 구현 시작 준비

목표:

- 스펙 폴더를 `.specs/draft/workspace-route-controller-refactor/`에서 `.specs/work/workspace-route-controller-refactor/`로 이동한다.
- 현재 frontend 테스트와 build 상태를 확인한다.

검증:

```powershell
cd src/frontend
npm test
npm run build
```

### 1. File Refresh 순수 helper 분리

목표:

- file changed event detail, affected directory 계산, selected file reload 판단을 순수 함수로 분리한다.
- timer와 Svelte 상태는 route에 남긴다.

예정 파일:

- `src/frontend/src/lib/workspaceFileRefresh.ts`
- `src/frontend/src/lib/workspaceFileRefresh.test.ts`

예정 API:

- `normalizeFileChangedDetail(detail)`
- `getAffectedRefreshDirectories(path, itemType)`
- `shouldReloadSelectedFile(changedPath, selectedPath)`
- `getSelectedFileRefreshDecision(options)`
- `mergeRefreshQueue(queue, path, itemType)`

검증:

- directory 변경 시 directory 자체와 parent directory가 refresh 대상이 되는지 테스트한다.
- 선택 파일이 외부에서 바뀌었을 때 unsaved 상태에 따라 reload 또는 external changed flag로 분기되는지 테스트한다.
- 같은 path가 queue에 반복 추가될 때 itemType이 보존되는지 테스트한다.

### 2. File Refresh route 연결

목표:

- `ProjectWorkspace.svelte`의 `handleFileChanged`, `queueExplorerRefresh`, `flushExplorerRefreshes`에서 순수 helper를 사용한다.
- 기존 debounce, store 호출 순서, selected file reload 동작은 유지한다.

검증:

```powershell
cd src/frontend
npm test
npm run build
```

### 3. File Actions helper 분리

목표:

- 폴더 생성 이름 검증, explorer target directory 계산, readonly mutation guard, drag/drop 파일 판단을 순수 helper로 분리한다.
- API 호출과 store mutation orchestration은 route에 남긴다.

예정 파일:

- `src/frontend/src/lib/workspaceFileActions.ts`
- `src/frontend/src/lib/workspaceFileActions.test.ts`

예정 API:

- `validateNewFolderName(name)`
- `getExplorerTargetDir(options)`
- `getNodeTargetDir(node, fallback)`
- `isReadOnlyMutationTarget(path)`
- `hasDraggedFiles(types)`
- `formatFileActionError(error, fallback)`

검증:

- 빈 폴더명, `.`, `..`, slash/backslash 포함 이름을 차단하는지 테스트한다.
- focused node, selected file, default inbox 기준 target directory 계산을 테스트한다.
- clean room path mutation guard와 drag/drop file type 판단을 테스트한다.

### 4. File Actions route 연결

목표:

- `beginCreateFolder`, `submitCreateFolder`, `triggerUpload`, `uploadSelectedFiles`, drag/drop handler에서 helper를 사용한다.
- overwrite retry 흐름과 사용자 메시지는 기존 동작을 유지한다.

검증:

```powershell
cd src/frontend
npm test
npm run build
```

### 5. Explorer Interaction helper 분리

목표:

- search result와 explorer node 선택 판단을 작은 helper로 분리한다.
- unsaved 변경 confirm 필요 여부를 테스트 가능한 함수로 만든다.

예정 파일:

- `src/frontend/src/lib/workspaceExplorerActions.ts`
- `src/frontend/src/lib/workspaceExplorerActions.test.ts`

예정 API:

- `buildFocusedSearchNode(item)`
- `shouldConfirmDiscardUnsaved(nextPath, selectedPath, hasUnsavedChanges)`
- `isDirectorySearchResult(item)`

검증:

- 파일/폴더 search result 변환을 테스트한다.
- 같은 파일 재선택 또는 unsaved 없음 상태에서는 confirm이 필요 없는지 테스트한다.
- 다른 파일로 이동하며 unsaved 변경이 있을 때 confirm이 필요한지 테스트한다.

### 6. Explorer Interaction route 연결

목표:

- `handleNodeClick`, `handleSearchResultClick`에서 helper를 사용한다.
- route는 navigation, store 호출, UI callback 조립만 담당하도록 정리한다.

검증:

```powershell
cd src/frontend
npm test
npm run build
```

### 7. 최종 정리

목표:

- `ProjectWorkspace.svelte`에서 제거 가능한 중복 helper와 import를 정리한다.
- 구현 결과와 검증 결과를 스펙 문서에 기록한다.
- 필요하면 `ProjectWorkspace.svelte`의 남은 큰 책임을 후속 스펙 후보로 기록한다.

검증:

```powershell
cd src/frontend
npm test
npm run build
git diff --check
```

## 구현 중단 또는 재설계 조건

- helper API가 route 내부 상태를 과도하게 많이 요구해 오히려 복잡해질 때
- Svelte reactivity를 우회하거나 `$state` 동작을 불안정하게 만드는 구조가 될 때
- 테스트가 순수 판단을 검증하지 못하고 구현 세부사항만 고정하게 될 때
- 기존 API/store 호출 순서를 유지하기 어려운 변경이 필요해질 때

이 경우 해당 단계에서 멈추고 `design.md`와 이 문서를 먼저 갱신한다.

## 완료 기준

- file refresh, file action, explorer interaction의 순수 판단 로직이 route 밖으로 분리된다.
- 분리된 helper에 Vitest가 추가된다.
- `ProjectWorkspace.svelte`는 route composition과 workflow orchestration에 집중한다.
- `npm test`, `npm run build`, `git diff --check` 결과가 문서화된다.
