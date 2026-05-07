# Bulky File Refactor Spec

작성일: 2026-05-07

## 문제

테스트 기반은 생겼지만 일부 파일은 여전히 여러 책임을 한 파일에 담고 있다.

- `src/frontend/src/routes/ProjectWorkspace.svelte`: 워크스페이스 상태, 파일 탐색기, 채팅, 렌더링, 리사이즈, 디버그 흐름이 섞여 있다.
- `src/backend/app/services/intent_turns.py`: intent 상태 관리, gate fallback, rule routing, LLM routing, 텍스트 판별 helper가 섞여 있다.
- `src/backend/app/services/workspace_file_db.py`: workspace DB facade 역할과 query/sync/io 세부 구현이 아직 함께 있다.
- `src/backend/app/services/chat_workspace.py`, `container_manager.py`, `app/main.py`, `routers/files.py`: path/io/reference/summary, Docker lifecycle/execution/deploy, startup/migration/seed, file API 모델/정책/변환이 각각 섞여 있다.
- `src/frontend/src/components/WorkspaceSidePanel.svelte`, `src/frontend/src/stores/files.ts`: side panel UI 세부와 파일 tree/API store helper가 섞여 있다.

## 목표

- 공개 API와 화면 동작을 유지하면서 큰 파일의 책임을 작은 모듈/컴포넌트로 분리한다.
- 기존 import 경로는 가능한 유지해 변경 파급을 줄인다.
- 백엔드 변경은 단위 테스트 또는 compile 검증으로 확인한다.
- 프론트엔드 변경은 Vitest와 production build로 확인한다.

## 비목표

- 라우팅 정책, 도구 선택 정책, SSE 이벤트명, DB schema를 바꾸지 않는다.
- UI 레이아웃을 새로 디자인하지 않는다.
- 모든 300줄 초과 파일을 이번 패치에서 반드시 300줄 이하로 만들지는 않는다.

## 우선 범위

1. `ProjectWorkspace.svelte`
   - 상단 바를 `WorkspaceTopBar.svelte`로 분리한다.
   - 채팅 패널을 `WorkspaceChatPanel.svelte`로 분리한다.
   - 가능하면 파일 탐색기 패널도 별도 컴포넌트로 분리한다.

2. `intent_turns.py`
   - dataclass와 constants를 별도 모델 모듈로 분리한다.
   - 텍스트 판별/JSON parse helper를 rule helper 모듈로 분리한다.
   - LLM/rule 라우팅을 별도 라우터 모듈로 분리한다.

3. `workspace_file_db.py`
   - connection/lock/atomic write helper를 분리한다.
   - query 함수와 sync/lifecycle 함수를 나눈다.
   - 기존 `workspace_file_db.py`는 facade import 중심으로 유지한다.

4. 추가 백엔드 facade 후보
   - `routers/files.py`: 모델, 경로 정책, 변환 helper를 분리한다.
   - `chat_workspace.py`: 경로, 파일 IO, 템플릿, 로그, 참조, 요약 책임을 분리한다.
   - `container_manager.py`: Docker gateway, DB query, lifecycle, execution, deploy, maintenance 책임을 분리한다.
   - `main.py`: app factory, lifespan, migration, seed, container background task를 분리한다.

5. 추가 프론트엔드 후보
   - `WorkspaceSidePanel.svelte`: activity rail, file explorer, catalog를 분리한다.
   - `stores/files.ts`: DTO 타입과 tree/path helper를 분리한다.
   - `ProjectWorkspace.svelte`: debug/viewer/panel resize/tree virtualization 순수 로직을 lib로 분리한다.

## 성공 기준

- `ProjectWorkspace.svelte`, `intent_turns.py`, `workspace_file_db.py`의 라인 수가 유의미하게 줄어든다.
- 새로 식별한 backend facade 후보가 public import 경로를 유지한 채 작은 모듈로 나뉜다.
- 백엔드 `pytest`가 통과한다.
- 프론트엔드 `npm test`, `npm run build`가 통과한다.
- `git diff --check`가 통과한다.

## 전략 검증 루프

질문: 이 전략에 100% 확신이 있나요?

초기 답: 아직 아니다. 가능한 허점은 다음과 같다.

- 허점: `ProjectWorkspace.svelte`의 상태가 많아 컴포넌트 분리 중 Svelte props 계약을 실수할 수 있다.
  - 수정: 순수 표시 컴포넌트에 가까운 top bar와 chat panel부터 분리하고, 양방향 상태는 callback으로 제한한다.
- 허점: `workspace_file_db.py`를 여러 파일로 나누면 circular import가 생길 수 있다.
  - 수정: `connection -> lifecycle/query -> db facade` 방향으로 의존성을 고정한다.
- 허점: `intent_turns.py` 라우팅 분리 중 기존 fallback 정책이 바뀔 수 있다.
  - 수정: 조건문 내용은 이동만 하고, 새 helper 테스트를 추가해 핵심 signal 판별을 고정한다.
- 허점: 너무 큰 범위를 한 번에 건드리면 회귀 원인을 찾기 어렵다.
  - 수정: UI 표시 컴포넌트, intent helper, workspace DB facade처럼 책임 경계를 나누고 각 단계마다 빌드/테스트를 확인한다.

수정 후 전략: 기존 계약을 보존하면서 facade와 표시 컴포넌트 중심으로 분리한다. 정책 변경은 하지 않는다.

사실상 확신 수준: 높음. 남은 위험은 Svelte props 실수와 import 경로 실수이며, 테스트와 빌드로 검출 가능하다.
