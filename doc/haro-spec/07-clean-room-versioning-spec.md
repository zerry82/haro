# Clean Room 버전 관리 스펙

## 1. 목적

haro는 전체 팀원이 함께 쓰는 업무 공간이다.
따라서 팀 공식 기준인 Clean Room은 실수로 깨지면 안 되고, 서비스 업데이트로 폴더나 메타 구조가 바뀔 때도 안전하게 복구할 수 있어야 한다.

Clean Room 버전 관리는 다음을 목표로 한다.

- 실수로 인한 공식 자료 훼손 방지
- 변경 이력 추적
- 이전 버전 복원
- 승격 요청 검토
- 서비스 업데이트 마이그레이션 전후 checkpoint
- 마이그레이션 실패 시 rollback

GitHub는 사용하지 않는다.
Git은 haro 내부 안전망으로만 사용하고, 작업공간의 `.haro/git/` 아래에 둔다.

## 2. Data Clean Room과 Meta Clean Room

Clean Room은 하나의 제품 개념이지만 내부 Git은 두 개로 나눈다.

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
```

| 구분 | 역할 | 내부 Git |
| --- | --- | --- |
| Data Clean Room | 공식 원본, 산출물, 템플릿 | `.haro/git/data-clean-room.git` |
| Meta Clean Room | 공식 규칙, 스킬, workflow, validator, schema, trigger, hook, 정책 | `.haro/git/meta-clean-room.git` |

분리 이유:

- 데이터 파일은 Excel, PDF, 이미지 같은 큰 파일이 많다.
- 메타 파일은 JSON, Markdown, schema, validator처럼 diff가 중요한 텍스트가 많다.
- 데이터 마이그레이션과 스킬/규칙 마이그레이션의 위험이 다르다.
- 스킬 변경 테스트가 실패해도 공식 데이터 이력과 섞이지 않아야 한다.

## 3. .haro 버전 관리 구조

```text
.haro/
  git/
    data-clean-room.git
    meta-clean-room.git
  datasources/
  db/
    workspace.db
  file_summaries/
  playground-index.json
  audit-log.jsonl
  promotions/
  migrations/
```

관리 기준:

- `clean-room/data`는 `data-clean-room.git`의 work-tree다.
- `clean-room/meta`는 `meta-clean-room.git`의 work-tree다.
- `playground/users/{user_id}`는 Git 관리 대상이 아니다.
- Playground 작업은 시작 시점의 Data/Meta Clean Room commit만 참조 메타데이터로 기록한다.
- 외부 데이터소스 연결과 가져오기 기록은 `.haro/datasources`에 저장하고, Clean Room Git과 분리한다.
- 사용자는 Git 용어를 보지 않고, haro UI에서는 저장 지점, 변경 내용, 복원, 반영 요청으로 표현한다.

## 4. 큰 파일 정책

큰 파일은 Git에 넣되 내용 diff를 하지 않는다.
버전 기록과 복원만 제공한다.

권장 `.gitattributes`:

```gitattributes
*.xlsx binary
*.xls binary
*.pdf binary
*.docx binary
*.pptx binary
*.png binary
*.jpg binary
*.jpeg binary
*.mp4 binary
*.zip binary
```

| 파일 유형 | 정책 |
| --- | --- |
| `.md`, `.csv`, `.json`, `.html`, `.txt`, `.ts`, `.js` | diff와 복원 제공 |
| `.xlsx`, `.pdf`, `.docx`, `.pptx` | version-only, diff 없음 |
| 이미지, 영상, zip | version-only, diff 없음 |
| Excel에서 변환한 CSV | diff와 복원 제공 |

초대용량 파일이 많아지면 `.haro/objects` 기반 object store 분리를 검토한다.

## 5. 승격 요청 모델

Playground는 자유 실험 공간이고 Clean Room은 공식 기준 공간이다.
따라서 Playground 결과를 Clean Room에 직접 쓰지 않고 승격 요청을 만든다.

### Data 승격

```text
playground 산출물/원본/템플릿
  -> data-clean-room feature branch 생성
  -> clean-room/data에 변경 적용
  -> 파일 무결성, 참조 관계, 보호 상태 검증
  -> 승인
  -> data-clean-room main에 merge
```

대상:

- 공식 원본 자료
- 공식 보고서
- 공식 대시보드
- 공유 패키지
- 업무 템플릿

### Meta 승격

```text
playground 스킬/규칙/workflow/validator
  -> meta-clean-room feature branch 생성
  -> clean-room/meta에 변경 적용
  -> validator와 케이스 테스트 실행
  -> 승인
  -> meta-clean-room main에 merge
```

대상:

- 업무규칙
- 스킬
- workflow
- input/output schema
- validator
- trigger
- hook
- 정책

스킬 수정은 반드시 Meta 승격 요청으로 처리한다.
테스트가 실패한 스킬은 active 상태로 반영하지 않는다.

## 6. 마이그레이션 checkpoint

서비스 업데이트로 하네스 구조나 `.haro` 메타데이터가 바뀔 수 있다.
마이그레이션 전에는 반드시 checkpoint를 만든다.

```text
1. Data Clean Room checkpoint commit
2. Meta Clean Room checkpoint commit
3. migration 실행
4. 검증
5. 성공 commit
6. 실패 시 checkpoint로 rollback
```

검증 예:

- 필수 폴더 존재
- `.haro/db/workspace.db` schema와 검색 인덱스 유효성
- Data/Meta Clean Room Git status 정상
- active skill registry 유효성
- 승격 요청 목록 유효성

## 6.1 Fork snapshot

프로젝트 fork는 source project의 `meta-clean-room` 특정 commit을 기준으로 한다.
fork snapshot은 프로젝트 전체 복제가 아니라 Meta Clean Room 템플릿 생성이다.

template manifest에는 다음을 기록한다.

- `source_project_id`
- `source_meta_commit`
- 생성자
- 생성 시각
- vertical family
- 포함된 스킬과 active version pointer
- 포함된 업무규칙
- 포함된 schema, validator, trigger, hook, policy
- 제외된 data/playground 경로
- 제외된 외부 데이터소스 인증 정보와 실제 원본 file id

fork된 새 프로젝트는 자기만의 `data-clean-room.git`과 `meta-clean-room.git`을 새로 가진다.
source project와 fork project의 meta는 fork 이후 독립적으로 진화한다.
source project의 변경을 자동으로 따라가지 않는다.

Data Clean Room의 실제 원본과 산출물, User Playground, 채팅 원문은 fork snapshot에 포함하지 않는다.
Google Drive 같은 외부 데이터소스의 OAuth token, 실제 file id, 가져온 snapshot도 fork snapshot에 포함하지 않는다.

## 7. 사용자 표현

Git은 내부 구현이다.
사용자에게는 다음 표현을 사용한다.

| 내부 Git | haro 표현 |
| --- | --- |
| commit | 저장 지점 |
| diff | 변경 내용 |
| branch | 검토 공간 |
| merge | Clean Room 반영 |
| revert/restore | 이전 버전 복원 |
| conflict | 반영 충돌 |
| checkpoint | 복구 지점 |

## 8. 성공 기준

- Clean Room 변경 전후 이력이 남는다.
- 공식 데이터와 공식 메타 변경 이력이 분리된다.
- Playground 작업은 Git에 직접 들어가지 않는다.
- 큰 파일은 diff 없이 버전과 복원만 제공한다.
- 스킬 수정은 Meta Clean Room 테스트를 통과해야 반영된다.
- 마이그레이션 실패 시 checkpoint로 복구할 수 있다.
- 외부 데이터소스에서 가져온 파일은 Clean Room 승격 전까지 공식 Git 이력에 들어가지 않는다.
