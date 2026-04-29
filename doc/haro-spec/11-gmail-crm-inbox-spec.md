# Gmail LLM 기반 CRM형 업무 인박스 스펙

## 1. 목적

Gmail 연동은 단순히 메일 첨부파일을 가져오는 기능이 아니다.
메일은 업무 요청, 고객 피드백, 승인 회신, 일정 합의, 후속 확인이 섞인 높은 엔트로피의 업무 trigger다.

haro는 Gmail을 CRM형 thread inbox로 다룬다.
v1 목표는 모든 메일을 처리하는 것이 아니라, 제목과 본문과 thread 맥락을 LLM이 읽어 “명확한 요청 메일”만 업무 인박스에 올리는 것이다.

```text
Gmail thread
  -> thread grouping
  -> LLM triage
  -> clear_request만 집중
  -> 핵심 내용/액션/결과물/일정 구조화
  -> 응답 초안 생성
  -> human review
  -> 사용자가 최종 발송
```

## 2. 핵심 원칙

- v1 provider는 Gmail 우선이다.
- Gmail label은 있으면 참고하는 약한 힌트일 뿐이다.
- 사용자가 label을 미리 설정했다고 가정하지 않는다.
- 전체 메일함을 업무 데이터로 가져오지 않는다.
- LLM triage 결과 필요한 thread만 haro 업무 인박스에 표시한다.
- haro는 메일 처리의 99%를 초안화하지만, 최종 발송은 사람이 한다.
- 자동 발송은 후속 pilot mode에서 별도 정책으로 다룬다.

## 3. Thread Grouping

메일은 개별 message가 아니라 thread 단위로 관리한다.

우선순위:

1. Gmail thread id
2. `References` header
3. `In-Reply-To` header
4. normalized subject
5. sender/recipient/time window

haro는 thread를 하나의 업무 단위로 보고, 이전 회신과 인용문을 정리해 현재 요청 맥락을 만든다.

## 4. LLM Triage

classification은 LLM이 수행한다.

입력:

- subject
- sender
- recipients
- body
- quoted history
- attachment summary
- date
- previous thread state
- optional hints: Gmail label, sender allowlist, Gmail search query

분류값:

| 분류 | 의미 |
| --- | --- |
| `clear_request` | 명확한 요청 메일 |
| `needs_context` | 요청 같지만 맥락이 부족함 |
| `informational` | 참고/공유 |
| `notification` | 시스템 알림 |
| `newsletter` | 뉴스레터/마케팅 |
| `personal_or_sensitive` | 민감하거나 개인적이라 자동 처리 금지 |
| `irrelevant` | 업무 무관 |

v1 기본 필터는 `clear_request` 중심이다.
confidence가 낮으면 자동 처리하지 않고 `needs_context`로 보낸다.

예:

```text
목표: 명확한 요청 메일만 집중

- “이번 주 보고서 오늘 5시까지 부탁드립니다.” -> clear_request
- “참고로 공유드립니다.” -> informational
- “뉴스레터 4월호” -> newsletter
- “계약 조건 관련 민감한 내용입니다.” -> personal_or_sensitive
```

## 5. Structured Email Model

메일 thread를 해석하면 다음 구조로 정리한다.

핵심 필드:

- 핵심 내용
- 기대하는 액션
- 결과물
- 일정

추가 필드:

- 요청자와 조직
- 관련 고객/프로젝트
- 수신자에게 기대하는 역할
- 긴급도
- 민감도
- 승인 필요 여부
- 첨부/참조 자료
- 누락된 정보
- 추천 workflow/skill
- 응답 초안
- 후속 추적 상태
- 참고한 사람 맥락

예:

```json
{
  "classification": "clear_request",
  "confidence": 0.91,
  "summary": "A광고주가 이번 주 성과 보고서와 다음 주 액션 플랜을 요청했다.",
  "expected_actions": [
    {
      "action": "주간 성과 보고서 작성",
      "deliverable": "report.md, dashboard.html, advertiser-comment.md",
      "due_at": "2026-04-29T17:00:00+09:00"
    }
  ],
  "requester": {
    "name": "김민지",
    "organization": "A광고주"
  },
  "project_hint": "A광고주 운영",
  "urgency": "high",
  "sensitivity": "normal",
  "approval_required": true,
  "missing_info": ["이번 주 네이버 리포트"],
  "recommended_skill": "agency-weekly-report",
  "human_context_refs": ["contact-a-client-manager", "self-jiyoon"],
  "followup_state": "needs_reply"
}
```

## 5.1 Sender/Contact Context

Gmail thread를 해석할 때 haro는 발신자와 수신자의 사람 맥락을 참고할 수 있다.
사람 맥락은 `.haro/context/`에 저장된 요약이며, 원문 전체나 민감한 개인정보를 직접 포함하지 않는다.

활용 예:

- “이 광고주는 보고서 첫 장에 액션 플랜을 먼저 보는 편이다.”
- “이 담당자는 일정과 누락 정보를 먼저 확인한다.”
- “사용자는 고객 메일 자동 발송을 원하지 않는다.”

응답 초안에는 위 맥락을 반영할 수 있다.
다만 사람 맥락은 초안과 우선순위 보조에만 사용하며, 자동 발송이나 외부 실행 판단에는 직접 쓰지 않는다.

UI에는 다음처럼 요약만 노출한다.

```text
haro가 참고한 사람 맥락

- A광고주 김민지 매니저는 보고서 첫 장에 액션 플랜을 먼저 보는 편입니다.
- 이 맥락은 사용자가 확인한 관찰입니다.

[수정] [이번에는 사용하지 않기] [삭제]
```

## 6. Thread Snapshot 저장

Gmail thread snapshot은 사용자 Playground에 저장한다.

```text
playground/users/{user_id}/00_inbox/email/{connection_name}/{thread_slug}/
  thread.md
  summary.json
  actions.json
  draft-reply.md
  attachments/
  metadata.json
```

파일 역할:

| 파일 | 역할 |
| --- | --- |
| `thread.md` | 사람이 읽을 수 있는 thread 정리본 |
| `summary.json` | classification, 핵심 내용, 프로젝트 힌트 |
| `actions.json` | 기대 액션, 결과물, 일정, 담당자 |
| `draft-reply.md` | 사용자가 검토할 응답 초안 |
| `attachments/` | 가져온 첨부파일 snapshot |
| `metadata.json` | Gmail thread id, message id, 원본 링크, import 시각 |

원문 전체를 Clean Room으로 자동 승격하지 않는다.
팀 기준으로 남길 내용은 요약, 결정, 업무규칙, 스킬 후보로 정제해 승격한다.

## 7. CRM형 상태

메일 thread는 업무 상태를 가진다.

| 상태 | 의미 |
| --- | --- |
| `new` | 새로 감지됨 |
| `triaged` | LLM triage 완료 |
| `needs_reply` | 응답 필요 |
| `waiting_internal` | 내부 자료/승인 대기 |
| `waiting_external` | 외부 회신 대기 |
| `draft_ready` | 응답 초안 준비 |
| `sent_by_user` | 사용자가 최종 발송 |
| `done` | 업무 완료 |
| `archived` | 보관 |

이 상태는 일반 메일함의 읽음/안읽음보다 업무 진행을 잘 표현해야 한다.

## 8. Workflow 연동

Gmail 처리 흐름:

```text
Gmail recent inbox/thread fetch
  -> thread grouping
  -> LLM triage
  -> clear_request만 업무 인박스에 표시
  -> 핵심 내용/액션/결과물/일정 추출
  -> 첨부파일 snapshot 저장
  -> 관련 workflow 추천
  -> draft-reply.md 생성
  -> human_review
  -> 사용자가 최종 발송
```

Trigger 초안:

- `gmail_clear_request_detected`
- `gmail_reply_received`
- `gmail_attachment_received`
- `gmail_followup_due`

Trigger 예:

```json
{
  "type": "gmail_clear_request_detected",
  "connection_id": "gmail-work",
  "classification": "clear_request",
  "min_confidence": 0.85,
  "recommended_skill": "agency-weekly-report"
}
```

## 9. 응답 초안과 Human Review

v1에서 haro는 Gmail에 자동 발송하지 않는다.
대신 사용자가 거의 그대로 보낼 수 있는 응답 초안을 만든다.

초안은 다음을 포함한다.

- 요청 이해 확인
- 필요한 결과물
- 예상 완료 일정
- 누락 정보 요청
- 첨부/링크 안내
- 다음 액션

응답 초안은 `draft-reply.md`로 저장하고, 사용자가 검토한 뒤 Gmail에서 최종 발송한다.

## 10. Pilot Mode

자동화 수준은 후속 기능으로 분리한다.

| 모드 | 의미 |
| --- | --- |
| `manual` | 초안 생성까지만, 사람이 발송 |
| `assist` | 낮은 민감도 메일은 승인 버튼 후 발송 |
| `auto` | 제한된 조건에서 자동 발송 |

v1 기본값은 `manual`이다.
`assist`와 `auto`는 민감도, 고객, 프로젝트, 발신자, 금액, 계약 여부 같은 정책이 준비된 뒤에만 허용한다.

## 11. Project Fork와 보안

Project Fork에는 Gmail의 실제 데이터와 인증 정보를 포함하지 않는다.

fork 제외 대상:

- Gmail OAuth token
- Gmail thread id
- Gmail message id
- raw email body
- email attachments
- imported thread snapshot
- `.haro/context/`
- self_profile
- contact_profile
- 사람 맥락 source_refs
- 개인/고객/계약/성과 데이터

선택적으로 포함 가능한 것:

- Gmail connector template
- LLM triage 기준
- “명확한 요청 메일만 집중” 같은 inbox policy
- 추천 workflow routing rule
- 응답 초안 템플릿
- 사람 맥락 사용 정책

fork된 프로젝트는 새 Gmail 연결을 다시 만들어야 한다.

## 12. API 초안

```http
POST /api/projects/{project_id}/datasources/gmail/connect
GET  /api/projects/{project_id}/datasources/gmail/threads
POST /api/projects/{project_id}/datasources/gmail/refresh
POST /api/projects/{project_id}/datasources/gmail/threads/{thread_id}/import
POST /api/projects/{project_id}/datasources/gmail/threads/{thread_id}/triage
POST /api/projects/{project_id}/datasources/gmail/threads/{thread_id}/draft-reply
```

## 13. UI 초안

데이터소스 탭의 Gmail 영역:

- Gmail 연결 상태
- LLM triage 결과
- `clear_request` 업무 인박스
- thread 목록
- 핵심 내용
- 기대 액션
- 결과물과 일정
- 초안 보기
- 사람 검토 상태
- 후속 추적일

메일 thread 상세:

- thread timeline
- 구조화 요약
- 첨부파일
- 추천 workflow
- 응답 초안
- 참고한 사람 맥락 요약
- `[초안 복사]`
- `[완료 처리]`
- `[추가 정보 필요]`

## 14. 성공 기준

- Gmail thread를 개별 message가 아니라 업무 thread로 묶을 수 있다.
- label 설정 없이 제목/본문/맥락 기반 LLM triage가 동작한다.
- `clear_request` 메일만 업무 인박스에 우선 표시된다.
- 핵심 내용, 기대 액션, 결과물, 일정이 구조화된다.
- 응답 초안이 생성되지만 최종 발송은 사람이 한다.
- 응답 초안은 검증된 사람 맥락을 보조로 참고할 수 있다.
- 사용자는 haro가 참고한 사람 맥락 요약을 수정, 삭제, 비활성화할 수 있다.
- Gmail token, thread id, raw email, attachments는 Project Fork에 포함되지 않는다.
- 사람 맥락과 `.haro/context/`도 Project Fork에 포함되지 않는다.
