# Claude Code 아키텍처 보고서

> 문과생도 이해할 수 있는, 소설처럼 읽는 코드 해부기

---

## 프롤로그: Claude Code란 무엇인가

터미널 — 그 까만 화면에서 텍스트만으로 컴퓨터와 대화하는 공간.
Claude Code는 바로 그 터미널 안에서 AI(Claude)와 함께 코딩하는 도구다.

"이 파일 읽어줘", "버그 고쳐줘", "커밋해줘" 같은 말을 치면,
Claude가 직접 파일을 열고, 코드를 수정하고, 명령어를 실행한다.

이 프로젝트는 TypeScript로 작성된 약 51만 줄, 1,900개 파일의 대규모 소프트웨어다.
그 안에는 놀라울 정도로 정교한 구조가 숨어 있다.

---

## 1장. 문이 열리는 순간 — 진입점(Entrypoint)

모든 이야기에는 시작이 있다. Claude Code의 시작은 `entrypoints/cli.tsx`다.

사용자가 터미널에 `claude`라고 치는 순간, 이 파일이 가장 먼저 깨어난다.
하지만 이 파일은 영리하다. 모든 것을 한꺼번에 불러오지 않는다.

```
사용자가 "claude --version"을 치면?
→ 버전 번호만 출력하고 즉시 종료. 다른 건 아무것도 로드하지 않는다.

사용자가 "claude"만 치면?
→ 그제서야 본격적인 프로그램(main.tsx)을 불러온다.
```

이것을 **"패스트 패스(Fast Path)"**라고 부른다.
레스토랑에 비유하면, 테이크아웃 손님에게 풀코스 메뉴판을 내밀지 않는 것과 같다.
필요한 만큼만, 최소한으로, 빠르게. 이것이 이 프로그램의 첫 번째 철학이다.

---

## 2장. 두뇌 — QueryEngine

`QueryEngine.ts`는 이 프로그램의 두뇌다. 약 46,000줄에 달하는 거대한 파일이다.

하는 일은 단순하게 요약된다:

1. 사용자의 말을 받는다
2. Claude AI에게 보낸다
3. Claude의 답변을 받는다
4. 답변 속에 "도구를 써달라"는 요청이 있으면, 도구를 실행한다
5. 도구 실행 결과를 다시 Claude에게 보낸다
6. 이 과정을 Claude가 "다 했어"라고 할 때까지 반복한다

이것을 **"도구 루프(Tool Loop)"**라고 부른다.

비유하자면 이렇다. 당신이 인테리어 디자이너(Claude)에게 "거실 꾸며줘"라고 말했다.
디자이너가 "먼저 거실 사진 좀 보여주세요"라고 한다. (→ FileReadTool)
사진을 보여주면 "벽 색깔을 바꿀게요"라고 한다. (→ FileWriteTool)
그리고 "가구 배치도 확인할게요"라고 한다. (→ GrepTool)
이 대화가 끝날 때까지 계속 왔다 갔다 하는 것이다.

```
[사용자] → "버그 고쳐줘"
    ↓
[QueryEngine] → Claude API 호출
    ↓
[Claude] → "먼저 파일을 읽어볼게요" (FileReadTool 요청)
    ↓
[QueryEngine] → FileReadTool 실행 → 결과를 Claude에게 전달
    ↓
[Claude] → "문제를 찾았어요. 수정할게요" (FileEditTool 요청)
    ↓
[QueryEngine] → FileEditTool 실행 → 결과를 Claude에게 전달
    ↓
[Claude] → "수정 완료했습니다!"
    ↓
[사용자에게 결과 표시]
```

---

## 3장. 손과 발 — Tool 시스템

Claude는 생각만 하는 존재다. 실제로 파일을 열거나, 명령어를 실행하는 건 **도구(Tool)**가 한다.

`Tool.ts`는 모든 도구의 설계도(청사진)다. 약 29,000줄.
모든 도구는 이 설계도를 따라 만들어진다.

### 도구의 해부학

모든 도구는 다음과 같은 구조를 가진다:

| 구성 요소 | 역할 | 비유 |
|-----------|------|------|
| `name` | 도구의 이름 | 직원의 이름표 |
| `inputSchema` | 어떤 입력을 받는지 | 주문서 양식 |
| `call()` | 실제로 일을 하는 함수 | 직원이 일하는 행위 |
| `checkPermissions()` | 이 일을 해도 되는지 확인 | 상사의 결재 |
| `description()` | Claude에게 "나는 이런 일을 해"라고 알려주는 설명 | 직원의 직무기술서 |
| `isReadOnly()` | 읽기만 하는지, 수정도 하는지 | 열람 권한 vs 수정 권한 |

### 주요 도구들

약 40개의 도구가 있다. 카테고리별로 나누면:

**파일 관련 — 서류 담당 직원**
- `FileReadTool` — 파일을 읽는다. 이미지, PDF, 노트북도 읽을 수 있다.
- `FileWriteTool` — 새 파일을 만들거나 덮어쓴다.
- `FileEditTool` — 파일의 일부분만 수정한다. 전체를 다시 쓰지 않고 필요한 부분만 바꾼다.

**검색 관련 — 탐정**
- `GlobTool` — 파일 이름 패턴으로 찾는다. "*.tsx 파일 다 찾아줘" 같은 요청.
- `GrepTool` — 파일 내용에서 특정 텍스트를 찾는다. ripgrep이라는 초고속 검색 엔진을 사용한다.
- `WebSearchTool` — 인터넷을 검색한다.
- `WebFetchTool` — 특정 웹페이지의 내용을 가져온다.

**실행 관련 — 현장 작업자**
- `BashTool` — 터미널 명령어를 실행한다. `npm install`, `git commit` 같은 것들.

**에이전트 관련 — 팀장**
- `AgentTool` — 하위 에이전트를 생성한다. 복잡한 작업을 여러 AI에게 나눠줄 수 있다.
- `SendMessageTool` — 에이전트끼리 메시지를 주고받는다.

### 도구가 만들어지는 과정

`buildTool()`이라는 함수가 설계도를 받아서 실제 도구를 만든다.
공장에서 설계도를 넣으면 제품이 나오는 것과 같다.

```typescript
// 이런 식으로 도구를 정의한다 (실제 코드를 단순화한 예시)
const FileReadTool = buildTool({
  name: 'Read',
  inputSchema: { file_path: "읽을 파일 경로" },
  async call({ file_path }) {
    // 파일을 읽어서 내용을 반환
    return readFile(file_path)
  },
  async checkPermissions(input) {
    // 이 파일을 읽어도 되는지 확인
    return checkReadPermission(input.file_path)
  }
})
```

---

## 4장. 경비원 — 권한(Permission) 시스템

Claude가 아무 파일이나 읽고, 아무 명령어나 실행하면 위험하다.
그래서 **권한 시스템**이 존재한다. 모든 도구 실행 전에 "이거 해도 돼?"라고 묻는 경비원이다.

권한 시스템은 세 가지 방식으로 작동한다:

**1. 사용자에게 직접 묻기**
```
Claude가 "rm -rf /" 를 실행하려 합니다. 허용하시겠습니까? [Y/n]
```

**2. 규칙 기반 자동 승인**
"이 폴더 안의 파일은 읽어도 돼"라는 규칙을 미리 설정해둘 수 있다.

**3. AI 분류기(Classifier)**
BashTool의 경우, 명령어가 안전한지 AI가 자동으로 판단하기도 한다.

권한 결정의 흐름은 이렇다:

```
도구 실행 요청
    ↓
거부 규칙에 해당하는가? → Yes → 차단
    ↓ No
허용 규칙에 해당하는가? → Yes → 실행
    ↓ No
사용자에게 물어보기 → 허용/거부
    ↓
사용자가 "항상 허용"을 선택하면 → 규칙으로 저장
```

이 시스템 덕분에 Claude는 강력하면서도 안전하다.
칼을 쥐고 있지만, 칼집에서 빼기 전에 항상 허락을 구하는 셈이다.

---

## 5장. 화면 — React + Ink 터미널 UI

놀라운 점이 있다. 이 프로그램의 화면은 **React**로 만들어져 있다.
React는 보통 웹사이트를 만들 때 쓰는 기술인데, 여기서는 터미널 화면을 그리는 데 쓴다.

**Ink**라는 라이브러리가 이것을 가능하게 한다.
웹에서 `<div>`와 `<span>`으로 화면을 구성하듯,
터미널에서 `<Box>`와 `<Text>`로 화면을 구성한다.

```
┌─────────────────────────────────────┐
│  Claude Code                        │  ← 상단 상태바
├─────────────────────────────────────┤
│                                     │
│  사용자: 버그 고쳐줘                  │  ← 메시지 목록
│                                     │
│  Claude: 파일을 확인하고 있습니다...   │
│  ⠋ Reading src/app.ts               │  ← 스피너 (로딩 표시)
│                                     │
├─────────────────────────────────────┤
│  > _                                │  ← 입력창 (PromptInput)
└─────────────────────────────────────┘
```

`REPL.tsx`가 이 화면 전체를 관장한다. 약 5,000줄의 거대한 컴포넌트다.
REPL은 "Read-Eval-Print Loop"의 약자로, "읽고-처리하고-보여주고-반복"이라는 뜻이다.

---

## 6장. 기억 — 상태 관리(State Management)

프로그램이 실행되는 동안 수많은 정보를 기억해야 한다.
"지금 어떤 모델을 쓰고 있지?", "권한 설정은 뭐였지?", "대화 내역은?"

이 기억을 관리하는 것이 **Store**다.

```typescript
// store.ts — 놀라울 정도로 단순하다
function createStore(initialState) {
  let state = initialState          // 현재 상태
  const listeners = new Set()       // 상태가 바뀌면 알려줄 대상들

  return {
    getState: () => state,          // 현재 상태 읽기
    setState: (updater) => {        // 상태 변경
      state = updater(state)
      listeners.forEach(fn => fn()) // 변경 알림
    },
    subscribe: (listener) => {      // 알림 구독
      listeners.add(listener)
      return () => listeners.delete(listener)
    }
  }
}
```

이것은 마치 칠판과 같다.
- 누구나 칠판을 볼 수 있다 (`getState`)
- 정해진 방법으로만 칠판에 쓸 수 있다 (`setState`)
- "칠판이 바뀌면 알려줘"라고 등록할 수 있다 (`subscribe`)

---

## 7장. 맥락 — Context 시스템

Claude가 똑똑하게 답하려면 **맥락**이 필요하다.
"지금 어떤 프로젝트에서 작업 중인지", "Git 상태는 어떤지", "오늘 날짜는 언제인지".

`context.ts`가 이 맥락을 수집한다.

```
시스템 맥락:
  - 운영체제: macOS 15.0
  - 셸: zsh
  - 현재 디렉토리: /Users/me/project

Git 맥락:
  - 현재 브랜치: feature/login
  - 메인 브랜치: main
  - 변경된 파일: 3개

사용자 맥락:
  - CLAUDE.md 파일의 내용 (프로젝트 규칙)
  - 메모리 파일 (이전 대화에서 기억한 것들)
```

이 모든 정보가 Claude에게 전달되어, Claude가 "아, 이 사람은 지금 로그인 기능을 만들고 있구나"라고 이해할 수 있게 된다.

---

## 8장. 시스템 프롬프트 — Claude에게 주는 대본

`constants/prompts.ts`는 Claude에게 주는 **대본**이다.

Claude는 범용 AI다. 아무 지시 없이는 코딩 도우미처럼 행동하지 않는다.
그래서 매 대화 시작 시, 이런 지시를 보낸다:

```
"너는 Claude Code라는 코딩 도우미야.
 사용자의 코드를 읽고, 수정하고, 명령어를 실행할 수 있어.
 다음 도구들을 사용할 수 있어: Read, Write, Edit, Bash, Grep...
 파일을 수정할 때는 반드시 권한을 확인해.
 현재 작업 디렉토리는 /Users/me/project이야.
 현재 Git 브랜치는 feature/login이야."
```

이 대본은 상황에 따라 동적으로 바뀐다.
사용 가능한 도구, 현재 환경, 사용자 설정에 따라 매번 다른 대본이 만들어진다.

---

## 9장. 비용 — Cost Tracker

AI API 호출에는 돈이 든다. `cost-tracker.ts`가 이 비용을 추적한다.

```
입력 토큰: 15,234개 → $0.045
출력 토큰: 3,891개 → $0.058
캐시 읽기 토큰: 8,000개 → $0.002
총 비용: $0.105
```

토큰이란 AI가 처리하는 텍스트의 단위다.
대략 영어 단어 하나가 1~2토큰, 한글 한 글자가 1~2토큰 정도다.

비용 추적기는 모델별, 세션별로 사용량을 기록하고,
사용자가 설정한 비용 한도에 도달하면 경고를 보낸다.

---

## 10장. 슬래시 커맨드 — 사용자의 지름길

`/`로 시작하는 명령어들이 있다. 약 50개.

```
/compact  — 대화 내역을 압축한다 (토큰 절약)
/commit   — Git 커밋을 만든다
/review   — 코드 리뷰를 요청한다
/memory   — 기억을 관리한다
/doctor   — 환경 진단을 실행한다
/config   — 설정을 변경한다
/diff     — 변경사항을 본다
/cost     — 현재까지의 비용을 확인한다
```

이것들은 Claude에게 말로 요청하는 것과 다르다.
프로그램이 직접 처리하는 **단축키** 같은 것이다.

---

## 11장. 다리 — Bridge 시스템

Claude Code는 터미널에서만 동작하는 게 아니다.
VS Code나 JetBrains 같은 IDE(코드 편집기)와도 연결된다.

`bridge/` 폴더가 이 연결을 담당한다.

```
[VS Code 확장]  ←→  [Bridge]  ←→  [Claude Code CLI]
```

Bridge는 양방향 통신 채널이다.
IDE에서 "이 코드 설명해줘"라고 하면, Bridge를 통해 CLI로 전달되고,
CLI의 응답이 다시 Bridge를 통해 IDE로 돌아온다.

JWT(JSON Web Token)로 인증하고, WebSocket으로 실시간 통신한다.

---

## 12장. 기억력 — Memory 시스템

Claude Code는 대화가 끝나도 중요한 것을 기억할 수 있다.

`memdir/` 폴더가 이 기억을 관리한다.

```
~/.claude/memory/
  ├── project-conventions.md    — "이 프로젝트는 탭 대신 스페이스 2칸을 쓴다"
  ├── user-preferences.md       — "사용자는 한국어로 답변받기를 원한다"
  └── recent-decisions.md       — "어제 로그인 로직을 JWT로 바꾸기로 했다"
```

대화 중에 중요한 정보가 나오면 자동으로 추출해서 저장하고,
다음 대화에서 이 기억을 불러와 맥락으로 활용한다.

---

## 13장. 성능의 비밀 — 최적화 패턴들

51만 줄의 코드가 빠르게 동작하는 비결이 있다.

### 병렬 프리페치 (Parallel Prefetch)
프로그램이 시작될 때, 여러 준비 작업을 **동시에** 실행한다.
설정 읽기, 인증 확인, API 연결을 순서대로 하면 느리지만,
동시에 하면 가장 느린 작업의 시간만큼만 걸린다.

### 지연 로딩 (Lazy Loading)
무거운 모듈은 실제로 필요할 때까지 불러오지 않는다.
OpenTelemetry(약 400KB)나 gRPC(약 700KB) 같은 것들은
사용자가 해당 기능을 쓸 때 비로소 로드된다.

### 빌드타임 기능 제거 (Dead Code Elimination)
```typescript
if (feature('VOICE_MODE')) {
  // 음성 모드 코드
}
```
`feature()` 함수는 빌드 시점에 true/false로 결정된다.
false인 코드는 최종 빌드에서 완전히 제거된다.
사용하지 않는 기능의 코드가 프로그램 크기를 늘리지 않는 것이다.

### 파일 읽기 중복 제거 (Dedup)
같은 파일을 두 번 읽으면, 두 번째는 "아까 읽은 거랑 같아"라는 짧은 메시지만 보낸다.
이것만으로 API 비용의 약 2.6%를 절약한다.

---

## 에필로그: 전체 흐름 요약

```
사용자가 "claude"를 실행
    ↓
[cli.tsx] 진입점 — 빠른 분기 처리
    ↓
[main.tsx] CLI 파싱 + React/Ink UI 시작
    ↓
[REPL.tsx] 대화 화면 렌더링
    ↓
사용자가 메시지 입력
    ↓
[context.ts] 맥락 수집 (Git, 환경, 메모리)
    ↓
[prompts.ts] 시스템 프롬프트 조립
    ↓
[QueryEngine.ts] Claude API 호출
    ↓
Claude가 도구 사용 요청 ←──────────────┐
    ↓                                   │
[Tool.ts] 도구 실행                      │
    ↓                                   │
[Permission] 권한 확인                   │
    ↓                                   │
도구 실행 결과를 Claude에게 전달 ──────────┘
    ↓
Claude가 최종 답변 생성
    ↓
[cost-tracker.ts] 비용 기록
    ↓
화면에 결과 표시
```

이것이 Claude Code의 심장이 뛰는 방식이다.

---

## 부록: 기술 스택 한눈에 보기

| 구분 | 기술 | 한 줄 설명 |
|------|------|-----------|
| 런타임 | Bun | Node.js보다 빠른 JavaScript 실행 환경 |
| 언어 | TypeScript | JavaScript에 타입을 더한 언어 |
| 터미널 UI | React + Ink | 웹 기술로 터미널 화면을 그리는 방식 |
| CLI 파싱 | Commander.js | 명령줄 옵션을 해석하는 라이브러리 |
| 스키마 검증 | Zod | 데이터 형식이 올바른지 확인하는 도구 |
| 코드 검색 | ripgrep | 초고속 텍스트 검색 엔진 |
| AI API | Anthropic SDK | Claude AI와 통신하는 공식 라이브러리 |
| 프로토콜 | MCP, LSP | AI 도구 연결(MCP), 코드 편집기 연결(LSP) |
| 인증 | OAuth 2.0, JWT | 사용자 인증과 보안 토큰 |
| 기능 플래그 | GrowthBook | 기능을 선택적으로 켜고 끄는 시스템 |

---

*이 보고서는 [codeaashu/claude-code](https://github.com/codeaashu/claude-code) 레포지토리의 소스코드를 분석하여 작성되었습니다.*
