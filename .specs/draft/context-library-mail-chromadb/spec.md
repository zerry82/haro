# ChromaDB 메일 관리 대상 선별/첨부 중심 인덱싱 스펙

## 1. 목적

Gmail에서 가져온 모든 메일을 ChromaDB 검색 대상으로 넣지 않는다.
먼저 관리 대상 메일인지 판정하고, 관리 대상 메일만 `메일 본문 + 첨부 핵심 내용`을 하나의 업무 문서로 정리해 embedding한다.

본문이 “첨부파일을 확인하세요” 수준이고 실제 업무 맥락이 첨부파일에 있는 경우, 첨부파일 요약을 메일 분류와 ChromaDB 저장의 핵심 근거로 사용한다.

## 2. 범위

포함:

- whitelist/blacklist/LLM blacklist 기반 관리 대상 판정
- whitelist 우선 정책
- 미결정 메일에만 LLM blacklist 적용
- 제외된 메일 목록과 수동 관리 지정
- Gmail 첨부파일을 사용자 `00_inbox`에 저장
- `txt`, `md`, `csv`, `xlsx`, `xls`, `pdf`, `png`, `jpeg`, `jpg` 첨부의 추출/요약 상태 관리
- 첨부 요약을 메일 구조화와 ChromaDB core text에 반영
- 첨부 추출 결과를 채팅 도구에서 읽기
- 관리 대상 메일만 ChromaDB에 upsert
- Chroma metadata `source=mail`

제외:

- 첨부파일 단독 Chroma 문서 중복 저장
- 본문 외부 참조 링크 다운로드
- zip/exe/기타 binary 내용 분석
- 조직 권한/공유 정책

## 3. 처리 흐름

```text
Gmail fetch/snapshot
  -> 첨부 메타데이터 수집
  -> 관리 대상 판정
  -> 관리 대상 후보 첨부를 00_inbox에 다운로드
  -> 지원 확장자 첨부 텍스트/이미지 요약
  -> 제외된 메일 검토/수동 관리 지정
  -> 관리 대상 메일 core text 생성
  -> ChromaDB upsert
  -> vector 검색
```

## 4. 관리 대상 판정

판정 결과:

- `managed`: 관리 대상
- `excluded`: 관리 제외
- `needs_review`: 자동 판정이 애매함

우선순위:

1. manual override
2. whitelist
3. blacklist
4. LLM blacklist
5. default managed

v1에서 whitelist는 blacklist보다 우선한다.
LLM blacklist는 whitelist/blacklist로 결정되지 않은 메일에만 적용한다.

각 thread metadata에는 다음을 남긴다.

- `management_decision`
- `decision_source`
- `decision_reason`
- `matched_rule_ids`
- `attachment_signals`
- `primary_context_source`

## 5. 첨부 중심 메일

첨부 처리 지원 범위:

- `pdf`
- `txt`, `md`
- `csv`, `xlsx`, `xls`
- `png`, `jpeg`, `jpg`

분석 대상 후보 메일의 Gmail 첨부파일은 사용자 작업공간의 `00_inbox/mail/gmail/...` 아래에 저장한다.
저장된 파일은 일반 파일 목록과 파일 검색에서도 찾을 수 있다.

지원 확장자는 추출/요약 후 `summary`, `key_points`, `content_profile`을 만든다.
지원하지 않는 파일은 저장은 하되 `extract_status=metadata_only`로 표시한다.
PDF에서 텍스트가 거의 없으면 `extract_status=unsupported_scanned_pdf`로 표시한다.
이미지는 Gemini Vision으로 보이는 텍스트, 표/차트/스크린샷 신호, 주요 확인사항을 요약한다.

본문 정보량이 낮고 첨부 요약이 있으면 `primary_context_source=attachment`로 표시한다.
본문과 첨부가 모두 의미 있으면 `primary_context_source=body_attachment`로 표시한다.

## 6. ChromaDB 저장

ChromaDB 저장 단위는 `메일+첨부 통합 문서`다.
첨부파일을 별도 문서로 중복 저장하지 않는다.

embedding 문서인 `mail_core_text`는 다음으로 구성한다.

- 제목
- 발신자
- 카테고리
- 본문 핵심 요약
- 첨부 핵심 요약
- 첨부 content profile 요약
- 요청사항
- 마감
- 참조 링크 목록
- 구조화 경고

Chroma metadata:

- `source=mail`
- `project_id`
- `run_id`
- `thread_id`
- `sender`
- `sender_domain`
- `category`
- `received_at`
- `primary_context_source`
- `attachment_count`
- `attachment_summary_status`

ChromaDB에 넣지 않는 것:

- OAuth token
- raw Gmail id
- 원문 HTML/body 전체
- 원본 첨부 binary

## 7. API

```http
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/excluded
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads/{thread_id}/manage
PUT  /api/projects/{project_id}/mail/gmail/management-policies
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/index-managed
POST /api/projects/{project_id}/mail/gmail/analysis/{run_id}/search
GET  /api/projects/{project_id}/mail/gmail/analysis/{run_id}/threads/{thread_id}/attachments/{attachment_ref}
```

`/search`는 관리 대상 ChromaDB collection을 사용한다.
ChromaDB나 embedding을 사용할 수 없으면 text fallback으로 조용히 내려가지 않고 명시적인 오류를 반환한다.

- 인덱싱 실패: `503`
- 검색 실패: `503`
- 검색어가 실질적으로 비어 있는 경우에만 최근 관리 대상 thread를 보여주는 `text_recent` 모드를 허용한다.

## 8. UI

- 상단 메뉴에 `제외된 메일` 탭을 추가한다.
- 메일 상세에 `본문 중심`, `첨부 중심`, `본문+첨부` badge를 표시한다.
- 첨부 목록에 inbox 저장 경로, 다운로드 상태, 추출 상태, 핵심 요약을 표시한다.
- 제외된 메일 탭에서 제외 사유와 `관리 지정` 버튼을 제공한다.
- 통계 화면에 `전체`, `관리 대상`, `제외`, `첨부 중심`, `다운로드`, `첨부 요약`, `추출 실패`, `수동 관리 지정`, `LLM 제외` 카운트를 표시한다.

## 9. 성공 기준

- excluded thread는 ChromaDB에 들어가지 않는다.
- 수동 관리 지정한 excluded thread는 ChromaDB 검색 대상에 포함된다.
- 본문이 약하고 첨부 요약이 있는 메일은 `primary_context_source=attachment`로 표시된다.
- Chroma metadata에 `source=mail`과 첨부 관련 metadata가 포함된다.
- 검색 결과는 관리 대상 메일만 우선 반환한다.
- “첨부파일 내용 확인” 질문에서 `mail_attachment_read`가 저장 경로와 추출 요약을 반환한다.
