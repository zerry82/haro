# 1번째 개발 주기: Haro Harness Bootstrap MVP

## 목표

새 프로젝트가 haro의 기본 업무 공간 구조로 시작하게 만든다.
사용자는 개인 Playground에서 자유롭게 파일을 만들고 업로드하되, 팀 공식 기준인 Clean Room은 실수로 직접 수정하지 못해야 한다.

## 구현 범위

- 프로젝트 생성 시 하네스 폴더를 자동 생성한다.
- 기존 프로젝트는 파일 트리를 처음 열 때 하네스 폴더를 비파괴적으로 보강한다.
- `.haro` 내부 메타데이터는 사용자 파일 API에서 접근하지 못하게 한다.
- `clean-room/**`은 읽기 전용으로 두고, 폴더 생성/업로드/파일 저장을 막는다.
- 새 폴더/업로드의 기본 대상은 사용자 Playground inbox로 둔다.
- 파일 트리에서 Clean Room과 내 Playground를 시각적으로 구분한다.

## 생성되는 기본 구조

```text
clean-room/
  data/
    00_inbox/
    10_sources/
    30_outputs/
    templates/
  meta/
    40_rules/
    45_skills/
    schemas/
    validators/
    triggers/
    hooks/
    policies/
    50_chats/
playground/
  users/
    {user_id}/
      00_inbox/
      20_working/
      30_outputs/
      40_rules/
      45_skills/
      50_chats/
90_archive/
.haro/
  git/
    data-clean-room.git
    meta-clean-room.git
  file_summaries/
  context/
    self/
    contacts/
    source-refs/
```

## API 동작

- `GET /api/projects/{project_id}/files?path=/clean-room/...`은 허용한다.
- `GET /api/projects/{project_id}/files/content?path=/clean-room/...`은 허용한다.
- `POST /files/directories`, `POST /files/upload`, `PUT /files/content`가 `/clean-room/**`을 대상으로 하면 `403`을 반환한다.
- 모든 파일 API에서 `/.haro/**`와 `/.openclaw/**` 접근은 `403`을 반환한다.

## 제외 항목

- Clean Room 승격 요청
- Project Fork / Meta Template Engine
- Google Drive, Gmail 데이터소스
- 스킬 제작 워크벤치
- 팀/조직 권한 모델
- Clean Room Git feature branch, merge, rollback UI

## 검증 체크리스트

- [x] 새 프로젝트 생성 후 하네스 폴더 구조가 생성된다.
- [x] 기존 프로젝트에서 파일 트리를 열면 하네스 폴더가 추가되고 기존 루트 파일은 이동하지 않는다.
- [ ] `/.haro` 목록/읽기/쓰기 요청은 `403`이다.
- [ ] `/clean-room/data/10_sources` 업로드와 폴더 생성은 `403`이다.
- [ ] `/playground/users/{user_id}/00_inbox` 업로드와 폴더 생성은 성공한다.
- [x] Git 사용 가능 환경에서 `.haro/git/data-clean-room.git`, `.haro/git/meta-clean-room.git`가 생성된다.
- [ ] Clean Room 파일은 읽을 수 있지만 에디터 저장 버튼이 비활성화된다.
- [x] `npm run build`를 통과한다.
- [x] `python -m py_compile app/routers/projects.py app/routers/files.py app/services/workspace_index.py app/services/harness.py`를 통과한다.

## 검증 기록

- `python -m py_compile app/routers/projects.py app/routers/files.py app/services/workspace_index.py app/services/harness.py` 통과.
- `npm run build` 통과.
- 임시 워크스페이스에서 하네스 폴더와 두 Clean Room bare Git repo의 `main` 초기 commit 생성을 확인.
- 현재 shell Python에는 `jwt` 패키지가 없어 라우터 직접 import 방식의 보호 로직 수동 스크립트는 실행하지 못했다. API 수동 검증은 백엔드 실행 환경에서 이어서 확인한다.

## 후속 주기 후보

다음 주기는 Playground 산출물을 Clean Room으로 올리는 `승격 요청`을 다루는 것이 자연스럽다.
이때 내부 Git feature branch와 checkpoint/rollback 정책을 함께 묶는다.
