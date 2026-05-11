# Workspace Folder View Modes Design

작성일: 2026-05-07

## 현재 구조 관찰

- backend harness는 `clean-room`, `playground/users/{user_id}`, `90_archive`, `.haro`를 만든다.
- `.haro`와 `.openclaw`는 내부 metadata 경로이며 read/write API에서 차단된다.
- frontend `ProjectWorkspace.svelte`는 `WorkspaceTopBar`, `WorkspaceSidePanel`, `WorkspaceFileExplorer`를 조립한다.
- 현재 topbar에는 개발자 모드 토글이 없다.
- 현재 explorer row는 실제 `TreeNode.path`를 기준으로 렌더링한다.
- 현재 directory API는 raw path 기준 pagination을 제공한다.

## 설계 원칙

- 사용자 모드는 product view, 개발자 모드는 raw filesystem view로 분리한다.
- 개발자 모드는 모든 사용자가 사용할 수 있는 고급 보기 모드이며 권한 상승 기능은 아니다.
- 사용자 모드는 실제 물리 구조를 직접 보여주지 않고, 필터링된 폴더 조회 결과를 보여준다.
- 물리 workspace 구조는 UX 이름이 아니라 system design, harness, agent tools, workspace index 정책을 따른다.
- workspace root는 `src/backend` 하위가 아니라 프로젝트 루트 하위 runtime data 영역을 기본으로 한다.
- 숨김 정책은 backend query 단계에서 적용한다.
- frontend는 alias prefix와 canonical path의 1:1 해석 규칙을 중앙 helper로 관리한다.
- 기존 workspace 보존 migration은 만들지 않는다. 필요하면 기존 개발/테스트 workspace를 안전하게 초기화한다.

## 시스템 항목 dot-prefix 정책

신규 시스템 항목은 이름 앞에 `.`을 붙인다.

예상 시스템 항목:

- `.haro`
- `.openclaw` legacy metadata
- `.git` 또는 clean-room 내부 git metadata
- `.chats` 또는 채팅 파일 동기화 산출물 중 사용자에게 직접 노출할 필요가 없는 항목
- `.summaries`, `.indexes`, `.runtime`, `.cache` 성격의 내부 파일/폴더

기존 `50_chats`, `40_rules`, `45_skills`처럼 사용자에게 일부 의미가 있을 수 있는 폴더는 즉시 dot-prefix로 단정하지 않는다. 다음 기준으로 분류한다.

- 사용자가 직접 열고 수정해야 하는가?
- 팀 규칙이나 스킬처럼 제품 기능으로 노출해야 하는가?
- 내부 sync/cache/index 목적인가?

내부 목적이면 dot-prefix 대상이다. 사용자 기능이면 사용자 모드에 친화적인 표시 이름으로 노출한다.

## Workspace Root 위치

현재 기본 설정은 `WORKSPACE_ROOT=./data/workspaces`이며, 백엔드를 `src/backend`에서 실행하면 `src/backend/data/workspaces`로 해석된다. 이 위치는 source tree와 runtime data를 섞으므로 장기적으로 좋지 않다.

권장 기본값:

```text
<project-root>/runtime/workspaces
```

정책:

- `workspace_root`는 프로젝트 루트 기준으로 resolve한다.
- `runtime/`은 git 추적 대상이 아니어야 한다.
- 운영 환경에서는 `runtime/workspaces`를 EFS mount point, bind mount, symlink 중 하나로 연결할 수 있어야 한다.
- backend package 내부 경로에 workspace data를 두지 않는다.

예상 설정:

```env
WORKSPACE_ROOT=runtime/workspaces
```

상대 경로는 project root 기준으로 resolve한다. 운영 환경에서는 절대 경로도 사용할 수 있다.

## 사용자 모드 filtered alias view

사용자 모드에서는 실제 root `/`를 그대로 보여주지 않는다. 대신 alias prefix root를 구성한다.

```text
팀 폴더       -> system-defined team/shared canonical prefix
내 폴더       -> system-defined current-user canonical prefix
```

초기 alias mapping 후보:

```text
팀 폴더/데이터      -> /clean-room/data
팀 폴더/규칙/스킬   -> /clean-room/meta
팀 폴더/공유 결과   -> /clean-room/data/30_outputs

내 폴더/받은 파일   -> /playground/users/{user_id}/00_inbox
내 폴더/작업 중     -> /playground/users/{user_id}/20_working
내 폴더/결과        -> /playground/users/{user_id}/30_outputs
```

위 canonical path는 현재 시스템 구조 기준의 후보일 뿐이다. 구현 중 system design이 다른 canonical path를 선택하면 alias mapping만 바꾸고 사용자 모드 이름은 유지한다.

사용자 모드 UI에는 `/playground/users/{user_id}` 자체를 직접 보여주지 않는다.

## 개발자 모드

개발자 모드에서는 현재 explorer와 거의 같은 raw tree를 사용한다.

- root `/`를 그대로 로드한다.
- raw path를 그대로 표시한다.
- dot-prefixed 항목도 표시한다.
- 모든 사용자가 사용할 수 있다.
- read-only guard와 internal metadata 접근 제한은 유지한다.

개발자 모드는 topbar toggle로 제어한다.

```text
localStorage key: haro:developerMode:{userId|anonymous}
```

채팅 debug mode와 별도 상태로 둔다.

## 사용자별 instruction 파일

사용자 root에는 hidden instruction 파일 두 개를 둔다.

```text
/playground/users/{user_id}/.HARO.md
/playground/users/{user_id}/AGENTS.md
```

- `.HARO.md`는 Haro가 관리하는 시스템 지침 파일이다. 하네스 보정 시 시스템 템플릿으로 유지하고 사용자 read/write API에서는 차단한다.
- `AGENTS.md`는 사용자 커스텀 지침 파일이다. 최초 생성 후 사용자가 수정할 수 있고, 하네스 보정으로 덮어쓰지 않는다.
- `.HARO.md`는 dot-prefixed 파일이므로 사용자 모드 explorer/search에는 숨긴다.
- `AGENTS.md`는 사용자 모드에서 `내 폴더/AGENTS.md` 파일 노드로 보이고 수정할 수 있다.
- `build_context`는 `.HARO.md`를 먼저 포함하고 `AGENTS.md`를 뒤에 포함한다.
- `AGENTS.md`는 사용자 선호를 담지만 `.HARO.md`의 안전, 권한, 시스템 경로 정책을 override할 수 없다.

채팅 UI에서는 기본 사용자 모드에서 raw canonical path를 alias path로 치환한다. tool step도 `file_create({...})` 같은 raw detail 대신 `파일 생성 완료` 같은 간단한 문구로 보여준다. debug mode 또는 developer mode에서는 raw detail을 유지한다.

## Backend API 설계

### Directory list

현재:

```http
GET /api/projects/{project_id}/files?path=/...
```

추가 query:

```http
GET /api/projects/{project_id}/files?path=/...&include_hidden=false
```

- `include_hidden=false`: 이름이 `.`으로 시작하는 항목과 backend가 system hidden으로 분류한 항목을 제외하고, 사용자 모드 alias allowlist에 포함된 canonical prefix 범위만 반환한다.
- `include_hidden=true`: 개발자 모드용. raw tree를 반환한다. 단, Clean Room 권한, read-only guard, workspace root escape 방지, `.haro` content read/write 제한은 유지한다.
- 기본값은 현재 동작 호환을 위해 `true` 또는 기존 동작 유지로 시작하고, 사용자 모드 호출에서 명시적으로 `false`를 넘긴다.

### Search

현재:

```http
GET /api/projects/{project_id}/files/search?q=...
```

추가 query:

```http
GET /api/projects/{project_id}/files/search?q=...&include_hidden=false
```

사용자 모드 검색은 hidden/system 항목을 제외하고 alias allowlist에 포함된 canonical prefix 범위에서만 검색한다. 개발자 모드 검색은 raw tree를 대상으로 한다.

### Path safety

모든 backend filesystem 작업은 canonical path resolve 이후 workspace root 내부인지 검증한다.

- `..`, absolute path injection, Windows drive prefix, UNC path, symlink/mount traversal은 resolved absolute path 기준으로 차단한다.
- EFS mount, 외부 volume, symlink를 쓰더라도 최종 resolved path가 configured workspace root 정책을 벗어나면 실패한다.
- read, write, create, upload, rename, move, delete, index rebuild, workspace 초기화에 같은 정책을 적용한다.

## Backend 내부 설계

새 helper 후보:

- `is_dot_prefixed_path(path)`
- `is_system_hidden_path(path)`
- `should_hide_workspace_item(path, include_hidden)`
- `workspace_alias_roots(user_id)`
- `resolve_workspace_alias_path(alias_path, user_id)`
- `alias_path_for_canonical_path(canonical_path, user_id)`

적용 지점:

- `workspace_file_queries.list_workspace_directory_page`
- `workspace_file_queries.search_workspace_files`
- `harness.ensure_harness_structure`
- `file_path_policy.assert_read_allowed`
- `file_path_policy.assert_write_allowed`
- `context.py`, `tool_registry.py`, `chat_workspace_paths.py`의 사용자 안내 경로

pagination은 SQL WHERE에서 숨김 조건을 적용해 total과 page size가 일치해야 한다.

## Frontend 설계

새 state:

- `developerMode`

Topbar:

- `WorkspaceTopBar.svelte`에 개발자 모드 토글 추가
- 토글은 짧은 label과 tooltip을 가진다.
- 값 변경 시 localStorage 저장

Explorer:

- 개발자 모드:
  - 기존 `fileTree`, `folderCache`, `buildExplorerRows` 흐름 사용
  - directory/search API 호출 시 `include_hidden=true`
- 사용자 모드:
  - alias root rows를 먼저 구성
  - alias node는 표시 prefix와 canonical prefix mapping을 가진다
  - directory/search API 호출 시 `include_hidden=false`
  - UI에 raw `/playground/users/{id}` 경로 대신 alias path를 보여준다.

View model 후보:

```ts
type WorkspaceExplorerMode = 'user' | 'developer';

type WorkspacePathAlias = {
  label: string;
  aliasPrefix: string;
  canonicalPrefix: string;
};

type WorkspaceAliasNode = TreeNode & {
  aliasPath?: string;
  canonicalPath: string;
  virtual?: boolean;
};
```

기존 `TreeNode.path`는 가능한 한 canonical path로 유지한다. 사용자 모드 표시가 필요할 때만 alias resolver로 `aliasPath`를 계산한다.

## 파일 생성/업로드 target

사용자 모드의 `팀 폴더` 중 read-only 영역에서는 기존처럼 생성/업로드를 막는다.

사용자 모드의 `내 폴더` alias node에서 생성/업로드할 때는 alias path를 canonical path로 resolve한다.

예:

```text
내 폴더/작업 중/new.md -> /playground/users/{user_id}/20_working/new.md
```

## 초기화 정책

기존 생성 워크스페이스는 migration하지 않는다. 개발/테스트 환경에서는 초기화가 허용된다.

초기화 절차 원칙:

- 초기화 전에 현재 코드와 스펙이 GitHub 원격에 커밋/푸쉬되어 있어야 한다.
- 초기화 대상은 설정된 `workspace_root` 하위 project workspace로 제한한다.
- 작업 전 resolved absolute path가 `workspace_root` 하위인지 검증한다.
- `workspace_root`는 프로젝트 루트 하위 runtime data 경로여야 하며, `src/backend` 하위 source tree를 기본 저장소로 사용하지 않는다.
- 서버가 실행 중이면 중지하거나 해당 project workspace를 사용하지 않는 상태에서 진행한다.
- 초기화 후 `ensure_harness_structure`로 시스템 물리 구조를 재생성한다.
- workspace file DB와 index는 새 구조 기준으로 rebuild한다.

GitHub 커밋/푸쉬는 code/spec 복구 지점이다. 보존이 필요한 runtime workspace 데이터가 생기면 별도 export/backup 절차 또는 migration 스펙을 작성한다.

## 테스트 전략

Backend:

- dot-prefixed path 판별 테스트
- directory list에서 hidden 항목 제외/포함 테스트
- search에서 hidden 항목 제외/포함 테스트
- 사용자 모드 search가 alias allowlist 밖 canonical prefix를 제외하는지 테스트
- pagination total이 hidden filter를 반영하는지 테스트
- path escape, absolute path injection, symlink traversal 차단 테스트
- 초기화 helper가 workspace root 밖 path를 거부하는지 테스트
- workspace root가 project root 하위 runtime 경로로 resolve되는지 테스트
- 초기화 전 git checkpoint 조건을 검증하는지 테스트 또는 수동 절차로 확인

Frontend:

- 개발자 모드 localStorage key 테스트
- 사용자 모드 alias root 구성 테스트
- alias path와 canonical path 변환 테스트
- explorer rows에서 hidden/system 항목이 기본 제외되는지 테스트

## 대안과 결정

- 대안 1: frontend에서만 숨긴다.
  - 기각: pagination/search total이 깨지고 API 응답에는 여전히 내부 경로가 노출된다.
- 대안 2: 사용자 모드 이름에 맞춰 물리 구조를 `/team`, `/me`로 바꾼다.
  - 기각: 사용자에게 보이는 것은 filtered view이며, 물리 구조는 system design을 따라야 한다.
- 대안 3: 기존 workspace를 migration한다.
  - 기각: 현재는 기존 workspace 초기화가 가능하므로 migration 복잡도를 만들지 않는다.
