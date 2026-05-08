# Workspace Folder View Modes Spec

작성일: 2026-05-07

## 문제

현재 workspace 파일 탐색기는 실제 내부 경로를 거의 그대로 보여준다.

- 시스템이 만든 폴더와 파일이 사용자 작업물과 같은 레벨에 노출된다.
- `playground/users/{user_id}`처럼 내부 사용자 ID가 사용자 화면의 경로에 드러난다.
- 팀 공간, 내 공간, 시스템 내부 공간이 한 트리 안에 섞여 있어 사용자가 어디에 무엇을 두어야 하는지 알기 어렵다.
- 현재 구현은 개발자/관리자에게는 유용하지만 일반 사용자에게는 지나치게 raw filesystem에 가깝다.

## 목표

- 시스템 전용 폴더와 파일은 이름 앞에 `.`을 붙이는 정책을 세운다.
- 개발자 모드가 꺼진 기본 사용자 모드에서는 dot-prefixed 시스템 항목을 숨긴다.
- topbar에 개발자 모드 토글을 추가한다.
- 개발자 모드가 켜진 경우 현재 파일 탐색기와 거의 같은 raw workspace tree를 보여준다.
- 사용자 모드에서는 실제 물리 구조를 그대로 보여주지 않고, 필터링된 폴더 조회 결과를 보여준다.
- 사용자 모드의 최상위는 `팀 폴더`와 `내 폴더` 개념으로 나눈다.
- 사용자 ID, 시스템 metadata path, 내부 sync/cache path가 사용자 모드 UI에 그대로 노출되지 않게 한다.
- 기존 생성 워크스페이스는 migration하지 않고 초기화할 수 있게 한다.
- workspace 저장 위치는 `src/backend` 하위가 아니라 프로젝트 루트 하위 runtime data 영역으로 옮긴다.

## 비목표

- 사용자 화면의 폴더 이름에 맞추기 위해 물리 workspace 구조를 억지로 바꾸지 않는다.
- 기존 사용자 파일을 보존하는 자동 migration을 만들지 않는다.
- Clean Room 권한 모델을 완화하지 않는다.
- 파일 내용 API의 읽기/쓰기 권한을 완화하지 않는다.
- 채팅, deploy, editor/viewer workflow를 함께 리팩토링하지 않는다.
- 개발자 모드에서 보이는 raw path를 없애지 않는다.

## 핵심 전제

사용자에게 보이는 것은 실제 filesystem tree가 아니라 **필터링된 폴더 조회 view**다. 실제 물리 구조는 시스템 설계를 따른다.

- backend harness, agent tools, workspace index, chat sync, clean-room 정책에 필요한 물리 구조는 시스템 기준으로 결정한다.
- 사용자 모드는 그 물리 구조 위에 표시 이름, 숨김 규칙, alias prefix, 검색 필터를 적용한 product view다.
- 개발자 모드는 시스템 물리 구조를 이해하고 점검하기 위한 raw view다.

## 모드 권한 정책

개발자 모드는 모든 사용자가 사용할 수 있는 고급 보기 모드다.

- 개발자 모드는 권한 상승 기능이 아니라 raw workspace tree를 확인하는 UI 모드다.
- 개발자 모드에서는 dot-prefixed 항목과 raw canonical path를 모두 보여준다.
- 개발자 모드에서도 기존 Clean Room 권한, read-only guard, workspace root escape 방지, internal metadata content read/write 제한은 유지한다.
- 사용자 모드는 기본값이며 일반 작업에 필요한 filtered alias view를 제공한다.

## 숨김/조회 정책

dot-prefixed 시스템 항목 숨김은 frontend 표시 단계가 아니라 backend directory/search query 단계에서 적용한다.

- 사용자 모드 조회는 backend에서 숨김 항목을 제외한 결과만 받는다.
- 사용자 모드 directory/search는 숨김 항목 제외에 더해 alias allowlist에 포함된 canonical prefix 범위로 제한한다.
- 개발자 모드 조회는 `include_hidden` 같은 명시적 옵션을 통해 raw 항목까지 받는다.
- pagination `total`, `has_more`, search 결과는 숨김 정책이 적용된 backend 결과를 기준으로 계산한다.
- frontend는 view mode 전환, alias prefix 표시, alias path와 canonical path 변환을 담당한다.
- API 응답에 사용자 모드에서 숨겨야 하는 내부 path가 노출되지 않도록 backend 응답 계약을 테스트한다.

## 경로 안전 정책

모든 filesystem 작업은 canonical path resolve 이후 workspace root 내부인지 검증한다.

- read, write, create, upload, rename, move, delete, search index rebuild, workspace 초기화는 workspace root 밖 path를 처리할 수 없다.
- `..`, absolute path injection, Windows drive prefix, UNC path, symlink/mount traversal은 resolved absolute path 기준으로 차단한다.
- EFS mount, 외부 volume, symlink를 쓰더라도 최종 resolved path가 configured workspace root 정책을 벗어나면 실패한다.
- 이 검증은 frontend 표시 규칙과 별개로 backend에서 수행한다.

## 이름 정책

`.`으로 시작하는 이름은 시스템 전용 namespace로 예약한다.

- 일반 사용자는 폴더나 파일을 생성, 업로드, 이름 변경할 때 `.`으로 시작하는 path segment를 만들 수 없다.
- `report.md`, `data.v1.csv`처럼 이름 중간이나 확장자에 들어가는 `.`은 허용한다.
- 시스템 항목은 dot-prefixed 이름을 사용하고, 사용자 모드에서는 기본적으로 숨긴다.
- 사용자 모드에 노출할 canonical prefix는 allowlist alias mapping으로 관리한다.
- backend는 파일 생성/업로드/rename API에서 사용자 입력 path를 검증하고, 위반 시 명확한 validation error를 반환한다.

## Workspace 저장 위치 정책

workspace runtime data는 source tree와 분리한다. 기본 `WORKSPACE_ROOT`는 프로젝트 루트 기준 top-level runtime 경로를 사용한다.

- 기본 위치는 `<project-root>/runtime/workspaces` 계열로 둔다.
- `src/backend/data/workspaces`처럼 source tree 아래에 runtime workspace를 두지 않는다.
- `runtime/`은 Git 추적 대상에서 제외한다.
- 운영 환경에서는 이 runtime workspace 경로를 EFS mount point, 외부 volume, 또는 symlink 대상으로 교체할 수 있게 한다.

## 용어

- 사용자 모드: 기본 explorer 모드. 팀/내 폴더 중심으로 정리된 필터링 view를 보여준다.
- 개발자 모드: 현재 explorer에 가까운 raw workspace tree를 보여준다.
- 시스템 항목: Haro가 내부 상태, 인덱스, 요약, 채팅 동기화, clean-room git, runtime metadata를 위해 생성하고 관리하는 폴더 또는 파일.
- dot-prefixed 항목: 이름이 `.`으로 시작하는 폴더/파일. 기본적으로 사용자 모드에서 숨긴다.
- canonical path: backend와 파일 API가 사용하는 실제 workspace path.
- alias prefix: 사용자 모드 UI에 보여주는 친화적인 prefix. 예를 들어 `내 폴더`는 실제 사용자 작업 root를 가리키는 즐겨찾기 또는 symlink 같은 개념이다.
- alias path: alias prefix로 시작하지만 canonical path와 1:1로 해석 가능한 사용자 모드 경로다.

## Alias/Canonical 변환 정책

backend와 frontend 모두 alias/canonical 변환 함수를 둔다. 단, 최종 권위는 backend resolver에 있다.

- frontend resolver는 사용자 모드 UI 표시, breadcrumb, selection, API 요청 payload 생성에 사용한다.
- backend resolver는 모든 파일 mutation 전에 alias path를 canonical path로 확정하고 검증한다.
- 파일 생성, 업로드, rename, move, delete, read/write API는 backend resolver를 거친 canonical path만 실제 filesystem 작업에 사용한다.
- alias는 별도의 저장 경로가 아니라 canonical prefix를 친화적인 이름으로 보여주는 prefix 치환 규칙이다.
- frontend와 backend의 alias mapping은 같은 정책 문서와 테스트 fixture를 기준으로 동기화한다.
- resolver 단위 테스트는 `내 폴더/...`, `팀 폴더/...`, 이미 canonical인 path, 허용되지 않은 alias prefix를 모두 검증한다.

## Frontend 상태/cache 주의사항

사용자 모드와 개발자 모드는 같은 path를 조회해도 결과가 다르므로 frontend 상태를 분리해서 관리한다.

- folder cache key는 path만 사용하지 않고 view mode를 함께 포함한다. 예: `user:/`, `developer:/`.
- mode 전환 시에는 cache를 reload하거나 mode별 cache를 명확히 분리한다.
- explorer 개발자 모드는 채팅 debug mode와 별도의 상태로 관리한다.
- 개발자 모드 저장 key는 `haro:developerMode:{userId|anonymous}`처럼 explorer 전용 key를 사용한다.
- 채팅 debug mode, agent trace 설정, workspace explorer 개발자 모드는 서로 영향을 주지 않는다.

## 사용자별 Instruction 파일

사용자 root에는 hidden instruction 파일 두 개를 둔다.

- `.HARO.md`: Haro 시스템 관리용. 사용자가 직접 수정할 수 없고, 모든 agent 프롬프트에 포함된다.
- `AGENTS.md`: 사용자 커스텀용. 사용자에게 보이고 수정할 수 있으며, 모든 agent 프롬프트에 `.HARO.md` 다음으로 포함된다.

`.HARO.md`는 사용자 모드 explorer/search에서 숨긴다. `AGENTS.md`는 `내 폴더/AGENTS.md`로 사용자에게 보이는 커스텀 파일이다. `AGENTS.md`는 사용자 선호를 담을 수 있지만 `.HARO.md`의 안전, 권한, 시스템 경로 정책을 override할 수 없다.

채팅 화면의 기본 사용자 모드에서는 raw canonical path와 tool JSON detail을 그대로 노출하지 않는다. 사용자-facing 답변은 alias path를 우선 사용하고, tool step은 간단한 진행/완료 문구로 표시한다. debug mode 또는 developer mode에서는 raw detail을 확인할 수 있다.

## 사용자 흐름

1. 사용자는 프로젝트에 진입하면 기본적으로 사용자 모드 explorer를 본다.
2. explorer 최상위에는 `팀 폴더`와 `내 폴더`가 보인다.
3. `팀 폴더`는 팀이 제공하는 읽기 전용 자료와 공유 산출물을 보여준다.
4. `내 폴더`는 현재 사용자의 작업 파일만 보여주며 내부 user id를 표시하지 않는다.
5. 시스템 내부 폴더와 파일은 기본적으로 보이지 않는다.
6. topbar에서 개발자 모드를 켜면 raw workspace tree와 dot-prefixed 시스템 항목을 확인할 수 있다.
7. 개발자 모드를 끄면 다시 사용자 모드로 돌아온다.

## 사용자 모드 루트 초안

```text
팀 폴더
  데이터
  규칙/스킬
  공유 결과

내 폴더
  받은 파일
  작업 중
  결과
```

이 이름들은 alias prefix이며, 실제 canonical path 매핑은 `design.md`에서 시스템 물리 구조 기준으로 정의한다.

## 초기화 정책

기존 개발/테스트 워크스페이스는 보존 migration 대상이 아니다. 구현 중 기존 워크스페이스 구조가 새 정책과 충돌하면 초기화할 수 있다.

- workspace root 내부의 기존 project workspace만 초기화한다.
- 초기화 실행 전 `git status`가 clean이고 현재 브랜치가 GitHub 원격에 push되어 있어야 한다.
- 변경 사항이 남아 있으면 먼저 현재 코드와 스펙을 GitHub에 커밋/푸쉬해 복구 지점을 만든다.
- 이 GitHub checkpoint는 코드/스펙 복구용이며 runtime workspace 데이터 백업을 대체하지 않는다.
- 프로젝트 DB 레코드와 workspace directory 사이의 참조가 깨지지 않도록 초기화 절차를 명시한다.
- 초기화 대상 path는 resolved absolute path 기준으로 configured `workspace_root`의 직접 하위 project workspace여야 한다.
- `workspace_root` 자체, repo root, `.specs`, `src`, 상위 디렉터리, 다른 project workspace는 초기화 대상이 될 수 없다.
- 필요한 경우 seed/sample 파일만 시스템 물리 구조에 맞춰 다시 만든다.

## 성공 기준

- topbar에서 개발자 모드를 켜고 끌 수 있다.
- 개발자 모드는 모든 사용자가 사용할 수 있고 raw workspace tree를 보여준다.
- 개발자 모드 off 상태에서 dot-prefixed 시스템 항목이 explorer와 검색 결과에 기본 노출되지 않는다.
- 개발자 모드 on 상태에서 현재 raw explorer에 가까운 구조를 볼 수 있다.
- 사용자 모드 파일 생성/업로드/rename은 `.`으로 시작하는 path segment를 거부한다.
- 사용자 모드에서 `팀 폴더`, `내 폴더`가 최상위 개념으로 보인다.
- 사용자 모드 UI에 `/playground/users/{user_id}` 같은 내부 식별자 기반 canonical prefix가 그대로 노출되지 않는다.
- 사용자 모드 검색은 alias allowlist 범위 밖 canonical path를 반환하지 않는다.
- backend pagination/search가 숨김 항목 때문에 빈 페이지나 잘못된 total을 만들지 않는다.
- backend filesystem 작업은 path escape, absolute path injection, symlink traversal을 차단한다.
- 파일 생성/업로드/저장은 alias path를 canonical path로 해석한 뒤 수행된다.
- frontend와 backend resolver가 같은 alias/canonical mapping을 기준으로 동작한다.
- frontend folder cache는 사용자 모드와 개발자 모드 결과를 섞지 않는다.
- explorer 개발자 모드는 채팅 debug mode와 독립적으로 저장되고 동작한다.
- `.HARO.md`와 `AGENTS.md`가 사용자 root에 생성되고 프롬프트에 포함된다.
- `.HARO.md`는 사용자 read/write API에서 차단된다.
- `AGENTS.md`는 사용자에게 보이고 수정할 수 있다.
- 사용자 모드 채팅 답변에서 `/playground/users/{user_id}` raw path가 기본 노출되지 않는다.
- frontend와 backend 단위 테스트가 추가된다.
- `cd src/backend; .\.venv\Scripts\python.exe -m pytest`가 통과한다.
- `cd src/frontend; npm test`가 통과한다.
- `cd src/frontend; npm run build`가 통과한다.

## 전략 검증 루프

검증 기준은 다음으로 갱신한다.

- 사용자 모드는 물리 구조가 아니라 필터링된 폴더 조회 view다.
- 실제 물리 구조는 시스템 설계를 따른다.
- 기존 workspace 보존 migration은 만들지 않는다.
- 기존 개발/테스트 workspace는 안전 검증 후 초기화할 수 있다.
- 초기화 전에는 GitHub commit/push checkpoint를 만든다.
- workspace root는 프로젝트 루트 하위 runtime data 경로를 사용한다.
- 사용자 모드는 product view이고, 개발자 모드는 raw filesystem view다.

질문: 현재 alias/canonical 전략에 100% 확신이 있나요?

답: 주요 허점은 위 정책과 주의사항에 반영했다. 구현 중 새 허점이 발견되면 이 루프에 다시 추가하고, 정책 또는 계획에 반영한 뒤 제거한다.

최종 전략: backend는 프로젝트 루트 하위 runtime workspace root에서 시스템 물리 구조를 유지하면서 hidden/system 항목 필터링과 `include_hidden` query 계약을 제공한다. frontend는 사용자/개발자 모드를 분리하고, 사용자 모드에서는 canonical path 위에 `팀 폴더`, `내 폴더` alias prefix view를 구성한다. 파일 mutation은 alias path를 canonical path로 resolve한 뒤 수행한다. 기존 workspace는 migration하지 않고 GitHub checkpoint를 만든 뒤 필요 시 안전 초기화로 정리한다.

사실상 확신 수준: 구현 시작 가능할 만큼 높음. 단, 구현 중 새 허점이 발견되면 전략 검증 루프를 다시 실행한다.
