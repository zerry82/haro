# 2번째 개발 주기: Workspace File DB + Search MVP

## 목표

파일/폴더 메타데이터를 워크스페이스 내부 SQLite DB로 관리한다.

파일이 3,000개 이상으로 늘어나도 사용자가 파일명과 요약 텍스트로 빠르게 검색할 수 있어야 한다.
또한 파일/폴더가 새로 추가되거나 수정될 때 DB와 검색 인덱스가 강하게 동기화되어야 한다.

이번 문서는 구현 코드가 아니라 2번째 개발 주기의 설계와 체크리스트다.

## 핵심 결정

- DB 위치는 `{workspace}/.haro/db/workspace.db`로 둔다.
- 전역 `haro.db`는 사용자, 프로젝트, 채팅 같은 서비스 메타데이터만 유지한다.
- 파일/폴더 목록, 검색, 보호 정책, 관계 정보는 workspace DB가 담당한다.
- SQLite FTS5 trigram tokenizer로 파일명, 경로, 요약 텍스트를 검색한다.
- 파일 본문 전체 검색은 이번 주기에서 제외한다.
- `.haro/file_summaries`는 유지하되, 검색용 요약은 workspace DB의 `summary_text`에도 반영한다.

## 구현 대상 테이블

상세 컬럼 구조는 [14-workspace-file-db-spec.md](../14-workspace-file-db-spec.md)를 따른다.

- `workspace_items`
- `workspace_items_fts`
- `workspace_item_relations`
- `workspace_file_events`
- `workspace_db_meta`

## 동기화 설계

파일 변경은 향후 `WorkspaceFileRegistry` 같은 단일 서비스 경로를 통해 수행한다.

```text
파일/폴더 변경 요청
  -> workspace writer lock 획득
  -> path 검증
  -> Clean Room / .haro 보호 정책 확인
  -> filesystem 변경
  -> workspace DB transaction 시작
  -> workspace_items 갱신
  -> workspace_items_fts delete/insert
  -> workspace_file_events 기록
  -> workspace DB transaction commit
  -> workspace writer lock 해제
```

강한 동기화 원칙:

- DB 갱신 실패를 조용히 무시하지 않는다.
- 실패하면 `sync_error` 이벤트를 남긴다.
- 복구가 필요하면 `workspace_db_meta.needs_rescan=true`를 기록한다.
- 다음 파일 트리 로딩 때 재스캔으로 복구한다.
- API 성공은 filesystem 변경과 DB/FTS 반영이 모두 끝난 상태를 의미한다.
- 같은 경로에 active item은 하나만 존재하도록 partial unique index를 사용한다.
- 업로드/저장은 임시 파일에 먼저 쓰고 atomic rename으로 반영한다.
- DB transaction은 파일 I/O 전체가 아니라 DB row/FTS/event 갱신 구간만 짧게 유지한다.
- 파일 내용 변경 시 기존 요약은 `summary_status=stale`로 표시하고 stale 요약은 FTS 검색 대상에서 제외한다.

## 검색 설계

검색 API 초안:

```http
GET /api/projects/{project_id}/files/search?q={query}
```

에이전트 도구:

- `dir_list(path)`: workspace DB 기반으로 직속 파일/폴더 목록과 개수를 조회한다.
- `file_search(query, limit, item_type)`: workspace DB/FTS 기반으로 파일명, 경로, 요약을 검색한다.
- `file_count(path, item_type, recursive)`: workspace DB 기반으로 파일/폴더 개수를 바로 조회한다.

검색 대상:

- 파일명
- 폴더명
- 경로
- `summary_text`

한국어 파일명과 요약 텍스트도 부분 검색이 가능하도록 FTS5 trigram tokenizer를 기본 설계로 둔다.
1~2글자 query는 FTS가 약할 수 있으므로 파일명/경로 `LIKE` fallback을 함께 사용한다.
검색어는 FTS `MATCH`에 넣기 전에 정규화하고 특수문자/따옴표를 안전하게 escape한다.

필터 후보:

- `room`
- `item_type`
- `language`
- `extension`
- `access_policy`
- `chat_id`

검색 결과는 `.haro/**`와 `is_deleted=1` 항목을 노출하지 않는다.

## UI 변경 방향

왼쪽 파일 패널에 검색 입력을 추가한다.

검색 결과는 파일 트리와 분리된 결과 목록으로 보여준다.
결과를 클릭하면 기존 파일 뷰어/에디터 흐름으로 열린다.

결과 항목에는 다음을 표시한다.

- 파일명
- 경로
- 파일 종류
- Clean Room / Playground 표시
- 읽기 전용 여부
- 요약 snippet

## 검증 체크리스트

- [x] 새 프로젝트 진입 시 `.haro/db/workspace.db`가 생성된다.
- [x] SQLite FTS5 trigram 지원 여부를 확인하고 지원되지 않으면 `search_unavailable` 상태를 반환한다.
- [x] 기존 프로젝트 첫 파일 트리 조회 시 기존 파일/폴더가 DB에 backfill된다.
- [x] 3,000개 파일 fixture에서 파일명 검색이 UI 사용에 무리 없이 동작한다.
- [x] 한국어 파일명 부분 검색과 요약 텍스트 부분 검색이 동작한다.
- [x] 1~2글자 검색어도 파일명/경로 fallback으로 동작한다.
- [x] 요약 텍스트 검색으로 파일을 찾을 수 있다.
- [x] 에이전트 `dir_list`와 `file_count`가 filesystem 직접 순회 대신 workspace DB를 사용한다.
- [x] 특수문자, 따옴표, 공백만 있는 검색어가 FTS 오류를 만들지 않는다.
- [ ] 새 폴더 생성 후 `workspace_items`와 FTS가 갱신된다.
- [ ] 파일 업로드 후 `workspace_items`와 FTS가 갱신된다.
- [ ] 파일 저장 후 size, mtime, summary 상태가 갱신된다.
- [x] 파일 저장 후 기존 요약은 stale 처리되고 stale 요약 텍스트는 검색 결과에 사용되지 않는다.
- [x] 파일 삭제 후 검색 결과에서 사라진다.
- [x] 삭제된 경로에 같은 이름의 파일을 다시 만들 수 있다.
- [ ] 외부에서 사라진 파일은 먼저 `sync_status=missing`이 되고 재스캔/확인 후 삭제 처리된다.
- [ ] Clean Room 파일은 DB에서도 `read_only`로 표시된다.
- [ ] `.haro` 내부 파일은 파일 트리와 검색 결과에 노출되지 않는다.
- [ ] 채팅 입력/산출물 관계가 `workspace_item_relations`에 기록된다.
- [ ] DB 손상 또는 `needs_rescan=true` 상태에서 재스캔으로 복구된다.
- [ ] 동시 업로드/저장 요청에서 workspace writer lock이 쓰기 충돌을 막는다.

## 제외 항목

- 파일 본문 전체 검색
- OS watcher 기반 실시간 감시
- 외부 검색 엔진 도입
- 대용량 object store 분리
- Clean Room 승격 요청 구현
- Git checkpoint/rollback UI 구현

## 검증 기록

- `python -m py_compile app/routers/files.py app/routers/chats.py app/services/workspace_file_db.py app/services/workspace_index.py app/services/chat_workspace.py app/services/agent.py app/services/harness.py app/main.py` 통과.
- `npm run build` 통과.
- 임시 워크스페이스에서 `.haro/db/workspace.db` 생성, 하네스 폴더 backfill, 한국어 파일명/요약 검색을 확인했다.
- 삭제된 경로에 같은 이름의 파일을 다시 생성하고 검색되는 것을 확인했다.
- 3,000개 파일 fixture에서 인덱스 생성 약 2.1초, 파일명 검색 약 39ms를 확인했다.
- 1~2글자 검색어 fallback과 특수문자 검색어 안전 처리를 확인했다.
- stale 처리된 기존 요약 텍스트가 검색 결과에서 제외되는 것을 확인했다.
- 동시 쓰기 충돌, 실제 UI 클릭 흐름은 수동 검증이 남아 있다.
