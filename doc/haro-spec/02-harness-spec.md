# 강력한 하네스 기능 스펙

## 1. 하네스 정의

haro의 하네스는 비개발자가 업무 파일을 올리고, AI가 이를 안전하게 이해하고 실행할 수 있도록 만드는 작업틀이다.

haro는 개인 도구가 아니라 전체 팀원이 함께 쓰는 업무 공간이다.
따라서 하네스는 팀 기준을 보호하는 공간과 개인이 자유롭게 실험하는 공간을 분리해야 한다.

하네스는 다음 기능을 제공한다.

- 정리: 파일과 폴더를 업무 단위로 배치한다.
- 해석: 파일이 어떤 업무 자료인지 파악한다.
- 추적: 원본, 변환본, 산출물, 실행 로그를 연결한다.
- 기록: 채팅세션, 결정, 피드백, 규칙 후보를 파일로 남긴다.
- 맥락: 사용자와 주요 커뮤니케이션 대상의 관찰 가능한 업무 선호를 숨은 맥락으로 관리한다.
- 안내: 사용자가 다음에 무엇을 해야 하는지 보여준다.

## 2. 현재 구현 기반

이미 구현된 하네스 기초:

- 프로젝트별 워크스페이스
- 파일/폴더 트리
- 폴더 생성
- 파일 업로드
- 드래그앤드랍 업로드
- Excel 파일 시트별 CSV 변환
- Markdown/HTML/CSV/코드 미리보기
- 텍스트 파일 편집
- CSV 셀 편집
- 프로젝트별 채팅세션
- 작업모드/배포모드
- 에이전트 도구 호출과 파일 변경 이벤트

## 3. 목표 사용자 경험

사용자는 처음부터 폴더를 직접 설계하지 않는다.

권장 첫 경험:

```text
사용자: 매주 광고주 보고서 만드는 게 힘들어요.
haro: 그럼 이 프로젝트를 "주간 광고 성과 보고" 하네스로 구성해볼게요.
      매체 리포트 파일을 여기에 끌어다 놓으세요.
```

파일을 업로드하면 haro는 다음을 수행한다.

1. 파일을 inbox에 넣는다.
2. 파일 타입과 출처를 추정한다.
3. Excel이면 CSV로 펼친다.
4. 원본과 변환본을 연결한다.
5. 필요한 폴더를 제안한다.
6. 사용자에게 “이 기준으로 정리할까요?”를 묻는다.

## 4. 기본 폴더 모델

비개발자용 기본 하네스 폴더는 코드 프로젝트 구조가 아니라 업무 흐름 구조여야 한다.

하네스의 최상위 구조는 `clean-room`과 `playground`를 구분한다.

- `clean-room`: 팀의 공식 기준 공간
- `clean-room/data`: 공식 업무 데이터, 원본, 산출물, 템플릿
- `clean-room/meta`: 공식 규칙, 스킬, schema, validator, 정책
- `playground/users/{user_id}`: 사용자별 개인 실험 공간
- `90_archive`: 완료/이전 버전 보관
- `.haro`: 시스템 메타데이터

```text
/
  clean-room/
    data/
      00_inbox/
      10_sources/
        media-reports/
        reviews/
        cs/
        briefs/
      30_outputs/
        reports/
        dashboards/
        creative-briefs/
        share-pages/
      templates/
    meta/
      40_rules/
        data-rules/
        report-rules/
        message-rules/
        execution-rules/
      45_skills/
        active/
        review/
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
          normalized-data/
          drafts/
          analysis/
        30_outputs/
          drafts/
          previews/
        40_rules/
          candidates/
        45_skills/
          sandbox/
        50_chats/
  90_archive/
  .haro/
    git/
      data-clean-room.git
      meta-clean-room.git
    context/
      self/
      contacts/
      source-refs/
    datasources/
    file_index.json
    playground-index.json
    audit-log.jsonl
    promotions/
    migrations/
```

### 폴더 역할

| 폴더 | 역할 |
| --- | --- |
| `clean-room/` | 팀이 신뢰하는 공식 기준 공간 |
| `clean-room/data/` | 공식 업무 데이터와 산출물 |
| `clean-room/data/00_inbox/` | 팀 기준으로 편입하기 전 대기 파일 |
| `clean-room/data/10_sources/` | 승인된 원본 자료 보관 |
| `clean-room/data/30_outputs/` | 사용자나 광고주에게 보여줄 공식 산출물 |
| `clean-room/data/templates/` | 재사용 가능한 공식 업무 템플릿 |
| `clean-room/meta/` | haro가 데이터를 해석하고 실행할 기준 |
| `clean-room/meta/40_rules/` | 승인된 업무규칙 |
| `clean-room/meta/45_skills/` | 검토 중이거나 활성화된 팀 스킬 |
| `clean-room/meta/schemas/` | 공식 입력/출력 schema |
| `clean-room/meta/validators/` | 공식 검증 로직 |
| `clean-room/meta/triggers/` | 공식 trigger 정의 |
| `clean-room/meta/hooks/` | 공식 hook 정의 |
| `clean-room/meta/policies/` | 보호 상태, 승인, 실행 정책 |
| `clean-room/meta/50_chats/` | 팀 기준으로 보존할 채팅세션 요약과 결정 |
| `playground/users/{user_id}/` | 사용자별 개인 실험 공간 |
| `playground/users/{user_id}/00_inbox/` | 개인이 자유롭게 올린 파일 |
| `playground/users/{user_id}/20_working/` | 정규화 데이터, 분석 중간 결과, 초안 |
| `playground/users/{user_id}/30_outputs/` | 개인 초안, 미리보기, 임시 산출물 |
| `playground/users/{user_id}/40_rules/` | 개인 규칙 후보 |
| `playground/users/{user_id}/45_skills/` | 개인 스킬 제작 샌드박스 |
| `playground/users/{user_id}/50_chats/` | 개인 작업 채팅 기록 |
| `90_archive/` | 완료된 작업 묶음, 이전 버전 |
| `.haro/git/data-clean-room.git` | `clean-room/data` 전용 내부 Git |
| `.haro/git/meta-clean-room.git` | `clean-room/meta` 전용 내부 Git |
| `.haro/context/` | 사용자와 주요 커뮤니케이션 대상의 숨은 사람 맥락 |
| `.haro/datasources/` | 외부 데이터소스 연결과 가져오기 기록 |

## 4.1 Clean Room과 User Playground

### Clean Room

Clean Room은 팀의 공식 기준 공간이다.

여기에는 다음 자산을 둔다.

- Data Clean Room의 승인된 원본 자료
- Data Clean Room의 승인된 산출물
- Data Clean Room의 공식 템플릿
- Meta Clean Room의 팀 규칙
- Meta Clean Room의 활성화된 스킬
- Meta Clean Room의 schema, validator, trigger, hook, 정책
- 고객/프로젝트 기준 문서
- 팀 기준으로 남겨야 하는 채팅 기록

Clean Room에서는 파일을 마음대로 수정하지 않는다.
수정은 다음 흐름을 따른다.

```text
변경 제안 -> 검토 -> 승인 -> 새 버전 반영
```

Clean Room은 내부적으로 두 개의 Git 저장소로 관리한다.

```text
clean-room/data -> .haro/git/data-clean-room.git
clean-room/meta -> .haro/git/meta-clean-room.git
```

Git은 사용자에게 노출하지 않는다.
haro는 이를 저장 지점, 변경 내용 보기, 이전 버전 복원, 승격 요청, 마이그레이션 rollback을 위한 내부 안전망으로 사용한다.

### User Playground

Playground는 사용자별로 제공되는 개인 실험 공간이다.

각 팀원은 자기 playground에서 다음을 자유롭게 할 수 있다.

- 파일 업로드
- CSV 변환과 정규화 실험
- 보고서 초안 생성
- 스킬 후보 테스트
- 실패해도 괜찮은 분석
- haro Agent에게 적극적인 파일 작업 요청

다른 팀원의 playground는 기본적으로 읽거나 수정할 수 없다.
공유가 필요하면 사용자가 명시적으로 공유하거나 Clean Room 승격 요청을 해야 한다.

### 승격 흐름

Playground의 결과가 팀 기준으로 쓸 만하면 Clean Room으로 승격한다.

```text
개인 playground 결과
  -> Clean Room 반영 요청
  -> 팀 리뷰
  -> 승인
  -> clean-room에 새 버전으로 반영
```

승격 대상:

- 정리된 원본 자료와 확정된 보고서: Data Clean Room
- 재사용할 업무규칙과 검증된 스킬: Meta Clean Room
- 팀과 공유할 채팅 기록 요약

### 공간별 정책

| 항목 | Clean Room | User Playground |
| --- | --- | --- |
| 소유 | 팀 | 사용자 개인 |
| 목적 | 공식 기준 보관 | 자유 실험 |
| 수정 | 승인 필요 | 자유 |
| 삭제 | 제한 | 사용자 본인 가능 |
| haro Agent | 승인 없이는 변경 불가 | 적극 작업 가능 |
| 기록 | audit 필수 | 실행 로그 중심 |
| 결과 반영 | 직접 반영 | 승격 요청 필요 |

## 4.2 Clean Room Git 관리 정책

Clean Room은 GitHub를 사용하지 않고 작업공간 안의 `.haro/git/`에 로컬 Git 저장소를 둔다.

```text
.haro/
  git/
    data-clean-room.git
    meta-clean-room.git
  datasources/
  file_index.json
  playground-index.json
  audit-log.jsonl
  promotions/
  migrations/
```

관리 기준:

- `clean-room/data`는 `.haro/git/data-clean-room.git`으로 관리한다.
- `clean-room/meta`는 `.haro/git/meta-clean-room.git`으로 관리한다.
- `playground/users/{user_id}`는 Git 관리 대상이 아니다.
- Playground 작업은 시작 시점의 Data/Meta Clean Room 기준 commit만 메타데이터로 기록한다.
- Clean Room 변경 전에는 checkpoint commit을 만든다.
- 서비스 업데이트 마이그레이션 전에도 checkpoint commit을 만들고, 실패하면 rollback한다.
- `.haro/audit-log.jsonl`에는 사용자 행동과 haro 자동 작업 요약을 남긴다.

큰 파일 정책:

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

텍스트 파일은 diff를 제공한다.
Excel, PDF, Office 문서, 이미지, 영상, zip은 버전과 복원만 제공하고 내용 diff는 제공하지 않는다.
초대용량 파일이 많아지면 `.haro/objects` 기반 별도 object store 분리를 검토한다.

상세 정책은 [07-clean-room-versioning-spec.md](./07-clean-room-versioning-spec.md)를 따른다.

## 4.3 채팅세션 폴더 모델

채팅세션도 하네스의 파일/폴더 자산으로 관리한다.

```text
playground/users/{user_id}/50_chats/
  2026-04-29-a-client-weekly-report/
    README.md
    conversation.md
    decisions.md
    rule-candidates.md
    linked-files.json
    artifacts.json
    agent-log.md
```

채팅 폴더는 다음 역할을 한다.

- `README.md`: 채팅 목적, 상태, 요약
- `conversation.md`: 주요 대화 기록
- `decisions.md`: 승인된 결정
- `rule-candidates.md`: 스킬 후보
- `linked-files.json`: 이 채팅에서 사용한 입력/변환/산출 파일
- `artifacts.json`: 생성된 보고서, 대시보드, 공유 페이지 목록
- `agent-log.md`: 주요 도구 실행 요약

상세 스펙은 [06-chat-session-file-spec.md](./06-chat-session-file-spec.md)를 따른다.

팀 기준으로 보존해야 하는 채팅세션은 요약과 결정만 `clean-room/meta/50_chats/`로 승격한다.
개인 playground의 전체 대화를 자동으로 팀 공간에 노출하지 않는다.

## 4.4 숨은 사람 맥락 저장소

사람 맥락은 Clean Room 공식 기준이 아니다.
사용자와 주요 커뮤니케이션 대상의 업무 선호를 답장 초안, 우선순위 판단, 누락 맥락 보강에만 쓰는 숨은 맥락이다.

```text
.haro/context/
  self/
    {user_id}.json
  contacts/
    {contact_hash}.json
  source-refs/
    {ref_id}.json
```

운영 원칙:

- 원문 전체를 저장하지 않고 요약과 근거 참조만 저장한다.
- 사람 맥락은 Project Fork, template package, Clean Room Git에 포함하지 않는다.
- 사용자는 사람 맥락을 열람, 수정, 삭제, 비활성화할 수 있어야 한다.
- 성격 단정, 심리 진단, 민감 신원 추정, 조작적 설득 전략은 금지한다.

상세 스펙은 [13-human-context-analysis-spec.md](./13-human-context-analysis-spec.md)를 따른다.

## 5. 파일 객체 메타데이터

하네스는 파일을 path만으로 보지 않는다. 각 파일은 다음 메타데이터를 가진다.

```json
{
  "path": "/clean-room/data/10_sources/media-reports/naver_weekly.csv",
  "room": "clean-room-data",
  "kind": "media_report",
  "source": "naver",
  "owner_scope": "team",
  "owner_user_id": null,
  "status": "classified",
  "protection": "approved",
  "origin_path": "/playground/users/zerry/00_inbox/report.xlsx",
  "derived_from": ["/playground/users/zerry/00_inbox/report.xlsx"],
  "related_outputs": ["/clean-room/data/30_outputs/reports/a-client-weekly.md"],
  "detected_columns": ["date", "campaign", "cost", "purchase_amount"],
  "confidence": 0.84,
  "notes": "네이버 검색광고 리포트로 추정"
}
```

v1에서는 DB 모델을 바로 크게 만들기보다 `.haro/file_index.json` 또는 SQLite 테이블 중 하나를 선택한다.

권장 시작점:

- DB 테이블: 검색/필터/상태 변경에 유리
- `.haro/file_index.json`: 빠른 구현과 이식성에 유리

POC 다음 단계에서는 `.haro/file_index.json`으로 시작하고, 검색/권한이 커지면 DB로 이동한다.

## 6. 파일 상태

파일은 다음 상태를 가진다.

| 상태 | 의미 |
| --- | --- |
| `new` | 막 업로드됨 |
| `classified` | 파일 종류와 출처를 추정함 |
| `needs_user_input` | 해석에 사용자 확인이 필요함 |
| `ready` | 작업 입력으로 사용 가능 |
| `processing` | 에이전트가 처리 중 |
| `derived` | 다른 파일에서 생성된 변환본 |
| `output` | 최종 산출물 |
| `archived` | 완료 또는 보관 |
| `error` | 처리 실패 |

## 6.1 보호 상태

팀원이 마음대로 건드려도 되는지 판단하기 위해 파일은 처리 상태와 별도로 보호 상태를 가진다.

| 보호 상태 | 의미 |
| --- | --- |
| `editable` | 소유자가 자유롭게 수정 가능 |
| `review` | 검토 중, 변경 이력 필요 |
| `approved` | 승인됨, 직접 수정 금지 |
| `locked` | 시스템 또는 관리자만 수정 |
| `archived` | 읽기 전용 |

기본 규칙:

- `playground/users/{user_id}`의 파일은 기본 `editable`
- `clean-room/data/10_sources`의 파일은 기본 `approved`
- `clean-room/data/30_outputs`의 공식 산출물은 승인 후 `approved`
- `clean-room/meta/40_rules`, `clean-room/meta/45_skills`는 검토/승인 흐름 필요
- `.haro`는 사용자가 직접 수정하지 않는다

## 7. 하네스 액션

### 7.1 정리 제안

사용자가 파일을 올리면 haro가 다음을 제안한다.

```text
report.xlsx는 Excel 파일이고 3개 시트가 있습니다.
시트 이름을 기준으로 CSV를 만들고, 아래처럼 정리해도 될까요?

- clean-room/data/10_sources/media-reports/naver.csv
- clean-room/data/10_sources/media-reports/meta.csv
- clean-room/data/10_sources/media-reports/kakao.csv
```

승인 전에는 사용자 playground에 정리안을 만들고, 사용자가 승인하면 Clean Room 반영 요청을 생성한다.

### 7.2 파일 묶음 생성

여러 파일을 하나의 업무 묶음으로 만든다.

예:

```text
주간 보고 입력 묶음
- naver_weekly.csv
- meta_weekly.csv
- kakao_weekly.csv
- previous_report.pdf
```

### 7.3 원본/변환본 연결

Excel 원본에서 생성된 CSV는 원본과 관계가 남아야 한다.

```text
report.xlsx
  -> report/Naver.csv
  -> report/Meta.csv
```

### 7.4 산출물 패키지

보고서 하나는 단일 파일이 아니라 패키지일 수 있다.

```text
clean-room/data/30_outputs/reports/a-client-weekly/
  report.md
  dashboard.html
  summary.csv
  share-comment.md
  sources.json
```

### 7.5 Clean Room 승격 요청

사용자가 playground에서 만든 결과를 팀 기준으로 쓰고 싶으면 승격 요청을 만든다.

```text
이 보고서를 Clean Room 공식 산출물로 올릴까요?

- 대상: playground/users/zerry/30_outputs/drafts/a-client-weekly.md
- 반영 위치: clean-room/data/30_outputs/reports/a-client-weekly/
- 변경 방식: 새 버전 생성
```

승격 요청은 다음 정보를 포함한다.

- 요청자
- 원본 playground 경로
- 목표 clean-room 경로
- 변경 요약
- 관련 입력 파일
- 관련 채팅세션
- 적용 규칙/스킬
- 승인자
- 승인 상태

### 7.6 Data/Meta 승격 사이클

Data 승격은 업무 데이터와 산출물을 공식 기준으로 올리는 흐름이다.

```text
playground 산출물/원본/템플릿
  -> data-clean-room feature branch 생성
  -> clean-room/data에 변경 적용
  -> 파일 무결성, 참조 관계, 보호 상태 검증
  -> 승인
  -> data-clean-room main에 merge
```

Meta 승격은 규칙, 스킬, workflow, validator를 공식 기준으로 올리는 흐름이다.

```text
playground 스킬/규칙/workflow/validator
  -> meta-clean-room feature branch 생성
  -> clean-room/meta에 변경 적용
  -> validator와 케이스 테스트 실행
  -> 승인
  -> meta-clean-room main에 merge
```

스킬 수정은 반드시 Meta 승격 요청으로 처리한다.
haro는 테스트가 실패한 Meta 변경을 활성 스킬로 반영하지 않는다.

### 7.7 Project Fork / Template Engine

성공한 프로젝트는 다른 프로젝트의 시작점이 될 수 있다.
이때 fork는 프로젝트 전체 복제가 아니라 Meta Clean Room 설정을 템플릿으로 저장하는 동작이다.

```text
성공 프로젝트
  -> Meta Template 생성
  -> 새 프로젝트 생성 시 template 적용
  -> 새 프로젝트의 Meta Clean Room 초기 상태로 사용
```

fork 포함 대상:

- `clean-room/meta/40_rules`
- `clean-room/meta/45_skills`
- `clean-room/meta/schemas`
- `clean-room/meta/validators`
- `clean-room/meta/triggers`
- `clean-room/meta/hooks`
- `clean-room/meta/policies`
- `.haro/skills` registry와 active version pointer
- 하네스 폴더 템플릿 정의

fork 제외 대상:

- `clean-room/data/10_sources`
- `clean-room/data/30_outputs`
- `playground/users/*`
- 채팅 원문과 개인 실험 산출물
- `.haro/context/` 사람 맥락
- 이메일 주소, 연락처 id, 관계 히스토리
- 고객/개인/계약/성과 데이터

선택적으로 `clean-room/data/templates`의 빈 양식과 익명화된 샘플, 사람 맥락 사용 정책 템플릿은 포함할 수 있다.
실제 사람 맥락은 포함하지 않는다.

사용자 경험:

```text
[템플릿으로 저장]
[기존 프로젝트 meta에서 시작]
```

새 프로젝트는 자기만의 Data/Meta Clean Room Git을 새로 가진다.
fork 후 source project와 fork project의 Meta Clean Room은 독립적으로 진화한다.

상세 정책은 [09-project-fork-template-spec.md](./09-project-fork-template-spec.md)를 따른다.

### 7.8 외부 데이터소스 가져오기와 업무 인박스

Google Drive 같은 외부 저장소는 haro 내부 파일시스템이 아니라 데이터소스로 연결한다.
v1에서는 양방향 동기화가 아니라 선택 파일을 snapshot으로 가져오는 방식을 사용한다.

```text
Google Drive
  -> 데이터소스 연결
  -> 선택 파일 가져오기
  -> playground/users/{user_id}/00_inbox
  -> 검토/정리
  -> Clean Room 승격 요청
```

기본 가져오기 위치:

```text
playground/users/{user_id}/00_inbox/google-drive/{connection_name}/
```

정책:

- Drive 원본은 외부 원천으로 남긴다.
- 가져온 파일은 사용자 Playground의 `editable` snapshot이다.
- Clean Room에는 직접 쓰지 않고 Data Clean Room 승격 요청을 거친다.
- 원본 Drive file id, URL, mime type, 수정 시각, checksum/etag, import 시각을 `.haro/datasources`에 기록한다.
- Project Fork에는 Drive token, 실제 file id, 실제 데이터가 포함되지 않는다.

상세 정책은 [10-google-drive-connector-spec.md](./10-google-drive-connector-spec.md)를 따른다.

Gmail 같은 이메일은 Drive와 다르게 thread/action 중심 데이터소스다.
메일은 노이즈가 많으므로 label 설정을 전제로 하지 않고, 제목/본문/thread 맥락을 LLM이 triage해 명확한 요청 메일만 업무 인박스에 올린다.

```text
Gmail thread
  -> thread grouping
  -> LLM triage
  -> clear_request만 집중
  -> 핵심 내용/액션/결과물/일정 구조화
  -> draft-reply.md 생성
  -> human_review
```

기본 저장 위치:

```text
playground/users/{user_id}/00_inbox/email/{connection_name}/{thread_slug}/
```

정책:

- Gmail label은 약한 힌트일 뿐 primary 분류 기준이 아니다.
- v1은 `clear_request` 메일 중심으로 처리한다.
- 최종 발송은 사람이 한다.
- Gmail token, thread id, message id, raw email, attachments는 Project Fork에 포함하지 않는다.

상세 정책은 [11-gmail-crm-inbox-spec.md](./11-gmail-crm-inbox-spec.md)를 따른다.

## 8. UI 스펙

### 왼쪽 폴더 패널

현재 파일 트리에 다음을 추가한다.

- Clean Room / 내 Playground 전환
- 검색 입력
- 상태 필터
- 업무 묶음 보기
- 추천 정리 버튼
- 파일 종류 badge

### 데이터소스 탭

왼쪽 `데이터소스` 탭은 외부 원천을 연결하고 haro로 가져오는 공간이다.

v1 Google Drive 항목:

- Drive 연결 목록
- 연결 상태와 마지막 새로고침 시각
- 폴더/파일 탐색
- 검색
- 선택 파일 가져오기
- 다시 가져오기
- 원본 Drive 링크 열기

v1 Gmail 항목:

- Gmail 연결 상태
- LLM triage 결과
- `clear_request` 업무 인박스
- thread 목록
- 핵심 내용, 기대 액션, 결과물, 일정
- 응답 초안
- 사람 검토 상태
- 후속 추적일

### 프로젝트 템플릿 액션

프로젝트 설정에는 다음 액션을 제공한다.

- 현재 프로젝트를 템플릿으로 저장
- 새 프로젝트를 기존 meta template에서 시작
- template에 포함될 스킬/규칙/정책 요약 보기
- template에서 제외되는 데이터와 개인 폴더 확인

### 가운데 뷰어

파일 메타 패널을 추가한다.

- 파일 종류
- 원본/파생 관계
- 적용된 규칙
- 관련 산출물
- 처리 상태

### 하네스 인박스

사용자 playground의 `00_inbox`에 파일이 있으면 상단에 작업 제안을 표시한다.

```text
정리되지 않은 파일 4개
[자동 정리 제안] [그대로 두기]
```

### Clean Room 잠금 표시

Clean Room의 승인된 파일에는 잠금 상태를 표시한다.

```text
이 파일은 Clean Room의 승인된 원본입니다.
[Playground로 복사해서 실험] [변경 요청]
```

## 9. API 초안

```http
GET  /api/projects/{project_id}/harness/files
POST /api/projects/{project_id}/harness/classify
POST /api/projects/{project_id}/harness/organize
POST /api/projects/{project_id}/harness/bundles
GET  /api/projects/{project_id}/harness/bundles/{bundle_id}
PATCH /api/projects/{project_id}/harness/files/{file_id}
POST /api/projects/{project_id}/harness/promotions
PATCH /api/projects/{project_id}/harness/promotions/{promotion_id}
POST /api/projects/{project_id}/forks/templates
POST /api/projects/from-template
POST /api/projects/{project_id}/datasources/google-drive/connect
GET  /api/projects/{project_id}/datasources
POST /api/projects/{project_id}/datasources/{datasource_id}/refresh
POST /api/projects/{project_id}/datasources/{datasource_id}/import
POST /api/projects/{project_id}/datasources/gmail/connect
GET  /api/projects/{project_id}/datasources/gmail/threads
POST /api/projects/{project_id}/datasources/gmail/refresh
POST /api/projects/{project_id}/datasources/gmail/threads/{thread_id}/import
POST /api/projects/{project_id}/datasources/gmail/threads/{thread_id}/triage
POST /api/projects/{project_id}/datasources/gmail/threads/{thread_id}/draft-reply
```

## 10. 성공 기준

v1 성공 기준:

- 사용자가 파일 10개를 올려도 “어디에 무엇이 있는지” 바로 알 수 있다.
- Excel 변환본과 원본 관계가 보인다.
- haro가 업로드 파일을 매체 리포트/리뷰/CS/브리프 중 하나로 분류한다.
- 사용자가 클릭 한 번으로 추천 폴더 정리를 승인할 수 있다.
- 에이전트가 하네스 메타데이터를 근거로 올바른 파일을 선택한다.
- 사용자는 자기 playground에서 자유롭게 실험할 수 있다.
- Clean Room의 승인된 자료는 실수로 수정되지 않는다.
- playground 결과를 Clean Room으로 승격 요청할 수 있다.
- 성공 프로젝트의 Meta Clean Room을 template으로 저장할 수 있다.
- 새 프로젝트 생성 시 기존 meta template을 적용할 수 있다.
- fork 시 실제 데이터와 개인 playground는 복제되지 않는다.
- Google Drive 파일은 데이터소스로 연결하고, 선택한 파일만 Playground로 가져올 수 있다.
- Drive에서 가져온 파일은 원본 메타데이터를 유지하고 Clean Room 승격 전에는 공식 자료가 되지 않는다.
- Gmail thread는 LLM triage로 명확한 요청 메일만 업무 인박스에 올릴 수 있다.
- Gmail 응답은 초안까지 생성하되 최종 발송은 사람이 한다.
