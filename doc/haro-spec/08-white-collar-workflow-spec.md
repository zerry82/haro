# 화이트칼라 Workflow 자동화 스펙

## 1. 핵심 관점

haro는 특정 직종의 자동화 도구가 아니다.
haro는 화이트칼라 업무를 workflow로 보고, 이를 비개발자가 만들고 검증하고 반복 실행할 수 있게 하는 업무 자동화 하네스다.

기본 가정:

```text
화이트칼라 업무는 workflow다.
결정적 계산이든 비결정적 판단이든,
입력, 조건, 결정, 산출물, 검증 기준이 있으면 자동화 가능하다.
```

여기서 workflow는 단순한 순서도가 아니다.
자료 확인, 조건 분기, 사람 승인, LLM 판단, 코드 실행, 외부 이벤트 대기, 산출물 검증이 연결된 의사결정 트리다.

## 2. 업무 구성 요소

화이트칼라 workflow는 대체로 다음 요소로 분해된다.

| 요소 | 의미 |
| --- | --- |
| input | 파일, 텍스트, 표, 메일, 티켓, 연결된 데이터소스, 외부 이벤트 |
| context | 고객, 팀, 프로젝트, 기간, 담당자, 과거 결정 |
| rule | 반드시 지켜야 하는 업무 기준 |
| decision | 조건에 따라 경로를 고르는 판단 |
| process | 입력을 산출물로 바꾸는 작업 |
| output | 보고서, 의견서, 승인 요청, 메시지, 대시보드 |
| validator | 결과가 맞는지 확인하는 기준 |
| trigger | workflow가 시작되는 명령이나 이벤트 |
| hook | 시작 전/완료 후/실패 시 연결되는 통지와 외부 서비스 후처리 |

## 3. 태스크 타입

haro workflow는 다음 태스크 타입을 지원해야 한다.

| 타입 | 역할 |
| --- | --- |
| `code` | 결정적 계산, 파싱, 변환, schema 생성 |
| `llm` | 요약, 해석, 문장화, 비정형 판단 |
| `decision` | 조건에 따른 분기 |
| `human_review` | 사람 승인, 검토, 선택 |
| `wait_event` | 파일 업로드, 승인 응답, webhook, 일정 대기 |
| `router` | 입력 종류나 업무 유형에 따라 workflow 선택 |
| `merge` | 여러 결과를 하나로 통합 |

이 타입 조합으로 대부분의 화이트칼라 업무를 표현한다.

## 3.1 Hook과 외부 액션

hook은 workflow가 외부 세계와 연결되는 지점이다.
trigger가 업무를 시작하게 한다면, hook은 업무 결과를 사람과 외부 서비스에 전달한다.

hook은 두 가지로 나눈다.

- 통지형 hook: Slack, KakaoTalk, Telegram, 메일, haro 내부 알림
- 외부 서비스 연계형 hook: API 호출, Google Drive 저장, Gmail 초안/발송, webhook 발행

자동 실행은 항상 정책 기반이어야 한다.
단순 통지는 자동 실행할 수 있지만, 외부 상태를 바꾸는 hook은 민감도, 대상, 스킬 정책, Clean Room 승인 여부를 보고 실행한다.

```text
workflow success
  -> messenger_notify
  -> google_drive_save
  -> gmail_draft
  -> human_review if required
```

메일 발송 같은 고위험 hook은 기본적으로 초안만 생성하고, pilot policy가 명시적으로 허용할 때만 자동 실행한다.

## 3.2 데이터소스 입력

화이트칼라 업무의 입력은 로컬 업로드 파일만이 아니다.
Google Drive 같은 외부 저장소, 메일 첨부, CRM export, 티켓 시스템 export도 workflow 입력이 될 수 있다.

haro는 외부 데이터소스를 공식 저장소로 보지 않고, workflow 입력 채널로 본다.
v1 Google Drive 연동은 선택 파일을 사용자 Playground로 가져온 뒤 처리한다.

```text
external datasource
  -> import snapshot
  -> playground input
  -> workflow execution
  -> Clean Room promotion if approved
```

이렇게 하면 원본 시스템 권한과 haro 내부 승인 정책을 분리할 수 있다.

Gmail은 파일형 데이터소스가 아니라 CRM형 업무 인박스에 가깝다.
메일은 노이즈가 많기 때문에 label 기반 분류를 기본으로 삼지 않는다.
LLM이 제목, 본문, thread history, 첨부 요약을 읽고 명확한 요청 메일만 `clear_request`로 분류한다.

```text
Gmail thread
  -> LLM triage
  -> clear_request
  -> 핵심 내용, 기대 액션, 결과물, 일정 추출
  -> draft reply
  -> human_review
```

Gmail workflow의 기본 산출물은 자동 발송이 아니라 사람이 검토할 응답 초안이다.

## 4. 직무별 예시

| 직무 | 입력 | decision 예시 | 산출물 |
| --- | --- | --- | --- |
| HR | 이력서, 평가표, 면접 메모 | 필수 역량 미달이면 보류, 통과면 다음 면접 요청 | 후보자 요약, 면접 질문, 평가 의견 |
| 재무 | 세금계산서, 지출 내역, 계약서 | 금액 기준 초과 시 승인 요청 | 지출 검토표, 승인 요청, 이상 항목 목록 |
| 법무 | 계약서, 약관, 메일 | 위험 조항이 있으면 법무 검토 | 리스크 요약, 수정 요청 목록 |
| 영업 | 미팅 노트, CRM 데이터, 제안서 | 고객 단계에 따라 follow-up 분기 | 제안서 초안, 후속 메일, 액션 목록 |
| CS | 문의 티켓, 고객 이력, 정책 문서 | 환불 기준 충족 여부 판단 | 답변 초안, 처리 분류, 에스컬레이션 |
| 운영 | 체크리스트, 로그, 요청서 | 장애/누락 조건이면 담당자 알림 | 점검 결과, 작업 지시, 완료 보고 |
| 마케팅 | 리포트, 소재, 리뷰 | 성과 변동이 크면 원인 분석 | 성과 보고서, 액션 플랜, 공유 코멘트 |

대행사 시나리오는 이 중 마케팅/운영 영역의 대표 예시다.

## 5. 범용 Workflow 제작 흐름

```text
1. 어떤 일을 자동화하고 싶은지 묻는다.
2. 입력, 출력, 프로세스, 목적을 정리한다.
3. 실제 케이스 자료를 모은다.
4. 결정 조건과 예외를 찾는다.
5. code/llm/decision/human_review/wait_event/router/merge 태스크로 workflow를 설계한다.
6. input/output validator를 만든다.
7. 케이스별로 테스트하고 실패 원인을 반영한다.
8. 사용자별 playground에서 실험한다.
9. 검증된 규칙과 스킬을 Meta Clean Room으로 승격한다.
10. 공식 산출물과 템플릿을 Data Clean Room으로 승격한다.
```

## 6. Project Fork와 Vertical Template Family

성공한 workflow는 한 프로젝트에만 머물지 않는다.
haro는 성공한 프로젝트의 Meta Clean Room 설정을 meta template으로 저장하고, 새 프로젝트 생성 시 적용할 수 있어야 한다.

```text
성공한 workflow project
  -> meta template 생성
  -> 같은 vertical의 다른 프로젝트에 적용
  -> 필요하면 다른 vertical에 맞게 변형
```

대행사용 자동화는 첫 template family가 될 수 있다.

```text
agency weekly report 성공
  -> agency/weekly-report template 생성
  -> 광고주 B~T 프로젝트에 적용
  -> 각 광고주 데이터와 playground는 독립
```

이후 같은 구조로 HR, 재무, 법무, 영업, CS, 운영 template family를 만든다.
핵심은 데이터 복제가 아니라, workflow meta의 복제와 변형이다.

## 7. 성공 기준

- 특정 직종 이름 없이도 사용자가 “이 업무를 자동화하고 싶다”고 설명하면 workflow 초안을 만들 수 있다.
- workflow에는 입력, 결정, 산출물, validator가 명확히 남는다.
- 결정적 처리는 `code`, 비결정적 판단은 `llm`, 사람 판단은 `human_review`로 구분된다.
- 대행사 템플릿은 예시일 뿐이고 HR, 재무, 법무, 영업, CS, 운영 업무에도 같은 구조를 적용할 수 있다.
- 공식 규칙과 스킬은 Meta Clean Room으로 승격되고, 공식 데이터와 산출물은 Data Clean Room으로 승격된다.
- 성공한 workflow meta를 template family로 저장하고 새 프로젝트에 적용할 수 있다.
- Google Drive 같은 외부 데이터소스는 가져오기 snapshot으로 workflow 입력에 연결된다.
- Gmail은 LLM triage 기반 CRM형 업무 인박스로 연결되고, 명확한 요청 메일만 workflow trigger가 된다.
- hook은 통지형과 외부 연계형으로 구분되고, 자동 실행은 정책 기반으로만 허용된다.
