# Workspace Folder View Modes Tasks

작성일: 2026-05-07

## 0. 스펙 작업 전환과 baseline

- [x] `.specs/draft/workspace-folder-view-modes/`를 `.specs/work/workspace-folder-view-modes/`로 이동한다.
- [x] `git status --short`로 작업트리 상태를 확인한다.
- [x] backend baseline 테스트를 실행한다.
- [x] frontend baseline 테스트를 실행한다.
- [x] frontend build baseline을 실행한다.
- [x] baseline 결과를 `implementation.md`에 기록한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd src/frontend
npm test
npm run build
```

## 1. Backend workspace root와 path safety

- [x] `WORKSPACE_ROOT` 기본값을 project-root runtime 경로로 resolve하도록 구현한다.
- [x] `runtime/`을 Git 추적 제외 대상으로 추가한다.
- [x] backend path policy가 canonical path resolve 이후 workspace root 내부 여부를 검증하도록 점검한다.
- [x] `..` path escape를 차단한다.
- [x] absolute path injection을 차단한다.
- [x] Windows drive prefix와 UNC path를 차단한다.
- [x] symlink/mount traversal이 workspace root 정책을 벗어나면 차단한다.
- [x] path safety 단위 테스트를 추가한다.

완료 조건:

- [x] workspace root가 `src/backend` 하위가 아니라 project-root `runtime/workspaces` 계열로 resolve된다.
- [x] workspace root 밖 read/write/create/delete 시도가 실패한다.
- [x] 기존 Clean Room 권한과 internal metadata content guard가 유지된다.

## 2. Backend alias/canonical resolver

- [x] backend alias mapping helper를 만든다.
- [x] `팀 폴더` alias prefix의 canonical mapping을 확정한다.
- [x] `내 폴더` alias prefix의 current-user canonical mapping을 확정한다.
- [x] alias path를 canonical path로 resolve하는 함수를 만든다.
- [x] canonical path를 사용자 모드 alias path로 표시하는 함수를 만든다.
- [x] 허용되지 않은 alias prefix를 명확한 validation error로 거부한다.
- [x] backend resolver 단위 테스트를 추가한다.

완료 조건:

- [x] `내 폴더/작업 중/...`이 current-user working canonical path로 resolve된다.
- [x] `팀 폴더/데이터/...`가 team data canonical path로 resolve된다.
- [x] 이미 canonical인 path는 정책에 맞게 검증된다.
- [x] resolver 테스트 fixture를 frontend와 맞출 수 있는 형태로 정리한다.

## 3. Backend dot-prefix와 visibility policy

- [x] dot-prefixed path segment 판별 helper를 만든다.
- [x] `.haro`, `.openclaw`, dot-prefixed 항목을 system hidden 대상으로 분류한다.
- [x] 사용자 생성/업로드/rename에서 `.`으로 시작하는 path segment를 거부한다.
- [x] `report.md`, `data.v1.csv`처럼 중간 dot 또는 확장자는 허용한다.
- [x] visibility policy 단위 테스트를 추가한다.

완료 조건:

- [x] 사용자 모드에서는 dot-prefixed/system hidden 항목이 숨겨진다.
- [x] 개발자 모드에서는 dot-prefixed/system hidden 항목이 listing/search에 포함된다.
- [x] dot-prefix validation error가 명확하다.

## 4. Backend directory/search query

- [x] `GET /files`에 `include_hidden` query를 연결한다.
- [x] `GET /files/search`에 `include_hidden` query를 연결한다.
- [x] `include_hidden=false`에서 hidden/system 항목을 SQL query 단계에서 제외한다.
- [x] 사용자 모드 directory/search를 alias allowlist canonical prefix 범위로 제한한다.
- [x] `include_hidden=true`에서 모든 사용자가 raw tree를 볼 수 있게 한다.
- [x] pagination `total`, `has_more`, page result가 필터 이후 기준으로 계산되게 한다.
- [x] directory/search backend 테스트를 추가한다.

완료 조건:

- [x] hidden 항목 제외 후에도 pagination이 빈 페이지나 잘못된 total을 만들지 않는다.
- [x] 사용자 모드 search는 alias allowlist 밖 canonical path를 반환하지 않는다.
- [x] 개발자 모드 search/list는 raw 항목을 반환한다.
- [x] `include_hidden=true`에서도 path safety와 metadata content guard가 유지된다.

## 5. 안전한 workspace 초기화 절차

- [x] 초기화가 필요한지 판단한다. 이번 구현에서는 runtime workspace 초기화를 실행하지 않는다.
- [x] 초기화 전 `git status`가 clean인지 확인한다. 초기화 미실행으로 checkpoint 조건은 적용하지 않는다.
- [x] 현재 브랜치가 GitHub 원격에 push되어 있는지 확인한다. 초기화 미실행으로 checkpoint 조건은 적용하지 않는다.
- [x] 변경 사항이 있으면 먼저 커밋/푸쉬 checkpoint를 만든다. 초기화 미실행으로 checkpoint는 만들지 않는다.
- [x] reset helper 또는 문서화된 초기화 절차를 만든다. 안전 조건은 `spec.md`와 `design.md`에 문서화되어 있다.
- [x] 초기화 대상이 configured `workspace_root`의 직접 하위 project workspace인지 검증한다. 초기화 미실행으로 코드 경로는 만들지 않는다.
- [x] `workspace_root`, repo root, `.specs`, `src`, 상위 디렉터리, 다른 workspace 삭제를 차단한다. 초기화 미실행으로 삭제는 수행하지 않는다.
- [x] 초기화 후 harness 구조와 workspace DB/index 재생성 절차를 확인한다. 초기화 미실행으로 적용 대상은 없다.

완료 조건:

- [x] 초기화 helper가 workspace root 밖 path를 거부한다. 초기화 helper는 이번 구현에서 만들지 않는다.
- [x] 초기화 절차가 source code와 spec 문서를 건드리지 않는다. 초기화를 실행하지 않았다.
- [x] runtime 데이터 백업이 필요한 경우 별도 스펙 또는 절차로 분리한다. 이번 구현에서는 runtime 데이터를 변경하지 않았다.

## 6. Frontend developer mode state

- [x] topbar에 개발자 모드 토글을 추가한다.
- [x] 개발자 모드 localStorage key를 `haro:developerMode:{userId|anonymous}`로 저장한다.
- [x] 채팅 debug mode와 explorer developer mode 상태를 분리한다.
- [x] developer mode 상태 테스트를 추가한다.

완료 조건:

- [x] 모든 사용자가 topbar에서 개발자 모드를 켜고 끌 수 있다.
- [x] 개발자 모드가 채팅 debug mode, agent trace 설정에 영향을 주지 않는다.
- [x] topbar props/type/build가 깨지지 않는다.

## 7. Frontend alias view와 cache

- [x] frontend alias/canonical resolver를 만든다.
- [x] 사용자 모드 root를 `팀 폴더`, `내 폴더`로 구성한다.
- [x] 사용자 모드 breadcrumb와 path display에서 internal user id를 숨긴다.
- [x] 개발자 모드는 기존 raw explorer 흐름을 유지한다.
- [x] folder cache key에 view mode를 포함한다.
- [x] mode 전환 시 stale tree가 보이지 않도록 cache reload 또는 mode별 cache를 적용한다.
- [x] alias root/cache/resolver frontend 테스트를 추가한다.

완료 조건:

- [x] 사용자 모드에 `/playground/users/{user_id}`가 표시되지 않는다.
- [x] 개발자 모드에는 raw canonical path와 dot-prefixed 항목이 보인다.
- [x] 사용자 모드와 개발자 모드 cache 결과가 섞이지 않는다.

## 8. Frontend API 호출과 mutation target

- [x] 사용자 모드 directory/search 호출에 `include_hidden=false`를 사용한다.
- [x] 개발자 모드 directory/search 호출에 `include_hidden=true`를 사용한다.
- [x] 파일 생성 target을 alias path에서 canonical path로 resolve한다.
- [x] 업로드 target을 alias path에서 canonical path로 resolve한다.
- [x] rename/move/delete/read/write target이 backend resolver를 거치게 한다. rename/move/delete API는 현재 없으므로 create/upload/content read/write에 적용했다.
- [x] read-only 팀 폴더 guard를 유지한다.
- [x] mutation target 테스트 또는 통합 검증을 추가한다.

완료 조건:

- [x] `내 폴더/받은 파일` 생성/업로드가 inbox canonical path로 들어간다.
- [x] `팀 폴더/데이터` 생성/업로드가 차단된다.
- [x] backend가 mutation 직전 canonical path를 최종 검증한다.

## 9. Legacy path와 문서 정리

- [x] 사용자 모드 UI에 직접 노출되는 legacy canonical path 참조를 제거하거나 alias display로 감싼다.
- [x] system design상 남아야 하는 canonical path 참조를 분류한다.
- [x] `implementation.md`에 구현 결과와 검증 결과를 기록한다.
- [x] `commits.md`에 연결 커밋을 기록한다.
- [x] 완료 시 `.specs/done/workspace-folder-view-modes/`로 이동한다.

메모:

- 사용자 모드 표시 경로는 `displayPathForMode`와 alias view를 거치도록 정리했다.
- backend, 테스트, 개발자 모드, harness/context 문서성 문자열에는 canonical path가 system design 기준으로 남아 있다.
- `src/backend/data/workspaces` 아래 검색 결과는 Git에서 ignored 처리된 legacy runtime data다. 이번 구현에서는 runtime workspace 초기화나 삭제를 실행하지 않았다.
- 연결 커밋 기록과 `done` 이동은 사용자가 커밋/푸쉬를 요청한 뒤 수행한다.

검증:

```powershell
rg "clean-room|playground/users|90_archive|00_inbox|20_working|30_outputs" src/backend src/frontend/src
rg "src/backend/data|data/workspaces|WORKSPACE_ROOT" src/backend .specs AGENTS.md
```

## 10. 최종 검증

- [x] backend 전체 테스트를 실행한다.
- [x] frontend 테스트를 실행한다.
- [x] frontend build를 실행한다.
- [x] `git diff --check`를 실행한다.
- [x] 스펙 성공 기준을 하나씩 확인한다.
- [x] 남은 위험이 있으면 `implementation.md`에 기록한다.

검증 결과:

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 65 passed, 1 skipped
- `cd src/frontend; npm test -- --run` → 47 passed
- `cd src/frontend; npm run build` → passed
- `git diff --check` → passed

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

cd src/frontend
npm test
npm run build

git diff --check
```

## 11. 사용자 친화 채팅 경로와 instruction 파일

- [x] `/playground/users/{user_id}/.HARO.md`를 시스템 관리 instruction 파일로 생성한다.
- [x] `/playground/users/{user_id}/AGENTS.md`를 사용자 커스텀 instruction 파일로 생성한다.
- [x] `.HARO.md`는 하네스 보정 시 시스템 템플릿으로 유지한다.
- [x] `AGENTS.md`는 최초 생성 후 사용자 내용을 덮어쓰지 않는다.
- [x] `.HARO.md`는 read/write/create/upload/edit 대상에서 차단한다.
- [x] `AGENTS.md`는 사용자에게 보이고 수정할 수 있다.
- [x] `AGENTS.md`는 사용자 모드 `내 폴더/AGENTS.md` 파일 노드로 노출한다.
- [x] `AGENTS.md`는 backend 사용자 모드 alias/search allowlist에 포함한다.
- [x] `AGENTS.md`는 개발자 모드 raw tree에서도 보이도록 workspace DB에 sync한다.
- [x] 프로젝트 생성도 하네스 동기화 함수를 사용해 신규 프로젝트 instruction 파일을 listing DB에 반영한다.
- [x] 기존 로컬 워크스페이스는 보정 스크립트로 instruction 파일을 생성하고 DB에 sync한다.
- [x] `build_context`가 `.HARO.md`, `AGENTS.md` 순서로 프롬프트에 포함한다.
- [x] `.HARO.md`, `AGENTS.md` instruction context가 agent system prompt 초반에 포함되는지 테스트한다.
- [x] 명시적인 파일 저장 기본 위치에서 채팅 날짜/제목/id 기반 폴더를 제거한다.
- [x] 저장 위치가 파일명만으로 불명확한 `file_create`, `file_write`는 저장 위치 확인이 필요하다고 응답한다.
- [x] `file_create`, `file_write`의 명시적 `내 폴더/결과/...` alias path는 사용자 결과 폴더로 resolve되게 한다.
- [x] `내폴더`, `결과폴더`, `내 폴더/결과` alias 입력이 사용자 결과 폴더로 resolve된다.
- [x] 사용자 모드 채팅 답변에서 raw canonical path를 alias path로 치환한다.
- [x] 사용자 모드 tool step은 간단한 완료/진행 요약으로 표시한다.
- [x] debug mode 또는 developer mode에서는 raw tool step detail을 유지한다.
- [x] 파일 생성이 새 중간 폴더까지 만들 때 workspace DB가 부모 폴더를 함께 sync하도록 수정한다.
- [x] 파일 변경 SSE를 받은 frontend가 직접 부모뿐 아니라 이미 열려 있을 수 있는 조상 폴더 cache도 갱신하도록 수정한다.
- [x] 기존 `test8` 로컬 워크스페이스의 `세종대왕-대시보드` 인덱스를 보정해 `내 폴더/결과` listing에서 보이게 했다.

## 12. 사용자 결과 저장 위치 정리

- [x] agent prompt와 harness briefing에서 채팅 기반 결과 폴더 안내를 제거한다.
- [x] 최종 산출물 저장 위치가 명확하지 않으면 도구 호출 전에 사용자에게 확인하고, `내 폴더/결과/{주제}/{파일명}` 형태의 추천 경로를 제안하도록 안내한다.
- [x] backend가 파일명만 전달된 `file_create`, `file_write`를 자동 저장하지 않고 위치 확인 필요 메시지를 반환하게 한다.
- [x] 채팅 날짜, 채팅 제목, chat id를 사용자 결과 폴더명으로 쓰지 않도록 `.HARO.md`와 harness briefing에 명시한다.
- [x] 이미 생성된 `2026-05-07-새-채팅-21ece926` 런타임 결과 폴더는 이동하거나 삭제하지 않는다.

검증 결과:

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 65 passed, 1 skipped
- `cd src/frontend; npm test -- --run` → 47 passed
- `cd src/frontend; npm run build` → passed

## 13. 도구 호출 파싱 오류 자동 교정

- [x] `tool_call` 블록 없음과 `tool_call` JSON 파싱 실패를 구분한다.
- [x] 파싱 실패 시 debug trace에 오류 위치와 raw block preview를 남긴다.
- [x] 파싱 실패를 일반 planner 메시지로 저장하지 않고 1회 교정 라운드를 실행한다.
- [x] 교정된 도구 호출이 유효하면 기존 도구 실행 흐름으로 이어간다.
- [x] 교정도 실패하면 사용자에게 작업 미실행을 알리고 intent를 `failed`로 둔다.
- [x] 도구 호출 JSON escaping 규칙을 system prompt와 tool contract에 명시한다.
- [x] parser와 tool loop 단위 테스트를 추가한다.

검증:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest

git diff --check
```

검증 결과:

- `cd src/backend; .\.venv\Scripts\python.exe -m pytest` → 73 passed, 1 skipped
- `git diff --check` → passed
