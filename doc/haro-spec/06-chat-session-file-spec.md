# 채팅세션 폴더/파일 관리 스펙

## 1. 배경

현재 haro의 채팅세션은 DB 중심으로 관리된다.

- 프로젝트 안에 여러 채팅세션이 있다.
- 메시지와 에이전트 로그는 DB에 저장된다.
- UI 오른쪽 채팅 패널에서 목록을 전환한다.

하지만 haro의 장기 방향이 “비개발자용 업무 하네스”라면 채팅세션도 단순 UI 목록이 아니라 업무 자산이어야 한다.

사용자 입장에서는 채팅이 곧 작업 지시, 의사결정, 피드백, 규칙 후보, 산출물 히스토리다. 따라서 채팅세션도 폴더와 파일로 관리되어야 한다.

## 2. 제품 원칙

1. 채팅은 대화 기록이 아니라 작업 폴더다.
2. 사용자는 지난 채팅을 “파일 찾듯이” 찾을 수 있어야 한다.
3. 채팅에서 나온 결정, 규칙, 산출물은 별도 파일로 분리되어야 한다.
4. DB는 빠른 조회와 실행 상태 관리를 담당하고, 파일은 사용자/에이전트가 이해하는 작업 기록을 담당한다.
5. 채팅 폴더는 하네스의 다른 파일, 규칙, 산출물과 연결되어야 한다.
6. 개인 작업 채팅은 사용자별 playground에 저장하고, 팀 공유가 필요한 요약과 결정만 Meta Clean Room으로 승격한다.

## 3. 폴더 구조

기본 하네스 폴더에는 Clean Room과 사용자별 Playground가 있다.
채팅세션은 기본적으로 사용자의 Playground에 생성된다.

```text
/
  clean-room/
    meta/
      50_chats/
  playground/
    users/
      {user_id}/
        50_chats/
  90_archive/
```

채팅세션 하나는 하나의 폴더다.

```text
playground/users/{user_id}/50_chats/
  2026-04-29-a-client-weekly-report/
    README.md
    conversation.md
    context.md
    decisions.md
    rule-candidates.md
    linked-files.json
    artifacts.json
    agent-log.md
    inputs/
    working/
    outputs/
    summaries/
      summary-0001.md
      index.json
```

## 4. 파일 역할

| 파일 | 역할 |
| --- | --- |
| `README.md` | 채팅세션의 목적, 상태, 요약 |
| `conversation.md` | 사용자와 haro의 주요 대화 기록 |
| `context.md` | 긴 대화를 압축한 현재 맥락 |
| `decisions.md` | 사용자가 승인한 결정과 판단 |
| `rule-candidates.md` | 스킬로 승격될 수 있는 자연어 규칙 후보 |
| `linked-files.json` | 이 채팅에서 사용한 원본/변환본/산출물 파일 경로 |
| `artifacts.json` | 생성된 산출물 목록과 타입 |
| `agent-log.md` | 주요 도구 실행과 결과 요약 |
| `inputs/` | 채팅에서 사용한 입력 파일 snapshot 또는 참조 |
| `working/` | 정규화 데이터, 실험 중간 산출물 |
| `outputs/` | 보고서, HTML, CSV 등 채팅 산출물 |
| `summaries/` | 맥락 압축 요약 파일 |

## 5. README.md 예시

```markdown
# A광고주 2026-W18 주간 성과 보고

status: active
created_at: 2026-04-29T10:12:00+09:00
last_activity_at: 2026-04-29T10:45:00+09:00
chat_id: 7b3...

## 목적

A광고주의 이번 주 매체별 성과 파일을 정리하고 광고주 공유용 보고서를 만든다.

## 현재 상태

- 입력 파일 3개 정리 완료
- 네이버 매출 컬럼 규칙 확인 필요
- 보고서 초안 생성 완료

## 주요 산출물

- ../../30_outputs/drafts/a-client-2026-w18/report.md
- ../../30_outputs/previews/a-client-2026-w18/dashboard.html
```

## 6. conversation.md 예시

```markdown
# Conversation

## 2026-04-29 10:12 사용자

이번 주 A광고주 주간 성과 보고서 만들어줘.

## 2026-04-29 10:13 haro

현재 업로드된 Meta, Naver, Kakao 리포트를 확인했습니다.
먼저 공통 컬럼으로 정규화하겠습니다.

## 2026-04-29 10:21 사용자

네이버 파일에서 장바구니금액은 매출로 쓰면 안 돼.
구매완료금액만 매출로 봐.
```

## 7. decisions.md 예시

```markdown
# Decisions

- 네이버 리포트에서 `장바구니금액`은 매출 계산에서 제외한다.
- 네이버 리포트의 매출 컬럼은 `구매완료금액`으로 본다.
- A광고주 보고서에서는 액션 플랜을 지표 요약보다 먼저 배치한다.
```

## 8. rule-candidates.md 예시

```markdown
# Rule Candidates

## 후보 1

type: data_rule
scope: A광고주 / 네이버 리포트
status: pending

네이버 리포트에서 장바구니금액은 매출로 쓰지 않고 구매완료금액만 매출로 본다.

## 후보 2

type: output_rule
scope: A광고주 / 주간 보고서
status: accepted

A광고주 보고서에서는 액션 플랜을 지표 요약보다 먼저 배치한다.
```

## 9. linked-files.json 예시

```json
{
  "inputs": [
    "/clean-room/data/10_sources/media-reports/meta_weekly.csv",
    "/clean-room/data/10_sources/media-reports/naver_weekly.csv"
  ],
  "derived": [
    "/playground/users/zerry/20_working/normalized-data/a-client-2026-w18.csv"
  ],
  "outputs": [
    "/playground/users/zerry/30_outputs/drafts/a-client-2026-w18/report.md",
    "/playground/users/zerry/30_outputs/previews/a-client-2026-w18/dashboard.html"
  ]
}
```

## 10. 파일 쓰기 기본 위치 규칙

채팅 중 파일 쓰기는 강제 격리가 아니다.
다만 사용자가 위치를 명확히 말하지 않으면 haro는 현재 채팅 폴더를 기본 작업 위치로 사용한다.

기본 규칙:

- 사용자가 “파일 만들어줘”, “보고서 저장해줘”처럼 위치를 말하지 않으면 `outputs/` 또는 `working/`에 저장한다.
- 사용자가 `/playground/users/{user_id}/30_outputs/...`처럼 명시한 합법 경로를 말하면 그 경로를 따른다.
- Clean Room과 `.haro` 내부 메타데이터는 직접 쓰지 않는다.
- 채팅 산출물을 다른 폴더로 보내야 하면 복사 후 연결한다.
- Clean Room으로 보내야 하면 직접 복사하지 않고 승격 요청으로 처리한다.

예:

```text
사용자: 보고서 초안 만들어줘.
저장 위치: playground/users/{user_id}/50_chats/{chat}/outputs/report.md

사용자: 이 파일을 /playground/users/{user_id}/30_outputs/drafts/report.md 로 저장해줘.
저장 위치: 사용자가 지정한 경로
```

## 11. 맥락 압축 규칙

채팅이 길어지면 haro는 요약 파일을 만들고 오래된 대화를 LLM 컨텍스트에서 제외할 수 있다.
원문 DB 메시지는 보존한다.

동작:

- 수동: 사용자가 `요약` 버튼을 눌러 현재 채팅을 요약한다.
- 자동 제안: 압축되지 않은 메시지가 일정 개수를 넘으면 haro가 요약을 제안한다.
- 요약 결과는 `summaries/summary-NNNN.md`에 저장한다.
- 최신 맥락은 `context.md`에 갱신한다.
- 이후 LLM은 `context.md + 최근 메시지`를 우선 사용한다.

v1 기본값:

- 최근 메시지 20개는 원문으로 유지한다.
- 압축되지 않은 메시지가 40개 이상이면 요약을 제안한다.
- 요약 실패 시 메시지를 compressed 처리하지 않는다.

## 12. DB와 파일의 관계

v1에서는 서비스 DB와 workspace DB를 함께 사용한다.

- 서비스 DB: 빠른 채팅 목록, 메시지 조회, 권한, SSE, 실행 상태
- workspace DB: 채팅 폴더, 입력 파일, 산출물, export 관계 검색
- 파일: 사용자가 읽고 에이전트가 참조할 수 있는 업무 기록

동기화 방향:

```text
DB chat_sessions/messages/agent_logs
  -> chat folder mirror
  -> workspace_item_relations
  -> harness context
```

초기에는 DB를 source of truth로 두고, 채팅이 생성/수정될 때 파일 mirror를 갱신한다.
채팅에서 읽은 파일과 생성한 파일의 관계는 workspace DB의 `workspace_item_relations`에도 기록한다.
`linked-files.json`과 `artifacts.json`은 사람이 읽기 쉬운 mirror이며, 검색과 관계 조회의 기준은 workspace DB로 둔다.

상세 파일관리 DB 스펙은 [14-workspace-file-db-spec.md](./14-workspace-file-db-spec.md)를 따른다.

## 13. 디버그 trace

채팅세션은 사용자의 업무 기록이지만, 개발과 품질 개선을 위해 에이전트 내부 동작도 턴별로 추적할 수 있어야 한다.

디버그 trace는 사용자가 보낸 메시지 하나를 기준으로 다음 정보를 연결한다.

- LLM에게 보낸 system instruction과 contents
- LLM이 돌려준 원문 응답
- tool call과 tool result
- 에러와 실행 시간

v1에서는 디버그 모드가 켜진 턴만 full trace를 저장한다.
기존 `agent_logs`는 운영 로그로 유지하고, 원문 전체 디버그 기록은 별도 `agent_debug_traces`로 분리한다.

채팅 UI에서는 사용자가 보낸 메시지 블럭을 클릭하면 중앙 모달로 해당 턴의 디버그 trace를 보여준다.
trace가 없는 과거 메시지는 “이 메시지는 디버그 기록이 없습니다.”라고 안내한다.

디버그 trace는 채팅 폴더의 일반 산출물이 아니다.
따라서 Project Fork, Clean Room 승격, workspace file DB 검색 대상에 포함하지 않는다.

상세 디버그 모드 스펙은 [15-debug-mode-spec.md](./15-debug-mode-spec.md)를 따른다.

## 14. 채팅 생성 규칙

채팅 생성 시:

1. DB chat_session 생성
2. `playground/users/{user_id}/50_chats/{date}-{slug}/` 폴더 생성
3. 기본 파일과 `inputs/`, `working/`, `outputs/`, `summaries/` 생성
4. chat_session에 `folder_path` 또는 metadata 연결

채팅 제목 변경 시:

- v1: 폴더명은 유지하고 `README.md` title만 변경
- v2: 안전한 rename 기능 제공

채팅 삭제 시:

- v1: DB 삭제와 함께 폴더를 `90_archive/chats/{user_id}/`로 이동
- 완전 삭제는 별도 위험 작업으로 둔다.

Clean Room 공유 시:

- 전체 대화를 자동 공유하지 않는다.
- `README.md`, `decisions.md`, accepted `rule-candidates.md`, 관련 산출물 요약만 승격 대상으로 삼는다.
- 승격 후 위치는 `clean-room/meta/50_chats/{date}-{slug}/`다.

## 15. UI 변경

### 채팅 패널

현재 오른쪽 채팅 목록은 유지하되, 각 채팅에 폴더 상태를 표시한다.

- 작업 폴더 열기
- 채팅 요약하기
- 관련 파일 보기
- 결정 보기
- 규칙 후보 보기
- 산출물 보기

### 폴더 패널

내 Playground의 `50_chats/` 아래 채팅 폴더가 보인다.

사용자는 채팅을 파일처럼 열 수 있다.

- `README.md`는 채팅 요약
- `conversation.md`는 대화 로그
- `decisions.md`는 결정 사항
- `rule-candidates.md`는 스킬 후보

### 가운데 뷰어

채팅 폴더를 선택하면 “채팅 작업 요약” 뷰를 보여준다.

## 16. 에이전트 컨텍스트

에이전트는 현재 채팅 DB 메시지만 보는 것이 아니라, 채팅 폴더의 요약 파일도 함께 본다.

포함 대상:

- 현재 채팅의 `context.md`
- 현재 채팅의 `README.md`
- 현재 채팅의 `decisions.md`
- 현재 채팅의 accepted `rule-candidates.md`
- linked files 요약

## 17. API 초안

```http
POST /api/projects/{project_id}/chats
  -> DB 채팅 생성 + 사용자 playground의 50_chats 폴더 생성

PATCH /api/projects/{project_id}/chats/{chat_id}
  -> README.md title/status 갱신

POST /api/projects/{project_id}/chats/{chat_id}/sync-files
  -> DB 메시지/로그를 채팅 폴더 파일로 재생성

GET /api/projects/{project_id}/chats/{chat_id}/folder
  -> 채팅 폴더 경로와 파일 목록 반환

POST /api/projects/{project_id}/chats/{chat_id}/summarize
  -> 요약 파일 생성, context.md 갱신, 오래된 메시지 압축 처리

POST /api/projects/{project_id}/chats/{chat_id}/files/export
  -> 채팅 산출물을 다른 Playground 폴더로 복사하고 연결 관계 기록

POST /api/projects/{project_id}/chats/{chat_id}/promote
  -> Meta Clean Room 공유용 채팅 요약 승격 요청 생성

GET /api/projects/{project_id}/chats/{chat_id}/messages/{message_id}/debug-trace
  -> 디버그 모드가 켜진 턴의 LLM 요청/응답/tool trace 반환
```

## 18. 성공 기준

- 새 채팅을 만들면 사용자별 playground의 `50_chats/` 아래 폴더가 생긴다.
- 채팅 메시지가 `conversation.md`에 누적된다.
- 경로를 말하지 않은 파일 생성은 현재 채팅 폴더에 저장된다.
- 사용자가 명시한 Playground 경로는 그대로 따른다.
- 채팅에서 사용한 입력 파일과 생성한 산출물 관계가 `workspace_item_relations`에 남는다.
- 긴 채팅을 요약하면 `summaries/`와 `context.md`가 갱신된다.
- 사용자의 명확한 피드백이 `rule-candidates.md` 후보로 남는다.
- 생성된 보고서와 대시보드가 `artifacts.json`에 연결된다.
- 담당자가 바뀌어도 채팅 폴더만 열면 작업 목적, 결정, 산출물, 다음 액션을 이해할 수 있다.
- 팀 공유가 필요한 채팅 요약만 Meta Clean Room으로 승격할 수 있다.
- 디버그 모드가 켜진 턴은 사용자 메시지 클릭으로 LLM 교신 trace를 확인할 수 있다.
