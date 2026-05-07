# haro 개발 주기 작업 목록

이 폴더는 haro 스펙을 실제 구현 주기로 쪼개어 관리한다.
각 작업 문서는 목표, 구현 범위, 검증 방법, 남은 리스크를 함께 기록한다.

## 작업 주기

| 주기 | 문서 | 상태 | 핵심 목표 |
| --- | --- | --- | --- |
| 1 | [01-harness-bootstrap.md](./01-harness-bootstrap.md) | 구현 완료 / 수동 검증 대기 | 새 프로젝트가 haro 하네스 구조로 시작하고 Clean Room을 직접 수정하지 못하게 한다. |
| 2 | [02-workspace-file-db.md](./02-workspace-file-db.md) | 구현 완료 / 부하·수동 검증 대기 | 파일 3,000개 이상에서도 파일명/요약 검색과 파일 변경 DB 동기화가 안정적으로 동작하게 한다. |
| 3 | [03-debug-mode.md](./03-debug-mode.md) | 스펙 작성 완료 / 구현 대기 | 채팅 턴별 LLM 요청·응답·도구 실행 trace를 디버그 모드에서 확인하게 한다. |

## 검증 원칙

- 각 주기는 `npm run build`와 주요 백엔드 파일 `py_compile`을 통과해야 한다.
- 문서 스펙과 실제 동작이 다르면 task 문서에 차이를 남긴다.
- Google Drive, Gmail, 스킬 제작, Project Fork처럼 큰 기능은 별도 주기로 분리한다.
