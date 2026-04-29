# Hook / External Action 연동 스펙

## 1. 목적

hook은 workflow 실행 전후에 haro가 외부 세계와 연결되는 지점이다.
trigger가 “언제 시작할지”를 정한다면, hook은 “시작 전후에 무엇을 알리고 어디에 반영할지”를 정한다.

hook의 목적은 두 가지다.

- 통지형 hook: 사람이나 팀 채널에 상태를 알린다.
- 외부 서비스 연계형 hook: API, Drive, Gmail 같은 외부 서비스에 산출물이나 액션을 반영한다.

v1은 정책별 자동 실행 모델을 사용한다.
자동 실행 여부는 hook type, 민감도, 대상, workspace policy, skill policy에 따라 결정한다.

## 2. Hook과 Trigger 구분

| 구분 | 역할 | 예 |
| --- | --- | --- |
| trigger | workflow 시작 조건 | Gmail 요청 메일 감지, Drive 파일 추가, 명령 입력 |
| hook | workflow 전후 후처리 | Slack 알림, Drive 저장, Gmail 초안 생성, API 호출 |

예:

```text
trigger: Gmail에서 명확한 요청 메일 감지
workflow: 요청 분석 -> 보고서 생성 -> 사람 검토
hook: Slack 알림 -> Google Drive 저장 -> Gmail 응답 초안 생성
```

## 3. 실행 시점

| 시점 | 의미 |
| --- | --- |
| `before_start` | 실행 전 확인, 사전 알림, 입력 요청 |
| `after_success` | 성공 후 알림, 산출물 전달, 외부 저장 |
| `after_failure` | 실패 알림, 재시도 요청, 담당자 호출 |
| `after_human_review` | 사람 승인 후 외부 연계 실행 |
| `on_deadline` | 일정/후속 추적 시점 도달 |

## 4. Hook Type

### 통지형 hook

| type | 역할 |
| --- | --- |
| `messenger_notify` | Slack, KakaoTalk, Telegram 같은 메신저 알림 |
| `email_notify` | 메일 알림 |
| `in_app_notify` | haro 내부 알림 |

통지형 hook은 외부 상태를 크게 바꾸지 않으므로 기본적으로 `auto`를 허용한다.
단, 민감 정보가 포함되면 메시지 본문을 요약하거나 승인 단계로 낮춘다.

### 외부 서비스 연계형 hook

| type | 역할 |
| --- | --- |
| `http_request` | 외부 API 호출 |
| `google_drive_save` | 특정 Google Drive 폴더에 산출물 저장 |
| `gmail_draft` | Gmail 응답 초안 생성 |
| `gmail_send` | 정책이 허용한 경우에만 Gmail 발송 |
| `webhook_emit` | 외부 webhook 발행 |

외부 서비스 연계형 hook은 외부 상태를 바꾸므로 기본적으로 `approval_required` 또는 `draft_only`에서 시작한다.
낮은 민감도와 승인된 스킬, 허용된 대상이 모두 충족되면 `auto`가 가능하다.

## 5. Execution Policy

hook은 `execution_policy`를 가진다.

| 정책 | 의미 |
| --- | --- |
| `auto` | 조건 충족 시 자동 실행 |
| `approval_required` | 사람 승인 후 실행 |
| `draft_only` | payload, 메일, 저장 계획만 생성 |
| `disabled` | 실행하지 않음 |

v1 기본 정책:

- 단순 통지형 hook은 기본 `auto`
- 외부 상태를 바꾸는 hook은 기본 `approval_required`
- 메일 발송은 기본 `draft_only`
- `gmail_send`의 `auto`는 pilot policy가 명시적으로 허용할 때만 가능
- 실패 시 되돌리기 어려운 hook은 자동 실행하지 않는다

정책 판단 기준:

- hook type
- 데이터 민감도
- 고객/프로젝트
- 외부 대상 allowlist
- 스킬 활성 버전
- Clean Room 승인 여부
- 실패 시 되돌릴 수 있는지 여부

## 6. Hook Schema 초안

```json
{
  "hooks": {
    "after_success": [
      {
        "id": "notify-team",
        "type": "messenger_notify",
        "channel": "slack",
        "target": "#weekly-report",
        "execution_policy": "auto",
        "message_template": "주간 보고서가 준비되었습니다."
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
        "template": "weekly-report-ready",
        "execution_policy": "draft_only"
      }
    ]
  }
}
```

## 7. Policy 예시

### 통지 자동 실행

```json
{
  "type": "messenger_notify",
  "execution_policy": "auto",
  "allowed_channels": ["slack", "telegram"],
  "sensitivity_max": "internal"
}
```

### Drive 저장 승인 필요

```json
{
  "type": "google_drive_save",
  "execution_policy": "approval_required",
  "allowed_connections": ["gd-a-client"],
  "allowed_folders": ["weekly-reports"]
}
```

### Gmail 발송 pilot

```json
{
  "type": "gmail_send",
  "execution_policy": "auto",
  "pilot": true,
  "allowed_recipients": ["*@trusted-client.com"],
  "sensitivity_max": "low",
  "requires_active_skill": true
}
```

`gmail_send` 자동 실행은 예외적이다.
기본은 `gmail_draft`로 초안을 만들고 사람이 최종 발송한다.

## 8. 저장 위치

hook 정의는 Meta Clean Room의 스킬과 정책에 포함된다.

```text
clean-room/meta/hooks/
clean-room/meta/policies/
clean-room/meta/45_skills/
```

실제 외부 연결 credential은 hook 정의에 저장하지 않는다.
credential은 `.haro/datasources` 또는 별도 secure integration store에서 관리한다.

## 9. Project Fork와 보안

Project Fork에는 hook 설정 템플릿은 포함할 수 있지만 인증 정보는 포함하지 않는다.

fork 포함 가능:

- hook type
- hook execution policy
- 메시지 템플릿
- Drive 저장 위치 템플릿
- API payload schema
- Gmail 초안 템플릿

fork 제외 대상:

- OAuth token
- API key
- endpoint secret
- webhook signing secret
- connector credential
- 실제 외부 folder id
- 실제 recipient list
- 실행 로그 원문

fork된 프로젝트는 외부 연결을 새로 설정하고, hook 대상 allowlist를 다시 확인해야 한다.

## 10. 성공 기준

- hook이 trigger와 명확히 구분된다.
- 통지형 hook과 외부 서비스 연계형 hook이 구분된다.
- hook마다 `execution_policy`가 있다.
- 자동 실행은 policy 기반으로만 가능하다.
- Gmail 자동 발송은 기본값이 아니며 pilot policy에서만 허용된다.
- Project Fork에 token, secret, credential이 포함되지 않는다.
