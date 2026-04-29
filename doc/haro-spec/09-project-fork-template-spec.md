# 프로젝트 Fork / Meta Template Engine 스펙

## 1. 목적

프로젝트 fork는 성공한 haro 프로젝트를 다른 프로젝트의 시작점으로 재사용하는 기능이다.
이 기능은 haro의 템플릿 엔진 역할을 한다.

여기서 fork는 프로젝트 전체 복제가 아니다.
실제 업무 데이터와 개인 작업 폴더를 복제하지 않고, 성공한 프로젝트의 Meta Clean Room 설정을 템플릿으로 추출해 새 프로젝트를 bootstrap하는 것이다.

```text
Project Fork = Meta Template 생성 + 새 프로젝트 bootstrap
```

예:

```text
광고주 A 프로젝트에서 주간 보고 workflow 도입 성공
  -> meta template 생성
  -> 광고주 B~T 새 프로젝트 생성 시 template 적용
  -> 각 광고주는 자기 Data Clean Room과 User Playground를 독립적으로 사용
```

이 구조는 대행사용 자동화로 시작해 HR, 재무, 법무, 영업, CS, 운영 등 다른 white-collar vertical template family로 확장할 수 있게 한다.

## 2. Fork 대상

기본 fork 대상은 Meta Clean Room이다.

```text
clean-room/meta/
  40_rules/
  45_skills/
  schemas/
  validators/
  triggers/
  hooks/
  policies/
```

추가로 `.haro`의 실행 메타 일부를 포함한다.

```text
.haro/
  skills/
    registry.json
    {skill_id}/current.json
```

포함 기준:

- 승인된 업무규칙
- 활성 스킬과 active version pointer
- workflow 정의
- input/output schema
- validator
- trigger
- hook
- 보호/승인/실행 정책
- 하네스 폴더 템플릿 정의
- 데이터소스 연결 템플릿

## 3. Fork 제외 대상

fork는 데이터 복제가 아니므로 다음은 제외한다.

```text
clean-room/data/10_sources/
clean-room/data/30_outputs/
playground/users/*
```

제외 기준:

- 고객 데이터
- 개인 데이터
- 계약/성과/매출/인사 등 실제 업무 데이터
- 채팅 원문
- 개인 playground 산출물
- 실행 로그 원문
- 업로드 원본 파일
- 공식 산출물 결과 파일
- Google Drive OAuth token
- 실제 Drive file id
- 실제 Drive folder id
- 데이터소스에서 가져온 원본 snapshot
- Gmail OAuth token
- Gmail thread id
- Gmail message id
- raw email body
- email attachments
- imported email thread snapshot
- hook connector token
- API key
- endpoint secret
- webhook signing secret
- 실제 외부 folder id
- 실제 recipient list
- `.haro/context/`
- self_profile
- contact_profile
- 이메일 주소와 연락처 id
- 관계 히스토리
- 사람 맥락 source_refs
- 사람별 초안/응답 이력

채팅세션은 원문을 fork하지 않는다.
다만 승인된 규칙, 스킬, 정책으로 승격된 내용은 Meta Clean Room에 포함될 수 있다.

## 4. 선택적 포함 대상

다음은 선택적으로 포함할 수 있다.

```text
clean-room/data/templates/
```

포함 가능한 것:

- 빈 입력 폴더 구조
- 보고서/제안서/검토서 템플릿
- 샘플 데이터가 아닌 빈 CSV/Markdown 양식
- 익명화된 예시 파일
- Google Drive 폴더 연결 가이드 같은 connector template
- Gmail LLM triage 기준과 CRM inbox policy
- Gmail 응답 초안 템플릿
- hook type과 execution policy 템플릿
- Slack/Drive/Gmail/API 연계 hook의 대상 설정 템플릿
- 사람 맥락 사용 정책 템플릿

사람 맥락 사용 정책은 포함할 수 있지만, 실제 사람 맥락은 포함하지 않는다.
예를 들어 “사람 맥락은 요약만 노출한다”, “고객 메일은 기본 초안만 만든다” 같은 정책은 템플릿화할 수 있다.

익명화된 예시 파일은 실제 Data Clean Room과 분리해 sample template로 관리한다.

```text
clean-room/data/templates/samples/
```

## 5. Template Manifest

프로젝트 fork 결과는 template manifest를 가진다.

```json
{
  "template_id": "agency-weekly-report-v1",
  "template_name": "대행사 주간 보고 자동화",
  "source_project_id": "project-a-client",
  "source_meta_commit": "abc1234",
  "created_by": "jiyoon",
  "created_at": "2026-04-29T10:00:00+09:00",
  "vertical_family": "agency",
  "included": {
    "rules": ["40_rules/data-rules/naver-sales.md"],
    "skills": ["45_skills/active/weekly-report"],
    "schemas": ["schemas/weekly-report.input.json"],
    "validators": ["validators/weekly-report/"],
    "triggers": ["triggers/weekly-report.json"],
    "hooks": ["hooks/weekly-report.json"],
    "policies": ["policies/approval.json"],
    "connector_templates": ["datasources/google-drive/weekly-report-folder.json"]
  },
  "excluded": [
    "clean-room/data/10_sources",
    "clean-room/data/30_outputs",
    "playground/users",
    "google-drive-oauth-token",
    "google-drive-file-id",
    "gmail-oauth-token",
    "gmail-thread-id",
    "raw-email-body",
    "human-context",
    "self-profile",
    "contact-profile",
    "hook-connector-token",
    "endpoint-secret"
  ]
}
```

manifest는 새 프로젝트가 어떤 기준에서 시작했는지 추적하기 위한 기록이다.

## 6. Fork 생성 흐름

성공한 프로젝트에서 사용자는 “템플릿으로 저장”을 선택한다.

```text
1. source project의 meta-clean-room 현재 commit 확인
2. 포함 가능한 Meta Clean Room 파일 수집
3. Data Clean Room 실제 데이터와 playground 제외
4. template manifest 생성
5. template package 저장
6. 사용자에게 포함된 스킬/규칙/정책 요약 표시
```

사용자 표현:

```text
이 프로젝트의 자동화 설정을 템플릿으로 저장할까요?

포함:
- 활성 스킬 3개
- 업무규칙 12개
- 입력/출력 schema 4개
- validator 6개

제외:
- 광고주 성과 데이터
- 보고서 결과물
- 개인 작업공간
- 채팅 원문
- Google Drive 인증 정보와 실제 파일 ID
- Gmail 인증 정보, thread ID, 원문 메일, 첨부파일
- 사람 맥락, 연락처 id, 관계 히스토리
- hook connector token, endpoint secret, 실제 외부 대상
```

## 7. 새 프로젝트 Bootstrap 흐름

새 프로젝트 생성 시 사용자는 기존 meta template에서 시작할 수 있다.

```text
1. 새 프로젝트 생성
2. Data Clean Room 초기화
3. Meta Clean Room 초기화
4. 선택한 template의 meta 파일 적용
5. 새 프로젝트 전용 data-clean-room.git 생성
6. 새 프로젝트 전용 meta-clean-room.git 생성
7. User Playground 빈 폴더 생성
8. source template manifest를 .haro에 기록
```

새 프로젝트는 source project와 독립적으로 진화한다.
fork 후 source project의 Meta Clean Room 변경은 새 프로젝트에 자동 반영하지 않는다.
필요하면 별도의 template update 또는 재적용 흐름을 사용한다.

## 8. Vertical Template Family

대행사용 자동화는 첫 template family다.

```text
agency/
  weekly-report/
  creative-brief/
  performance-diagnosis/
  handover-summary/
```

같은 구조로 다른 white-collar vertical family를 확장한다.

```text
hr/
  resume-screening/
  interview-summary/
  onboarding-checklist/

finance/
  expense-review/
  invoice-check/
  monthly-close/

legal/
  contract-review/
  clause-risk-check/
  approval-request/

sales/
  meeting-followup/
  proposal-draft/
  crm-update/
```

haro의 확장 방식은 직종별 hard-coded 제품을 만드는 것이 아니다.
성공한 workflow meta를 템플릿화하고, 새로운 프로젝트와 vertical에 복제/변형하는 방식이다.

## 9. 성공 기준

- 성공 프로젝트의 Meta Clean Room을 template로 저장할 수 있다.
- 새 프로젝트 생성 시 template을 적용할 수 있다.
- Data Clean Room의 실제 데이터는 fork되지 않는다.
- User Playground는 fork되지 않는다.
- Google Drive token, 실제 file id, 가져온 snapshot은 fork되지 않는다.
- Gmail token, thread id, raw email, attachments는 fork되지 않는다.
- 사람 맥락, self_profile, contact_profile, 관계 히스토리는 fork되지 않는다.
- hook token, secret, endpoint credential은 fork되지 않는다.
- fork된 프로젝트는 source project와 독립된 Data/Meta Clean Room Git을 가진다.
- template manifest에 `source_project_id`, `source_meta_commit`, 생성자, 생성 시각, 포함된 스킬/규칙 버전이 남는다.
- 대행사 첫 성공 사례를 여러 광고주 프로젝트로 확산할 수 있다.
- 같은 구조로 다른 white-collar vertical template family를 만들 수 있다.
