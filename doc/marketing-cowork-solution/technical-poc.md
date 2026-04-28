# 기술 POC 계획

## 1. POC 목적

이 POC의 목적은 마케팅 코워크 솔루션의 핵심 실행환경이 기술적으로 가능한지 검증하는 것이다.

이번 POC는 수요검증이 아니다. 고객이 이 제품을 원하는지, 어떤 가격을 낼지, 어떤 포지셔닝이 맞는지를 확인하는 단계가 아니다.

검증하려는 핵심 질문은 다음이다.

> 프로젝트 생성 시 Docker 기반 샌드박스를 만들고, 그 안에서 파일 관리, 코드 생성/실행, 브라우저 자동화, 보고서/대시보드 생성, 웹서버 실행, 아카이빙/복구까지 안정적으로 제공할 수 있는가?

이 단계에서는 LLM의 지능적 업무 수행보다 먼저, LLM이 사용할 수 있는 **실행 기반시설**이 가능한지를 확인한다.

즉, 목표는 다음 최소 기술 루프의 가능성 확인이다.

```text
프로젝트 생성
  -> 샌드박스 생성
  -> 파일 조작
  -> 코드 실행
  -> 브라우저 조작
  -> 보고서/대시보드 생성
  -> 웹서버 노출
  -> 아카이브
  -> 복구
```

## 2. 프로젝트 생성 시 필요한 샌드박스 구조

프로젝트가 생성되면 독립된 Docker 기반 샌드박스 환경을 만든다.

샌드박스 내부는 다음 영역으로 나눈다.

```text
project-sandbox/
  team/
    files/
    datasets/
    reports/
  users/
    {user_id}/
      files/
      drafts/
      private-context/
  skills/
    data-cleaning/
    report-generation/
    campaign-planning/
  personas/
    client-success/
    media-buyer/
    brand-manager/
  triggers/
    schedules/
    webhooks/
    event-rules/
  runtime/
    src/
    scripts/
    outputs/
    logs/
  browser/
    profiles/
    screenshots/
    overlays/
    traces/
  server/
    app/
    public/
    logs/
  archive/
```

각 영역의 역할은 다음과 같다.

| 영역 | 역할 |
| --- | --- |
| `team/` | 팀의 공통 자료, 캠페인 데이터, 공유 리포트, 공용 산출물 |
| `users/{user_id}/` | 개인 사용자별 자료, 초안, 개인 컨텍스트 |
| `skills/` | 업무 처리 로직 정의. 예: 데이터 정리, 리포트 생성, 캠페인 기획 |
| `personas/` | 이메일/메시지 대응 로직 정의. 예: 고객사 담당자, 미디어 바이어, 브랜드 매니저 |
| `triggers/` | 자동화 규칙. 예: 정기 실행, 웹훅, 파일 업로드 이벤트 |
| `runtime/` | 샌드박스 안에서 생성/실행되는 코드와 결과물 |
| `browser/` | 브라우저 자동화 세션, 스크린샷, overlay, trace |
| `server/` | 샌드박스 안에서 실행되는 웹서버 코드와 정적 파일 |
| `archive/` | 비활성화/스냅샷/복구용 아카이브 |

## 3. POC 검증 항목

### 3.1 샌드박스 생성

프로젝트 생성 시 다음이 가능해야 한다.

- 독립된 샌드박스 생성
- 프로젝트별 고유 ID 부여
- 기본 폴더 구조 생성
- 파일/코드/로그/설정 저장 위치 분리
- 샌드박스별 리소스 제한 적용

검증 기준:

- 새 프로젝트마다 별도 파일시스템 루트가 생긴다.
- 프로젝트 A에서 프로젝트 B의 파일을 볼 수 없다.
- 기본 디렉터리 구조가 자동 생성된다.

### 3.2 샌드박스 내 영역 구분과 파일 구조 변경

샌드박스를 활성화한 뒤 실제 파일 구조를 변경할 수 있어야 한다.

검증할 작업:

- `team/files/`에 CSV 또는 XLSX 업로드
- `users/{user_id}/drafts/`에 개인 초안 생성
- `skills/`에 업무 로직 정의 파일 추가
- `personas/`에 메일 응대 페르소나 정의 파일 추가
- `triggers/`에 자동화 규칙 파일 추가
- 파일 이동, 이름 변경, 삭제, 복사

검증 기준:

- 파일 생성/수정/삭제가 샌드박스 내부에서 정상 동작한다.
- 영역별 파일 권한을 구분할 수 있다.
- 변경 이력이 로그로 남는다.

### 3.3 샌드박스 내 코드 생성 및 실행

샌드박스 내부에서 코드를 생성하고 실행할 수 있어야 한다.

검증할 작업:

- `runtime/scripts/`에 Python 또는 TypeScript 코드 생성
- `team/datasets/`의 입력 파일 읽기
- 데이터 정리 또는 변환 수행
- `runtime/outputs/`에 결과 파일 쓰기
- 실행 로그를 `runtime/logs/`에 저장

예시 시나리오:

1. `team/datasets/campaign.csv` 업로드
2. `runtime/scripts/clean_campaign_data.py` 생성
3. 코드가 CSV를 읽고 결측치/컬럼명을 정리
4. `runtime/outputs/cleaned_campaign.csv` 생성
5. 실행 로그 저장

검증 기준:

- 샌드박스 내 코드가 같은 샌드박스의 파일을 읽고 쓸 수 있다.
- 허용되지 않은 외부 경로 접근은 차단된다.
- 코드 실행 결과와 에러가 기록된다.
- 반복 실행이 가능하다.

### 3.4 샌드박스 내 웹서버 실행 및 엔드포인트 노출

샌드박스 안에서 웹서버를 실행하고 외부 엔드포인트를 통해 접근할 수 있어야 한다.

검증할 작업:

- `server/app/`에 간단한 웹서버 코드 생성
- 샌드박스 내부 포트에서 서버 실행
- 외부 라우팅 엔드포인트 연결
- HTTP 요청으로 결과 확인
- 정적 리포트 또는 대시보드 페이지 제공

예시 엔드포인트:

```text
https://{project_id}.sandbox.example.com/
https://{project_id}.sandbox.example.com/report
https://{project_id}.sandbox.example.com/api/summary
```

검증 기준:

- 샌드박스 내부 웹서버가 정상 실행된다.
- 외부에서 프로젝트별 URL로 접근할 수 있다.
- 서버 로그가 저장된다.
- 샌드박스 종료 시 웹서버도 함께 종료된다.

### 3.5 샌드박스 내 보고서/대시보드 생성

샌드박스 내부에서 업로드 데이터와 분석 결과를 바탕으로 마케터가 바로 공유할 수 있는 보고서/대시보드를 생성할 수 있어야 한다.

검증할 작업:

- 업로드 데이터 기반 요약 리포트 생성
- 차트 이미지 또는 HTML 차트 생성
- 광고주/의사결정자용 설명 문구 생성
- 정적 HTML 또는 간단한 웹 대시보드 생성
- `server/public/` 또는 `runtime/outputs/`에 결과 저장

검증 기준:

- 산출물이 단순 파일이 아니라 사용자가 이해할 수 있는 보고서/대시보드 형태로 생성된다.
- 생성된 결과물을 preview URL로 볼 수 있다.
- 사용자의 수정 요청을 반영해 다시 생성할 수 있다.

### 3.6 샌드박스 내 브라우저 자동화

샌드박스 안에서 브라우저를 실행하고, 에이전트가 현재 화면을 관찰한 뒤 DOM 기반으로 액션을 수행할 수 있어야 한다.

결정한 기술은 다음이다.

```text
Playwright + Chromium
```

관찰 방식은 다음이다.

```text
현재 화면 screenshot
  + accessibility snapshot
  + visible DOM elements
  + DOM bounding boxes
  + element id overlay
```

실행 방식은 다음이다.

```text
LLM은 overlay screenshot을 보고 판단
실제 실행은 Playwright locator/ref 기반으로 click/type/select
```

검증할 작업:

- 샌드박스 내부에서 Chromium 실행
- Playwright로 특정 URL 접속
- 현재 화면 스크린샷 저장
- accessibility snapshot 생성
- visible DOM element와 bounding box 추출
- screenshot 위에 element id overlay 생성
- element id로 click/type 실행
- 사용자별 browser profile 저장
- 2FA/MFA 상황에서 사용자 takeover 흐름 확인

검증 기준:

- 브라우저가 샌드박스 내부에서 정상 실행된다.
- overlay screenshot과 element map이 생성된다.
- element id 기반 액션이 DOM/accessibility ref로 실행된다.
- 로그인 세션이 사용자별 profile에 저장된다.
- 2FA/MFA가 필요한 순간에는 사용자가 개입하고, 이후 에이전트가 이어서 실행할 수 있다.

저장 위치:

```text
browser/profiles/{user_id}/
browser/screenshots/
browser/overlays/
browser/traces/
```

### 3.7 샌드박스 비활성화, 아카이빙, 재활성화

샌드박스를 비활성화하면 상태가 안전하게 저장되어야 한다. 이후 다시 활성화하면 이전 상태를 이어서 사용할 수 있어야 한다.

검증할 작업:

- 샌드박스 비활성화
- 파일시스템 스냅샷 생성
- 실행 로그와 메타데이터 저장
- 실행 중인 프로세스 종료
- 다음 활성화 시 파일과 설정 복구
- 이전 결과물과 로그 확인
- 사용자별 browser profile 복구

검증 기준:

- 비활성화 전 파일이 재활성화 후 그대로 남아 있다.
- 실행 로그와 산출물이 보존된다.
- 웹서버/프로세스는 중복 실행되지 않는다.
- browser profile과 주요 스크린샷/trace가 보존된다.
- 아카이브 손상 시 복구 실패를 명확히 감지한다.

## 4. LLM 적용 전/후 검증 순서

기술 POC는 두 단계로 나눈다.

### 4.1 1단계: LLM 없이 실행환경 검증

먼저 사람이 명시적으로 명령을 내려서 샌드박스 기능을 검증한다.

검증 범위:

- 샌드박스 생성
- 폴더 구조 생성
- 파일 업로드/변경
- 코드 파일 생성
- 코드 실행
- 결과 파일 생성
- 보고서/대시보드 생성
- 웹서버 실행
- 엔드포인트 접속
- 브라우저 실행
- overlay screenshot 생성
- DOM 기반 브라우저 액션
- 2FA/MFA 사용자 개입
- 샌드박스 아카이빙/복구

이 단계의 목표는 “인프라가 되는가?”를 확인하는 것이다.

### 4.2 2단계: LLM이 파일/코드/브라우저 작업을 수행할 수 있는지 검증

1단계가 성공하면 다음으로 LLM이 실제로 파일 구조 변경, 코드 생성/실행, 브라우저 관찰/액션을 수행할 수 있는지 검증한다.

검증 범위:

- LLM이 샌드박스 구조를 이해하는가?
- LLM이 적절한 위치에 파일을 만들 수 있는가?
- LLM이 입력 데이터를 읽고 필요한 코드를 생성하는가?
- LLM이 생성한 코드를 실행하고 에러를 수정할 수 있는가?
- LLM이 결과 파일을 올바른 위치에 저장하는가?
- LLM이 overlay screenshot과 element list를 이해하는가?
- LLM이 element id를 선택하고 DOM 기반 브라우저 액션을 수행하는가?
- 2FA/MFA 상황에서 사용자 개입을 요청하고 이후 이어서 실행하는가?
- LLM이 변경 내용과 실행 결과를 사용자에게 설명할 수 있는가?

이 단계의 목표는 “에이전트가 실행환경을 실제 업무 도구처럼 사용할 수 있는가?”를 확인하는 것이다.

## 5. POC 성공 기준

최소 성공 기준은 다음과 같다. 여기서 성공은 수요가 있다는 뜻이 아니라, 기술 루프가 실제로 가능하다는 뜻이다.

1. 프로젝트 생성 시 샌드박스와 기본 디렉터리 구조가 자동 생성된다.
2. 샌드박스 내부 파일을 생성/수정/삭제할 수 있다.
3. 샌드박스 내부에서 코드가 실행되고, 내부 파일을 읽고 쓸 수 있다.
4. 샌드박스 내부 웹서버를 실행하고 외부 URL로 접근할 수 있다.
5. 업로드 데이터 기반 보고서/대시보드를 생성할 수 있다.
6. 샌드박스 내부 브라우저를 실행하고 Playwright로 조작할 수 있다.
7. 브라우저 화면을 overlay screenshot + element map으로 관찰할 수 있다.
8. 브라우저 액션은 DOM/accessibility ref 기반으로 실행된다.
9. 2FA/MFA 상황에서는 사용자가 개입할 수 있다.
10. 샌드박스를 비활성화해도 파일, 로그, 결과물, browser profile이 아카이빙된다.
11. 재활성화 시 이전 상태를 이어서 사용할 수 있다.
12. 이후 LLM이 파일 변경, 코드 실행, 브라우저 액션, 보고서 생성을 같은 방식으로 수행할 수 있다.

## 6. 비기능 요구사항

기술 POC 단계에서도 다음 요구사항은 최소한으로 고려한다.

| 항목 | 요구사항 |
| --- | --- |
| 격리 | 프로젝트별 파일시스템과 프로세스 격리 |
| 보안 | 외부 경로 접근 차단, 민감 파일 접근 제한 |
| 권한 | 팀 공용 영역과 개인 영역 권한 구분 |
| 관측성 | 파일 변경, 코드 실행, 서버 실행 로그 기록 |
| 재현성 | 같은 입력과 코드로 다시 실행 가능 |
| 비용 | 유휴 샌드박스 비활성화, 필요 시 재활성화 |
| 복구 | 아카이브 기반 상태 복원 |
| 사용자 개입 | 2FA/MFA 등 자동화가 멈춰야 하는 지점에서 takeover 제공 |

## 7. 결정 기술

POC에서 사용할 기술은 다음으로 고정한다.

| 기능 | 후보 |
| --- | --- |
| 샌드박스 실행 | Docker |
| 파일 저장 | Docker volume |
| 아카이빙 | tar/zip 스냅샷, 볼륨 스냅샷, 오브젝트 스토리지 동기화 |
| 코드 실행 | Python, Node.js, Bun, shell runner |
| 브라우저 자동화 | Playwright + Chromium |
| 브라우저 관찰 | accessibility snapshot + DOM bounding box overlay |
| 사용자 takeover | noVNC |
| 보고서/대시보드 | 정적 HTML, Next.js export, chart generation |
| 웹서버 노출 | Traefik |
| 로그 | 파일 로그, OpenTelemetry, 실행 이벤트 테이블 |
| 권한 | 프로젝트 ACL, 사용자별 workspace policy |

## 8. 다음 액션

다음 단계에서는 이 문서를 바탕으로 실제 POC 구현안을 정한다.

정해야 할 것:

- Docker 기반 project sandbox 초기 구조
- 프로젝트/샌드박스 메타데이터 스키마
- 샌드박스 파일 구조 초기화 스크립트
- 코드 실행 API
- 브라우저 observe/action API
- noVNC takeover 흐름
- 웹서버 라우팅 방식
- 아카이빙 방식
- LLM이 호출할 도구 인터페이스

이번 POC에서 아직 다루지 않을 것:

- 수요검증
- 고객 인터뷰
- 가격/과금
- 제품 포지셔닝
- 마케팅 자동화 완성도
- VM/microVM 도입
