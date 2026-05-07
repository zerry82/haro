# Workspace Route Controller Refactor Implementation

작성일: 2026-05-07

## 현재 상태

구현, 검증, 커밋 기록을 완료했다. 스펙은 `.specs/done/` 아래에 있다.

## 예정 변경 파일

- `src/frontend/src/routes/ProjectWorkspace.svelte`
- `src/frontend/src/lib/workspaceFileRefresh.ts`
- `src/frontend/src/lib/workspaceFileRefresh.test.ts`
- `src/frontend/src/lib/workspaceFileActions.ts`
- `src/frontend/src/lib/workspaceFileActions.test.ts`
- `src/frontend/src/lib/workspaceExplorerActions.ts`
- `src/frontend/src/lib/workspaceExplorerActions.test.ts`

## 구현 기록

- 2026-05-07: 구현 전 단계별 계획을 `plan.md`로 추가했다.
- 2026-05-07: file refresh 판단 로직을 `workspaceFileRefresh.ts`로 분리했다.
  - `file-changed` detail normalize
  - refresh affected directory 계산
  - selected file reload/external changed decision
  - refresh queue merge
- 2026-05-07: file action 판단 로직을 `workspaceFileActions.ts`로 분리했다.
  - 폴더명 검증
  - explorer/drop target directory 계산
  - readonly mutation target guard
  - drag/drop file type 판단
  - unknown error formatting
- 2026-05-07: explorer interaction 판단 로직을 `workspaceExplorerActions.ts`로 분리했다.
  - search result focused node 변환
  - directory search result 판별
  - unsaved changes confirm 필요 여부 판단
- 2026-05-07: `ProjectWorkspace.svelte`를 새 helper에 연결했다.
  - Svelte `$state`, timer lifecycle, API/store 호출 orchestration은 route에 남겼다.
  - UI props, API 경로, SSE 이벤트명, store public API는 변경하지 않았다.
- 2026-05-07: 각 helper별 Vitest를 추가했다.

## 검증 기록

- 2026-05-07: `cd src/frontend; npm test`
  - 결과: 통과
  - 테스트 파일: 10개 통과
  - 테스트 케이스: 37개 통과
- 2026-05-07: `cd src/frontend; npm run build`
  - 결과: 통과
  - Vite production build 완료

## 남은 작업

- 없음. 후속 개선은 별도 스펙으로 다룬다.

## 남은 위험

- `ProjectWorkspace.svelte`는 여전히 route composition, chat, deploy, viewer/editor orchestration을 함께 가진 큰 파일이다.
- 이번 변경은 파일 refresh/action/explorer interaction의 순수 판단 로직을 분리한 1차 리팩토링이며, chat/deploy/viewer workflow는 후속 스펙 후보로 남는다.
- SSE/timer 흐름은 production build와 helper 테스트로 기본 검증했지만, 실제 브라우저 상호작용 검증은 별도 수동 확인이 필요하다.
