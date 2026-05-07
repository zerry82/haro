# 기술스택 결정안

기준 문서: [technical-core-concepts.md](technical-core-concepts.md)

## 1. 전제

현재 구현은 수요검증용 단계가 아니다.

목표는 다음 기술 가능성을 확인하는 것이다.

> 마케터가 자료와 지침을 넣으면, 에이전트가 내부 샌드박스에서 파일 처리, 코드 실행, 브라우저 자동화, 보고서/대시보드 생성을 수행하고, 최종 결과물을 공유 가능한 웹 링크로 제공할 수 있는가?

사용자는 개발자가 아니다. 사용자는 Docker, VM, 터미널, 포트, 런타임, 브라우저 자동화 구조를 이해하지 않는다.

따라서 제품의 최종 경험은 다음에 가까워야 한다.

```text
프로젝트 생성
  -> 자료 업로드
  -> 목표/지침 선택
  -> 에이전트 실행
  -> 결과 확인
  -> 수정 요청
  -> 예쁜 웹 대시보드/보고서 링크 공유
```

내부 구현은 복잡해도, 사용자에게는 “알아서 처리해주는 마케팅 실행 작업공간”으로 보여야 한다.

## 2. 최종 제품 그림

최종 제품은 개발환경 서비스가 아니다.

목표는 다음이다.

> 마케팅 업무 자동 실행기 + 결과물 포장/공유 시스템

사용자가 기대하는 결과는 다음과 같다.

- 엑셀/CSV/문서/이미지를 업로드하면 알아서 분석한다.
- 캠페인 성과를 정리한다.
- 보고서와 차트를 만든다.
- 광고주/의사결정자에게 보여줄 웹 대시보드를 예쁘게 만든다.
- 사용자가 전략 방향을 조금 수정하면 결과물을 다시 정리한다.
- 공유 가능한 URL을 제공한다.

사용자가 몰라도 되는 것은 다음이다.

- Docker
- VM
- terminal
- container
- runtime
- port
- archive
- browser profile
- Playwright

## 3. 최종 스택 결정

최종 기본 런타임은 **Docker 기반 project sandbox**로 결정한다.

| 영역 | 결정 |
| --- | --- |
| Web UI | Next.js + TypeScript |
| Control Plane API | Node.js + TypeScript + Fastify |
| Metadata DB | PostgreSQL |
| ORM | Drizzle |
| Sandbox Runtime | Docker 기반 project sandbox |
| Workspace Storage | Docker volume |
| Archive Storage | MinIO, 이후 S3/R2 호환 object storage |
| Routing / Preview | Traefik |
| Browser Automation | Playwright + Chromium |
| Browser Observation | accessibility snapshot + DOM bounding box overlay screenshot |
| Human Takeover | noVNC, 2FA/MFA 개입용 |
| Report/Dashboard Output | 정적 HTML/Next.js export 또는 sandbox 내 preview server |
| LLM Tool Layer | 자체 tool interface |

한 문장으로 정리하면 다음과 같다.

> Next.js/Fastify control plane이 프로젝트별 Docker sandbox를 생성하고, 그 안에서 파일 처리, 코드 실행, 브라우저 자동화, 보고서/대시보드 생성을 수행하며, Traefik으로 결과물을 공유 가능한 웹 링크로 노출한다.

## 4. 왜 Docker로 충분한가

이번 제품은 CodeSandbox 같은 개발환경 서비스가 아니다.

사용자는 터미널을 오래 열어두고, 임의 repo를 개발하고, Docker-in-Docker를 돌리고, 커널 수준 기능을 요구하는 개발자가 아니다.

사용자는 마케터다.

사용자가 원하는 것은 다음이다.

- 자료를 넣는다.
- 지침을 준다.
- 에이전트가 알아서 처리한다.
- 보고서를 본다.
- 광고주에게 예쁜 링크를 보낸다.

이 요구에는 Docker가 충분하다.

Docker로 가능한 것:

- 파일 업로드/조회/수정
- Python/Node/Bun 코드 실행
- 데이터 정리와 차트 생성
- Playwright/Chromium 브라우저 자동화
- noVNC 기반 2FA/MFA 사용자 개입
- 웹서버 실행
- Traefik preview URL 노출
- Docker volume 기반 상태 보존
- workspace archive/restore
- 장시간 호스팅 container 운영

즉, 현재 구현과 초기 제품에 필요한 핵심 기능은 전부 Docker로 가능하다.

## 5. VM/microVM은 언제 필요한가

VM/microVM은 지금 기본 선택이 아니다.

다음 요구가 커질 때 검토한다.

- 고객별 강한 격리 요구
- 엔터프라이즈 보안 심사
- 임의 쉘/개발환경 장시간 제공
- Docker-in-Docker 요구
- 실행 중 메모리 snapshot/resume
- 범용 클라우드 컴퓨터 UX
- 대규모 멀티테넌트에서 더 강한 보안 경계 필요

현재 제품의 본질은 개발환경 제공이 아니라 마케팅 결과물 생성이다.

따라서 현재 결정은 다음이다.

```text
현재 기본:
  Docker-based Project Sandbox

미래 옵션:
  VM/microVM isolation layer
```

VM/microVM은 Docker를 대체하는 현재 결정이 아니라, 보안/운영 요구가 커졌을 때 추가할 수 있는 격리 계층이다.

## 6. 핵심 아키텍처

```text
Browser UI
  -> Next.js Web App
  -> Fastify Control Plane API
  -> Project Sandbox Service
  -> Docker Engine
       -> project sandbox container
       -> project workspace volume
       -> Playwright + Chromium
       -> report/dashboard generator
       -> preview web server
  -> Traefik
       -> shareable report/dashboard URL
  -> PostgreSQL
       -> project / sandbox / run metadata
  -> MinIO or S3-compatible Storage
       -> workspace archive
       -> generated artifacts
```

중요한 실행 방식:

```text
Docker-in-Docker를 기본 방식으로 쓰지 않는다.
```

API container가 host Docker daemon을 호출해 프로젝트별 sandbox container를 형제로 생성한다.

```text
EC2 or Docker Host
  -> Docker Engine
       -> web container
       -> api container
       -> traefik container
       -> postgres container
       -> project-sandbox-123 container
       -> project-sandbox-456 container
```

```text
api container
  -> /var/run/docker.sock
  -> host Docker Engine
  -> create sibling sandbox container
```

이 방식이면 sandbox 안에서 실행한 웹서버도 Traefik을 통해 외부 URL로 노출할 수 있다.

```text
project-sandbox-123:3000
  -> Traefik
  -> https://preview.example.com/p/project_123
```

현재 구현에서는 Docker socket mount를 허용한다. 다만 운영 단계에서는 API와 Docker 제어 권한을 분리하기 위해 별도 sandbox controller service로 옮긴다.

## 7. 사용자 경험 기준

사용자가 보는 개념은 다음이어야 한다.

```text
프로젝트
자료
지침
실행 상태
결과물
수정 요청
공유 링크
```

사용자가 보지 않아야 하는 개념은 다음이다.

```text
sandbox
container
Docker volume
exec command
port
browser profile
archive tar.gz
```

기술 스택은 사용자에게 노출되는 기능을 위해 존재한다. 기술 개념이 UX에 새면 안 된다.

## 8. Browser Runtime 결정

브라우저 자동화는 다음으로 확정한다.

```text
Playwright + Chromium
```

브라우저 관찰은 다음 방식으로 한다.

```text
BrowserTool.observe()
  -> screenshot
  -> accessibility snapshot
  -> visible DOM elements
  -> DOM bounding boxes
  -> overlay screenshot
  -> element_id map
```

실행은 다음 방식으로 한다.

```text
BrowserTool.action()
  -> element_id
  -> Playwright locator/ref
  -> click/type/select
```

핵심 원칙:

```text
해석: visual overlay
실행: DOM/accessibility ref
```

LLM은 overlay screenshot과 compact element list를 보고 판단한다. 실제 액션은 좌표 클릭이 아니라 Playwright locator/ref 기반으로 실행한다.

2FA/MFA는 자동화 대상이 아니다. 사용자 개입 지점으로 처리한다.

```text
Agent detects 2FA
  -> waitForUserTakeover(reason)
  -> user opens noVNC browser view
  -> user completes 2FA
  -> agent resumes Playwright automation
```

## 9. Stagehand / browser-use 판단

핵심 런타임은 Playwright 직접 구현으로 간다.

이유:

- overlay screenshot + DOM bounding box + element_id map을 제품의 핵심 관찰 형식으로 직접 통제해야 한다.
- 2FA takeover, workspace archive, browser profile 저장 위치를 sandbox 구조와 맞춰야 한다.
- LLM tool interface를 우리 control plane 기준으로 설계해야 한다.

Stagehand와 browser-use는 다음처럼 본다.

| 도구 | 판단 |
| --- | --- |
| Stagehand | 추후 자연어 기반 `observe/act/extract` 상위 레이어로 검토 |
| browser-use | 빠른 실험/벤치마크용 참고 구현 |

현재 결정은 다음이다.

```text
Core Browser Runtime: Playwright 직접 구현
Optional High-level Layer: Stagehand 추후 검토
Benchmark/Reference: browser-use
```

## 10. Workspace 구조

프로젝트 workspace는 다음 구조를 가진다.

```text
/workspace/
  team/
    files/
    datasets/
    reports/
  users/
    {user_id}/
      files/
      drafts/
      private-context/
      browser-profile/
  skills/
  personas/
  triggers/
  runtime/
    src/
    scripts/
    outputs/
    logs/
  browser/
    screenshots/
    overlays/
    traces/
  server/
    app/
    public/
    logs/
  archive/
```

기술적으로는 파일시스템이지만, 제품에서는 다음처럼 보여야 한다.

| 내부 구조 | 사용자 표현 |
| --- | --- |
| `team/files/` | 팀 자료 |
| `team/datasets/` | 업로드 데이터 |
| `runtime/outputs/` | 분석 결과 |
| `server/public/` | 공유 리포트 |
| `users/{user_id}/drafts/` | 개인 초안 |
| `skills/` | 자동화 템플릿 |
| `personas/` | 응답 톤/역할 |
| `triggers/` | 자동 실행 조건 |

## 11. Control Plane API

초기 API는 내부 실행 루프를 검증하기 위해 다음을 제공한다.

```text
POST   /projects
GET    /projects
GET    /projects/:projectId

POST   /projects/:projectId/sandbox/start
POST   /projects/:projectId/sandbox/stop
GET    /projects/:projectId/sandbox/status

GET    /projects/:projectId/files
GET    /projects/:projectId/files/content?path=
PUT    /projects/:projectId/files/content
DELETE /projects/:projectId/files?path=

POST   /projects/:projectId/exec
GET    /projects/:projectId/exec/:runId
GET    /projects/:projectId/exec/:runId/logs

POST   /projects/:projectId/browser/start
POST   /projects/:projectId/browser/observe
POST   /projects/:projectId/browser/action
POST   /projects/:projectId/browser/takeover
GET    /projects/:projectId/browser/screenshot/:screenshotId

POST   /projects/:projectId/report/generate
GET    /projects/:projectId/report

POST   /projects/:projectId/preview/start
POST   /projects/:projectId/preview/stop
GET    /projects/:projectId/preview

POST   /projects/:projectId/archive
POST   /projects/:projectId/restore
GET    /projects/:projectId/archives
```

나중에 LLM은 이 API를 직접 호출하지 않고, 같은 기능을 감싼 tool interface를 사용한다.

## 12. 구현 단계

이 단계들은 고객 반응을 확인하기 위한 구현 단계가 아니다. 각 단계는 기술 가능성의 참/거짓을 확인하기 위한 실험이다.

### Phase 0. Control Plane과 Docker Sandbox 골격

목표:

- Fastify API 서버 생성
- PostgreSQL 연결
- Docker 기반 sandbox controller 생성
- 프로젝트 생성 API 작성
- sandbox start/stop/status API 작성

성공 기준:

- API 요청으로 프로젝트 sandbox와 workspace를 만들 수 있다.
- 프로젝트별 sandbox 상태가 DB에 저장된다.

### Phase 1. 파일 시스템 검증

목표:

- 기본 workspace 구조 생성
- 파일 업로드
- 파일 목록 조회
- 파일 읽기/쓰기/삭제

성공 기준:

- API를 통해 sandbox 내부 파일 구조를 변경할 수 있다.
- 파일 변경 이벤트가 기록된다.

### Phase 2. 코드 실행 검증

목표:

- sandbox 내부 명령 실행
- Python/Node 코드 저장
- 코드 실행
- 다른 파일 읽기
- 결과 파일 쓰기
- 로그 저장

성공 기준:

- sandbox 내부 코드가 `/workspace` 안의 파일을 읽고 쓴다.
- 실행 결과와 에러가 DB 또는 로그 파일로 남는다.

### Phase 3. 브라우저 자동화 검증

목표:

- sandbox 내부에서 Chromium 실행
- Playwright로 페이지 이동/클릭/입력
- 현재 화면 screenshot 저장
- accessibility snapshot 생성
- visible DOM element의 bounding box 계산
- overlay screenshot 생성
- element_id 기반 click/type 실행
- persistent browser profile 저장
- 2FA 상황에서 noVNC takeover 흐름 확인

성공 기준:

- LLM 또는 사람이 overlay screenshot을 보고 target element를 고를 수 있다.
- 실제 실행은 Playwright locator/ref 기반으로 수행된다.
- 로그인 세션이 `/workspace/users/{user_id}/browser-profile/`에 유지된다.
- 2FA/MFA가 필요한 순간에는 사용자가 브라우저 화면에 개입할 수 있다.

### Phase 4. 보고서/대시보드 생성 검증

목표:

- sandbox 내부에서 업로드 데이터 기반 분석 코드 실행
- 정적 HTML 또는 간단한 웹 대시보드 생성
- 차트, 요약, 인사이트 영역 생성
- 광고주/의사결정자에게 공유 가능한 형태로 포장

성공 기준:

- sandbox 내부 산출물이 사용자가 이해할 수 있는 보고서/대시보드 형태로 생성된다.

### Phase 5. 웹서버 노출 검증

목표:

- sandbox 내부에서 웹서버 실행
- Traefik으로 preview URL 연결
- 브라우저에서 결과 확인

성공 기준:

- `https://preview.example.com/p/{project_id}`로 sandbox 내부 웹 결과물에 접근할 수 있다.

### Phase 6. 아카이빙/복구 검증

목표:

- sandbox stop
- workspace tar.gz 생성
- MinIO에 업로드
- container/volume 제거
- archive에서 workspace 복구
- sandbox 재시작

성공 기준:

- 비활성화 전 파일, 결과물, browser profile이 재활성화 후 유지된다.
- 실행 로그와 archive metadata를 확인할 수 있다.

### Phase 7. LLM 도구 연동

목표:

- API 기능을 LLM tool interface로 감싸기
- LLM이 파일 생성/수정/코드 실행 수행
- LLM이 BrowserTool observe/action 루프 수행
- LLM이 보고서/대시보드 생성 루프 수행
- 실행 실패 시 로그를 읽고 수정 후 재실행

성공 기준:

- LLM이 sandbox 안에서 간단한 파일 처리 작업을 끝까지 수행한다.
- LLM이 overlay screenshot을 해석하고 DOM 기반 브라우저 액션을 수행한다.
- LLM이 최종 결과물을 공유 가능한 보고서/대시보드로 포장한다.

## 13. 구현 성공 기준

기술 구현는 다음을 만족하면 성공이다. 여기서 성공은 사용자가 원한다는 뜻이 아니라, 우리가 상상한 실행환경이 실제로 구현 가능하다는 뜻이다.

1. 프로젝트 생성 시 Docker sandbox와 workspace가 생성된다.
2. sandbox 내부에 기본 디렉터리 구조가 생성된다.
3. API로 파일을 생성/수정/삭제/조회할 수 있다.
4. sandbox 내부에서 코드가 실행된다.
5. 실행된 코드가 다른 파일을 읽고 새 파일을 쓸 수 있다.
6. sandbox 내부 Chromium을 Playwright로 조작할 수 있다.
7. 현재 화면을 overlay screenshot + element map으로 관찰할 수 있다.
8. 실제 브라우저 실행은 DOM/accessibility ref 기반으로 수행된다.
9. 2FA/MFA 상황에서 사용자 takeover가 가능하다.
10. 업로드 데이터 기반 보고서/대시보드를 생성할 수 있다.
11. sandbox 내부 웹서버를 외부 preview URL로 볼 수 있다.
12. sandbox 비활성화 시 workspace와 browser profile이 archive로 저장된다.
13. 재활성화 시 archive에서 workspace와 browser profile을 복구할 수 있다.
14. LLM tool interface를 같은 API 위에 얹을 수 있다.

## 14. 현재 구현에서 하지 않는 것

이번 단계에서는 하지 않는다.

- 수요검증
- 고객 인터뷰 반영
- 과금/가격 검증
- 제품 포지셔닝 검증
- 외부 샌드박스 SaaS 비교
- VM/microVM 도입
- 완전한 멀티테넌시
- 복잡한 조직 권한 모델
- 고급 workflow builder
- 완성형 마케팅 자동화
- 대규모 동시 실행
- 범용 원격 데스크톱 제품 수준의 browser takeover
- 브라우저 anti-bot 회피 최적화

현재 구현 목표는 작고 명확하다.

> Docker 기반 project sandbox로 마케터용 AI 작업공간의 최소 기술 루프를 증명한다.

## 15. 참고 자료

- Docker port publishing
  - https://docs.docker.com/get-started/docker-concepts/running-containers/publishing-ports/
- Docker volumes
  - https://docs.docker.com/engine/storage/volumes/
- Docker local file sharing
  - https://docs.docker.com/guides/docker-concepts/running-containers/sharing-local-files/
- Traefik Docker provider
  - https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/docker/
- Next.js Route Handlers
  - https://nextjs.org/docs/app/getting-started/route-handlers
- Playwright
  - https://playwright.dev/
- Playwright MCP snapshots
  - https://playwright.dev/mcp/snapshots
- Playwright accessibility snapshots
  - https://playwright.dev/docs/aria-snapshots
- Stagehand
  - https://docs.stagehand.dev/v3/first-steps/introduction
- browser-use
  - https://docs.browser-use.com/open-source/customize/browser/basics
