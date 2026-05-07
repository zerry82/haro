# Workspace Route Controller Refactor Spec

작성일: 2026-05-07

## 문제

`src/frontend/src/routes/ProjectWorkspace.svelte`는 이전 리팩토링으로 표시 컴포넌트와 순수 유틸을 많이 분리했지만, 아직 route component 안에 여러 workflow controller가 남아 있다.

특히 다음 책임이 한 파일에 함께 있다.

- 파일 저장, 되돌리기, 재로드, 외부 변경 감지
- 폴더 생성, 파일 업로드, drag/drop 처리
- 파일 변경 SSE 이벤트를 받아 directory dirty marking, debounce refresh, 현재 선택 파일 reload 판단
- 파일 검색 결과 선택, 파일/폴더 node 선택, load more 처리
- 채팅 선택/생성/삭제/전송/요약
- 프로젝트 상태 로딩, deploy toggle, preview URL 결정
- viewer/editor tab 상태와 preview refresh

라인 수 자체가 hard limit는 아니지만, 이 파일은 UI route orchestration과 세부 workflow 상태 전이가 함께 있어 SRP 점검 신호가 계속 남아 있다.

## 목표

- `ProjectWorkspace.svelte`를 route composition root에 가깝게 축소한다.
- 파일 작업 workflow와 file refresh queue를 우선 분리한다.
- 분리한 workflow의 순수 판단 로직은 Vitest로 검증한다.
- 화면 동작, API 경로, store 계약, SSE 이벤트명은 유지한다.
- 이후 chat/deploy/editor workflow 분리를 이어갈 수 있는 구조를 만든다.

## 비목표

- UI 레이아웃이나 시각 디자인을 바꾸지 않는다.
- backend API, SSE payload, store public API를 바꾸지 않는다.
- `ProjectWorkspace.svelte`를 이번 패치에서 반드시 300줄 이하로 만들지는 않는다.
- Svelte store 전체 구조를 새 상태관리 패턴으로 갈아엎지 않는다.

## 우선 범위

1. 파일 refresh queue 분리
   - `file-changed` event detail normalize
   - affected directory 계산
   - selected file reload 여부 판단
   - unsaved change가 있을 때 external changed flag 판단
   - debounce queue 자료구조와 flush orchestration

2. 파일 mutation workflow 분리
   - 저장/되돌리기/재로드
   - 폴더 생성 시작/취소/제출
   - 업로드 target 계산과 overwrite retry 흐름
   - drag/drop target 결정

3. 파일 탐색 interaction 분리
   - explorer target dir 계산
   - node click, search result click, load more directory
   - readonly path guard 메시지

## 후순위 후보

- chat workflow controller
  - select/new/delete/send/summarize
- project runtime controller
  - project load, deploy toggle, preview URL
- viewer/editor controller
  - active tab, editor base/draft sync, markdown/html/csv preview trigger

후순위 후보는 이번 패치 중 너무 넓어지면 별도 스펙 또는 같은 스펙의 2차 구현으로 남긴다.

## 성공 기준

- `ProjectWorkspace.svelte`에서 파일 작업과 file refresh 관련 함수 수가 유의미하게 줄어든다.
- 새 helper/controller는 하나의 명확한 책임을 갖는다.
- 파일 refresh 판단 로직과 파일 action helper는 Vitest로 검증한다.
- `cd src/frontend; npm test`가 통과한다.
- `cd src/frontend; npm run build`가 통과한다.
- `git diff --check`가 통과한다.

## 전략 검증 루프

질문: 이 전략에 100% 확신이 있나요?

초기 답: 아직 아니다. 가능한 허점은 다음과 같다.

- 허점: Svelte `$state` 값을 외부 controller로 직접 옮기면 reactivity가 깨질 수 있다.
  - 수정: 첫 단계는 순수 판단 함수와 얇은 action helper 위주로 분리한다. `$state` 자체는 route에 남기고, callback/context 객체로 필요한 값만 전달한다.
- 허점: 파일 refresh queue는 timer와 store update가 섞여 있어 테스트가 어려울 수 있다.
  - 수정: affected path 계산, reload decision, queue merge 같은 순수 로직을 먼저 분리하고 테스트한다. timer orchestration은 작은 wrapper로 둔다.
- 허점: 파일 mutation workflow를 크게 이동하면 props/store 호출 순서가 바뀔 수 있다.
  - 수정: 기존 함수별 동작 순서를 유지하고, 한 workflow씩 이동한 뒤 Vitest/build를 반복한다.
- 허점: `ProjectWorkspace.svelte`를 줄이는 목표에 치우쳐 조립 책임까지 과도하게 숨길 수 있다.
  - 수정: route는 params, store subscription, top-level UI 조립을 유지한다. 숨길 대상은 도메인 판단과 반복 workflow뿐이다.

수정 후 전략: Svelte route state는 보존하고, 파일 refresh와 mutation 판단 로직을 순수 helper/controller로 분리한다. 동작 변경 없이 테스트 가능한 경계를 우선 만든다.

사실상 확신 수준: 높음. 남은 위험은 event/timer orchestration 회귀이며, 순수 helper 테스트와 production build로 대부분 검출 가능하다.
