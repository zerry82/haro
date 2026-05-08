# AGENTS.md

이 파일은 Codex CLI 세션이 초기화되더라도 이 저장소에서 계속 참고해야 할 프로젝트 지침이다.

## 프로젝트 방향성

haro는 ChatGPT와 유사한 대화형 AI 서비스이지만, 핵심 차별점은 프로젝트마다 독립된 물리적 파일 작업공간을 제공한다는 점이다.

사용자는 하나의 프로젝트 안에서 여러 채팅을 이어갈 수 있고, AI 에이전트는 단순 답변을 넘어 프로젝트 워크스페이스의 파일과 폴더를 직접 생성, 수정, 검색, 삭제하며 실제 산출물을 만든다.

현재 구현의 방향은 팀장/팀원 멀티 에이전트 구조가 아니라 단일 에이전트가 의도 판단, 계획, 도구 실행을 모두 담당하는 구조다. MCP/FastMCP 기반 스킬 시스템은 확장 방향으로 남아 있지만, 현재 실행 경로는 백엔드 내장 도구 중심이다.

## 핵심 아키텍처

현재 주 흐름은 `Project` + `ChatSession`이다. `Session`, `Todo`, `Chat.svelte`, `sessions.ts` 등은 초기 설계의 레거시 호환 요소로 보고, 새 기능을 설계할 때는 프로젝트/채팅 세션 구조를 우선한다.

전체 요청 흐름:

```text
사용자 브라우저
  -> Svelte SPA
  -> FastAPI API
  -> POST /api/projects/{project_id}/chats/{chat_id}/messages
  -> SSE 스트리밍 응답
  -> run_agent()
      -> 사용자 메시지 저장
      -> intent gate 판단
      -> intent router가 실행 가능 여부와 선택 도구 결정
      -> Gemini 스트리밍 호출
      -> tool_call JSON 블록 파싱
      -> 백엔드 내장 도구 실행
      -> 파일 변경, 로그, 디버그 트레이스, 프리뷰 이벤트 기록
```

주요 기술 스택:

- 백엔드: FastAPI, SQLAlchemy async, SQLite
- 프론트엔드: Svelte 5, Vite, svelte-spa-router
- 실시간 통신: POST 응답 기반 SSE
- 인증: JWT Bearer token, bcrypt password hash
- LLM: Google Gemini API
- 파일 저장: 로컬 파일시스템 워크스페이스
- 파일 인덱스: 워크스페이스별 `.haro/db/workspace.db`
- 코드 실행/프리뷰: Docker SDK와 `denoland/deno:latest` 컨테이너

에이전트 도구 실행은 현재 `src/backend/app/services/tool_registry.py`와 `src/backend/app/services/agent_tools.py`를 기준으로 이해한다. Docker 코드 실행과 웹 프리뷰는 `src/backend/app/services/container_manager.py`가 담당한다.

## 상위 폴더 구성

```text
.
  AGENTS.md    Codex가 세션마다 우선 참고할 저장소 지침
  .specs/      중요한 패치 단위의 스펙, 구현 결과, 연결 커밋 기록
  DESIGN.md    초기 설계 또는 디자인 관련 문서
  doc/         제품/기술/마케팅/구현 정리 문서
  scripts/     보조 스크립트
  src/         실제 제품 소스와 설계 문서
  study/       학습/조사 자료
  tmp/         임시 작업 파일
```

`src` 하위 구조:

```text
src/
  backend/           FastAPI 백엔드
  frontend/          Svelte 5 + Vite 프론트엔드
  sandbox-runtime/   독립형 샌드박스 런타임 실험 구현
  plan/              제품 설계/기획 문서
```

`doc/src/README.md`는 `src` 구현을 이해하기 위한 최신 요약 문서다. `src` 관련 작업을 시작할 때는 이 문서를 먼저 확인하고, 실제 코드는 그다음에 읽는다.

## 작업 원칙

- 변경 전에 관련 파일을 먼저 읽고 현재 구현 흐름을 확인한다.
- 요청 범위에 직접 연결되는 파일만 수정한다.
- 기존 스타일과 현재 아키텍처를 우선한다.
- 불확실한 부분은 가정을 명시하고, 위험한 선택지는 질문한다.
- 레거시 코드를 발견해도 요청과 직접 관련이 없으면 정리하지 않고 언급만 한다.
- 파일 작업, 에이전트 도구, 워크스페이스 정책을 바꿀 때는 `doc/src/README.md`와 `src/plan` 문서도 함께 참고한다.

## 코드 설계와 테스트 원칙

백엔드는 기능 변경과 리팩토링을 할 때 단위 테스트 작성을 필수로 본다. 테스트를 작성하기 어려운 구조라면, 먼저 테스트 가능한 순수 함수나 작은 모듈을 분리하고 그 경계부터 테스트한다. 정말 테스트를 추가하지 못하는 경우에는 이유와 남은 위험을 작업 결과에 명시한다.

백엔드 코드는 강력한 모듈화를 기본 원칙으로 삼는다. 클래스와 모듈은 디자인 패턴 설계 원칙을 따른다. 특히 SRP(Single Responsibility Principle)를 강하게 지켜, 하나의 클래스/모듈/함수가 하나의 명확한 책임만 갖도록 한다.

여러 하위 서비스나 복잡한 실행 흐름을 조립할 때는 Facade 패턴을 우선 고려한다. 외부 호출자는 단순한 Facade API를 사용하고, 내부 세부 단계는 작은 모듈들로 나눠 유지한다. 패턴 이름을 위한 패턴이 아니라 책임 분리, 테스트 용이성, 호출부 단순화를 위해 적용한다.

파일, 클래스, 컴포넌트, 함수의 라인 수는 SRP 점검을 위한 신호일 뿐 hard limit가 아니다. 300줄을 넘으면 "의심된다", "설계 냄새가 날 수 있다"는 감각으로 먼저 살펴본다. 300줄을 넘어도 하나의 명확한 책임을 유지하고 변경 이유가 하나라면 허용한다. 반대로 300줄 미만이어도 여러 변경 이유가 섞여 있거나, UI 표현/상태 전이/API 호출/도메인 정책이 한 단위에 뒤섞이면 리팩토링 대상으로 본다.

비대한 파일을 평가할 때는 라인 수보다 SRP를 먼저 본다. 다음 질문에 하나라도 걸리면 분리 후보로 판단한다.

- 이 파일/컴포넌트/클래스가 서로 다른 이유로 자주 바뀔 가능성이 있는가?
- UI 표현, 데이터 로딩, 도메인 정책, 인프라 호출, 포맷 변환이 불필요하게 한곳에 섞여 있는가?
- 테스트하려는 핵심 로직을 외부 시스템이나 거대한 화면 상태 없이 검증하기 어려운가?
- Facade 또는 composition root로 남겨도 되는 조립 책임과, 내부 세부 책임이 구분되어 있는가?

Facade, route component, router module처럼 조립이 본질인 파일은 여러 하위 모듈을 연결할 수 있다. 이 경우에도 직접 정책/세부 알고리즘을 많이 품기 시작하면 내부 모듈로 분리한다.

사용자가 "남은 파일들을 하나씩 진행", "모두 끝낼 때까지 중단하지 마"처럼 범위 내 완결을 명시하면, 이미 식별한 리팩토링 후보를 우선순위대로 하나씩 처리한다. 각 파일/책임 단위마다 가능한 테스트를 추가하거나 기존 테스트를 갱신하고, 단계별 검증을 병행한다. 중간에 멈춰서 계획만 보고하지 않고, 발견한 후보의 책임 분리, 테스트, 빌드/검증, 스펙 문서 갱신까지 현재 턴에서 가능한 한 완결한다.

프론트엔드는 Svelte의 컴포넌트 기능을 적극 활용해 SRP를 지킨다. 화면 하나에 파일 탐색, 채팅, 뷰어, 디버그, 배포 같은 책임이 섞이면 작은 컴포넌트와 스토어/유틸로 분리한다. 컴포넌트는 UI 표현, 상호작용, 데이터 조립 책임이 불필요하게 섞이지 않도록 설계한다.

## 실행 커맨드

개발 서버 기본 포트는 백엔드 `8001`, 프론트엔드 `5174`를 사용한다.

서버 실행 코드, 환경 설정, 의존성, 에이전트 프롬프트/도구/하네스 정책처럼 실행 중인 개발 서버에 바로 영향을 주는 파일을 변경한 뒤 현재 서버가 떠 있으면, 사용자가 별도로 막지 않는 한 해당 서버를 자동으로 재시작한다. 재시작 전후에는 대상 포트의 리스닝 PID와 헬스체크를 확인한다. 기존 프로세스를 종료할 때는 해당 개발 서버 포트의 PID만 대상으로 한다.

프론트엔드 일반 코드 변경은 Vite HMR로 반영되면 재시작하지 않아도 된다. 다만 `vite.config`, `.env`, 의존성, dev server 설정, HMR 실패처럼 런타임 재기동이 필요한 변경이면 프론트엔드 서버도 재시작한다.

가능하면 VS Code 내장 터미널의 task로 실행한다. 저장소에는 `.vscode/tasks.json`이 있으며, VS Code에서 `Terminal > Run Task...`를 열어 다음 task를 사용할 수 있다.

- `dev: backend (8001)`
- `dev: frontend (5174)`
- `dev: all (8001 + 5174)`
- `dev: frontend fallback (5341)`
- `dev: all fallback (8001 + 5341)`

Windows에서 `5174`가 TCP excluded port range에 포함되어 `EACCES`가 나면 fallback task인 `5341`을 사용한다. 이 경우 프론트엔드 접속 주소는 `http://localhost:5341`이다.

Python 백엔드는 반드시 가상환경을 사용한다. 전역 Python 환경에 직접 패키지를 설치하지 않는다. 기본 가상환경 위치는 `src/backend/.venv`다.

백엔드 실행:

```powershell
cd src/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

PowerShell 실행 정책이나 셸 상태 때문에 activate가 어려우면 가상환경의 Python을 직접 호출한다.

```powershell
cd src/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

백엔드 단위 테스트:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

프론트엔드 실행:

```powershell
cd src/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

프론트엔드 단위 테스트와 빌드 확인:

```powershell
cd src/frontend
npm test
npm run build
```

기본 접속:

- 프론트엔드: `http://localhost:5174`
- 백엔드 헬스체크: `http://localhost:8001/api/health`
- 백엔드 CORS 기본값: `http://localhost:5174`

Docker 샌드박스 확인:

```powershell
docker version
docker info
docker image inspect denoland/deno:latest
```

`denoland/deno:latest` 이미지가 없으면 다음으로 받아둔다.

```powershell
docker pull denoland/deno:latest
```

코드 실행과 웹 프리뷰 기능은 Docker 데몬이 정상 실행 중이어야 한다. Docker가 꺼져 있으면 로그인, 프로젝트, 파일 API는 가능한 한 동작하지만 `code_run`, `web_preview`, deploy/preview 경로는 실패할 수 있다. 샌드박스 관련 문제를 확인할 때는 Docker 데몬 상태, `denoland/deno:latest` 이미지 존재 여부, 백엔드 `.env`의 `SANDBOX_*` 설정, 프로젝트의 `container_status`를 함께 확인한다.

## 스펙 드리븐 개발

단순 수정이 아니라 범위가 크거나 제품/아키텍처에 의미 있는 패치 단위라면 스펙을 먼저 만드는 방식을 강하게 우선한다. 사용자가 바로 구현을 요청하더라도, 다음 조건 중 하나에 해당하면 "스펙을 먼저 만드는 것이 좋겠다"고 제안하고 이유를 짧게 설명한다.

- 데이터 모델, API 계약, SSE 이벤트, 에이전트 라우팅, 도구 실행, 워크스페이스 정책이 바뀌는 작업
- 프론트엔드와 백엔드가 함께 바뀌는 기능
- 기존 사용자 데이터, 파일 워크스페이스, Docker 샌드박스, 인증/권한에 영향을 줄 수 있는 작업
- 여러 커밋으로 나누는 것이 자연스러운 크기의 작업
- 요구사항 해석이 애매하거나, 구현 후 되돌리기 어려운 선택지가 있는 작업

스펙을 실제로 개발하기 전에는 구현 전략을 한 번 더 검토한다. "이 전략에 100% 확신이 있나요?"라고 스스로 묻고, 그렇지 않다면 가능한 허점, 실패 조건, 데이터 손상 위험, 되돌리기 어려운 결정, 사용자 경험의 빈틈을 찾아낸다. 발견한 허점마다 적절한 수정 사항을 제안하고, 수정된 전략에 사실상 100% 확신이 들 때까지 이 검토 루프를 반복한다.

스펙은 루트의 `.specs/draft/{spec}/`, `.specs/work/{spec}/`, `.specs/done/{spec}/` 아래에 둔다. `{spec}`은 짧고 의미 있는 kebab-case 이름을 사용한다.

```text
.specs/draft/{spec}/
  {스펙관련 문서들}.md
  {구현결과 문서들}.md
  {연결된 커밋들}.md

.specs/work/{spec}/
  {스펙관련 문서들}.md
  {구현결과 문서들}.md
  {연결된 커밋들}.md

.specs/done/{spec}/
  {스펙관련 문서들}.md
  {구현결과 문서들}.md
  {연결된 커밋들}.md
```

스펙 생명주기는 다음을 따른다.

- `.specs/draft/{spec}/`: 아이디어, 문제 정의, 설계 초안이 있고 아직 구현을 시작하지 않은 스펙
- `.specs/work/{spec}/`: 현재 구현 중이거나 검증/문서 동기화가 진행 중인 스펙
- `.specs/done/{spec}/`: 구현, 검증, 문서 동기화, 연결 커밋 기록까지 끝난 스펙

구현을 시작할 때는 `draft`에서 `work`로 옮기고, 완료되면 `work`에서 `done`으로 옮긴다.

권장 파일 구성:

- `spec.md`: 문제, 목표, 비목표, 사용자 흐름, 성공 기준
- `design.md`: 아키텍처, 데이터 모델, API/SSE 계약, UI 영향, 대안과 결정 이유
- `implementation.md`: 구현 결과, 변경 파일, 검증 결과, 남은 작업
- `commits.md`: 연결된 커밋 해시, 브랜치, PR, 배포/릴리즈 기록

스펙이 있는 작업을 구현할 때는 코드 변경 후 `implementation.md`와 `commits.md`를 최신 상태로 유지한다. 커밋 요청을 받았을 때 연결된 스펙이 있으면 해당 스펙의 문서 동기화 상태도 함께 확인한다.

## 커밋, 푸쉬, 문서 동기화

작업을 마쳤다고 해서 자동으로 커밋하거나 푸쉬하지 않는다. 사용자가 명시적으로 "커밋해줘", "커밋하고 푸쉬해줘"처럼 요청했을 때만 커밋/푸쉬 절차를 수행한다.

커밋 요청을 받으면 다음 순서로 처리한다.

1. `git status`와 관련 diff를 확인해 내가 만든 변경과 기존 사용자 변경을 구분한다.
2. 코드 변경이 문서화된 아키텍처, API, 워크스페이스 정책, 실행 흐름에 영향을 주면 관련 문서도 함께 동기화한다.
3. 가능한 검증 명령을 실행하고, 실행하지 못한 검증은 이유를 기록한다.
4. 요청 범위에 맞는 파일만 stage한다. 관련 없는 변경이나 사용자가 만든 변경은 임의로 포함하지 않는다.
5. 명확한 커밋 메시지로 커밋한다.
6. 사용자가 푸쉬까지 요청했거나 "커밋해줘"를 커밋+푸쉬 의미로 사용한 맥락이 분명하면 현재 브랜치를 원격에 푸쉬한다. 원격/브랜치가 불명확하면 확인 후 진행한다.

문서 동기화는 코드 변경의 일부로 본다. 특히 `src` 구조, 에이전트 도구, SSE 이벤트, 데이터 모델, 워크스페이스 정책, 실행 명령이 바뀌면 `doc/src/README.md`, `src/plan`, 또는 관련 `doc` 문서를 함께 갱신해야 한다.

커밋을 마친 뒤 채팅창에는 다음 내용을 요약해 보고한다.

- 변경 요약: 어떤 코드/설정/문서를 변경했는지 핵심만 정리한다.
- 문서 동기화 요약: 어떤 문서의 어떤 부분을 현재 코드와 맞췄는지, 또는 문서 변경이 필요 없었다면 그 이유를 말한다.
- 검증 결과: 실행한 테스트, 빌드, 린트, 수동 확인 결과를 적고, 실행하지 못한 검증은 이유를 말한다.
- 아쉬움과 위험 요소: 커밋 과정에서 검토했을 때 남아 있는 기술 부채, 애매한 부분, 테스트 공백, 운영상 주의할 점을 솔직하게 적는다.
- 커밋/푸쉬 정보: 커밋 해시, 브랜치, 푸쉬 여부를 알려준다.
