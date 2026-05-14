# Context Library Gmail 구조화 테스트 스펙

## 1. 목적

Context Library는 파일 검색보다 상위의 정제 지식 검색 계층이다.
메일, 첨부파일, 사람, 조직, 주제, 요청사항, 일정, 결정사항을 구조화하고 관계로 연결해 사용자가 자연어로 다시 찾고 인사이트를 얻을 수 있게 만든다.

v1은 Gmail 최신 thread 분석과 구조화 품질 테스트에 집중한다.
기본 분석 대상은 최근 50개 thread이며, 사용자는 테스트 목적에 맞게 1~500개 사이에서 개수를 조절할 수 있다.
사용자는 Gmail을 연결하고, 최근 N개 메일을 분석한 뒤, haro가 메일을 업무 지식으로 제대로 이해했는지 자연어 검색과 인사이트 질의로 검증한다.

v1의 핵심은 항목을 팀 지식으로 올릴지 결정하는 관리 절차가 아니다.
사용자는 “어떤 항목을 선별할지 고르는 사람”이 아니라, “haro가 메일을 업무 지식으로 잘 이해했는지 검증하는 사람”이다.

## 2. 범위

### 포함

- Gmail 읽기 전용 연결
- 최근 N개 메일 분석
- 워크스페이스 `.haro/cache` 기반 Gmail snapshot 저장과 재사용
- thread grouping
- 보낸사람/받은사람 정규화
- 첨부파일 메타데이터 추출
- 분석 대상 Gmail 첨부파일을 사용자 `00_inbox`에 저장
- txt/md, csv, xlsx/xls, pdf, png/jpeg/jpg 첨부 추출/요약
- 요청사항, 일정, 주제, 카테고리 후보 추출
- 구조화 품질 상태 표시
- 자연어 검색 테스트
- 인사이트 추출 테스트
- 선택 메일/최신 분석 run을 오른쪽 채팅 컨텍스트로 전달
- 구조화가 애매한 항목 표시
- 테스트 결과 요약
- 개선 후보 저장

### 제외

- 라이브 polling
- 과거 기간 마이그레이션
- 항목별 선별/승인 플로우
- clean-room 요약 파일 생성
- 자동 메일 발송
- Google Pub/Sub 실시간 연동
- vector embedding
- multi-provider 메일 연동
- 조직/팀 권한 모델

## 3. 현재 UI 문제

현재 `메일 관리` 메뉴를 선택하면 왼쪽 사이드 패널 안에 연결, 분석, 카테고리, 필터, 검색이 모두 세로로 압축되어 보인다.
중앙 영역은 여전히 파일 뷰어의 빈 상태인 “파일을 선택하세요”를 보여준다.

이 화면은 사용자가 다음을 이해하기 어렵다.

- 지금 메일 구조화 과정의 어느 단계에 있는지
- 최근 50개 분석 결과가 어디에 표시되는지
- haro가 어떤 thread, 요청사항, 일정, 첨부를 추출했는지
- 구조화가 잘 된 항목과 애매한 항목이 무엇인지
- 자연어 검색이 실제 업무 질문에 잘 답하는지
- 여러 메일을 묶어 어떤 인사이트를 얻을 수 있는지
- 다음 개선 후보가 무엇인지

따라서 `메일 관리`는 파일 탐색기의 보조 패널이 아니라 별도의 작업 화면처럼 보여야 한다.

## 4. 화면 원칙

메일 메뉴 선택 시 화면의 책임을 다음처럼 나눈다.

| 영역 | 역할 |
| --- | --- |
| 왼쪽 Activity Rail | `메일 관리` 아이콘 선택 상태 표시 |
| 왼쪽 사이드 패널 | 메일 관리 내부 내비게이션과 상태 요약 |
| 중앙 메인 영역 | Gmail 연결, 최근 분석, 구조화 결과, 자연어 테스트, 인사이트 결과 |
| 오른쪽 채팅 패널 | 선택 메일과 최신 분석 run을 유지한 채 자연어 검색과 인사이트 질의를 입력하는 보조 채팅 |

`메일 관리`가 선택되면 중앙 영역은 `메일 관리 워크벤치`로 전환된다.
중앙 영역에 “파일을 선택하세요” 빈 상태를 표시하지 않는다.

왼쪽 사이드 패널은 설정 폼이 아니라 목차와 상태 요약이다.

채팅 패널은 메일 모드에서도 독립적으로 사라지지 않는다.
사용자가 메일 thread를 선택하면 채팅 입력창에는 현재 메일 컨텍스트 chip이 표시되고, 전송되는 메시지는 `open_mail_context`로 최신 completed run과 선택 thread를 함께 보낸다.
채팅 입력의 `워크벤치에서 보기` 액션은 사용자를 다시 `메일 관리` 워크벤치로 돌려보낸다.

## 5. 정보 구조

메일 관리 v1의 내부 화면은 다음으로 제한한다.

1. `개요`
2. `최근 분석`
3. `구조화 테스트`
4. `자연어 검색`
5. `인사이트`
6. `테스트 결과`

왼쪽 사이드 패널에는 다음 요소가 필요하다.

- Gmail 연결 상태
- 마지막 분석 시각
- 분석 대상 개수
- 구조화 완료 thread 수
- 구조화 주의 항목 수
- 테스트 실행 상태
- 개선 후보 수
- 내부 화면 목록
- 주요 CTA 1개

주요 CTA:

- 연결 전: `Gmail 연결`
- 연결 후 분석 전: `최근 50개 분석` 및 분석 개수 조절
- 분석 후 테스트 전: `구조화 테스트 시작`
- 테스트 후: `개선 후보 보기`

## 6. 사용자 흐름

v1 흐름은 다음으로 고정한다.

```text
Gmail 연결
  -> 최근 N개 분석
  -> 1차 구조화 결과 확인
  -> 자연어 검색 테스트
  -> 인사이트 추출 테스트
  -> 구조화 오류/애매한 항목 확인
  -> 테스트 결과 요약
  -> 개선 후보 저장
```

상단 단계 표시는 사용자를 막는 wizard가 아니라 현재 진행 상황을 알려주는 상태 표시로 사용한다.

예:

```text
1 Gmail 연결 완료
2 최근 N개 분석 완료
3 구조화 테스트 진행 중
4 개선 후보 4개 발견
```

## 7. 화면별 기획

### 7.1 개요

메일 관리 첫 화면이다.

필요한 요소:

- Gmail 연결 카드
- 최근 분석 카드
- 구조화 품질 카드
- 테스트 결과 카드
- 개선 후보 카드
- 최근 활동 로그

연결 전에는 Gmail 연결 카드가 가장 크게 보여야 한다.
연결 후에는 분석 개수 입력과 `최근 50개 분석` CTA가 가장 중요하다.
분석 후에는 `구조화 테스트 시작` CTA가 가장 중요하다.

카드 예:

```text
Gmail
연결됨: jiyoon@agency.com
권한: 읽기 전용
마지막 분석: 아직 없음
```

```text
최근 분석
최근 50개
전체 thread 50개
구조화 완료 47개
주의 필요 3개
```

```text
구조화 테스트
테스트 질문 8개
성공 6개
주의 2개
개선 후보 4개
```

### 7.2 최근 분석

최근 N개 Gmail 분석 결과를 보여준다.

필요한 요소:

- 대상 표시: 기본 최근 50개 thread, 1~500개 조절 가능
- 분석 실행 버튼
- 분석 run 히스토리
- 1차 통계 요약
- 보낸사람별 구조화 결과
- 카테고리별 구조화 결과
- thread 목록
- 첨부파일 목록

상단 요약 카드:

- 전체 thread 수
- 구조화 완료 thread 수
- 구조화 주의 thread 수
- 첨부파일 수
- 요약 가능 첨부 수
- 추출된 요청사항 수
- 추출된 일정 수
- 카테고리 후보 수

보낸사람 표 컬럼:

- 보낸사람
- 도메인
- thread 수
- 추출된 요청사항 수
- 첨부 수
- 대표 카테고리
- 구조화 품질

카테고리 표 컬럼:

- 카테고리
- thread 수
- 요청사항 수
- 일정 수
- 첨부 수
- 구조화 품질

thread 목록 컬럼:

- 구조화 상태
- 카테고리
- 제목
- 보낸사람
- 받은사람
- 수신일
- 추출된 요청사항
- 추출된 일정
- 첨부 수
- 요약
- 주의 이유

thread 상세에 필요한 요소:

- 제목
- 보낸사람
- 받은사람
- 수신일
- 카테고리
- 구조화 상태
- 요약
- `.haro/cache` snapshot에 저장된 메일 본문 전문
- 추출된 요청사항
- 추출된 일정
- 첨부파일 목록
- haro가 이 thread를 이렇게 이해한 근거
- 구조화 주의 이유

### 7.3 첨부파일 구조화

첨부파일이 업무 지식으로 어떻게 구조화되었는지 확인하는 화면이다.

표 컬럼:

- 파일 제목
- 확장자
- 용량
- 연결 thread
- 보낸사람
- 요약 가능 여부
- 요약 상태
- 추출된 핵심 내용

요약 대상:

- text
- ppt/pptx
- pdf
- xlsx/xls
- csv

요약 제외 대상도 명확히 보여준다.
예를 들어 zip 파일은 메타데이터만 검색 가능하고 내용 요약은 제외한다.

### 7.4 구조화 테스트

구조화 테스트는 사용자가 haro의 이해 품질을 확인하는 중심 화면이다.

필요한 요소:

- 자연어 검색창
- 추천 테스트 질문
- 최근 테스트 질문 히스토리
- 결과 패널
- 근거 thread 목록
- 구조화 품질 판단 버튼
- 개선 후보로 저장 버튼

추천 테스트 질문 예:

```text
- 이번 주 A광고주가 요청한 성과 보고 관련 메일 찾아줘
- 금요일까지 해야 하는 요청만 모아줘
- 첨부파일이 있는 고객 요청만 보여줘
- client-a.com에서 온 메일 중 액션 플랜을 요구한 것만 찾아줘
- 일정이 명확하지 않은 요청을 보여줘
- 이번 주 고객들이 반복해서 요구한 것은 뭐야?
- 첨부된 엑셀 파일들이 어떤 지표를 담고 있는지 요약해줘
```

테스트 결과에는 항상 근거가 포함되어야 한다.

근거 예:

- 제목 매칭
- sender domain 매칭
- 요청사항 추출 근거
- 일정 추출 근거
- 첨부 요약 근거
- 연결된 thread 근거

### 7.5 자연어 검색

사용자가 업무 언어로 질문하면 구조화된 메일 인덱스에서 결과를 찾는다.

지원해야 하는 검색 유형:

- 고객/조직 기반 검색
- 보낸사람 도메인 기반 검색
- 카테고리 기반 검색
- 요청사항 기반 검색
- 일정/마감 기반 검색
- 첨부파일 기반 검색
- 구조화 주의 항목 검색

검색 결과 카드에 필요한 정보:

- 제목
- 카테고리
- 보낸사람
- 보낸사람 도메인
- 요청사항
- 일정
- 첨부
- 요약
- 근거
- 구조화 품질

검색 결과는 파일 경로 중심이 아니라 업무 지식 중심으로 보여야 한다.

### 7.6 인사이트

인사이트 화면은 여러 메일을 묶어 반복 패턴과 업무 위험을 보여준다.

지원해야 하는 인사이트 유형:

- 반복 요청 패턴
- 고객별 주요 요청
- 마감 집중도
- 일정 누락 요청
- 결과물이 불명확한 요청
- 첨부파일 지표 요약
- 고객별 리스크
- 구조화가 애매한 항목 원인 분석

인사이트 응답에는 다음이 포함되어야 한다.

- 요약 결론
- 근거 thread 수
- 대표 thread
- 관련 첨부
- 품질/주의 표시
- 다음 개선 후보

예:

```text
최근 50개 고객 요청에서 반복된 패턴은 4가지입니다.

1. 성과 보고서에 다음 액션 플랜을 함께 요구
   - A광고주, B광고주, D광고주에서 반복
   - 단순 수치 보고보다 "다음 주에 무엇을 할지"를 요구하는 흐름

2. 금요일 마감 요청 집중
   - 명시 마감 19개 중 11개가 금요일
   - 주간 리포트 업무가 금요일 오후에 몰리는 패턴
```

### 7.7 테스트 결과

사용자가 실행한 자연어 검색과 인사이트 테스트 결과를 요약한다.

필요한 요소:

- 테스트 질문 수
- 성공 수
- 주의 수
- 실패 수
- 잘 된 검색 유형
- 주의가 필요한 검색 유형
- 구조화 오류 원인
- 개선 후보 목록

테스트 결과 예:

```text
테스트 질문: 8개
성공: 6개
주의: 2개
실패: 0개

잘 된 점:
- 고객별 요청 검색
- 첨부파일 요약 기반 검색
- 마감 있는 요청 검색
- 모호한 요청 탐지
- 반복 요청 인사이트

주의할 점:
- "이번 주 안에" 같은 상대 날짜 정규화
- 소재 관련 메일의 결과물 구분
```

개선 후보는 다음 스킬/규칙/프롬프트 개선의 입력으로 남긴다.
v1에서는 개선 후보 저장까지만 다루고, 자동 재구조화는 하지 않는다.

## 8. 빈 상태와 오류 상태

### Gmail 미연결

보여줄 것:

- Gmail 연결 CTA
- 읽기 전용 권한 설명
- 원문 메일이 곧바로 팀 지식으로 저장되지 않는다는 안내
- 최근 50개 분석 후 구조화 품질을 테스트한다는 설명

보여주지 않을 것:

- 필터 폼
- 검색 테스트 화면
- 빈 통계 테이블

### 분석 전

보여줄 것:

- 최근 50개 분석 CTA
- 분석 후 확인할 수 있는 구조화 항목 안내

보여주지 않을 것:

- 자연어 검색창
- 인사이트 결과 영역
- 의미 없는 0개 통계 카드

### 분석 중

보여줄 것:

- 진행 상태
- 현재 단계
- 실패 시 재시도 가능한 단계
- `최근 N개 분석` 요청 직후 생성된 run id
- cache-first 분석인지, Gmail 강제 갱신인지
- LLM 구조화 단계가 진행 중인지

단계 예:

```text
Gmail thread 가져오는 중
thread 묶는 중
보낸사람/받은사람 정규화 중
첨부파일 메타데이터 읽는 중
요청사항과 일정 추출 중
검색 가능한 구조로 인덱싱 중
```

구현 단계명:

```text
queued -> fetching -> normalizing -> structuring -> indexing -> completed
failed
```

`structuring` 단계에서는 기존 Gemini client와 `gemini-3-flash-preview`를 사용해 10개 thread 단위로 LLM 구조화를 수행한다.
LLM 구조화 실패는 전체 분석 실패로 처리하지 않고, 해당 batch에 `structure_warnings`와 낮은 `confidence`를 남기는 fallback으로 처리한다.

### 구조화 테스트 전

보여줄 것:

- 추천 테스트 질문
- 구조화 테스트의 목적
- “검색 결과를 보고 품질을 판단한다”는 안내

### 구조화 주의 항목

보여줄 것:

- 애매한 이유
- 누락된 정보
- confidence 또는 품질 상태
- 추천 후속 질문
- 개선 후보로 저장 버튼

### 오류

보여줄 것:

- 실패 단계
- 재시도 버튼
- 연결 재확인 버튼
- 기술 상세 펼치기

## 9. 데이터 모델

### 애플리케이션 DB

Gmail 분석과 구조화 테스트 상태는 애플리케이션 DB에 저장한다.

주요 레코드:

- `MailConnection`
- `MailAnalysisRun`
- `MailThreadStructured`
- `MailAttachmentSummary`
- `MailStructureTest`
- `MailInsightRun`
- `MailImprovementCandidate`

`MailThreadStructured`의 주요 필드:

- source_ref
- subject
- sender
- sender_domain
- recipients
- received_at
- summary
- category
- extracted_actions
- extracted_due_dates
- attachments
- structure_status
- structure_warnings
- evidence_refs

### 구조화 검색 인덱스

최근 분석 결과는 자연어 검색과 인사이트 테스트를 위해 검색 가능한 인덱스로 만든다.

v1 검색 인덱스 범위:

- 제목
- 요약
- 카테고리
- 보낸사람
- 보낸사람 도메인
- 추출된 요청사항
- 추출된 일정 표현
- 첨부파일 제목
- 첨부파일 요약
- 구조화 주의 사유

검색 엔진은 ChromaDB 기반 벡터 검색을 기본 검색 경로로 사용한다.
각 completed run은 프로젝트 워크스페이스의 `.haro/db/chroma/mail` 아래 run별 collection으로 인덱싱된다.
embedding 문서에는 메일 원문 전체를 넣지 않고, 제목, 발신자, 수신자, 요약, 카테고리, 추출된 요청사항, 마감, 첨부 요약, 구조화 경고만 넣는다.

검색 시에는 벡터 유사도와 기존 텍스트 점수를 결합한 hybrid ranking을 사용한다.
ChromaDB 패키지, embedding 모델, API key가 준비되지 않은 환경에서는 기존 텍스트 검색으로 조용히 대체하지 않고 명확한 오류를 반환한다.
API 응답에는 `retrieval.mode`로 `hybrid_vector` 또는 빈 질의의 최신 목록 조회를 뜻하는 `text_recent`를 표시한다.

채팅 패널에서 메일 관련 질문을 하는 경우 에이전트는 파일 검색 도구가 아니라 `mail_search` 도구로 최신 completed Gmail 분석 run을 검색한다.
예를 들어 “카카오에서 온 메일들 요약해줘”는 workspace 파일을 찾지 않고 Gmail staging thread의 sender/subject/summary/구조화 필드를 검색해야 한다.

### 개선 후보

구조화 테스트에서 발견된 문제는 개선 후보로 저장한다.

예:

- 상대 날짜 표현 정규화 필요
- 소재 관련 메일의 결과물 구분 필요
- 특정 도메인 메일의 요청사항 추출 품질 개선 필요
- zip 첨부파일은 내용 검색이 아니라 메타데이터 검색으로 명확히 표시 필요

개선 후보는 즉시 구조를 바꾸는 작업이 아니라, 다음 스킬/규칙/프롬프트 개선의 입력이다.

## 10. API

v1 API는 최근 분석과 구조화 테스트에 필요한 범위만 포함한다.

```http
POST /api/projects/{project_id}/mail/gmail/connect
GET  /api/projects/{project_id}/mail/gmail/status
POST /api/projects/{project_id}/mail/gmail/analyze-recent
POST /api/projects/{project_id}/mail/gmail/incremental/preview
POST /api/projects/{project_id}/mail/gmail/incremental/analyze
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads/{thread_id}
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/attachments
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/search
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/insights
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/structure-tests
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/structure-tests
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/improvement-candidates
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/improvement-candidates
```

`POST /analyze-recent` 계약:

- request: `max_threads`, `force_refresh`
- response: 즉시 생성된 `MailAnalysisRun`과 현재 stats
- `force_refresh=false`: snapshot cache를 우선 사용
- `force_refresh=true`: Gmail API를 다시 호출하고 snapshot을 갱신
- 진행 상태는 `GET /analysis/{run_id}`를 polling해서 확인
- 진행 중에는 `threads`가 빈 배열일 수 있다.
- 완료 후 thread metadata에는 `extracted_actions`, `extracted_due_dates`, `structure_warnings`, `confidence`가 포함된다.
- 실패 시 `stats.error.stage`, `stats.error.message`를 표시한다.

`POST /incremental/preview` 계약:

- request: `{ scan_limit?: number }`
- 최신 completed 분석 run 이후 새로 도착한 Gmail thread 후보를 계산한다.
- 기준은 최신 completed run의 가장 최근 `received_at`과 이미 처리된 `source_ref`다.
- response에는 `new_count`, `since_received_at`, `fetched_count`, `fetched_at`, `threads[]` 미리보기가 포함된다.
- preview 과정에서 Gmail을 확인하고 snapshot cache를 갱신하지만, 구조화 run은 만들지 않는다.

`POST /incremental/analyze` 계약:

- request: `{ scan_limit?: number }`
- preview와 같은 기준으로 신규 thread를 다시 계산한다.
- 신규 thread가 없으면 “마지막 처리 이후 추가된 메일이 없음”을 반환한다.
- 신규 thread가 있으면 `incremental:*` range의 `MailAnalysisRun`을 만들고 기존 비동기 구조화 job으로 넘긴다.
- response는 `POST /analyze-recent`와 동일하게 즉시 생성된 run 상태를 반환하고, UI는 `GET /analysis/{run_id}`를 polling한다.

`POST /analysis/{run_id}/search` 계약:

- request: `{ query, limit? }`
- response에는 `query`, `run`, `retrieval`, `items[]`가 포함된다.
- `retrieval.mode=hybrid_vector`이면 ChromaDB 벡터 유사도와 텍스트 점수를 결합해 정렬한 결과다.
- `retrieval.mode=text_recent`이면 검색어가 비어 있어 최신 관리 대상 메일 목록을 반환한 결과다.
- 각 item에는 `score`, `matched_fields`, `evidence`, `retrieval.vector_score`, `retrieval.text_score`가 포함될 수 있다.
- 검색 결과에는 raw Gmail id, OAuth token, 원문 body 전체, 원본 첨부파일을 포함하지 않는다.

`GET /analysis/{run_id}/threads/{thread_id}` 계약:

- 목록 API와 달리 선택된 thread 상세에만 snapshot 본문을 포함한다.
- response thread에는 `body`, `body_source`, `body_truncated`, `body_html`, `body_html_source`, `body_html_truncated`, `attachment_source`가 포함될 수 있다.
- `body_source=snapshot`이면 `.haro/cache`의 개인 Gmail snapshot에서 가져온 본문이다.
- snapshot이 없으면 `body_source=staging_sample`로 구조화용 짧은 샘플만 표시한다.
- HTML 메일은 `body_html`로 별도 저장하고 UI에서 sandbox iframe 원본 렌더러로 표시한다.
- 원본 렌더러는 script/form/object/embed/iframe/event handler와 외부 이미지 src를 제거하고, iframe CSP로 외부 리소스와 스크립트를 차단한다.
- 텍스트 보기는 HTML 메일을 문단/목록 단위로 읽기 좋게 정규화한 fallback이다.
- 첨부파일은 원본 파일이 아니라 제목, 확장자, mime type, 용량, 가능한 요약만 표시한다.

`POST /analysis/{run_id}/insights` 계약:

- request: `{ "query": string }`
- v1은 LLM 호출 없이 완료된 staging thread의 sender, category, attachment, due date, warning을 집계한다.
- response에는 `summary`, `insights[]`, 각 insight의 `thread_ids`, `attachments`, `evidence`, `severity`가 포함된다.
- 원문 body, raw Gmail id, OAuth token은 포함하지 않는다.

`POST /analysis/{run_id}/structure-tests` 계약:

- request: `{ query, result_kind, rating, notes?, result? }`
- `result_kind`는 `search` 또는 `insight`, `rating`은 `good`, `warning`, `bad`다.
- 사용자가 자연어 검색/인사이트 결과를 어떻게 평가했는지 기록한다.

`POST /analysis/{run_id}/improvement-candidates` 계약:

- request: `{ title, reason, priority?, source?, query?, thread_ids?, evidence? }`
- 검색/인사이트 품질 평가에서 발견한 개선 후보를 저장한다.
- 후보는 다음 프롬프트/규칙/스킬 개선의 입력이며, 저장 즉시 메일 구조를 자동 변경하지 않는다.

## 11. 보안 원칙

- OAuth token 원문을 애플리케이션 DB에 저장하지 않는다.
- Gmail raw body를 `clean-room`에 쓰지 않는다.
- Gmail snapshot은 `/.haro/cache/mail/gmail/{account_hash}`에 저장한다.
- 기본 분석은 snapshot을 우선 사용하고, `Gmail 다시 가져오기`에서만 강제로 fetch한다.
- snapshot에는 OAuth token, raw Gmail id, 원본 첨부파일을 저장하지 않는다.
- Gmail thread id, message id는 사용자에게 필요한 최소 참조로만 관리한다.
- 자연어 검색 결과에는 원문 전체가 아니라 구조화 요약과 근거만 표시한다.
- ChromaDB 벡터 문서에도 Gmail 원문 전체, raw Gmail id, OAuth token, 원본 첨부파일을 넣지 않는다.
- 메일 본문 전문은 선택한 thread 상세 화면에서만 사용자에게 표시하고, 검색 결과/Team Context Library/clean-room에는 복사하지 않는다.
- 첨부파일 원본은 사용자 `00_inbox`에 저장하지만, clean-room/Team Library/ChromaDB에는 binary를 복사하지 않는다.
- Project Fork에는 Gmail 원문, token, 원본 첨부, 개인 연락처 맥락을 포함하지 않는다.

## 12. 성공 기준

- `메일 관리` 메뉴 선택 시 중앙 영역이 메일 관리 워크벤치로 전환된다.
- 중앙 영역에 “파일을 선택하세요” 빈 상태가 표시되지 않는다.
- Gmail 미연결, 분석 전, 분석 중, 분석 후, 구조화 테스트 전 상태가 각각 다르게 표현된다.
- 최근 50개 분석 후 sender, thread, category, attachment, extracted action, due date 통계를 볼 수 있다.
- 구조화 완료 항목과 주의 항목을 구분해서 볼 수 있다.
- 자연어 검색으로 고객별 요청, 마감 있는 요청, 첨부 기반 요청을 찾을 수 있다.
- 의미가 비슷하지만 단어가 정확히 일치하지 않는 메일 질문은 ChromaDB hybrid vector 검색으로 찾을 수 있다.
- 검색 결과마다 근거 thread와 구조화 근거가 표시된다.
- 인사이트 질의로 반복 요청, 고객별 리스크, 마감 집중, 구조화 오류 원인을 얻을 수 있다.
- 선택 메일 기준 질문을 보낼 때 오른쪽 채팅 입력과 사용자 메시지에 메일 컨텍스트가 표시된다.
- 메일 모드에서 화면 폭을 줄여도 메일 목록, 상세, 검색 결과, 채팅 입력이 겹치지 않는다.
- 구조화가 애매한 항목은 무리하게 확정하지 않고 주의 이유와 누락 정보를 보여준다.
- 테스트 결과 화면에서 성공/주의/실패 질문과 개선 후보를 볼 수 있다.
- 개선 후보를 다음 스킬/규칙/프롬프트 개선 입력으로 저장할 수 있다.

