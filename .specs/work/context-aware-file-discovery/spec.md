# Context-Aware File Discovery Spec

작성일: 2026-05-10

## 배경

사용자가 제공한 trace에서 하로 에이전트는 "서울 날씨 브리핑에서 현재 html을 건들지 말고, 아래 5.10일 내용을 추가해줘"라는 요청을 받았고, 추가 내용 확인 질문 뒤 사용자가 "이미 파일로 추가했었어"라고 답했다.

이 상황에서 에이전트는 사용자가 말한 "파일"을 찾기 위해 `날씨`, `0510`, `서울`, `5월`, `10일`, `weather` 같은 키워드를 반복 검색하고 여러 폴더를 순차 조회했다. 하지만 이미 확인된 유력 후보인 `내 폴더/결과/날씨_브리핑/서울_날씨_대시보드_20260509.html`, 최근 intent, linked files, artifacts, chat inputs, 메시지 첨부/참조 같은 구조화된 단서를 중심으로 후보를 좁히지 못했다.

이 스펙은 하로가 사용자 질문과 최근 대화 맥락에서 정확한 파일과 관련 위치를 찾아내는 방식을 개선하기 위한 초안이다. 구현에 들어가기 전, 로컬 `study` 폴더의 Claude Code 구현을 참고해 어떤 원칙을 가져올지 정리한다.

## 문제

현재 파일 탐색 흐름에는 다음 문제가 있다.

- "이미 파일로 추가했어" 같은 후속 답변을 파일 후보 단서로 해석하지 못하고, 일반 키워드 검색으로만 처리한다.
- 이전 intent의 요약, clarification question, recent messages, latest artifact, linked files, artifacts metadata를 파일 후보 랭킹에 충분히 반영하지 못한다.
- 검색 결과로 유력한 폴더/파일이 나와도 그 후보 안에서 content search나 targeted read로 전환하지 못하고, 다른 키워드 검색을 반복한다.
- 이미 실패한 검색어와 검색 범위를 기억하지 않아 같은 목적의 넓은 탐색을 여러 번 수행한다.
- 사용자에게 다시 질문해야 하는 시점이 늦고, "어디를 찾아봤는지"와 "무엇이 없었는지"가 구조화되어 전달되지 않는다.
- `file_search` 결과가 후보 랭킹에 필요한 mtime, 파일 타입, 위치 우선순위, 요약/스니펫, 이전 참조 여부 같은 정보를 충분히 제공하지 않을 수 있다.
- "현재 html을 건들지 말고"처럼 대상 파일과 금지 조건이 함께 있는 요청에서, 대상 artifact와 추가할 source file을 분리해 찾는 전략이 약하다.
- Haro UI에서 사용자가 현재 열어 둔 파일이 있어도, 그 상태가 에이전트의 파일 후보 맥락으로 안정적으로 전달되지 않는다.

## Claude Code 조사 요약

로컬 `study` 폴더의 Claude Code 구현을 기준으로 다음 흐름을 확인했다.

- 사용자 입력 단계에서 붙여넣은 텍스트 참조는 `parseReferences`와 `expandPastedTextRefs`로 모델 입력에 먼저 확장된다.
- 첨부 파일, 이미 읽은 파일, compact 이전에 읽었던 파일, IDE에서 선택한 줄, IDE에서 열려 있는 파일, 사용자가 수정한 파일은 일반 텍스트 검색어가 아니라 모델-visible system reminder 또는 tool result 형태로 주입된다.
- 파일 찾기 도구는 역할이 분리되어 있다. `Glob`은 파일명 패턴 검색, `Grep`은 내용 검색, `Read`는 정확한 파일 읽기, `Explore` agent는 여러 라운드의 열린 탐색을 담당한다.
- `Glob`과 `Grep`은 기본적으로 최근 수정 파일을 우선 보여주거나, glob/type/output mode/context line/pagination 같은 검색 제어를 제공한다.
- `Grep` 프롬프트는 검색 작업에 `Grep`을 우선 쓰라고 명시하고, 여러 차례 glob/grep이 필요한 열린 탐색은 별도 read-only 탐색 agent로 넘기도록 유도한다.
- `Read`는 정확한 경로가 있을 때 사용하는 도구이며, 필요한 경우 offset/limit으로 부분 읽기를 한다.
- 시스템 컨텍스트에는 현재 작업 디렉터리, git 상태, 최근 커밋, 프로젝트 지침, 날짜가 들어가며, 이는 사용자의 짧은 지시를 해석하는 주변 맥락이 된다.

하로가 그대로 복제할 필요는 없지만, 핵심은 "먼저 구조화된 참조와 최근 작업 맥락을 후보화하고, 그다음 검색 도구를 목적별로 사용한다"는 점이다.

## 목표

- 파일 탐색 전에 deterministic한 후보 수집 단계를 둔다.
- 후보 수집은 사용자 메시지뿐 아니라 recent messages, previous intent, latest artifact, latest preview, linked files, artifacts, chat inputs/outputs, 사용자가 업로드하거나 붙여넣은 파일 메타데이터를 함께 본다.
- 후보마다 경로, 종류, 근거, confidence, 추천 next action을 구조화해 모델 컨텍스트와 debug trace에 제공한다.
- 파일명 검색, 내용 검색, 정확 파일 읽기, 폴더 목록 조회의 역할을 분리해 반복적인 넓은 검색을 줄인다.
- 동일 intent 안에서 이미 검색한 query/scope/result를 기억하고 중복 검색을 막는다.
- 유력한 target artifact와 source content 후보를 분리해 랭킹한다.
- 후보가 없을 때는 제한된 탐색 후 즉시 사용자에게 경로 또는 파일 업로드를 요청한다.
- Haro UI에서 현재 열린 파일, 활성 탭, 선택 영역, dirty 상태를 파일 후보 신호로 전달한다.
- 열린 파일의 전체 내용을 무조건 보내지 않고, 경로/메타데이터를 기본으로 보내며 선택 영역이나 제한된 스니펫만 필요 시 포함한다.
- 사용자-facing 답변에서는 raw canonical path보다 `내 폴더/결과/...` 같은 alias를 우선 사용한다.
- 기존 저장 위치 정책, Clean Room/.haro 보호 정책, selected tools 정책을 유지한다.

## 비목표

- v1에서 vector DB나 embedding 기반 의미 검색을 새로 도입하지 않는다.
- v1에서 전체 파일 트리를 모델 컨텍스트에 주입하지 않는다.
- v1에서 모든 파일 도구를 Claude Code와 동일한 API로 바꾸지 않는다.
- v1에서 웹 검색으로 누락 파일을 보완하지 않는다.
- v1에서 partial file edit 도구의 상세 구현을 다시 설계하지 않는다. 해당 내용은 `partial-file-operations` 스펙을 따른다.
- v1에서 멀티 에이전트 구조로 전환하지 않는다.
- v1에서 사용자가 열어 둔 모든 파일의 전체 내용을 매 요청마다 모델 컨텍스트에 넣지 않는다.
- v1에서 전체 시스템 프롬프트 패키징, prompt cache, stable/dynamic section 분리 구조를 전면 개편하지 않는다. 해당 작업은 별도 스펙으로 다룬다.

## 범위 결정

이 스펙은 "정확한 파일과 관련 위치를 찾기 위한 맥락"까지만 책임진다.

포함 범위:

- File Discovery Context의 입력 데이터, 후보 랭킹, 모델-visible 요약 형식
- active/opened file, linked files, artifacts, recent intent 같은 파일 후보 신호
- 전체 내용을 보내지 않고 경로/메타데이터/선택 영역/제한된 스니펫만 보내는 정책
- 중복 검색을 막기 위한 intent-local search state

별도 스펙 범위:

- 시스템 프롬프트를 stable/dynamic/turn-local section으로 나누는 구조
- prompt cache 또는 provider별 cache control 적용
- 매 턴 반복되는 하네스/정책/도구 계약 텍스트의 delta 전송
- 긴 system instruction을 압축하거나 세션 단위로 재사용하는 전반적 prompt packaging

따라서 이번 스펙의 v1 구현은 "프롬프트 전체 개편" 없이도 적용 가능해야 한다. 다만 추후 prompt packaging 개편이 들어오면 File Discovery Context는 turn-local dynamic context로 이동할 수 있어야 한다.

## 핵심 개념

### File Discovery Context

에이전트가 도구 호출 전에 받는 파일 후보 요약이다.

포함 정보:

- 최근 intent와 clarification 상태
- latest artifact / latest preview
- linked files와 artifacts metadata
- Haro UI에서 현재 열린 파일, 활성 파일, 선택 영역, dirty 상태
- chat input/output/working/summaries의 관련 파일
- "기존에 작성했어"처럼 대화 안의 기존 작성물을 가리키는 경우 recent messages의 제한된 원문 preview
- 사용자가 첨부, 붙여넣기, 열람, 선택, 수정한 파일
- 최근 도구 결과에서 발견된 후보 파일
- 후보별 alias path, canonical path, file kind, confidence, reason, recommended action

### Open File Context

Haro UI의 파일 탐색기, 에디터, 미리보기에서 사용자가 현재 열어 둔 파일 상태다.

기본 포함 정보:

- active file path
- opened file paths
- selected line range와 선택 텍스트 일부
- dirty 여부
- 마지막으로 focus된 시각 또는 순서
- 파일 타입과 크기

전달 원칙:

- active file은 강한 후보 신호로 본다.
- opened file은 약한 후보 신호로 보되, 사용자 요청의 주제어와 맞으면 가중치를 높인다.
- 선택 영역은 Claude Code처럼 모델-visible reminder로 전달할 수 있다.
- 전체 파일 내용은 자동 포함하지 않고, 작은 텍스트 파일 또는 사용자가 직접 선택한 범위만 제한적으로 포함한다.
- dirty 파일은 디스크 내용과 UI 내용이 다를 수 있으므로 후보 이유에 dirty 상태를 명시한다.
- 사용자가 "이 파일", "방금 열어둔 파일", "현재 보고 있는 파일"이라고 말하면 active file을 1순위 후보로 사용한다.

### Candidate Ranking

후보 파일은 다음 신호로 점수화한다.

- 사용자가 명시한 경로 또는 파일명과 일치하는가
- 현재 intent의 주제어와 파일명/폴더명/요약이 일치하는가
- latest artifact 또는 linked file인가
- Haro UI의 active/opened file인가
- 현재 chat inputs 또는 outputs에 있는가
- 사용자 결과 폴더의 관련 주제 폴더에 있는가
- 최근 수정 파일인가
- 요청의 action과 파일 타입이 맞는가
- 이전 검색 또는 도구 결과에서 이미 유력 후보로 등장했는가
- 대상 artifact인지, source content인지 구분 가능한가

### Search Plan

후보 랭킹 뒤에 수행할 bounded search 계획이다.

예시:

```text
1. linked/artifact/input 후보 확인
2. 주제 폴더 안에서 source content 후보 검색
3. 유력 target file 내부에서 날짜/섹션 content search
4. 실패 시 탐색 요약과 함께 사용자에게 파일 경로 요청
```

Search Plan은 intent 안에서 searched query/scope를 기록해 중복 호출을 방지한다.

## 사용자 흐름

### 1. 사용자가 "이미 파일로 추가했어"라고 답한 경우

하로는 먼저 사용자의 답변을 "추가할 정보가 파일 형태로 존재한다"는 clarification answer로 해석한다.

우선순위:

1. 현재 메시지의 첨부/붙여넣기/파일 참조
2. Haro UI의 active file과 선택 영역
3. 최근 대화 메시지에 남아 있는 기존 작성물 preview
4. linked files와 artifacts
5. chat inputs
6. latest artifact가 있는 폴더의 관련 파일
7. 사용자 결과 폴더의 주제 폴더
8. 제한된 file search/content search

이 순서에서 후보가 없으면, 더 넓게 반복 검색하지 않고 "현재 확인한 위치에는 파일이 없다"는 요약과 함께 파일 경로 또는 재업로드를 요청한다.

### 2. target artifact와 source content가 분리된 경우

예: "서울 날씨 브리핑에서 현재 html을 건들지 말고, 아래 5.10일 내용을 추가해줘"

하로는 다음을 분리한다.

- target artifact: 기존 서울 날씨 브리핑 HTML 또는 결과물
- source content: 사용자가 추가했다고 말한 5월 10일 정보 파일
- constraint: 현재 HTML을 직접 수정하지 말라는 조건

따라서 기존 HTML만 찾았다고 바로 편집하지 않는다. source content 후보를 찾고, 없으면 사용자에게 source file 위치를 묻는다.

### 3. 후보가 하나로 좁혀진 경우

하로는 해당 파일을 읽거나 content search를 수행하기 전에 다음을 짧게 확인한다.

- 어떤 근거로 이 파일이 후보인지
- 이 파일을 읽는 것이 요청 해결에 필요한지
- 쓰기 도구가 필요한지, 읽기 도구만 필요한지

사용자가 명확히 수정 요청을 했고 대상/소스가 충분히 확인된 경우에만 편집 도구를 사용한다.

### 4. 사용자가 현재 열린 파일을 지시한 경우

예: "이 파일에 추가해줘", "지금 보고 있는 파일 기준으로 해줘", "열어둔 HTML은 건드리지 마"

하로는 active file/opened files를 먼저 확인한다.

- active file이 하나면 해당 파일을 1순위 후보로 둔다.
- 선택 영역이 있으면 해당 범위를 우선 맥락으로 사용한다.
- opened file이 여러 개이고 사용자 지시가 모호하면 후보 목록과 근거를 짧게 제시하고 확인한다.
- dirty 상태라면 디스크 파일을 읽기 전에 UI의 최신 내용이 저장됐는지 또는 dirty buffer를 사용할 수 있는지 확인한다.

## 성공 기준

- 제공된 trace와 같은 상황에서 3회 이상의 넓은 반복 검색 없이 후보 수집 결과를 만든다.
- `내 폴더/결과/날씨_브리핑/서울_날씨_대시보드_20260509.html`을 target artifact 후보로 식별하되, source content 후보가 없다는 사실을 분리해 판단한다.
- 후보가 없으면 "확인한 위치"와 "없는 정보"를 요약하고 사용자에게 파일 경로 또는 재업로드를 요청한다.
- debug trace에 `file_discovery_candidates`, `file_search_plan`, `file_search_exhausted` 같은 이벤트가 남는다.
- 동일 intent 안에서 같은 query/scope 조합을 반복 호출하지 않는다.
- router가 읽기/탐색 단계에서는 write 도구를 과하게 선택하지 않고, 실제 수정 가능성이 생길 때만 편집 도구를 포함한다.
- 사용자가 "이 파일" 또는 "현재 보고 있는 파일"이라고 말하면 Haro UI active file이 1순위 후보로 들어간다.
- 열린 파일 메타데이터는 모델 컨텍스트에 포함되지만, 전체 파일 내용은 크기/선택 여부/필요성 기준을 통과할 때만 제한적으로 포함된다.
- 단위 테스트로 후보 랭킹, 중복 검색 방지, artifact/linked file 우선순위, 탐색 고갈 후 질문 전환을 검증한다.

## 검증 기준

- trace 기반 회귀 테스트: "이미 파일로 추가했었어" 후속 답변에서 후보 수집과 탐색 고갈 동작을 검증한다.
- 후보 랭킹 테스트: latest artifact, linked file, chat input, mtime, file type이 점수에 반영되는지 확인한다.
- 열린 파일 테스트: active file, opened file, selected range, dirty 상태가 후보 점수와 모델-visible context에 반영되는지 확인한다.
- 중복 검색 테스트: 같은 intent에서 동일 query/scope가 재실행되지 않는지 확인한다.
- 프롬프트/라우터 테스트: target artifact와 source content를 분리한 요약이 모델 요청에 포함되는지 확인한다.
- 수동 디버그 확인: debug trace에서 후보, 검색 계획, 질문 전환 이유가 읽히는지 확인한다.

## 남은 질문

- 현재 하로에서 사용자가 "파일로 추가"한 항목은 DB, `linked-files.json`, message attachment, chat inputs 중 어디에 가장 안정적으로 기록되는가?
- `file_search` 인덱스에 mtime, 파일 크기, parent alias, content snippet, linked/artifact 여부를 추가할 수 있는가?
- File Discovery Context는 router에서 만들지, agent context builder에서 만들지, 별도 facade service에서 만들지 결정해야 한다.
- Haro UI의 opened/active file 상태를 백엔드에 어떻게 동기화할지 정해야 한다. 예: 메시지 전송 payload, 별도 session state API, 또는 SSE/웹소켓 상태 업데이트.
- dirty buffer가 있는 열린 파일의 최신 내용을 백엔드가 받을 수 있는지, 받을 수 있다면 저장된 파일과 어떻게 구분할지 정해야 한다.
- "현재 html을 건들지 말고"는 v1에서 "기존 HTML 수정 금지"로 해석할지, "HTML 구조는 유지하고 내용만 추가"로 해석할지 사용자 확인 규칙이 필요하다.
- 후보가 낮은 confidence로 여러 개일 때 자동으로 읽을 수 있는 최대 후보 수를 어떻게 제한할지 정해야 한다.
