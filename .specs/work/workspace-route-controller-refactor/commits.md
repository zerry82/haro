# Workspace Route Controller Refactor Commits

작성일: 2026-05-07

## 연결된 커밋

아직 없음.

## 브랜치

- 현재 브랜치: `main`

## PR

아직 없음.

## 문서 동기화

- `spec.md`: 문제, 목표, 범위, 성공 기준 정의
- `design.md`: file refresh, file action, explorer action 분리 설계 정의
- `plan.md`: workspace route 리팩토링 단계, 검증 명령, 중단 조건 정의
- `implementation.md`: 구현 결과, 검증 결과, 남은 위험 기록
- `commits.md`: 연결 커밋은 구현 후 갱신 예정

## 현재 검증

- `cd src/frontend; npm test`: 통과
- `cd src/frontend; npm run build`: 통과

## 커밋 전 보고 후보

- 변경 요약:
  - workspace route의 file refresh, file action, explorer interaction 판단 로직을 `src/frontend/src/lib` helper로 분리
  - helper별 Vitest 추가
  - `ProjectWorkspace.svelte`는 상태 보유와 API/store orchestration 중심으로 정리
- 문서 동기화:
  - `.specs/work/workspace-route-controller-refactor/implementation.md`에 구현/검증/위험 기록
  - `.specs/work/workspace-route-controller-refactor/commits.md`에 커밋 전 보고 후보 기록
- 아쉬움과 위험:
  - `ProjectWorkspace.svelte`는 아직 1000줄 이상이며 chat/deploy/viewer workflow가 남아 있음
  - 브라우저 drag/drop과 SSE timer 흐름은 수동 UI 검증 여지가 있음
