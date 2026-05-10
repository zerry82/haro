# Context-Preserving Agent Loop Spec

작성일: 2026-05-10
상태: work

## 배경

haro의 현재 에이전트 실행 흐름은 사용자의 메시지를 먼저 gate와 router가 해석하고, router가 `intent`, `can_execute`, `selected_tools`, `missing_info`를 결정한 뒤 executor가 그 결과 안에서 도구를 호출하는 구조다.

이 구조는 단순 요청에는 빠르게 동작하지만, 사용자의 짧은 후속 지시나 화면/파일 맥락에 강하게 의존하는 요청에서 의미가 납작해지는 문제가 있다.

대표 사례:

- 사용자가 2026년 5월 9일 서울 날씨 HTML 대시보드를 열어 둔 상태에서 "지금 뭐가 보여?"라고 물었다.
- 에이전트는 현재 열린 HTML을 읽고 5월 9일 날씨 대시보드라고 설명했다.
- 사용자가 "여기에 오늘 날짜도 아래에 추가해줘"라고 요청했다.
- 이 맥락에서 자연스러운 의미는 "기존 5월 9일 섹션 아래에 오늘인 5월 10일 날씨 섹션을 추가"하는 것이다.
- 그러나 에이전트는 파일 하단에 작은 `업데이트: 2026년 5월 10일 일요일` 문구만 추가했다.

이는 단순한 파일 탐색 실패가 아니라, 대화 전체와 도구 결과를 기준으로 작업 의미를 계속 보존하고 재해석하지 못한 문제다.

## 문제

현재 구조의 핵심 문제는 router가 executor보다 앞에서 작업 의미를 과하게 결정한다는 점이다.

- router가 `file_search`, `file_read`, `file_edit` 같은 도구 선택을 좁히는 과정에서 사용자의 실제 의도가 손실될 수 있다.
- executor는 전체 대화, 열린 파일, 최근 도구 결과, 파일 구조를 종합해 판단하기보다 route 결과와 selected tools에 끌려간다.
- "여기에", "아래에", "오늘 날짜도", "이미 파일로 추가했어", "응?" 같은 짧은 표현을 직전 파일 읽기 결과와 assistant 응답 맥락에서 충분히 해석하지 못한다.
- 파일을 읽은 뒤 구조를 이해하고 편집 단위를 정해야 하는데, router 단계에서 이미 "어떤 종류의 작업"인지 과도하게 압축된다.
- source content가 없거나 모호한 상황에서, 반복 검색과 부정확한 질문으로 빠지기 쉽다.
- 현재 시스템 프롬프트와 tool description은 "이번 턴 선택 도구" 중심이라, 모델이 스스로 탐색-진단-수정 루프를 유지하기 어렵다.
- 사용자가 짧게 문제 제기했을 때, 에이전트가 최근 변경과 도구 결과를 다시 점검하기보다 방어적 설명이나 새 검색으로 흐를 수 있다.

## Claude Code 조사 요약

로컬 `study` 폴더의 Claude Code 구현과 기존 `partial-file-operations/claude-code-reference.md` 조사에서 다음 원칙을 확인했다.

- Claude Code는 별도 router가 작업 의미를 세부 intent로 잘라 executor에 넘기는 구조가 아니다.
- 메인 모델이 대화 전체, 현재 작업 디렉터리, 열린 파일/선택 영역, 날짜, 프로젝트 지침, 도구 결과를 함께 보고 다음 행동을 판단한다.
- IDE에서 열린 파일과 선택 영역은 일반 검색어가 아니라 system reminder 또는 attachment 맥락으로 모델에 전달된다.
- 파일 수정 전에는 먼저 파일을 읽고, 기존 구조를 확인한 뒤 edit/write 도구를 사용하도록 강하게 유도한다.
- 사용자의 지시가 일반적이거나 짧으면 현재 작업 디렉터리, 최근 대화, 읽은 파일, 도구 결과를 기준으로 해석한다.
- 도구 실패나 사용자 반응이 나오면 같은 행동을 반복하지 않고, 왜 실패했는지 진단한 뒤 다른 접근을 선택한다.
- 파일 탐색은 `Glob`, `Grep`, `Read`처럼 역할을 나누되, 어떤 도구를 쓸지는 메인 루프가 상황에 따라 결정한다.
- 불확실한 지시를 모두 질문으로 되돌리지 않는다. 먼저 현재 작업 맥락과 도구 결과로 합리적 해석을 시도하고, 파일 변경/삭제/외부 전송처럼 되돌리기 어렵거나 업무상 위험한 경우에만 구체적인 확인을 요구한다.
- 질문이 필요할 때도 "무엇을 원하시나요?"처럼 넓게 묻기보다, 현재 후보와 위험을 제시하고 사용자가 빠르게 확정할 수 있게 한다.

haro가 그대로 복제할 필요는 없지만, 핵심 방향은 "의미 판단을 router가 끝내지 않고, context-preserving executor loop가 계속 맡는다"이다.

## 목표

- router-driven 실행 구조를 context-preserving agent loop 구조로 전환한다.
- gate는 대화 흐름 판단만 담당하고, 작업 의미는 executor가 대화/파일/도구 결과를 보고 판단한다.
- 기존 `intent_router`의 세부 intent 판단과 selected tools 축소 책임을 제거한다.
- 새 `ExecutionPolicyResolver`는 의미 판단이 아니라 안전 프로필과 broad tool set만 결정한다.
- `Working Context`를 구성해 사용자 원문, 최근 대화, 현재 날짜, 열린 파일, latest artifact, file discovery candidates, 최근 도구 결과를 executor에 compact하게 전달한다.
- `TurnToolState`를 도입해 같은 턴에서 읽은 파일, 검색한 query/scope, 변경한 파일, checksum/source 상태를 추적한다.
- 기존 파일 수정/삭제/이동은 같은 턴에서 대상 파일을 먼저 읽거나 stat/search_content/read_range로 확인해야 실행한다.
- "오늘 날짜도 아래에 추가" 같은 지시에서 파일 구조를 읽은 뒤 peer section/card 추가 의도를 해석하도록 한다.
- "이미 파일로 추가했어" 같은 말은 source 후보 신호로 보되, source가 없으면 반복 검색보다 명확한 경로/재업로드 요청으로 전환한다.
- "응?", "안 보이는데?", "이게 아니야" 같은 반응은 최근 작업 결과를 재진단하는 신호로 처리한다.
- 기존 Plan Mode, IntentTurn 기록, 도구 호출 JSON 계약, workspace path 정책은 유지한다.

## 비목표

- v1에서 멀티 에이전트 구조로 전환하지 않는다.
- v1에서 Claude Code의 모든 tool API를 동일하게 복제하지 않는다.
- v1에서 vector DB나 embedding 검색을 새로 도입하지 않는다.
- v1에서 전체 파일 트리를 모델 컨텍스트에 넣지 않는다.
- v1에서 dirty editor buffer 전체를 매 요청마다 백엔드로 보내지 않는다.
- v1에서 provider별 prompt cache를 완성하지 않는다. 다만 stable/dynamic prompt section 분리를 가능하게 만든다.
- v1에서 Plan Mode 승인 흐름을 제거하지 않는다.
- v1에서 IntentTurn DB 자체를 삭제하지 않는다. 단, `current_intent` 의미는 세부 작업 intent에서 execution profile 또는 `agentic_task` 중심으로 바뀔 수 있다.

## 기존 File Discovery 스펙과의 관계

`.specs/work/context-aware-file-discovery`는 폐기하지 않고 이 스펙의 하위 구성요소로 흡수한다.

역할 변경:

- 기존 File Discovery Context는 router를 hard-block하는 결정자가 아니다.
- File Discovery Context는 `Working Context` 안의 후보 신호로 들어간다.
- target artifact, source content, context file 후보 분리는 유지한다.
- source content가 없다는 사실은 executor가 판단에 참고할 정보이며, 자동으로 모든 실행을 막지는 않는다.
- 단, 사용자가 명시한 source가 반드시 필요한 작업이고 web/search/context로도 보완할 수 없으면 executor가 사용자에게 경로 또는 재업로드를 요청한다.
- 중복 검색 방지와 search exhaustion trace는 `TurnToolState`와 결합한다.

## 핵심 개념

### Context Confirmation

에이전트는 사용자의 짧거나 지시적인 표현을 무조건 실행으로 연결하지 않는다. 먼저 어떤 맥락을 기준으로 삼는지 확정한다.

확정 대상:

- 현재 열린 파일인지, 최근 산출물인지, 이전 intent인지
- 수정 대상 파일인지, 참고 source 파일인지
- "여기", "아래", "오늘", "방금", "이 파일" 같은 지시어가 가리키는 대상
- 사용자가 원하는 작업이 새 섹션/peer item 추가인지, 메타데이터 문구 추가인지, 기존 내용 교체인지
- dirty editor 상태 때문에 디스크 파일과 화면 내용이 다를 가능성이 있는지

정책:

- 맥락 후보가 하나이고 confidence가 높으면 바로 진행한다.
- 후보가 여러 개이거나 active file과 latest artifact가 다르면 구분해서 말하고, 필요한 경우 확인 질문을 한다.
- 쓰기 작업에서 대상이나 작업 단위가 모호하면 수정 전에 질문한다.
- 질문은 "어떤 파일인가요?"처럼 넓게 묻지 않고, 후보와 이유를 함께 제시해 사용자가 한 번에 선택할 수 있게 한다.
- 읽기/확인 질문은 가볍게 처리하되, 파일 변경/삭제/이동은 맥락 확정 없이 실행하지 않는다.

### B2B Context Assurance

haro는 B2B 업무용 에이전트이므로, 사용자의 맥락을 빠르게 해석하는 능력과 중요한 순간에 확실히 확인하는 능력을 동시에 가져야 한다.

원칙:

- 사용자가 짧게 말해도 최근 대화, 현재 열린 파일, 선택 영역, latest artifact, 도구 결과를 종합해 먼저 해석한다.
- 단순 읽기/요약/확인 요청은 confidence가 충분하면 확인 질문 없이 진행한다.
- 파일 수정, 삭제, 이동, 외부 최신 정보 반영, 업무 데이터 재가공, 산출물 배포처럼 되돌리기 어렵거나 신뢰 비용이 큰 작업은 target/source/작업 단위 confidence를 따로 계산한다.
- confidence가 낮으면 추가 검색을 무한 반복하지 않고, 지금까지 확인한 후보와 부족한 정보를 요약한 뒤 구체적으로 확인한다.
- 확인 질문은 업무 흐름을 끊지 않도록 선택지를 좁혀 제시한다.
- 같은 질문을 반복하지 않기 위해 한 intent 안에서 이미 확인한 후보, 실패한 검색, 사용자의 정정 내용을 `TurnToolState`에 기록한다.

Confidence 축:

- `context_confidence`: 사용자가 가리키는 현재 맥락이 무엇인지에 대한 확신도
- `target_confidence`: 수정/읽기/분석 대상 파일 또는 artifact에 대한 확신도
- `source_confidence`: 추가로 참고해야 할 원본 데이터나 사용자가 "추가했다"고 말한 파일에 대한 확신도
- `operation_confidence`: 사용자가 원하는 작업 단위가 추가/교체/요약/비교/삭제 중 무엇인지에 대한 확신도
- `risk_level`: 작업이 잘못되었을 때 데이터 손상, 업무 혼선, 외부 노출, 되돌리기 비용이 얼마나 큰지

정책 매트릭스:

| 조건 | 동작 |
| --- | --- |
| read-only이고 context/target confidence가 높음 | 바로 읽고 답변한다. |
| read-only이지만 active file과 latest artifact가 다름 | active file을 우선하되 둘을 구분해 설명한다. |
| file write이고 target confidence는 높지만 operation confidence가 낮음 | 파일을 읽고 구조를 진단한 뒤, 수정 전 구체적 후보를 확인한다. |
| file write이고 target/source 중 하나가 낮음 | 반복 검색 전에 확인한 위치와 누락 정보를 말하고 경로/재업로드/웹 검색 허용 여부를 묻는다. |
| delete/move/overwrite/deploy처럼 되돌리기 어려움 | confidence가 높아도 핵심 대상과 행동을 한 번 확정한다. |
| 사용자가 "응?", "아니", "그게 맞아?"로 정정함 | 방어적 설명보다 직전 판단 근거와 실제 파일/도구 결과를 재검증한다. |

좋은 확인 질문 예:

- "현재 열린 파일은 `건설업등록목록 1.csv`이고, 직전 산출물은 `서울_날씨_대시보드_20260509.html`입니다. '지금 뭐가 보여?'는 현재 열린 CSV 기준으로 설명하겠습니다."
- "`오늘 날짜도 아래에 추가`는 기존 5월 9일 카드 아래에 5월 10일 날씨 카드를 추가하는 의미로 보입니다. 5월 10일 실제 날씨 데이터가 아직 없는데, 웹 검색으로 채워도 될까요?"
- "`이미 파일로 추가`하신 source 파일을 `받은 파일`, 채팅 `inputs`, `날씨_브리핑` 폴더에서 찾지 못했습니다. 파일 경로를 알려주시거나 다시 업로드해 주세요."

나쁜 확인 질문 예:

- "어떤 파일인가요?"
- "무엇을 원하시나요?"
- "다시 설명해 주세요."

### Thin Gate

Gate는 다음 정도만 판단한다.

- 일반 대화인지
- 진행 중인 clarification 또는 plan approval에 대한 답변인지
- 최근 artifact/preview/작업에 대한 후속인지
- 취소 요청인지
- 참조 대상이 모호한지

Gate는 도구 선택이나 작업 의미를 결정하지 않는다.

### ExecutionPolicyResolver

`ExecutionPolicyResolver`는 기존 router의 대체물이다. 단, 의미 판단을 하지 않고 안전 프로필만 고른다.

예상 profile:

- `chat_only`: 도구 없이 답변
- `read_only`: 파일/폴더/상태 확인
- `file_work`: 파일 생성/수정/부분 편집
- `workspace_admin`: 이동/정리/삭제 같은 workspace 관리
- `research`: 외부 최신 정보 또는 출처 확인
- `code_or_preview`: 코드 실행, 웹 프리뷰, 산출물 확인
- `plan_mode`: 승인 전 계획 수립

각 profile은 broad tool set을 제공한다. 예를 들어 `file_work`는 `file_search`, `dir_list`, `file_read`, `file_stats`, `file_search_content`, `file_read_range`, `file_edit`, `file_append`, `file_replace_range`, `file_create`를 포함할 수 있다.

### Working Context

Executor가 매 턴 받는 compact context다.

포함 정보:

- 현재 사용자 메시지 원문
- gate decision과 이유
- 최근 사용자/assistant 메시지
- latest artifact / latest preview
- open file context
- file discovery candidates
- current date/time
- chat workspace와 user result folder alias
- 최근 intent/plan 상태
- 이전 tool result 요약
- 사용자가 명시한 제약

Working Context는 "현재 턴 라우팅 맥락"이 아니라 "현재 작업 맥락"이다.

### TurnToolState

한 턴의 도구 루프 동안 유지되는 실행 상태다.

추적 정보:

- read/stat/search_content/read_range로 확인한 파일과 checksum
- 이미 실행한 search query/scope/signature
- target/source/context 후보
- write/delete/move가 시도된 경로
- blocked tool call과 이유
- web_search 성공/실패 상태

정책:

- 기존 파일 수정/삭제/이동은 같은 턴에서 파일 상태를 확인한 뒤 실행한다.
- 동일 query/scope의 반복 file search는 synthetic result로 막는다.
- web_search 실패 후 내부 지식으로 최신 정보를 대체하지 않는다.
- write guard가 막은 경우 모델에는 "먼저 파일을 읽거나 범위를 확인하라"는 tool result를 돌려준다.

### Prompt Assembler

기존 `SYSTEM_PROMPT`, tool descriptions, routing context instruction을 한 덩어리로 합치는 방식을 분리한다.

섹션:

- stable system policy
- workspace policy
- tool contract
- agentic workflow policy
- working context
- plan mode 또는 approved plan context

v1에서는 prompt cache를 구현하지 않아도 되지만, stable/dynamic section이 분리되도록 만든다.

## 사용자 흐름

### 1. 현재 파일을 묻는 경우

사용자: "지금 뭐가 보여?"

동작:

- gate는 artifact/open file follow-up 또는 read-only task로만 판단한다.
- policy는 `read_only`를 선택한다.
- executor는 open file context를 latest artifact보다 우선한다.
- active file이 있으면 그 파일을 먼저 읽고, latest artifact는 보조 후보로만 둔다.
- 답변은 실제 active file의 내용과 구조를 기준으로 한다.
- active file과 latest artifact가 다르면, "현재 열려 있는 파일은 X이고, 이전 작업 산출물은 Y"처럼 구분해 설명한다.

### 2. 현재 파일 아래에 오늘 날짜를 추가하는 경우

사용자: "여기에 오늘 날짜도 아래에 추가해줘"

동작:

- policy는 `file_work`를 선택한다.
- executor는 현재 파일 또는 latest artifact를 먼저 읽는다.
- 기존 파일이 날짜별 대시보드/섹션 구조라면, "오늘 날짜도 아래에"를 같은 수준의 새 날짜 섹션 추가로 해석한다.
- 오늘 날짜의 실제 날씨 데이터가 파일/대화/web_search 결과로 없으면 사용자에게 source를 묻거나, web_search 허용이 필요하다고 판단한다.
- 단순 footer timestamp만 추가하지 않는다.

### 3. 기존에 작성한 파일을 찾는 경우

사용자: "이미 파일로 추가했었어"

동작:

- 이 말은 source content 후보가 존재한다는 신호로 처리한다.
- executor는 recent messages, open file context, linked files, artifacts, chat inputs/outputs, topic folder를 우선 본다.
- 후보가 없으면 같은 키워드 검색을 반복하지 않고, 확인한 위치와 없는 정보를 요약한 뒤 경로 또는 재업로드를 요청한다.

### 4. 사용자가 짧게 문제를 제기하는 경우

사용자: "응?", "이게 아닌데", "안 보이는데?"

동작:

- gate는 최근 artifact/tool result follow-up으로 판단한다.
- executor는 직전 assistant message, 직전 tool result, 변경 파일 후보를 Working Context로 받는다.
- 필요한 경우 변경 파일을 다시 읽거나 diff/trace를 확인한다.
- 방어적 설명보다 "제가 어떤 의미로 처리했고, 실제 파일에는 무엇이 들어갔는지"를 먼저 진단한다.

### 5. 열린 파일과 최근 산출물이 다른 경우

상황:

- 직전 작업 산출물은 `서울_날씨_대시보드_20260509.html`이다.
- 하지만 사용자가 현재 에디터에서 보고 있는 active file은 `건설업등록목록 1.csv`다.
- 사용자가 "지금은 뭐가 보여?"라고 묻는다.

동작:

- executor는 latest artifact를 현재 화면이라고 가정하지 않는다.
- active file context가 있으면 active file을 1순위로 읽고 설명한다.
- latest artifact가 있더라도 "이전 작업 파일"과 "현재 열린 파일"을 분리한다.
- active file을 읽을 수 없거나 open file context가 없을 때만 latest artifact 또는 최근 대화 맥락을 fallback으로 사용한다.
- fallback을 사용한 경우에는 "현재 열린 파일 정보가 없어 최근 산출물을 기준으로 답한다"고 명시한다.

## 성공 기준

- router가 "작업 의미"를 결정하지 않는다. 의미 판단은 executor가 Working Context와 도구 결과를 보고 수행한다.
- `selected_tools`는 narrow intent 결과가 아니라 execution profile 기반 broad tool set이다.
- executor가 `context_confidence`, `target_confidence`, `source_confidence`, `operation_confidence`, `risk_level`을 사용해 진행/추가 탐색/확인 질문/차단을 구분한다.
- 기존 파일 변경 전 target file read/stat/search_content/read_range 중 하나가 선행된다.
- "오늘 날짜도 아래에 추가" 회귀에서 footer timestamp만 추가하는 행동을 방지한다.
- "이미 파일로 추가했어" 회귀에서 target HTML과 source content 후보를 분리하고, source가 없으면 반복 검색 대신 경로/재업로드 요청으로 전환한다.
- active file과 latest artifact가 다를 때 latest artifact를 현재 열린 파일로 오인하지 않는다.
- 맥락 후보가 여러 개이거나 작업 단위가 모호하면 파일 변경 전에 확인 질문을 한다.
- 확인 질문이 필요한 경우 넓고 모호한 질문이 아니라 후보, 이유, 누락 정보를 포함한 구체적 질문을 한다.
- 낮은 위험의 read-only 요청에서는 충분한 confidence가 있으면 불필요한 확인 질문 없이 진행한다.
- "응?" 같은 반응에서 최근 작업 결과를 재진단한다.
- debug trace에서 `execution_policy`, `working_context`, `tool_state_guard`, `file_discovery_candidates`, `duplicate_file_search_skipped`를 확인할 수 있다.
- Plan Mode와 approved plan execution은 기존 사용자 경험을 유지한다.
- 기존 파일 도구 JSON 계약은 깨지지 않는다.

## 검증 기준

Backend unit tests:

- `ExecutionPolicyResolver`가 일반 대화, read-only, file_work, workspace_admin, research, code_or_preview, plan_mode 요청을 올바른 profile로 분류한다.
- `Working Context`가 open file, latest artifact, file discovery candidates, recent messages를 compact하게 포함한다.
- write tool이 대상 파일 확인 없이 호출되면 `TurnToolState` guard가 synthetic result로 차단한다.
- 동일 intent 안에서 같은 `file_search`, `dir_list`, `file_search_content` signature가 반복 실행되지 않는다.
- "지금 뭐가 보여?"는 active/latest file 기반 read-only 흐름으로 간다.
- active file이 `건설업등록목록 1.csv`이고 latest artifact가 날씨 HTML이면, "지금 뭐가 보여?" 답변은 CSV를 기준으로 한다.
- "여기에 오늘 날짜도 아래에 추가해줘"는 기존 파일 구조 확인 후 peer date section 추가 의도로 처리된다.
- "이미 파일로 추가했어"는 source candidate 신호로 처리된다.
- "응?"은 최근 tool result와 assistant message를 포함한 재진단 흐름으로 간다.
- low-risk read-only 요청은 확인 질문 없이 진행하고, high-risk write/delete/move 요청은 confidence가 낮을 때 구체적인 확인 질문으로 전환한다.
- 확인 질문 생성 로직은 후보 경로, 후보 역할, 판단 이유, 누락 정보를 포함한다.

Frontend checks:

- active file path, opened file paths, language, active tab, dirty, selection preview가 메시지 payload에 포함된다.
- selection이 없으면 파일 본문 preview를 보내지 않는다.
- dirty 파일 전체 내용은 자동 전송하지 않는다.

Verification commands:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd ../frontend
npm run build
```

## 남은 질문

- 기존 `RouterDecision` 타입을 완전히 새 `ExecutionPolicy` 타입으로 교체할지, migration 기간 동안 compatibility adapter를 둘지 정해야 한다.
- `IntentTurn.current_intent`에는 profile 이름을 저장할지, 별도 `execution_profile` 컬럼을 추가할지 정해야 한다.
- "오늘 날짜" 같은 현재 정보가 필요한 작업에서 web_search를 자동 허용할 기준을 design 단계에서 더 좁혀야 한다.
- prompt assembler의 stable/dynamic section 경계와 debug trace 노출 범위를 design 단계에서 확정해야 한다.
- existing `context-aware-file-discovery` work spec을 언제 새 스펙의 design/implementation 문서로 병합할지 정해야 한다.
