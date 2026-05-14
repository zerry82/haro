# Context Library Gmail 단계별 개발 태스크

## 0. 개발 기준

최신 UI 기준은 다음 와이어프레임 구조다.

```text
Top Bar
  └─ Workspace
      ├─ Activity Rail
      ├─ Mail Panel: 필터 + 메일 목록 + 메일 상세
      ├─ Mail Workbench: 상단 메뉴 + 메일 콘텐츠/검색/통계
      └─ Chat Panel: 대화 이력 + 대화/커맨드
```

상단 메뉴는 3개로 압축한다.

```text
메일 탐색 | 설정 | 통계
```

각 메뉴의 책임:

| 메뉴 | 책임 |
| --- | --- |
| `메일 탐색` | 메일 목록, 선택 메일 콘텐츠, 자연어 검색, 메일 기준 대화/커맨드 |
| `설정` | Gmail 연결, 최근 N개 분석 실행, 구조화 기준/필터/개선 후보 관리 |
| `통계` | 최근 분석 통계, 구조화 품질, 테스트 결과, 인사이트 요약 |

개발 전략은 mock-first가 아니라 Gmail fetcher-first로 둔다.
즉, 첫 번째 수직 슬라이스부터 실제 Google OAuth 연결과 Gmail 최근 N개 fetch를 통과해야 한다.
분석 개수 기본값은 50개이며, 테스트 목적에 맞게 UI에서 1~500개 사이로 조절할 수 있어야 한다.
mock 데이터는 UI 독립 개발과 테스트 fixture 용도로만 사용한다.

Phase 완료 원칙:

- 각 Phase는 백엔드/API만 끝내지 않고, 그 기능을 사용자가 볼 수 있는 최소 UI까지 같이 끝낸다.
- UI는 최종 화면을 한 번에 만들지 않고, 해당 Phase의 기능이 자연스럽게 드러나는 수준으로 점진적으로 확장한다.
- Phase가 끝났다고 말하려면 다음 세 가지가 모두 가능해야 한다.
  - API 또는 서비스 동작이 테스트로 검증된다.
  - 사용자가 화면에서 해당 기능의 상태, 성공, 실패를 이해할 수 있다.
  - 다음 Phase에서 UI를 버리고 다시 만들지 않아도 되도록 기존 화면 구조와 호환된다.
- 큰 레이아웃 재설계가 필요한 경우에도, 현재 Phase 기능에 해당하는 UI 상태는 먼저 완성한다.

v1에서 하지 않는 것:

- 라이브 polling
- 과거 기간 마이그레이션
- 항목별 승격/승인 플로우
- clean-room 요약 파일 생성
- 자동 메일 발송
- vector search

## 1. Phase 0 - 문서 정합성과 OAuth 전제 정리

목표:

- `spec.md`, `ui-design.md`, `user-scenario.md`가 같은 UI 구조와 같은 개발 전략을 보도록 맞춘다.
- `개요/최근 분석/구조화 테스트/자연어 검색/인사이트/테스트 결과`를 독립 상단 메뉴로 두는 표현을 제거하고, `메일 탐색/설정/통계` 3메뉴 아래의 하위 기능으로 재배치한다.
- Gmail 연결은 수동 token 입력이 아니라 Google OAuth 2.0 authorization code flow로 정의한다.

작업:

- `spec.md`의 화면 원칙과 정보 구조를 최신 와이어프레임 기준으로 수정한다.
- `ui-design.md`의 상단 메뉴를 3개로 압축한다.
- `user-scenario.md`에서 사용자가 클릭하는 메뉴명을 `메일 탐색`, `설정`, `통계` 기준으로 정리한다.
- Gmail 연결 설명을 `OAuth auth_url 생성 -> Google 동의 -> callback -> token 저장 -> MailConnection 갱신` 흐름으로 맞춘다.
- 기존 제외 범위인 라이브/마이그레이션/승격 플로우가 다시 들어가지 않았는지 확인한다.

완료 기준:

- 세 문서 모두 `메일 탐색 | 설정 | 통계`를 기준으로 설명한다.
- Gmail 연결은 `token_ref` 직접 입력이 아니라 OAuth flow로 설명된다.
- 문서 검색에서 `라이브`, `마이그레이션`, `승격`, `재통계`가 핵심 플로우로 등장하지 않는다.
- 구현자가 문서만 보고 같은 화면 구조와 같은 연결 방식을 떠올릴 수 있다.

검증:

```powershell
rg -n "라이브|마이그레이션|승격|재통계" .specs/draft/context-library-mail
rg -n "메일 탐색|설정|통계|OAuth|callback|fetcher" .specs/draft/context-library-mail
```

## 2. Phase 1 - Gmail OAuth 연결 기반

목표:

- 사용자가 `Gmail 연결`을 누르면 Google OAuth 화면으로 이동하고, callback 후 프로젝트의 Gmail 연결 상태가 `connected`가 된다.
- refresh token 원문은 애플리케이션 DB에 저장하지 않고 `token_ref`만 저장한다.

작업:

- 백엔드 설정 추가:

```env
GOOGLE_GMAIL_CLIENT_ID=
GOOGLE_GMAIL_CLIENT_SECRET=
GOOGLE_GMAIL_REDIRECT_URI=http://127.0.0.1:8001/api/auth/google/gmail/callback
GOOGLE_GMAIL_SCOPES=https://www.googleapis.com/auth/gmail.readonly
GOOGLE_OAUTH_STATE_SECRET=
MAIL_TOKEN_ENCRYPTION_KEY=
```

- `src/backend/app/config.py`에 Gmail OAuth 설정 필드를 추가한다.
- Google OAuth client 의존성을 추가한다.
  - 후보: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
- OAuth state 생성/검증 유틸을 만든다.
  - state에는 `project_id`, `user_id`, `return_url`, nonce, 만료 시간을 포함한다.
  - state는 서명해서 변조를 막는다.
- token 저장소를 만든다.
  - dev v1은 `MAIL_TOKEN_ENCRYPTION_KEY`로 암호화한 local token store를 사용한다.
  - `MailConnection.token_ref`에는 secret key/reference만 저장한다.
- API를 OAuth 방식으로 바꾼다.

```http
POST /api/projects/{project_id}/mail/gmail/connect
GET  /api/auth/google/gmail/callback
GET  /api/projects/{project_id}/mail/gmail/status
```

- `POST /connect`는 token을 받지 않고 `auth_url`을 반환한다.
- callback은 Google code를 token으로 교환하고, 연결 계정 이메일을 확인한 뒤 `MailConnection`을 갱신한다.
- callback 성공 후 프론트의 메일 관리 화면으로 돌아갈 수 있게 redirect한다.
- UI는 `설정` 또는 현재 메일 패널의 Gmail 영역에서 OAuth 연결 상태를 표현한다.
  - 미설정: OAuth 환경변수/암호화 키가 필요하다는 오류를 표시한다.
  - 미연결: `Gmail 연결` CTA와 읽기 전용 안내를 표시한다.
  - 연결 진행: Google 동의 화면으로 이동 중임을 표시한다.
  - callback 성공: 연결된 이메일과 `읽기 전용` 권한을 표시한다.
  - callback 실패/취소: 재시도 가능한 오류 메시지를 표시한다.

완료 기준:

- `Gmail 연결` 클릭 시 Google OAuth URL이 열린다.
- Google 동의 후 haro로 돌아온다.
- `GET /gmail/status`가 connected 상태와 연결 이메일을 반환한다.
- DB에는 refresh token 원문이 저장되지 않는다.
- OAuth 실패, state 만료, 사용자가 동의를 취소한 경우 오류 상태가 표현된다.
- 화면에서 연결 상태, 연결 계정, 읽기 전용 권한, 재시도 액션을 확인할 수 있다.

검증:

- OAuth state 생성/검증 단위 테스트
- token store 저장/조회/삭제 단위 테스트
- callback 성공/실패 API 테스트
- 수동 확인: 개인 Gmail test user로 로컬 OAuth 왕복
- 프론트엔드 테스트/빌드

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest
```

## 3. Phase 2 - Gmail Fetcher와 Workspace Snapshot Cache

목표:

- 연결된 Gmail 계정에서 최근 N개 message/thread를 실제로 가져온다.
- 기본값은 50개이며, UI와 API에서 수집 개수를 조절할 수 있다.
- 가져온 thread는 워크스페이스의 숨김 시스템 영역에 snapshot으로 저장해 다시 fetch하지 않아도 재분석할 수 있게 한다.
- 이 단계에서는 분석 품질보다 안정적인 fetch, 정규화, cache 재사용, 중복 방지가 우선이다.

작업:

- `GmailFetcher` 서비스를 만든다.
- `MailSnapshotStore` 서비스를 만든다.
  - 저장 위치: `/.haro/cache/mail/gmail/{account_hash}/threads/{source_ref}.json`
  - index 위치: `/.haro/cache/mail/gmail/{account_hash}/index.json`
  - `.haro` 내부 캐시이므로 파일 목록, agent tool, clean-room에는 노출하지 않는다.
- token store의 `token_ref`로 Google credential을 복원한다.
- 만료된 access token은 refresh token으로 갱신한다.
- Gmail API에서 최신 메시지를 조회하고 thread를 중복 제거해 `max_threads` 개수만큼 수집한다.
  - 기본값: `max_threads=50`
  - 허용 범위: 1~500
  - 날짜 기반 `newer_than` query는 v1 테스트 경로에서 사용하지 않는다.
  - message list pagination 처리
  - unique `threadId`로 묶기
- 각 thread의 상세를 가져온다.
  - subject
  - from
  - to/cc
  - date
  - snippet
  - text/plain body
  - text/html body의 안전한 text 변환
  - attachment filename, mime type, size, attachment id
- 원문 body는 분석 입력으로만 사용하고, `clean-room`에는 쓰지 않는다.
- 원문 body snapshot은 `.haro/cache`에만 제한 저장하고, clean-room summary나 Team Context Library에는 쓰지 않는다.
- snapshot에는 OAuth token, raw Gmail thread/message id, 원본 첨부 파일을 넣지 않는다.
- 긴 body는 분석용 길이 제한을 둔다.
- Gmail idempotency key를 만든다.
  - 예: `gmail:{account_email}:{thread_id}`
- fetch 결과를 내부 `MailThreadInput` 형태로 변환하는 adapter를 만든다.
- 실제 Gmail API 호출은 interface 뒤에 숨겨 테스트에서 fake client를 주입한다.
- `POST /analyze-recent`는 `force_refresh=false`를 기본값으로 둔다.
  - 캐시가 충분하면 Gmail API를 호출하지 않고 snapshot에서 분석한다.
  - 캐시가 부족하면 Gmail API를 호출하고 snapshot을 upsert한 뒤 분석한다.
  - `force_refresh=true`면 캐시가 충분해도 Gmail API를 다시 호출한다.
- UI는 최근 N개 분석 버튼, `Gmail 다시 가져오기` 버튼, 개수 입력, cache/fetch 상태를 표시한다.
  - 연결 전에는 수집 버튼을 비활성화한다.
  - cache-first 분석 중인지, Gmail에서 다시 가져오는 중인지 메시지를 구분한다.
  - 수집 완료 후 가져온 thread 수, 첨부 수, 마지막 수집 시각을 표시한다.
  - Gmail API 오류, 권한 만료, 빈 메일함을 서로 다른 빈/오류 상태로 표시한다.

완료 기준:

- `analyze-recent`가 빈 mock input 없이 실제 Gmail fetcher를 호출할 수 있다.
- 캐시가 충분하면 `analyze-recent`가 Gmail fetcher를 호출하지 않고 snapshot만으로 분석 run을 만들 수 있다.
- `Gmail 다시 가져오기`는 `force_refresh=true`로 Gmail fetcher를 호출하고 snapshot을 갱신한다.
- 최근 N개 thread가 `MailAnalysisRun`과 thread staging/structured row로 저장된다.
- 같은 thread를 다시 가져와도 snapshot index와 staging 분석 결과의 중복이 폭증하지 않는다.
- 첨부파일은 최소한 제목, 확장자, mime type, 용량, 연결 thread를 가진다.
- Gmail API 장애, 권한 만료, rate limit, 빈 메일함 상태를 구분해서 반환한다.
- 화면에서 최근 N개 수집 상태, 수집 개수, 수집 결과 수치를 확인할 수 있다.

검증:

- fake Gmail client 기반 fetcher 단위 테스트
- snapshot store 저장/조회/upsert/index 정렬 단위 테스트
- cache hit/cache miss/force refresh 분석 흐름 테스트
- pagination 테스트
- thread id 중복 제거 테스트
- header/body/attachment parsing 테스트
- 수동 확인: 본인 Gmail 최근 N개 fetch

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest
```

## 4. Phase 3 - LLM 기반 비동기 Gmail 구조화 분석

목표:

- `최근 N개 분석` 클릭 즉시 `MailAnalysisRun`을 만들고, 실제 구조화 분석은 백그라운드 job으로 실행한다.
- fetcher/cache에서 가져온 thread를 LLM 구조화 서비스에 전달해 요청사항, due date, 구조화 경고, confidence를 추출한다.
- UI는 완료 응답을 기다리지 않고 run 상태를 polling하며 진행 단계를 보여준다.

작업:

- `POST /analyze-recent`는 `queued` run을 생성한 뒤 즉시 응답한다.
- in-process async background task를 실행한다.
  - 서버 재시작 내구성은 v1 범위 밖이다.
- job 상태를 DB에 기록한다.
  - `queued`
  - `fetching`
  - `normalizing`
  - `structuring`
  - `indexing`
  - `completed`
  - `failed`
- 실패 시 `stats_json.error`에 실패 stage와 사용자 표시용 message를 남긴다.
- cache-first fetch 정책은 유지한다.
  - 기본 분석은 snapshot 우선
  - `Gmail 다시 가져오기`는 `force_refresh=true`
- `MailStructuringService`를 추가한다.
  - 기존 Gemini client와 `gemini-3-flash-preview`를 사용한다.
  - 10개 thread 단위 batch로 요청한다.
  - strict JSON 응답을 파싱한다.
  - batch 실패 시 해당 batch는 fallback warning과 낮은 confidence로 처리한다.
- LLM prompt에는 token, raw Gmail id, 원문 전체를 넣지 않는다.
- body는 길이 제한 sample만 전달한다.
- 분석 파이프라인을 Gmail payload에 맞춘다.
  - thread summary
  - sender/recipient normalization
  - sender domain
  - attachment metadata
  - request/action extraction
  - due date extraction
  - category proposal
  - confidence
- thread 상세 조회 API를 추가한다.

```http
GET /api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads
GET /api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads/{thread_id}
GET /api/projects/{project_id}/mail/gmail/analysis/{run_id}/attachments
```
- UI는 분석 run 결과를 즉시 볼 수 있게 한다.
  - 분석 중 단계 표시
  - thread 수, sender 수, 첨부 수, 요청사항/일정 수 요약
  - 분석 완료 후 첫 thread 목록 표시
  - 분석 실패 시 실패 단계와 재시도 버튼 표시
  - polling 상태 문구: 수집 중, 정규화 중, LLM 구조화 중, 저장 중, 완료, 실패

완료 기준:

- `POST /analyze-recent`가 완료까지 block하지 않고 진행 중 run을 반환한다.
- 연결된 계정에서 `최근 50개 분석` 또는 사용자가 조절한 개수로 실제 Gmail thread 기반 비동기 분석 run이 생성된다.
- run 상태가 `queued -> fetching -> normalizing -> structuring -> indexing -> completed/failed`로 갱신된다.
- 분석 결과에 sender, thread, category, attachment, extracted action, due date 통계가 포함된다.
- thread metadata에 `extracted_actions`, `extracted_due_dates`, `structure_warnings`, `confidence`가 포함된다.
- thread 목록과 상세 API가 실제 분석 결과를 반환한다.
- 원문 전체와 refresh token은 응답에 포함되지 않는다.
- 화면에서 분석 run의 진행 상태, 완료 요약, action/due date/warning 통계를 확인할 수 있다.

검증:

- LLM 구조화 JSON 파싱/fallback/batch/body limit 단위 테스트
- action/due date/warning 통계 단위 테스트
- cache hit/force refresh job 흐름 테스트
- 진행 중 run/status API 테스트
- thread 목록/상세/첨부 API 테스트
- 실제 Gmail test account smoke test

## 5. Phase 4 - 메일 관리 레이아웃 셸과 연결 상태 UI

목표:

- `메일 관리` 선택 시 기존 파일 뷰어 중앙 빈 화면 대신 메일 전용 레이아웃이 열린다.
- UI는 처음부터 실제 `gmail/status` API를 읽는다.
- 이전 Phase에서 만든 Gmail 연결/수집/분석 UI를 버리지 않고 새 레이아웃 안으로 이동한다.

작업:

- `WorkspaceMailShell` 컴포넌트를 만든다.
- `Activity Rail`에서 메일 메뉴 선택 시 `WorkspaceMailShell`을 렌더링한다.
- 왼쪽 영역을 `MailPanel`로 분리한다.
- 중앙 영역을 `MailWorkbench`로 분리한다.
- 오른쪽 채팅 패널은 기존 구조를 유지하되, 메일 모드에서도 보이게 한다.
- 중앙 상단에 `메일 탐색`, `설정`, `통계` segmented/tab 메뉴를 만든다.
- `설정` 메뉴에 Gmail 연결 상태 카드를 연결한다.
- `Gmail 연결` 버튼은 `POST /connect`로 받은 `auth_url`을 연다.

완료 기준:

- `메일 관리` 클릭 시 중앙에 “파일을 선택하세요”가 보이지 않는다.
- 상단 메뉴 3개가 보인다.
- 오른쪽 채팅 패널은 사라지지 않는다.
- Gmail 미연결/연결됨/오류 상태가 실제 API 상태로 표시된다.
- 파일/스킬/툴 탭의 기존 동작은 유지된다.

검증:

- 프론트엔드 테스트/빌드 성공
- 수동 확인: `폴더 -> 메일 관리 -> 폴더` 전환 시 레이아웃이 깨지지 않음

```powershell
cd src/frontend
npm test
npm run build
```

## 6. Phase 5 - 실제 메일 목록/상세 UI

목표:

- 사용자가 실제 Gmail 최근 분석 결과에서 메일 목록을 보고, 메일을 선택해 상세를 확인한다.

작업:

- `MailThreadList` 컴포넌트 추가
- `MailThreadDetail` 컴포넌트 추가
- `stores/mail.ts`를 최신 API에 맞게 재정리한다.
- 최근 분석 실행
- thread 목록 로딩
- thread 상세 로딩
- attachment 목록 로딩
- 목록 필터 UI 추가
  - 전체
  - 구조화 좋음
  - 주의 필요
  - 첨부 있음
  - 일정 있음
  - 요청사항 있음
- thread row 정보 표시
  - 상태 badge
  - 보낸사람
  - 제목
  - 짧은 요약
  - 요청사항 수
  - 일정 여부
  - 첨부 여부
  - 수신일
- 선택한 thread 상세 표시
  - 제목
  - 보낸사람/받은사람
  - 수신일
  - 카테고리
  - 구조화 상태
  - 요약
  - snapshot에 저장된 메일 본문 전문
  - HTML 메일 원본 렌더러와 텍스트 fallback 전환
  - 요청사항
  - 일정
  - 첨부 파일 메타데이터와 가능한 경우 파일 요약
  - 주의 이유

완료 기준:

- `최근 N개 분석` 버튼이 실제 Gmail fetch + analysis API를 호출한다.
- 분석 run이 있으면 실제 메일 목록이 표시된다.
- 메일 목록에서 항목을 클릭하면 왼쪽 상세와 중앙 콘텐츠가 바뀐다.
- 메일 상세에서 본문 전문, HTML 원본 렌더러, 첨부 파일 목록을 함께 확인할 수 있다.
- 필터를 누르면 목록이 바뀐다.
- 선택된 메일 row가 시각적으로 표시된다.
- 좁은 패널에서도 텍스트가 겹치지 않는다.

검증:

- 필터 유틸 단위 테스트
- 프론트엔드 테스트/빌드 성공
- 백엔드 테스트 성공
- 수동 확인: 실제 Gmail 최근 N개 분석 후 목록/상세 표시

## 7. Phase 6 - 상단 메뉴별 중앙 화면과 API 연결

목표:

- `메일 탐색`, `설정`, `통계` 메뉴의 중앙 화면을 실제 API와 연결한다.

작업:

### 메일 탐색

- 선택 메일 콘텐츠 영역
- 구조화 요약
- 요청사항/일정/첨부 섹션
- 자연어 검색 입력창
- 추천 질문
- 검색 결과 카드
- `이 메일 기준으로 질문하기` 버튼

### 설정

- Gmail 연결 상태 카드
- 최근 N개 분석 실행 카드
- 구조화 기준 요약
- 카테고리 후보 요약
- 개선 후보 목록
- 분석 전/분석 중/분석 후 상태별 CTA

### 통계

- 전체 thread
- 구조화 완료
- 주의 필요
- 첨부파일
- 요청사항
- 일정
- 테스트 성공/주의/실패
- 인사이트 요약

완료 기준:

- 상단 메뉴를 누르면 중앙 화면이 바뀐다.
- 선택된 메일은 `메일 탐색` 화면에 반영된다.
- `설정` 화면에서 Gmail 연결/분석 상태가 실제 API 기준으로 보인다.
- `통계` 화면에서 구조화 품질과 테스트 결과가 한눈에 보인다.
- loading/error/empty 상태가 각각 다르게 표현된다.

검증:

- 프론트엔드 테스트/빌드 성공
- 수동 확인: 메뉴 전환, 선택 메일 유지, 채팅 패널 유지

## 8. Phase 7 - 자연어 검색, 인사이트, 구조화 품질 테스트

목표:

- 실제 Gmail 분석 결과를 대상으로 자연어 검색과 인사이트 질의를 실행한다.
- 사용자가 결과 품질을 평가하고 개선 후보로 남기는 루프를 완성한다.
- 1차 구현은 LLM 인사이트가 아니라 staging thread 통계를 기반으로 한 deterministic 인사이트 API로 시작한다.

작업:

- 1차 검색 API를 구현/정렬한다.

```http
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/search
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/insights
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/improvement-candidates
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/improvement-candidates
```

- `run_id=latest` 또는 agent 내부 호출에서는 최신 completed run을 기본 검색 대상으로 사용한다.
- 검색 대상은 subject, sender, recipients, summary, category, attachment metadata/summary, extracted action/due date/warning이다.
- 오른쪽 채팅에서 메일 관련 질문을 하면 `file_search`가 아니라 `mail_search` agent tool을 선택한다.
- 메일 관리 화면에서 채팅 요청을 보낼 때 latest run과 선택 thread context를 함께 보낸다.
- SQLite FTS5 기반 검색 인덱스를 만든다. 1차 구현에서는 staging row 직접 검색으로 동작시키고, 검색량이 커질 때 FTS5로 교체한다.
- 검색 결과에 근거 thread와 구조화 근거를 포함한다.
- 인사이트 결과에 대표 thread, 근거 수, 관련 첨부, 주의 표시를 포함한다.
- 검색/인사이트 결과의 품질 판단은 `MailStructureTest`에 저장한다.
- `일부 아쉬움` 또는 `부정확함` 평가는 `MailImprovementCandidate`로 저장할 수 있다.
- 검색 결과 품질 판단 UI
  - 정확함
  - 일부 아쉬움
  - 부정확함
- 인사이트 결과 품질 판단 UI
- `개선 후보로 저장` 액션
- 개선 후보 목록
- 관련 질문, 관련 thread, 원인, 우선순위 저장
- `통계` 메뉴에서 테스트 결과 요약 표시

완료 기준:

- 실제 분석 run에 대해 자연어 검색을 실행할 수 있다.
- 검색 결과는 파일 경로가 아니라 업무 지식 중심으로 표시된다.
- 사용자가 검색/인사이트 결과를 개선 후보로 저장할 수 있다.
- 개선 후보는 `통계` 메뉴에서 볼 수 있다.
- 개선 후보는 관련 query/thread 근거를 포함한다.
- 개선 후보 저장이 메일 원문을 복사하지 않는다.

검증:

- 검색 인덱스 단위 테스트
- 백엔드 개선 후보 API 테스트
- 프론트 저장/목록 렌더 테스트

## 9. Phase 8 - 채팅과 중앙 워크벤치 상호작용

목표:

- 중앙 워크벤치와 오른쪽 채팅이 같은 선택 메일/분석 run/query를 공유한다.
- 채팅 입력 영역과 사용자 메시지에 현재 메일 컨텍스트가 보이게 한다.

작업:

- 선택 메일 context를 전역 또는 상위 상태로 올린다.
- `이 메일 기준으로 질문하기` 클릭 시 채팅 입력에 context chip 표시
- 중앙 검색 실행 시 오른쪽 채팅에 query 연결
- 채팅 답변에서 `워크벤치에서 보기`, `메일 상세 보기` 액션 제공
- 채팅에서 메일 관련 질문을 하면 중앙 메뉴를 `메일 탐색` 또는 `통계`로 전환할 수 있는 이벤트 설계

완료 기준:

- 왼쪽에서 메일 선택 후 오른쪽 채팅이 선택 메일을 인식한다.
- 중앙 결과 카드에서 채팅으로 이어 질문할 수 있다.
- 채팅 입력의 `워크벤치에서 보기`로 메일 워크벤치를 다시 열 수 있다.
- 중앙과 오른쪽이 서로 다른 메일을 보고 있다는 혼란이 없다.

검증:

- 상태 유틸 테스트
- 수동 확인: 선택 메일 변경, 질문하기, 답변에서 상세 열기

## 10. Phase 9 - 시각 품질과 사용성 다듬기

목표:

- 업무 도구처럼 조용하고 밀도 있게 보이도록 화면 품질을 다듬는다.
- 좁은 화면에서 메일 목록/상세/검색/인사이트/채팅 입력이 겹치지 않도록 한다.

작업:

- 패널 너비와 overflow 정리
- 메일 목록 가상 스크롤 또는 pagination 검토
- 긴 이메일/제목/file name ellipsis와 tooltip
- 상태 badge 색상 정리
- 빈 상태/오류 상태 문구 정리
- keyboard focus
- 버튼 tooltip
- 모바일 또는 좁은 화면 대응 범위 결정
- 상단 탭, 검색 결과, 인사이트 카드, 메일 상세, 채팅 context chip 반응형 처리

완료 기준:

- 텍스트가 버튼/패널 밖으로 튀지 않는다.
- 메일 목록과 상세, 중앙, 채팅 패널이 서로 겹치지 않는다.
- 필수 상태가 색상뿐 아니라 텍스트로도 구분된다.
- 프론트 빌드가 통과한다.

검증:

```powershell
cd src/frontend
npm test
npm run build
```

## 11. Phase 10 - 문서와 테스트 마감

목표:

- 실제 구현 결과와 스펙/시나리오/UI 설계를 맞춘다.

작업:

- `spec.md` 구현 결과 반영
- `ui-design.md` 구현과 달라진 점 반영
- `user-scenario.md` 실제 클릭 흐름과 맞추기
- `doc/src/README.md` 업데이트
- backend/frontend 검증 결과 기록

완료 기준:

- 사용자가 문서만 보고 현재 UI를 이해할 수 있다.
- 구현된 API와 문서 API가 맞다.
- Gmail OAuth/fetcher 설정 방법이 문서화되어 있다.
- 테스트 명령과 결과가 기록되어 있다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd ../frontend
npm test
npm run build
```

## 12. Phase 11 - ChromaDB 기반 메일 벡터 검색

목표:

- 메일 검색을 단순 키워드 포함 방식에서 ChromaDB 기반 hybrid vector retrieval로 개선한다.
- 의미가 비슷하지만 단어가 정확히 일치하지 않는 업무 질문도 구조화된 메일에서 찾을 수 있게 한다.
- 의미 검색 설정이 준비되지 않은 환경에서는 조용히 텍스트 검색으로 대체하지 않고, 설정 오류를 명확히 표시한다.

작업:

- `chromadb` 의존성 추가
- 워크스페이스별 Chroma 저장 위치를 `.haro/db/chroma/mail`로 정의
- completed analysis run의 staging thread를 run별 collection으로 인덱싱
- embedding 문서에는 제목, 발신자, 수신자, 요약, 카테고리, 요청사항, 마감, 첨부 요약, 구조화 경고만 포함
- raw Gmail id, OAuth token, 원문 body 전체, 원본 첨부파일은 벡터 문서에서 제외
- `mail_search`가 ChromaDB vector hit와 기존 text score를 결합해 정렬
- API 응답에 `retrieval.mode`, `vector_score`, `text_score` 표시
- ChromaDB/embedding 실패 시 검색 실패 사유를 사용자에게 표시
- 프론트 검색 결과에 vector 검색 여부와 오류 사유 표시

완료 기준:

- `POST /analysis/{run_id}/search`가 가능한 경우 `hybrid_vector` 검색 결과를 반환한다.
- ChromaDB가 설치되지 않았거나 embedding 설정이 없으면 검색 API가 명확한 오류를 반환한다.
- 검색 인덱스에 원문 메일 전체와 raw Gmail id가 들어가지 않는다.
- agent tool `mail_search`도 동일한 hybrid retrieval 결과를 사용한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd ../frontend
npm test
npm run build
```

## 13. Phase 12 - 마지막 처리 이후 추가 메일 구조화

목표:

- 최신 completed 분석 run 이후 새로 도착한 Gmail thread를 확인하고, 필요한 경우 그 thread만 추가 구조화한다.
- 사용자가 바로 구조화를 시작하지 않고, 먼저 “몇 개가 추가되었는지” 확인한 뒤 진행 여부를 결정하게 한다.
- 기존 최근 N개 전체 분석을 반복하지 않고, 증분 메일만 별도 run으로 처리한다.

작업:

- `POST /mail/gmail/incremental/preview` API 추가
  - 최신 completed run의 가장 최근 `received_at`과 이미 처리된 `source_ref`를 기준으로 신규 thread 후보 계산
  - Gmail에서 최근 `scan_limit`개를 확인하고 snapshot cache를 갱신
  - 신규 thread 개수, 마지막 처리 시각, 확인한 thread 수, 일부 미리보기 반환
- `POST /mail/gmail/incremental/analyze` API 추가
  - preview와 같은 기준으로 신규 thread를 계산
  - 신규 thread가 있으면 `incremental:*` range의 분석 run 생성
  - 기존 비동기 구조화 job에 신규 thread payload만 넘겨 `queued -> ... -> completed` 흐름으로 처리
- UI 설정 탭에 `추가 메일 구조화` 버튼 추가
  - 클릭 시 preview API 호출
  - 모달에서 추가된 메일 개수와 미리보기 표시
  - `아니요`는 닫기, `예, 구조화 진행`은 증분 분석 시작

완료 기준:

- 최신 완료 분석 이후 추가된 메일 개수를 모달에서 확인할 수 있다.
- 사용자가 `예`를 선택한 경우에만 증분 구조화 run이 생성된다.
- 추가된 메일이 없으면 구조화 버튼은 실행되지 않고 안내만 표시된다.
- 기존 최근 N개 분석, Gmail 다시 가져오기, 메일 목록/상세 UI는 그대로 동작한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd ../frontend
npm test
npm run build
```

## 14. Phase 13 - Gmail 첨부파일 다운로드/추출/검색 통합

목표:

- 분석 대상 메일의 Gmail 첨부파일을 실제 사용자 `00_inbox`에 저장한다.
- 저장된 첨부에서 텍스트/표/PDF/이미지 맥락을 추출해 메일 구조화, ChromaDB 검색 문서, 채팅 답변에 반영한다.
- 본문이 “첨부 확인” 수준인 메일도 첨부 요약을 기준으로 검색 가능하게 한다.

작업:

- Gmail attachment API로 첨부 binary를 다운로드한다.
- 저장 위치를 `/playground/users/{user_id}/00_inbox/mail/gmail/{YYYY-MM-DD}/{subject}/{filename}`로 둔다.
- 같은 파일명은 suffix로 dedupe한다.
- 저장 후 workspace file DB를 sync하고 file summary를 갱신한다.
- 지원 확장자를 추출/요약한다.
  - `txt`, `md`: 텍스트 preview
  - `csv`: 컬럼, 샘플 행, preview
  - `xlsx`, `xls`: sheet/컬럼/샘플
  - `pdf`: pypdf 텍스트 추출, 스캔본 상태 표시
  - `png`, `jpeg`, `jpg`: Gemini Vision 요약
- deterministic blacklist/manual excluded 메일은 다운로드하지 않는다.
- 첨부 요약과 content profile을 LLM 구조화 prompt와 `mail_core_text`에 포함한다.
- `mail_attachment_read` 도구와 첨부 상세 API를 추가한다.
- 메일 상세 UI에 저장 경로, 다운로드 상태, 추출 상태, 요약, 주요 포인트를 표시한다.

완료 기준:

- 최근 N개 분석 후 대상 메일의 첨부가 `00_inbox`에 저장된다.
- 첨부 요약이 `summary`, `key_points`, `content_profile`에 남는다.
- ChromaDB 검색 문서와 텍스트 검색 대상에 첨부 추출 내용이 포함된다.
- raw Gmail id, OAuth token, 원본 binary는 API/Chroma 응답에 노출되지 않는다.
- 채팅에서 특정 thread의 첨부 내용을 물으면 `mail_attachment_read` 결과를 근거로 답할 수 있다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd ../frontend
npm test
npm run build
```

## 15. 권장 개발 순서 요약

1. 문서 정합성과 OAuth 전제 정리
2. Gmail OAuth 연결 기반
3. Gmail fetcher와 최근 N개 수집
4. 실제 Gmail 데이터 기반 최근 분석
5. 메일 관리 레이아웃 셸과 연결 상태 UI
6. 실제 메일 목록/상세 UI
7. 상단 3메뉴 중앙 화면과 API 연결
8. 자연어 검색, 인사이트, 구조화 품질 테스트
9. 채팅-워크벤치 상호작용
10. 시각 품질/사용성 다듬기
11. 문서/테스트 마감
12. ChromaDB 기반 메일 벡터 검색
13. 마지막 처리 이후 추가 메일 구조화
14. Gmail 첨부파일 다운로드/추출/검색 통합

가장 먼저 구현할 최소 수직 슬라이스:

```text
메일 관리 클릭
  -> 설정 탭에서 Gmail 연결 클릭
  -> Google OAuth 동의
  -> callback 후 connected 상태 표시
  -> 최근 N개 분석 클릭
  -> Gmail fetcher가 실제 thread 수집
  -> 분석 run 생성
  -> 왼쪽에 실제 메일 목록 표시
  -> 메일 선택
  -> 중앙 메일 탐색 화면에 선택 메일 콘텐츠 표시
  -> 오른쪽 채팅 패널 유지
```

이 슬라이스가 완성되면 연결, 수집, 분석, 목록, 상세, 채팅 공존까지 한 번에 검증할 수 있다.

