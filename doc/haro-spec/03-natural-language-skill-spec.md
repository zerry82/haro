# 비개발언어 스킬 제작 스펙

## 1. 시작점

스킬 제작은 haro의 이 질문에서 시작한다.

```text
어떤 걸 자동화 해보고 싶으세요?
```

사용자는 함수명, API, 코드, 스키마를 먼저 말하지 않는다. 사용자는 자신의 업무를 말한다.

예:

```text
계약서 파일을 받으면 위험 조항을 확인하고,
금액이 크면 팀장 승인까지 받은 뒤,
검토 의견서와 수정 요청 목록을 만드는 일을 자동화하고 싶어요.
```

haro는 이 말을 바로 스킬로 저장하지 않는다. 먼저 업무를 이해하고, 입력/출력/프로세스/목적이 명확해질 때까지 사용자와 대화한다.

## 2. 스킬 정의

haro에서 스킬은 비개발자가 말한 업무를 반복 실행 가능한 decision workflow로 만든 것이다.

스킬은 단순 프롬프트가 아니다.
스킬은 다음을 포함한다.

- 어떤 입력을 받는지
- 어떤 과정을 거치는지
- 어떤 출력을 만들어야 하는지
- 성공 목적이 무엇인지
- 어떤 조건에서 어떤 경로로 분기되는지
- 어디에서 사람의 검토나 승인이 필요한지
- 어떤 명령이나 이벤트에 의해 시작되는지
- 시작 전/완료 후 어떤 알림이나 후처리를 할지
- 각 단계가 LLM 판단인지, 결정적 코드 실행인지
- 입력과 출력이 유효한지 검사하는 validator
- 검증 케이스와 실행 이력
- 활성화/비활성화 상태
- 버전

## 3. 스킬 구성 요소

스킬의 최상위 구성은 다음이다.

| 구성 요소 | 의미 |
| --- | --- |
| `input scheme` | 스킬이 받는 입력 자료와 입력 조건 |
| `process` | 입력에서 출력까지 가는 처리 방식 |
| `output scheme` | 스킬이 만들어야 하는 산출물 구조 |
| `objective` | 이 스킬이 성공했다고 판단하는 기준 |
| `trigger` | 스킬이 언제, 어떤 명령/이벤트로 실행되는지 |
| `hook` | 시작 전, 완료 후, 실패 시 연결되는 알림/후처리 |

## 4. 스킬 제작 사이클

전체 사이클은 다음과 같다.

```text
0. 시작 질문
  -> 1. 업무 이해 과정
  -> 2. 업무 이해 산출물
  -> 3. 자료 추가 요구
  -> 4. 업무 이해 검증
      -> 부족하면 1 또는 2로 회귀
      -> 충분하면 5로 이동
  -> 5. workflow 설계
  -> 6. 케이스 검증과 workflow 개발
  -> 7. 사용자 보고와 샌드박스 테스트
  -> 8. trigger 설정
  -> 9. hook 설정
  -> 10. 활성화와 버전 고정
```

## 5. 1단계: 업무 이해 과정

목표:

- 입력이 무엇인지 명확히 한다.
- 출력이 무엇인지 명확히 한다.
- 프로세스가 무엇인지 명확히 한다.
- 목적이 무엇인지 명확히 한다.

haro는 질문만 던지지 않고 중간 이해 내용을 계속 공유한다.

예:

```text
haro:
제가 이해한 업무는 이렇습니다.

- 입력: 매체별 주간 성과 파일
- 출력: 광고주 공유용 보고서와 다음 주 액션 플랜
- 과정: 파일 취합 -> 컬럼 정규화 -> 성과 계산 -> 이슈 판단 -> 보고서 생성
- 목적: 광고주가 다음 주 실행 결정을 빠르게 내리게 하는 것

맞나요?
```

질문 예:

- 보통 어떤 파일을 입력으로 받나요?
- 입력 파일은 몇 개 정도인가요?
- 파일마다 꼭 있어야 하는 컬럼이 있나요?
- 최종 결과물은 보고서인가요, 표인가요, 대시보드인가요?
- 결과물은 누가 보나요?
- 좋은 결과물과 나쁜 결과물의 차이는 무엇인가요?
- 매번 사람이 판단하는 부분은 어디인가요?
- 절대 자동으로 하면 안 되는 부분이 있나요?

## 6. 2단계: 업무 이해 산출물

haro는 업무 이해가 어느 정도 진행되면 다음 산출물을 사용자에게 보여준다.

```markdown
# 업무 이해 산출물

## 입력 정의

- Meta 주간 성과 리포트
- Naver 검색광고 리포트
- Kakao 광고 리포트
- 지난주 보고서

## 출력 정의

- 광고주 공유용 주간 보고서
- 핵심 지표 요약
- 다음 주 액션 플랜
- 공유용 코멘트

## 프로세스 정의

1. 입력 파일 확인
2. 매체별 컬럼 정규화
3. 공통 지표 계산
4. 전주 대비 변화 계산
5. 이슈 후보 추출
6. 액션 플랜 생성
7. 보고서와 공유 코멘트 생성

## 목적 정의

광고주가 이번 주 성과와 다음 주 액션을 빠르게 이해하고 승인할 수 있게 한다.
```

사용자는 이 산출물을 보고 수정한다.

## 7. 3단계: 자료 추가 요구

업무 정의만으로는 스킬을 만들 수 없다. haro는 입력과 출력에 대한 실제 자료를 여러 케이스로 요구한다.

요구 자료 예:

- 정상 입력 파일 2~3개
- 컬럼이 다른 입력 파일
- 잘못된 입력 파일
- 과거에 사람이 만든 좋은 출력물
- 사용자가 마음에 들지 않았던 출력물
- 광고주가 수정 요청한 사례

haro의 요청 방식:

```text
이 업무를 안정적으로 자동화하려면 케이스가 더 필요합니다.

1. 지난주 매체별 리포트 묶음
2. 사람이 만든 최종 보고서 예시
3. 틀리기 쉬운 네이버 리포트 예시

이 세 가지를 올려주시면 입력/출력 검증 기준을 만들 수 있습니다.
```

## 8. 4단계: 업무 이해 검증과 회귀

haro는 수집한 케이스로 업무 이해 산출물을 검증한다.

검증 결과는 다음처럼 보여준다.

```text
검증 결과:

- 입력 정의: 보완 필요
  Naver 리포트에 `장바구니금액`과 `구매완료금액`이 함께 있습니다.
  어떤 값을 매출로 볼지 규칙이 필요합니다.

- 출력 정의: 충분
  과거 보고서 3개 모두 같은 섹션 구조를 사용합니다.

- 목적 정의: 보완 필요
  광고주가 원하는 핵심 액션의 기준이 아직 모호합니다.
```

검증 결과가 부족하면 1단계 또는 2단계로 회귀한다.

충분하면 workflow 설계로 이동한다.

## 9. 5단계: Workflow 설계

workflow는 입력부터 출력까지 연결되는 단위 태스크들의 그래프다.
화이트칼라 workflow는 단순 순차 실행보다 의사결정 트리에 가깝다.
따라서 haro의 workflow는 결정적 처리, 비결정적 판단, 조건 분기, 사람 승인, 외부 이벤트 대기를 모두 표현해야 한다.

각 태스크는 다음 속성을 가진다.

| 속성 | 의미 |
| --- | --- |
| `id` | 태스크 식별자 |
| `name` | 사용자에게 보이는 태스크 이름 |
| `type` | `code`, `llm`, `decision`, `human_review`, `wait_event`, `router`, `merge` |
| `input` | 이 태스크가 받는 입력 |
| `output` | 이 태스크가 만드는 출력 |
| `process` | 처리 방식 설명 |
| `input_validator` | 입력 유효성 검사 |
| `output_validator` | 출력 유효성 검사 |
| `depends_on` | 선행 태스크 |

### 태스크 type

#### `code`

결정적 처리가 필요한 태스크다.

예:

- CSV 파싱
- 컬럼 매핑
- 지표 계산
- 계약 금액 추출
- 날짜/기간 검증
- 정해진 schema로 JSON 생성

#### `llm`

비결정적 판단이 필요한 태스크다.

예:

- 사용자가 이해하기 쉬운 요약 작성
- 이슈 후보 해석
- 리스크 조항 설명
- 액션 플랜 문장화
- 고객 응답 초안 작성
- Gmail thread의 요청 여부와 기대 액션 분류
- 사용자와 커뮤니케이션 대상의 사람 맥락을 참고한 톤/구성 조정

#### `decision`

조건에 따라 다음 경로를 고르는 태스크다.

예:

- 금액이 1천만 원 이상이면 승인 단계로 이동
- 필수 조항이 없으면 보완 요청 생성
- 입력 파일 종류에 따라 처리 workflow 선택
- 위험도가 높으면 사람 검토로 이동

#### `human_review`

사람의 판단이나 승인이 필요한 태스크다.

예:

- 팀장 승인
- 법무 검토
- 고객에게 보낼 문구 최종 확인
- Clean Room 반영 승인

#### `wait_event`

외부 이벤트나 자료를 기다리는 태스크다.

예:

- 누락 파일 업로드 대기
- 승인자 응답 대기
- 외부 시스템 webhook 대기
- 정해진 날짜/시간까지 대기

#### `router`

입력 자료나 요청 유형에 따라 적절한 workflow 경로를 선택하는 태스크다.

예:

- 계약서, 견적서, 회의록 중 파일 종류 식별
- HR 요청, 재무 요청, 법무 요청 분류
- 신규 업무인지 기존 스킬 실행인지 판단

#### `merge`

여러 태스크 결과를 하나의 산출물이나 결정 근거로 합치는 태스크다.

예:

- 여러 검토자의 의견 합치기
- 코드 계산 결과와 LLM 해석 결과 병합
- 입력 파일별 분석 결과를 보고서 하나로 통합

## 10. Workflow 예시

```json
{
  "workflow": [
    {
      "id": "collect_inputs",
      "name": "입력 파일 확인",
      "type": "code",
      "input": "uploaded_files",
      "output": "validated_input_files",
      "process": "필수 파일과 확장자, 시트 수를 확인한다.",
      "input_validator": "uploaded_files_exist",
      "output_validator": "required_media_reports_present",
      "depends_on": []
    },
    {
      "id": "normalize_media_reports",
      "name": "매체 리포트 정규화",
      "type": "code",
      "input": "validated_input_files",
      "output": "normalized_performance_table",
      "process": "매체별 컬럼명을 공통 지표로 매핑한다.",
      "input_validator": "known_media_columns",
      "output_validator": "performance_table_schema",
      "depends_on": ["collect_inputs"]
    },
    {
      "id": "interpret_changes",
      "name": "성과 변화 해석",
      "type": "llm",
      "input": "normalized_performance_table",
      "output": "performance_insights",
      "process": "성과 변화와 원인 후보를 광고주 맥락에 맞게 해석한다.",
      "input_validator": "performance_table_has_baseline",
      "output_validator": "insight_schema",
      "depends_on": ["normalize_media_reports"]
    },
    {
      "id": "approval_needed",
      "name": "승인 필요 여부 판단",
      "type": "decision",
      "input": "performance_insights",
      "output": "approval_route",
      "process": "리스크가 높거나 예산 변경이 필요한 경우 사람 승인 단계로 보낸다.",
      "input_validator": "insight_schema",
      "output_validator": "approval_route_schema",
      "depends_on": ["interpret_changes"]
    },
    {
      "id": "manager_review",
      "name": "담당자 검토",
      "type": "human_review",
      "input": "approval_route",
      "output": "review_decision",
      "process": "필요한 경우 담당자가 액션 플랜을 승인하거나 수정 요청한다.",
      "input_validator": "approval_route_schema",
      "output_validator": "review_decision_schema",
      "depends_on": ["approval_needed"]
    },
    {
      "id": "generate_report",
      "name": "보고서 생성",
      "type": "llm",
      "input": "performance_insights, review_decision",
      "output": "weekly_report",
      "process": "사용자 공유용 보고서를 생성한다.",
      "input_validator": "insight_schema",
      "output_validator": "report_schema",
      "depends_on": ["interpret_changes", "manager_review"]
    }
  ]
}
```

## 11. Input Scheme

Input scheme은 사용자가 어떤 자료를 던져야 스킬이 실행 가능한지 정의한다.

예:

```json
{
  "required": [
    {
      "name": "media_reports",
      "type": "file[]",
      "accepted_extensions": [".csv", ".xlsx", ".xls"],
      "min_count": 1,
      "description": "매체별 주간 성과 리포트"
    }
  ],
  "optional": [
    {
      "name": "previous_report",
      "type": "file",
      "accepted_extensions": [".md", ".pdf", ".pptx"],
      "description": "지난주 보고서"
    }
  ]
}
```

## 12. Output Scheme

Output scheme은 스킬이 무엇을 만들어야 하는지 정의한다.

예:

```json
{
  "outputs": [
    {
      "name": "weekly_report",
      "type": "markdown",
      "path_template": "/playground/users/{user_id}/30_outputs/drafts/{client}/{week}/report.md",
      "required_sections": ["action_plan", "summary", "metrics", "risks"]
    },
    {
      "name": "dashboard",
      "type": "html",
      "path_template": "/playground/users/{user_id}/30_outputs/previews/{client}/{week}/dashboard.html"
    },
    {
      "name": "share_comment",
      "type": "markdown",
      "path_template": "/playground/users/{user_id}/30_outputs/drafts/{client}/{week}/share-comment.md"
    }
  ]
}
```

## 13. Objective

Objective는 단순 설명이 아니라 성공 기준이다.

나쁜 objective:

```text
보고서를 잘 만든다.
```

좋은 objective:

```text
검토자가 핵심 리스크와 다음 액션을 3분 안에 이해하고,
승인/보완/반려 중 하나를 결정할 수 있게 한다.
```

objective는 output validator와도 연결된다.

## 14. Validator

validator는 input과 output 모두에 존재한다.

### Input validator

예:

- 필수 파일이 있는가?
- 지원 확장자인가?
- 연결된 데이터소스에서 가져온 snapshot인가?
- CSV 컬럼을 읽을 수 있는가?
- 매체 리포트로 추정할 수 있는가?
- 같은 기간의 파일인가?

### Output validator

예:

- 보고서에 필수 섹션이 있는가?
- 숫자 지표가 입력 데이터와 일치하는가?
- 액션 플랜이 최소 3개 이상인가?
- 금지 표현이나 금지 판단을 사용하지 않았는가?
- share comment가 너무 길지 않은가?
- 결정 근거가 출력에 남아 있는가?
- 사람 승인 단계가 필요한 케이스를 건너뛰지 않았는가?

validator type:

- `code`: 구조, 숫자, schema 검사
- `llm`: 표현, 맥락, 설득력, 대상자 적합성 검사
- `human`: 사용자의 최종 승인

### 사람 맥락 validator

workflow의 LLM 태스크는 선택적으로 `human_context`를 입력으로 받을 수 있다.
이 맥락은 사용자와 주요 커뮤니케이션 대상의 관찰 가능한 업무 선호를 요약한 것이다.

사용 예:

- 광고주 보고서 공유 코멘트 생성
- HR 민감 문의 응답 초안
- CS 답변 톤 조정
- 거래처 일정 확인 메일 초안

제한:

- 낮은 confidence의 사람 맥락은 중요한 결정 근거로 쓰지 않는다.
- `user_verified=false`인 맥락은 표현 보조 정도로만 사용한다.
- 금액, 계약, HR 민감 판단, 자동 발송 여부는 사람 맥락만으로 결정하지 않는다.
- 사람 맥락을 사용한 결과물에는 “참고한 맥락” 요약을 남긴다.
- 성격 단정, 심리 진단, 민감 신원 추정, 조작적 설득 전략은 금지한다.

## 15. 6단계: 케이스 검증과 Workflow 개발

workflow는 한 번에 완성되지 않는다.

haro는 여러 케이스를 돌려보고 실패 이유를 기록한다.

케이스 구조:

```text
cases/
  case-001-normal/
    input/
    expected/
    actual/
    result.md
  case-002-missing-column/
    input/
    expected/
    actual/
    result.md
```

검증 결과 예:

```markdown
# Case 002 결과

status: failed

## 실패 이유

Naver 리포트에 `구매완료금액` 컬럼이 없고 `구매액` 컬럼만 있음.

## 수정 제안

컬럼 alias 규칙 추가:
- 구매완료금액
- 구매액
- purchase_amount
```

실패하면 업무 이해, input scheme, workflow, validator 중 필요한 단계로 회귀한다.

## 16. 7단계: 샌드박스 테스트

스킬 제작이 완료되면 haro는 사용자에게 보고하고 직접 테스트할 수 있는 샌드박스 환경을 제공한다.

여기서 샌드박스는 운영 스킬이 아니라 임시 테스트 폴더다.

```text
.haro/
  skill-sandboxes/
    weekly-media-report/
      input/
      output/
      runs/
      README.md
```

사용자 경험:

```text
haro:
스킬 초안이 준비됐습니다.
테스트 폴더를 만들었어요.

- input 폴더에 새 파일을 넣고
- [테스트 실행]을 누르면
- output 폴더에서 결과를 확인할 수 있습니다.
```

## 17. 8단계: Trigger 설정

trigger는 스킬이 언제 실행되는지를 정한다.

### 명령 trigger

```text
"이 계약서 검토해줘"
"이번 주 리포트 만들어줘"
"이 파일들로 고객 공유용 보고서 만들어줘"
```

### 자료 trigger

```text
특정 폴더에 파일이 추가되면 실행
예: /playground/users/{user_id}/00_inbox/a-client-weekly/ 에 CSV 또는 Excel 파일 추가
```

### 이벤트 trigger

```text
매주 금요일 10시
외부 webhook 수신
카톡/메일로 파일 수신
Google Drive 연결 폴더에 새 파일 추가
Gmail thread에서 명확한 요청 메일 감지
```

Trigger scheme 예:

```json
{
  "triggers": [
    {
      "type": "command",
      "phrases": ["계약서 검토해줘", "주간 보고서 만들어줘", "이번 주 리포트야"]
    },
    {
      "type": "folder_watch",
      "path": "/playground/users/{user_id}/00_inbox/a-client-weekly",
      "extensions": [".csv", ".xlsx"]
    },
    {
      "type": "google_drive_folder_changed",
      "datasource_id": "gd-a-client",
      "event": "file_added",
      "extensions": [".csv", ".xlsx"]
    },
    {
      "type": "gmail_clear_request_detected",
      "connection_id": "gmail-work",
      "min_confidence": 0.85,
      "classification": "clear_request"
    }
  ]
}
```

Gmail trigger는 label 설정을 전제로 하지 않는다.
LLM이 제목, 본문, thread history, 첨부 요약을 보고 `clear_request`를 판단한다.
메일 스킬은 핵심 내용, 기대 액션, 결과물, 일정, 누락 정보, 응답 초안을 구조화해야 한다.

## 18. 9단계: Hook 설정

hook은 스킬 실행 전후에 연결되는 알림과 후처리다.
trigger가 workflow 시작 조건이라면, hook은 workflow 전후에 사람과 외부 서비스로 결과를 이어주는 동작이다.

hook은 두 가지 목적을 가진다.

- 통지형 hook: Slack, KakaoTalk, Telegram, 메일, haro 내부 알림
- 외부 서비스 연계형 hook: API 호출, Google Drive 저장, Gmail 초안/발송, webhook 발행

### 시작 전 hook

- 실행 전 사용자 확인
- 입력 파일 부족 알림
- 담당자에게 파일 요청

### 완료 후 hook

- Slack/카톡/메일 알림
- 보고서 링크 공유
- Google Drive 특정 폴더에 산출물 저장
- Gmail 응답 초안 생성
- 외부 API 호출
- 산출물 archive
- 다음 액션 todo 생성

### 실패 hook

- 실패 이유 알림
- 필요한 파일 목록 요청
- 사용자 검토 큐에 추가

### 실행 정책

hook은 `execution_policy`를 가진다.

| 정책 | 의미 |
| --- | --- |
| `auto` | 조건 충족 시 자동 실행 |
| `approval_required` | 사람 승인 후 실행 |
| `draft_only` | payload, 메일, 저장 계획만 생성 |
| `disabled` | 실행하지 않음 |

v1 기본값:

- 단순 통지형 hook은 기본 `auto`
- 외부 상태를 바꾸는 hook은 기본 `approval_required`
- 메일 발송은 기본 `draft_only`
- `gmail_send` 자동 실행은 pilot policy가 명시적으로 허용할 때만 가능

Hook scheme 예:

```json
{
  "hooks": {
    "before_start": [
      {
        "type": "confirm",
        "message": "이 workflow 실행을 시작할까요?"
      }
    ],
    "after_success": [
      {
        "id": "notify-team",
        "type": "messenger_notify",
        "channel": "slack",
        "target": "#weekly-report",
        "execution_policy": "auto",
        "message": "workflow 실행이 완료되었습니다."
      },
      {
        "id": "save-report-to-drive",
        "type": "google_drive_save",
        "connection_id": "gd-a-client",
        "target_folder": "weekly-reports",
        "files": ["report.md", "dashboard.html"],
        "execution_policy": "approval_required"
      },
      {
        "id": "draft-client-reply",
        "type": "gmail_draft",
        "connection_id": "gmail-work",
        "thread_ref": "input.gmail_thread",
        "execution_policy": "draft_only"
      }
    ],
    "after_failure": [
      {
        "type": "in_app_notify",
        "channel": "owner",
        "execution_policy": "auto",
        "message": "입력 파일이 부족해 실행하지 못했습니다."
      }
    ]
  }
}
```

상세 정책은 [12-hook-integration-spec.md](./12-hook-integration-spec.md)를 따른다.

## 19. 스킬 내장 폴더

스킬 제작은 특수한 내장 폴더에서 진행한다.

스킬 제작 중인 파일은 사용자별 playground에 둔다.
팀 전체가 사용하는 공식 스킬은 Meta Clean Room에 둔다.

```text
playground/users/{user_id}/45_skills/sandbox/
  weekly-media-report/
    skill.md
    objective.md
    input.schema.json
    output.schema.json
    workflow.json
    triggers.json
    hooks.json
    validators/
    cases/

clean-room/meta/45_skills/
  active/
    weekly-media-report/
  review/
    weekly-media-report/
```

권장 구조:

```text
.haro/
  skills/
    registry.json
    weekly-media-report/
      skill.md
      current.json
      versions/
        v0.1.0/
          objective.md
          input.schema.json
          output.schema.json
          workflow.json
          triggers.json
          hooks.json
          validators/
          cases/
          notes.md
        v0.2.0/
          objective.md
          input.schema.json
          output.schema.json
          workflow.json
          triggers.json
          hooks.json
          validators/
          cases/
          notes.md
      sandbox/
        input/
        output/
        runs/
```

`.haro/skills`는 registry, 실행 이력, 현재 활성 버전 포인터를 관리한다.
스킬의 팀 공식 원본은 `clean-room/meta/45_skills`에 있고, Git 관리는 `.haro/git/meta-clean-room.git`이 담당한다.

## 20. 활성화/비활성화

스킬은 활성화와 비활성화를 지원한다.

상태:

| 상태 | 의미 |
| --- | --- |
| `authoring` | 제작 중 |
| `draft` | 초안 완성, 아직 활성화 전 |
| `testing` | 샌드박스 테스트 중 |
| `active` | trigger에 의해 실행 가능 |
| `paused` | 보관하지만 자동 실행하지 않음 |
| `deprecated` | 새 버전으로 대체됨 |
| `archived` | 사용 종료 |

활성화 조건:

- input scheme 확정
- output scheme 확정
- objective 확정
- workflow 확정
- 최소 1개 정상 케이스 통과
- trigger 설정
- 사용자가 활성화 승인

## 21. 버전 관리

스킬은 변경될 때 버전이 올라간다.

버전 변경 기준:

| 변경 | 버전 |
| --- | --- |
| 문구 수정, 설명 보완 | patch |
| validator 추가, trigger 추가 | minor |
| input/output scheme 변경 | major |
| workflow 구조 변경 | major |

예:

```text
v0.1.0: 첫 초안
v0.2.0: 네이버 컬럼 alias 추가
v1.0.0: 사용자 승인 후 활성화
v1.1.0: folder_watch trigger 추가
v2.0.0: output scheme에 dashboard 추가
```

이전 버전은 삭제하지 않는다. 특정 산출물이 어떤 스킬 버전으로 만들어졌는지 추적해야 하기 때문이다.

## 21.1 스킬 수정 반영 흐름

기존 스킬을 수정할 때도 사용자는 Clean Room을 직접 바꾸지 않는다.
수정은 사용자별 playground에서 시작하고, Meta Clean Room 반영 요청을 통해 공식 스킬로 승격한다.

```text
1. Playground에서 기존 스킬을 복사한다.
2. 사용자가 input/output/workflow/validator/trigger/hook을 수정한다.
3. 사용자가 Clean Room 반영 요청을 만든다.
4. haro가 meta-clean-room feature branch를 생성한다.
5. haro가 수정 내용을 clean-room/meta/45_skills/review/에 적용한다.
6. haro가 validator와 케이스 테스트를 실행한다.
7. 테스트가 통과하면 변경 요약과 영향 범위를 보여준다.
8. 승인되면 meta-clean-room main에 merge한다.
9. 스킬 버전을 올리고 active 포인터를 갱신한다.
```

테스트가 실패하면 feature branch는 유지하되 활성 스킬에는 반영하지 않는다.
haro는 실패 리포트를 playground로 돌려보내고 사용자가 다시 수정할 수 있게 한다.

## 22. 스킬 제작 UI

스킬 제작 화면은 코드 에디터가 아니라 제작 마법사에 가깝다.

화면 구성:

- 업무 이해 대화
- 현재 업무 정의
- 입력/출력 자료 목록
- workflow 캔버스
- 케이스 검증 결과
- 샌드박스 테스트 폴더
- trigger 설정
- hook 설정
- 버전 이력
- 활성화 버튼

## 23. 성공 기준

v1 성공 기준:

- 사용자가 “어떤 걸 자동화하고 싶다”고 말하면 haro가 업무 이해 질문을 시작한다.
- haro가 입력, 출력, 프로세스, 목적 정의를 문서로 만든다.
- 사용자가 입력/출력 예시를 여러 개 올릴 수 있다.
- haro가 workflow 단위 태스크를 제안한다.
- 각 태스크에는 input, output, type, process, validator가 있다.
- LLM 태스크는 필요할 때 `human_context`를 보조 입력으로 사용할 수 있다.
- 사람 맥락은 초안/우선순위/맥락 보강에만 쓰고 자동 발송이나 민감 판단에는 직접 쓰지 않는다.
- 최소 1개 케이스를 샌드박스에서 테스트할 수 있다.
- 사용자가 trigger와 hook을 설정할 수 있다.
- 스킬을 활성화/비활성화할 수 있다.
- 스킬 변경 이력이 버전으로 남는다.
