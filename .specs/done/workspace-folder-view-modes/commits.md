# Workspace Folder View Modes Commits

작성일: 2026-05-07

## 연결된 커밋

- `09a1ab3` refactor workspace folder views
- `7e5c031` Handle malformed tool call JSON

## 브랜치

- 현재 브랜치: `main`

## PR

없음. 사용자 요청에 따라 원격 브랜치로 직접 푸쉬된 이력이다.

## 문서 동기화

- `spec.md`: 문제, 목표, 비목표, 핵심 전제, 사용자 흐름, 초기화 정책, 성공 기준, 전략 검증 루프 정의
- `design.md`: system physical structure 원칙, project-root workspace root, filtered alias view, backend hidden policy, frontend 사용자/개발자 모드, 초기화 정책 정의
- `plan.md`: alias mapping 확정, GitHub checkpoint, 안전 초기화, workspace root 이동, hidden query, filtered alias view model, 검증 명령, 중단 조건 정의
- `tasks.md`: 구현 체크리스트, instruction 파일 작업, baseline/final 검증 결과 기록
- `implementation.md`: 구현 결과, duplicate row key 버그 수정, instruction 파일과 채팅 경로 표시, `내 폴더/AGENTS.md`와 개발자 모드 raw tree 노출, 기본 저장 위치 변경, 검증 결과, 남은 위험 기록
- `commits.md`: 연결 커밋과 브랜치/PR 상태를 기록했다.

## 현재 검증

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 64 passed, 1 skipped
- `cd src/frontend; npm test -- --run` → 47 passed
- `cd src/frontend; npm run build` → passed
- `git diff --check` → passed

적용 확인과 연결 커밋 기록을 마쳤다.
