# 개발 로드맵

## 1. 현재 위치

현재 구현된 기반:

- 프로젝트 워크스페이스
- 파일/폴더 트리
- 폴더 생성
- 파일 업로드
- 드래그앤드랍 업로드
- Excel -> CSV 변환
- Markdown/HTML/CSV/code preview
- 텍스트/CSV 편집
- 채팅 기반 에이전트
- DB 기반 채팅세션
- 작업모드/배포모드
- 스킬/툴/데이터소스 사이드 탭

다음 개발은 “파일 탐색기”를 “업무 하네스”로 바꾸는 일부터 시작한다.
제품 방향은 대행사 전용 자동화가 아니라, 화이트칼라 업무를 workflow와 의사결정 트리로 구조화하는 범용 자동화 플랫폼이다.
데이터소스 탭은 아직 표시 중심이므로, Google Drive 같은 외부 원천을 가져오기 중심으로 연결하는 단계가 필요하다.
이메일은 파일형 데이터소스보다 노이즈가 크므로, Gmail thread를 LLM triage하는 CRM형 업무 인박스로 별도 설계한다.

## 2. Phase 1: 하네스 폴더 템플릿

목표:

- 프로젝트 생성 후 업무용 기본 폴더 구조를 만들 수 있다.
- 사용자가 선택한 템플릿에 따라 폴더가 생성된다.

기능:

- 하네스 템플릿 선택 UI
- 기본 폴더 생성 API
- Project Fork / Template Engine
- 성공 프로젝트의 Meta Clean Room을 template으로 저장
- 새 프로젝트 생성 시 기존 meta template 적용
- `clean-room` 공식 기준 공간
- `clean-room/data` Data Clean Room
- `clean-room/meta` Meta Clean Room
- `playground/users/{user_id}` 사용자별 실험 공간
- Data Clean Room 아래 `00_inbox`, `10_sources`, `30_outputs`, `templates`
- Meta Clean Room 아래 `40_rules`, `45_skills`, `schemas`, `validators`, `triggers`, `hooks`, `policies`, `50_chats`
- User Playground 아래 `00_inbox`, `20_working`, `30_outputs`, `40_rules`, `45_skills`, `50_chats`
- `90_archive`
- `.haro/git/data-clean-room.git`, `.haro/git/meta-clean-room.git`
- 기존 프로젝트에도 템플릿 적용 가능

구현 후보:

- `POST /api/projects/{project_id}/harness/templates/apply`
- `POST /api/projects/{project_id}/harness/playgrounds`
- `POST /api/projects/{project_id}/harness/clean-room/checkpoint`
- `POST /api/projects/{project_id}/forks/templates`
- `POST /api/projects/from-template`
- 템플릿 정의 파일: `src/backend/app/harness_templates/*.json`

검증:

- 새 프로젝트에서 “주간 성과 보고” 템플릿 적용
- 폴더 트리에 Clean Room과 내 Playground 기본 구조 표시
- Data/Meta Clean Room 내부 Git 초기화
- 마이그레이션 전 checkpoint 생성과 실패 시 rollback 확인
- 성공 프로젝트에서 meta template 생성
- 새 프로젝트에 meta template 적용
- Data Clean Room 실제 데이터와 User Playground가 fork되지 않는지 확인

## 3. Phase 2: 업로드 파일 분류

목표:

- 업로드 파일을 inbox에 받고 파일 종류를 자동 추정한다.
- 사용자가 정리 제안을 승인하면 적절한 폴더로 이동한다.

기능:

- 파일 메타데이터 생성
- Excel 원본/CSV 변환본 관계 저장
- 파일 종류 추정
- 정리 제안 UI

파일 종류 v1:

- `media_report`
- `previous_report`
- `creative_brief`
- `review_data`
- `cs_data`
- `unknown`

검증:

- Excel 업로드 후 시트별 CSV가 `derived` 상태로 표시
- 사용자가 정리 제안을 승인하면 파일 위치 변경

## 3.5 Phase 2.5: Google Drive 데이터소스 가져오기

목표:

- Google Drive를 haro 내부 파일시스템이 아니라 외부 데이터소스로 연결한다.
- 사용자가 선택한 Drive 파일을 사용자 Playground inbox로 가져온다.
- Clean Room 반영은 기존 Data Clean Room 승격 흐름을 사용한다.

기능:

- Google Drive OAuth 연결
- 개인 Drive 또는 Shared Drive 폴더 연결
- 데이터소스 탭에서 Drive 파일 탐색과 검색
- 선택 파일 가져오기
- Google Sheets/Docs/Slides export
- Drive 원본 메타데이터 저장
- 수동 새로고침과 변경 감지
- `google_drive_folder_changed` trigger 초안

검증:

- Drive 연결 후 파일 목록이 데이터소스 탭에 표시
- 선택 파일이 `playground/users/{user_id}/00_inbox/google-drive/{connection_name}/` 아래 생성
- Google Sheets를 `.xlsx` 또는 `.csv`로 가져오기
- 가져온 파일에 Drive 원본 file id, URL, 수정 시각이 기록
- Drive 파일이 Clean Room에 직접 쓰이지 않는지 확인
- Project Fork 시 Drive token과 실제 file id가 제외되는지 확인

## 3.6 Phase 2.6: Gmail CRM형 업무 인박스

목표:

- Gmail thread를 업무 요청 단위로 묶는다.
- label 설정에 의존하지 않고 LLM이 제목, 본문, thread history를 읽어 triage한다.
- v1은 “명확한 요청 메일만 집중”한다.
- haro는 응답 초안까지 만들고 최종 발송은 사람이 한다.

기능:

- Gmail OAuth 연결
- recent inbox/thread fetch
- Gmail thread id 기반 thread grouping
- LLM triage
- `clear_request`, `needs_context`, `informational`, `notification`, `newsletter`, `personal_or_sensitive`, `irrelevant` 분류
- 핵심 내용, 기대 액션, 결과물, 일정 추출
- 첨부파일 snapshot 저장
- 추천 workflow/skill 연결
- `draft-reply.md` 생성
- `gmail_clear_request_detected` trigger 초안

검증:

- label 설정 없이 명확한 요청 메일이 `clear_request`로 분류
- confidence가 낮은 메일은 `needs_context`로 이동
- 핵심 내용, 기대 액션, 결과물, 일정이 구조화
- 응답 초안이 생성되지만 자동 발송하지 않음
- Project Fork 시 Gmail token, thread id, raw email, attachments가 제외되는지 확인

## 3.7 Phase 2.7: Human Context / 사람 맥락 분석

목표:

- 사용자 자신과 주요 커뮤니케이션 대상의 관찰 가능한 업무 선호를 숨은 맥락으로 관리한다.
- 사람 맥락은 답장 초안, 우선순위 판단, 누락 맥락 보강에만 사용한다.
- 성격 단정, 심리 진단, 민감 신원 추정, 조작적 설득 전략은 금지한다.

기능:

- `.haro/context/self/{user_id}.json`
- `.haro/context/contacts/{contact_hash}.json`
- `self_profile`, `contact_profile` 후보 생성
- Gmail thread 상세에서 “haro가 참고한 사람 맥락” 요약 표시
- 사람 맥락 수정, 삭제, 비활성화
- workflow LLM 태스크의 선택적 `human_context` 입력

검증:

- 사용자의 반복 피드백이 `self_profile` 후보로 저장
- 주요 연락처의 업무 선호가 `contact_profile` 후보로 저장
- 낮은 confidence 또는 미검증 맥락은 중요한 결정 근거로 사용하지 않음
- 사람 맥락이 Project Fork, template package, Clean Room Git에 포함되지 않음

## 4. Phase 3: 자연어 규칙 추출

목표:

- 사용자의 피드백을 규칙 후보로 추출한다.
- 채팅세션의 주요 결정과 규칙 후보를 파일로 남긴다.

기능:

- 채팅 메시지에서 규칙 후보 감지
- 채팅 폴더의 `conversation.md`, `decisions.md`, `rule-candidates.md` 갱신
- 규칙 유형 분류
- 적용 범위 질문
- 규칙 후보 카드 표시

규칙 유형 v1:

- 데이터 규칙
- 산출물 규칙
- 판단 규칙
- 메시지 규칙
- 실행 규칙

검증:

```text
사용자: 네이버 파일에서 장바구니금액은 매출로 쓰면 안 돼.
```

haro가 데이터 규칙 후보를 생성해야 한다.

## 5. Phase 4: 채팅세션 파일화

목표:

- 채팅세션을 사용자별 playground의 `50_chats/` 아래 작업 폴더로 관리한다.
- DB 메시지와 에이전트 로그를 사용자가 읽을 수 있는 파일로 mirror한다.

기능:

- 새 채팅 생성 시 채팅 폴더 생성
- `README.md`, `conversation.md`, `decisions.md`, `rule-candidates.md`, `linked-files.json`, `artifacts.json`, `agent-log.md` 생성
- 메시지 추가 시 `conversation.md` append
- 도구 실행/산출물 생성 시 `linked-files.json`, `artifacts.json`, `agent-log.md` 갱신
- 채팅 삭제 시 폴더를 `90_archive/chats/`로 이동

검증:

- 새 채팅을 만들면 `playground/users/{user_id}/50_chats/{date}-{slug}/` 폴더가 생긴다.
- 사용자가 피드백을 남기면 규칙 후보 파일에 남는다.
- 생성된 보고서와 관련 입력 파일이 채팅 폴더에서 추적된다.
- 팀에 공유할 결정과 요약만 Meta Clean Room으로 승격할 수 있다.

## 6. Phase 5: 스킬 제작 워크벤치

목표:

- “어떤걸 자동화 해보고 싶으세요?”에서 시작해 업무 이해, 자료 수집, workflow 설계, 케이스 검증, 샌드박스 테스트까지 이어지는 스킬 제작 흐름을 제공한다.
- 사용자가 코드를 몰라도 input scheme, process, output scheme, objective, trigger, hook을 확정할 수 있다.

기능:

- 스킬 제작 대화 시작점
- 업무 이해 질문/응답
- 입력, 출력, 프로세스, 목적 산출물 생성
- 입력/출력 사례 추가 수집
- workflow 단위 태스크 설계
- 태스크별 input, output, type, process, validator 정의
- 태스크 type: `code`, `llm`, `decision`, `human_review`, `wait_event`, `router`, `merge`
- decision node와 human review node UI
- 케이스별 반복 검증과 회귀
- 샌드박스 테스트 폴더 제공
- Meta Clean Room 반영 요청
- `meta-clean-room` feature branch 기반 테스트/merge
- trigger 설정
- hook 설정
- 통지형 hook과 외부 서비스 연계형 hook 구분
- hook execution policy 설정
- 활성화/비활성화
- 버전 관리

저장 위치 v1:

```text
.haro/skills/registry.json
.haro/skills/{skill_id}/current.json
.haro/skills/{skill_id}/versions/v0.1.0/
.haro/skills/{skill_id}/sandbox/
```

검증:

- 사용자가 자동화하고 싶은 업무를 말하면 haro가 업무 이해 질문을 시작한다.
- 입력, 출력, 프로세스, 목적 산출물이 생성된다.
- 여러 케이스 자료를 기반으로 workflow와 validator가 만들어진다.
- 조건 분기와 사람 승인 단계가 workflow에 표현된다.
- 샌드박스에서 사용자가 직접 테스트한다.
- trigger와 hook을 설정한 뒤 스킬을 활성화한다.
- hook이 `auto`, `approval_required`, `draft_only`, `disabled` 중 하나의 실행 정책을 가진다.
- 변경 이력이 버전으로 남는다.
- 스킬 수정은 `clean-room/meta/45_skills`에 merge되기 전 테스트를 통과해야 한다.

## 7. Phase 6: Hook Integration

목표:

- workflow 실행 전후에 통지와 외부 서비스 연계를 정책 기반으로 실행한다.
- hook을 trigger와 명확히 구분한다.
- 외부 상태를 바꾸는 hook은 민감도와 정책을 기준으로 자동 실행 여부를 결정한다.

기능:

- 통지형 hook: `messenger_notify`, `email_notify`, `in_app_notify`
- 외부 서비스 연계형 hook: `http_request`, `google_drive_save`, `gmail_draft`, `gmail_send`, `webhook_emit`
- 실행 시점: `before_start`, `after_success`, `after_failure`, `after_human_review`, `on_deadline`
- 실행 정책: `auto`, `approval_required`, `draft_only`, `disabled`
- 외부 대상 allowlist
- hook 실행 로그와 실패 리포트
- Project Fork에서 token, secret, credential 제외

검증:

- Slack 같은 통지형 hook은 정책 충족 시 자동 실행
- Google Drive 저장 hook은 기본적으로 승인 후 실행
- Gmail 발송은 기본 초안 생성이며 pilot policy에서만 자동 실행
- 외부 API 호출 hook은 endpoint allowlist와 secret 분리 확인
- Project Fork 시 hook 템플릿은 포함되지만 token/secret은 제외

## 8. Phase 7: 하네스 기반 실행

목표:

- 에이전트가 파일 경로만 보는 것이 아니라 하네스 메타데이터와 활성 스킬을 보고 작업한다.

기능:

- 에이전트 시스템 컨텍스트에 하네스 요약 포함
- 현재 채팅 폴더의 `README.md`, `decisions.md`, accepted rule candidates 포함
- 활성 스킬 목록 포함
- 파일 묶음 단위 실행
- 산출물 패키지 생성

검증:

- “A광고주 주간 보고서 만들어줘” 요청 시 관련 파일 묶음과 스킬을 자동 선택
- 결과물에 적용 규칙 목록 표시

## 9. Phase 8: 검색과 대량 파일 대응

목표:

- 파일이 2,000개 이상이어도 쓸 수 있는 탐색/검색 UX를 만든다.

기능:

- 파일 검색 API
- limit/pagination
- ignore 규칙
- 하네스 메타데이터 기반 필터
- 채팅 폴더와 대화 요약 검색
- 최근 작업/관련 파일 우선 정렬

검증:

- 2,000개 파일이 있는 프로젝트에서 검색 응답이 빠르게 반환
- UI는 상위 100개 결과와 더 구체화 안내를 표시

## 10. 우선순위 제안

바로 개발할 순서:

1. 하네스 템플릿 적용
2. 사용자별 playground 생성
3. Data/Meta Clean Room 내부 Git 초기화
4. Clean Room checkpoint와 migration rollback
5. Project Fork / Meta Template Engine
6. `.haro/file_index.json` 메타데이터 저장
7. 업로드 파일 분류와 정리 제안
8. Google Drive 데이터소스 가져오기
9. Gmail CRM형 업무 인박스
10. Human Context / 사람 맥락 분석
11. `playground/users/{user_id}/50_chats/` 채팅세션 폴더 mirror
12. Data/Meta Clean Room 승격 요청
13. 범용 workflow task type 모델
14. decision/human_review node UI
15. 자연어 규칙 후보 카드
16. 스킬 제작 워크벤치
17. `.haro/skills/` 버전 저장 구조
18. 스킬 샌드박스 테스트 폴더
19. Hook Integration과 execution policy
20. 활성 스킬과 현재 채팅 폴더 요약을 에이전트 컨텍스트에 포함

초기 vertical 확산:

1. 대행사 광고주 A 프로젝트에서 workflow 성공
2. `agency/weekly-report` meta template 생성
3. 광고주 B~T 프로젝트 생성 시 template 적용
4. 각 광고주별 Data Clean Room과 User Playground는 독립 유지
5. 같은 구조를 HR, 재무, 법무 등 다른 vertical template family로 확장

## 11. 설계 결정 필요

다음 항목은 구현 전 결정이 필요하다.

| 항목 | 선택지 | 권장 |
| --- | --- | --- |
| 파일 메타 저장 | JSON 파일 / DB | v1은 JSON, 검색 커지면 DB |
| 스킬 저장 | Markdown / DB / 둘 다 | v1은 Markdown, UI 상태는 DB 가능 |
| 정리 실행 | 즉시 이동 / 사용자 승인 후 이동 | 사용자 승인 후 이동 |
| 공식/실험 공간 | 단일 폴더 / Clean Room+공용 Playground / Clean Room+사용자별 Playground | Clean Room+사용자별 Playground |
| Clean Room Git | 단일 Git / Data+Meta 별도 Git | Data+Meta 별도 Git |
| GitHub 연동 | 필수 / 선택 / 제외 | v1 제외 |
| Playground 버전 관리 | Git 관리 / 메타데이터만 / 없음 | 메타데이터만 |
| 프로젝트 fork | 전체 복제 / Meta만 template / Data 포함 | Meta만 template |
| 데이터소스 연동 | 양방향 동기화 / 가져오기 중심 / 검색만 | v1은 가져오기 중심 |
| Gmail 분류 | label 기반 / LLM triage / 수동 분류 | LLM triage, label은 약한 힌트 |
| Gmail 발송 | 자동 발송 / 승인 후 발송 / 초안만 | v1은 초안만, 사람 최종 발송 |
| 사람 맥락 범위 | 사용자만 / 사용자+주요대상 / 모든 등장인물 | 사용자+주요대상 |
| 사람 맥락 노출 | 완전 숨김 / 요약만 노출 / 항상 명시 | 요약만 노출, 수정/삭제 가능 |
| 사람 맥락 활용 | 초안/우선순위 / 스킬분기 / 자동행동 | v1은 초안/우선순위/맥락 보강 |
| hook 자동 실행 | 모두 수동 / 통지만 자동 / 정책별 자동 실행 | 정책별 자동 실행 |
| 외부 연계 hook | 초안만 / 승인 후 실행 / 조건부 자동 | 기본 승인 후, 낮은 민감도만 자동 |
| template 확산 | 단일 프로젝트 / 같은 vertical / cross-vertical | 같은 vertical 먼저, 이후 cross-vertical |
| 큰 파일 diff | Git diff / binary version-only / object store | v1은 binary version-only |
| 마이그레이션 복구 | 수동 백업 / checkpoint rollback | checkpoint rollback |
| 규칙 적용 | 자동 / 매번 확인 / 위험도별 | 위험도별 |
| Excel 원본 보관 | 보관 / 폐기 | 보관 권장 |
| 채팅 저장 | DB만 / 파일만 / DB+파일 mirror | DB+파일 mirror |
| 채팅 삭제 | 즉시 삭제 / archive 이동 | archive 이동 |
| 스킬 태스크 실행 | LLM만 / code만 / LLM+code / decision workflow | decision workflow |
| workflow node type | code/llm만 / decision 포함 / human review 포함 / 전체 노드 | code/llm/decision/human_review/wait_event/router/merge |
| 스킬 버전 저장 | 덮어쓰기 / 폴더 버전 | 폴더 버전 |
| trigger/hook 저장 | 스킬 내부 / 전역 설정 | 스킬 내부, registry 요약 |
