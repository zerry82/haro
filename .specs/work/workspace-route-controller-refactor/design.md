# Workspace Route Controller Refactor Design

작성일: 2026-05-07

## 설계 원칙

- `ProjectWorkspace.svelte`는 route composition root로 남긴다.
- `$state`, `$effect`, Svelte lifecycle은 급하게 외부로 옮기지 않는다.
- 테스트 가능한 순수 판단 로직을 먼저 `src/frontend/src/lib`로 분리한다.
- store mutation/API 호출이 필요한 workflow는 작은 action module로 분리하되, route에서 context를 주입한다.
- 기존 컴포넌트 props 계약은 가능한 유지한다.

구현 순서와 단계별 검증은 `plan.md`를 따른다.

## 목표 구조

```text
src/frontend/src/routes/
  ProjectWorkspace.svelte

src/frontend/src/lib/
  workspaceFileRefresh.ts
  workspaceFileActions.ts
  workspaceExplorerActions.ts

src/frontend/src/lib/*.test.ts
  workspaceFileRefresh.test.ts
  workspaceFileActions.test.ts
  workspaceExplorerActions.test.ts
```

## File Refresh 설계

`workspaceFileRefresh.ts`는 다음 순수 helper를 제공한다.

- `normalizeFileChangedDetail(detail)`
  - SSE/browser custom event detail에서 path/type을 안전하게 뽑는다.
- `getAffectedRefreshDirectories(path, itemType)`
  - 변경 path의 parent directory와 directory 자체 dirty 대상 계산
- `shouldReloadSelectedFile(changedPath, selectedPath)`
  - 현재 선택 파일을 reload해야 하는지 판단
- `getSelectedFileRefreshDecision(...)`
  - unsaved changes가 있으면 external changed flag를 세우고, 아니면 reload 대상 반환
- `mergeRefreshQueue(queue, path, itemType)`
  - debounce queue에 같은 path가 여러 번 들어올 때 itemType 보존 정책을 정의

Timer 자체는 `ProjectWorkspace.svelte` 또는 얇은 wrapper가 유지한다. 이렇게 하면 핵심 판단은 DOM 없이 테스트할 수 있다.

## File Actions 설계

`workspaceFileActions.ts`는 다음 helper를 제공한다.

- `validateNewFolderName(name)`
  - 빈 값, `.`, `..`, slash/backslash 차단
- `getExplorerTargetDir(...)`
  - focused node/selected file/default inbox 기준 target directory 결정
- `getNodeTargetDir(node, fallback)`
  - drag/drop 대상 directory 결정
- `isReadOnlyMutationTarget(path)`
  - Clean Room 직접 mutation guard
- `formatFileActionError(error, fallback)`
  - unknown error message 추출

API 호출이 포함된 저장/업로드/폴더 생성 함수는 route 상태와 store 함수 의존성이 많으므로 1차에서는 route에 남길 수 있다. 대신 입력 검증과 target 계산을 helper로 빼서 테스트한다.

## Explorer Actions 설계

`workspaceExplorerActions.ts`는 다음 판단 helper를 제공한다.

- `buildFocusedSearchNode(item)`
  - search result를 explorer node shape으로 변환
- `shouldConfirmDiscardUnsaved(nextPath, selectedPath, hasUnsavedChanges)`
  - 파일 전환 confirm 필요 여부 판단
- `isDirectorySearchResult(item)`
  - directory result 처리 분기

## ProjectWorkspace에 남기는 책임

- route params 검증과 navigation
- Svelte store 값 읽기와 top-level 상태 보유
- child component props/callback 연결
- 실제 API/store function 호출 순서 조립
- window event listener와 timer 등록/해제

## 검증

- `cd src/frontend; npm test`
- `cd src/frontend; npm run build`
- `git diff --check`

필요하면 backend에 영향이 없음을 확인하기 위해 backend test는 생략할 수 있지만, 커밋 전 전체 검증 단계에서는 기존 정책대로 가능한 검증 범위를 보고한다.
