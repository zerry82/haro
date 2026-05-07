# .specs

중요한 패치 단위의 스펙과 구현 기록을 보관하는 폴더다.

## 구조

```text
.specs/draft/{spec}/
  spec.md
  design.md
  implementation.md
  commits.md

.specs/work/{spec}/
  spec.md
  design.md
  implementation.md
  commits.md

.specs/done/{spec}/
  spec.md
  design.md
  implementation.md
  commits.md
```

`{spec}`은 짧고 의미 있는 kebab-case 이름을 사용한다.

스펙 생명주기는 다음을 따른다.

- `.specs/draft/{spec}/`: 아이디어, 문제 정의, 설계 초안이 있고 아직 구현을 시작하지 않은 스펙
- `.specs/work/{spec}/`: 현재 구현 중이거나 검증/문서 동기화가 진행 중인 스펙
- `.specs/done/{spec}/`: 구현, 검증, 문서 동기화, 연결 커밋 기록까지 끝난 스펙

구현을 시작할 때는 `draft`에서 `work`로 옮기고, 완료되면 `work`에서 `done`으로 옮긴다.

## 문서 역할

- `spec.md`: 문제, 목표, 비목표, 사용자 흐름, 성공 기준
- `design.md`: 아키텍처, 데이터 모델, API/SSE 계약, UI 영향, 대안과 결정 이유
- `implementation.md`: 구현 결과, 변경 파일, 검증 결과, 남은 작업
- `commits.md`: 연결된 커밋 해시, 브랜치, PR, 배포/릴리즈 기록

## 사용 기준

단순 수정이 아니라 데이터 모델, API, SSE, 에이전트 도구, 워크스페이스 정책, 프론트엔드/백엔드 연동, 인증/권한, Docker 샌드박스처럼 제품 또는 아키텍처에 의미 있는 영향을 주는 작업은 스펙을 먼저 만든다.
