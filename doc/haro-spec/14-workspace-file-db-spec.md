# Workspace File DB 스펙

## 1. 목적

haro의 파일 관리는 단순한 폴더 탐색이 아니다.

사용자는 파일을 올리고, haro는 그 파일이 어떤 업무 자료인지 이해하고, 채팅과 산출물, 요약, Clean Room 보호 상태까지 함께 추적해야 한다.

파일이 3,000개 이상으로 늘어나도 다음 작업은 막히지 않아야 한다.

- 파일명 검색
- 폴더명 검색
- 경로 검색
- 요약 텍스트 검색
- 파일/폴더 개수 조회
- Clean Room / Playground / Archive 필터
- 채팅에서 사용한 파일과 생성한 산출물 추적
- 파일/폴더 변경 후 즉시 검색 반영

이를 위해 각 워크스페이스는 자기 내부에 SQLite 기반 파일 관리 DB를 가진다.

## 2. DB 위치

워크스페이스별 SQLite DB를 사용한다.

```text
{workspace}/.haro/db/workspace.db
```

역할 분리:

| DB | 위치 | 역할 |
| --- | --- | --- |
| 서비스 DB | `src/backend/data/pgdata/haro.db` | 사용자, 인증, 프로젝트, 채팅 세션, 메시지 |
| Workspace File DB | `{workspace}/.haro/db/workspace.db` | 파일/폴더 메타데이터, 검색, 관계, 동기화 상태 |

전역 `haro.db`에는 업무 파일의 상세 메타데이터를 넣지 않는다.
워크스페이스가 EFS 같은 외부 스토리지로 이동해도 파일 관리 DB가 같이 이동해야 하기 때문이다.

## 3. 설계 원칙

1. filesystem이 원본이다.
2. workspace DB는 강한 인덱스다.
3. 사용자 파일 API를 통한 변경은 DB와 즉시 동기화한다.
4. 외부에서 직접 바뀐 파일은 재스캔으로 복구한다.
5. `.haro` 내부는 사용자 파일 트리에서 숨긴다.
6. Clean Room 보호 정책은 DB에도 기록한다.
7. 검색은 SQLite FTS5 trigram tokenizer를 사용한다.
8. v1 검색 범위는 파일명, 폴더명, 경로, 요약 텍스트다.
9. 파일 본문 전체 검색은 후속 주기로 둔다.

## 4. 테이블 개요

```text
workspace_items
  파일/폴더의 기준 메타데이터

workspace_items_fts
  파일명, 경로, 요약 텍스트 검색 인덱스

workspace_item_relations
  원본, 변환본, 채팅 입력, 채팅 산출물, export 관계

workspace_file_events
  DB 동기화와 문제 추적을 위한 변경 로그

workspace_db_meta
  schema version, 마지막 scan, 재스캔 필요 여부
```

## 5. `workspace_items`

파일과 폴더의 기준 메타데이터 테이블이다.

| column | type | required | description |
| --- | --- | --- | --- |
| `id` | TEXT PK | yes | 내부 UUID |
| `path` | TEXT | yes | `/clean-room/...` 형태의 정규화 경로 |
| `parent_path` | TEXT | yes | 부모 폴더 경로, root 자식은 `/` |
| `name` | TEXT | yes | 파일/폴더 이름 |
| `item_type` | TEXT | yes | `file`, `dir` |
| `extension` | TEXT NULL | no | `.md`, `.csv`, `.html` 등 |
| `language` | TEXT NULL | no | `markdown`, `csv`, `html`, `json` 등 |
| `mime_type` | TEXT NULL | no | 업로드 또는 추론된 MIME |
| `size_bytes` | INTEGER NULL | no | 파일 크기, 폴더는 NULL |
| `mtime_ms` | INTEGER NULL | no | filesystem 수정 시각 |
| `content_hash` | TEXT NULL | no | 내용 hash, 큰 파일은 lazy 계산 |
| `summary_text` | TEXT NULL | no | 검색용 요약 텍스트 |
| `summary_status` | TEXT | yes | `none`, `fresh`, `stale`, `skipped`, `error` |
| `summary_updated_at` | TEXT NULL | no | 요약 갱신 시각 |
| `room` | TEXT | yes | `clean_room_data`, `clean_room_meta`, `playground`, `archive`, `root` |
| `access_policy` | TEXT | yes | `writable`, `read_only`, `hidden` |
| `owner_user_id` | TEXT NULL | no | 사용자 playground 소유자 |
| `chat_id` | TEXT NULL | no | 채팅 폴더 또는 채팅 산출물 연결 |
| `source_kind` | TEXT | yes | `local`, `upload`, `agent`, `chat`, `drive`, `gmail`, `generated` |
| `sync_status` | TEXT | yes | `synced`, `stale`, `missing`, `conflict`, `error` |
| `is_deleted` | INTEGER | yes | soft delete 여부, 0 또는 1 |
| `last_seen_at` | TEXT | yes | 마지막 scan 확인 시각 |
| `indexed_at` | TEXT | yes | DB 인덱싱 시각 |
| `created_at` | TEXT | yes | 생성 시각 |
| `updated_at` | TEXT | yes | DB row 갱신 시각 |
| `deleted_at` | TEXT NULL | no | 삭제 시각 |
| `metadata_json` | TEXT NULL | no | 확장 메타데이터 |

권장 제약:

- `path`는 항상 `/`로 시작한다.
- `.haro/**`는 v1에서 `workspace_items`에 색인하지 않는다. 시스템 메타데이터는 별도 내부 테이블이나 `workspace_db_meta`로 관리한다.
- `clean-room/**`는 기본 `read_only`다.
- `playground/users/{user_id}/**`는 기본 `writable`이다.
- `is_deleted=1`인 row는 일반 파일 트리와 검색 결과에서 제외한다.
- 같은 `path`에는 active row가 하나만 존재할 수 있다.
- 삭제된 row는 이력으로 남길 수 있지만, 새 파일이 같은 경로에 생성되면 새 active row를 만들 수 있어야 한다.
- 파일 내용이 바뀌면 기존 요약은 `summary_status=stale`로 표시한다.

권장 인덱스:

```sql
CREATE UNIQUE INDEX idx_workspace_items_active_path ON workspace_items(path) WHERE is_deleted = 0;
CREATE INDEX idx_workspace_items_parent ON workspace_items(parent_path, is_deleted);
CREATE INDEX idx_workspace_items_room ON workspace_items(room, is_deleted);
CREATE INDEX idx_workspace_items_access_policy ON workspace_items(access_policy, is_deleted);
CREATE INDEX idx_workspace_items_chat ON workspace_items(chat_id, is_deleted);
CREATE INDEX idx_workspace_items_sync ON workspace_items(sync_status, is_deleted);
```

## 6. `workspace_items_fts`

파일명, 경로, 요약 텍스트 검색용 SQLite FTS5 테이블이다.

| column | type | description |
| --- | --- | --- |
| `item_id` | UNINDEXED | `workspace_items.id` |
| `name` | TEXT | 파일/폴더명 검색 |
| `path` | TEXT | 경로 검색 |
| `summary_text` | TEXT | 요약 텍스트 검색 |

권장 생성 형태:

```sql
CREATE VIRTUAL TABLE workspace_items_fts USING fts5(
  item_id UNINDEXED,
  name,
  path,
  summary_text,
  tokenize='trigram'
);
```

검색 정책:

- 검색 결과는 `workspace_items`와 join해 실제 보호 상태와 삭제 상태를 확인한다.
- `is_deleted=1`인 항목은 검색 결과에서 제외한다.
- `.haro/**` 항목은 검색 결과에서 제외한다.
- 검색 snippet은 `summary_text`에서 만든다.
- v1은 형태소 분석 대신 trigram 기반 부분 검색을 사용한다.
- 한국어 파일명과 요약 텍스트도 띄어쓰기나 완전 일치에만 의존하지 않고 찾을 수 있어야 한다.
- trigram 검색이 약한 1~2글자 query는 `name LIKE` / `path LIKE` fallback을 함께 사용한다.
- FTS `MATCH`에 넣기 전 검색어를 정규화하고 특수문자/따옴표를 안전하게 escape한다.
- 검색어가 비어 있거나 escape 후 의미 있는 토큰이 없으면 FTS를 실행하지 않고 빈 결과를 반환한다.

동기화 정책:

- v1에서는 DB trigger보다 명시적 동기화를 사용한다.
- `workspace_items` 변경과 같은 SQLite transaction 안에서 기존 FTS row를 `item_id`로 삭제한 뒤 새 row를 insert한다.
- 삭제 또는 soft delete 시에도 같은 transaction 안에서 FTS row를 삭제한다.
- FTS 동기화 실패는 전체 DB 갱신 실패로 본다.

## 7. `workspace_item_relations`

파일 간 관계와 채팅 산출물 관계를 기록한다.

| column | type | required | description |
| --- | --- | --- | --- |
| `id` | TEXT PK | yes | 내부 UUID |
| `from_item_id` | TEXT NULL | no | 원본 item id |
| `from_path` | TEXT NULL | no | 원본 path snapshot |
| `to_item_id` | TEXT NULL | no | 대상 item id |
| `to_path` | TEXT NULL | no | 대상 path snapshot |
| `relation_type` | TEXT | yes | `chat_input`, `chat_output`, `derived_from`, `exported_to`, `summary_of`, `imported_from` |
| `chat_id` | TEXT NULL | no | 관련 채팅 |
| `created_by_user_id` | TEXT NULL | no | 생성 사용자 |
| `created_at` | TEXT | yes | 생성 시각 |
| `metadata_json` | TEXT NULL | no | 추가 정보 |

관계 예:

| relation_type | 의미 |
| --- | --- |
| `chat_input` | 채팅에서 읽거나 참고한 입력 파일 |
| `chat_output` | 채팅에서 생성한 산출물 |
| `derived_from` | Excel 원본에서 CSV가 생성됨 |
| `exported_to` | 채팅 산출물을 다른 Playground 폴더로 복사함 |
| `summary_of` | 요약 파일이 원본 대화/파일을 요약함 |
| `imported_from` | Drive, Gmail 등 외부 데이터소스에서 가져옴 |

## 8. `workspace_file_events`

DB 동기화와 문제 추적을 위한 변경 로그다.

| column | type | required | description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | yes | autoincrement |
| `event_type` | TEXT | yes | `created`, `modified`, `deleted`, `moved`, `indexed`, `rescan_started`, `rescan_completed`, `sync_error` |
| `item_id` | TEXT NULL | no | 대상 item |
| `path` | TEXT | yes | 대상 경로 |
| `old_path` | TEXT NULL | no | 이동 전 경로 |
| `actor_type` | TEXT | yes | `user`, `agent`, `system`, `import` |
| `actor_id` | TEXT NULL | no | 사용자/에이전트 id |
| `chat_id` | TEXT NULL | no | 관련 채팅 |
| `created_at` | TEXT | yes | 이벤트 시각 |
| `metadata_json` | TEXT NULL | no | 오류/상세 정보 |

이 테이블은 Clean Room Git의 정식 audit log를 대체하지 않는다.
v1에서는 파일 인덱스 동기화 문제를 추적하기 위한 운영 로그로 사용한다.

## 9. `workspace_db_meta`

DB 상태와 재스캔 필요 여부를 기록한다.

| column | type | required | description |
| --- | --- | --- | --- |
| `key` | TEXT PK | yes | `schema_version`, `last_full_scan_at`, `needs_rescan` 등 |
| `value` | TEXT | yes | 값 |
| `updated_at` | TEXT | yes | 갱신 시각 |

기본 key:

| key | value example | 의미 |
| --- | --- | --- |
| `schema_version` | `1` | workspace DB schema version |
| `last_full_scan_at` | `2026-04-30T10:00:00+09:00` | 마지막 전체 scan 시각 |
| `needs_rescan` | `false` | 재스캔 필요 여부 |
| `last_sync_error_at` | `2026-04-30T10:10:00+09:00` | 마지막 sync 오류 시각 |

## 10. 동기화 정책

### API 기반 변경

사용자 파일 API와 에이전트 파일 도구는 향후 단일 파일 관리 서비스 경로를 사용한다.

에이전트의 목록/검색/개수 조회 도구도 같은 workspace DB를 기준으로 동작해야 한다.
특히 `몇 개`처럼 개수만 필요한 질문은 파일 시스템을 직접 훑지 않고 DB count query로 처리한다.

```text
파일/폴더 변경 요청
  -> workspace writer lock 획득
  -> path 검증
  -> Clean Room / .haro 보호 정책 확인
  -> filesystem 변경
  -> workspace DB transaction 시작
  -> workspace_items upsert/delete
  -> workspace_items_fts delete/insert
  -> workspace_file_events 기록
  -> workspace DB transaction commit
  -> workspace writer lock 해제
```

파일 쓰기와 업로드는 가능하면 임시 파일에 먼저 쓰고 atomic rename으로 반영한다.
DB transaction은 파일 I/O 전체를 감싸지 않고, DB row와 FTS 갱신 구간만 짧게 유지한다.

DB 갱신 실패를 조용히 무시하지 않는다.

- filesystem 변경 전 실패: 요청 실패
- filesystem 변경 후 DB 갱신 실패: 요청은 실패로 반환하고 `sync_error` 기록 시도
- 오류 기록도 실패: `workspace_db_meta.needs_rescan=true`를 다음 가능한 시점에 남김
- 다음 파일 트리 로딩 때 전체 또는 부분 재스캔
- API 성공은 filesystem 변경과 DB/FTS 반영이 모두 끝난 상태를 의미한다.
- filesystem 변경을 되돌릴 수 없는 실패는 `needs_rescan=true`를 남기고 사용자에게 “파일은 변경됐지만 인덱스 복구가 필요함” 상태를 알려야 한다.
- 파일 내용 변경 시 `summary_status=stale`로 바꾸고, FTS에는 최신 `name/path`와 빈 `summary_text`를 반영한다.
- 새 요약이 생성되면 `summary_status=fresh`와 `summary_text`를 갱신한 뒤 FTS를 다시 갱신한다.

### 외부 변경

v1에서는 OS watcher를 도입하지 않는다.

다음 상황에서 재스캔한다.

- workspace DB가 없음
- schema version이 오래됨
- `needs_rescan=true`
- 사용자가 수동 새로고침을 누름
- 파일 목록과 실제 filesystem 사이의 불일치가 발견됨

삭제 처리:

- 사용자 API를 통한 삭제는 `is_deleted=1`, `deleted_at` 기록, FTS row 삭제로 처리한다.
- 외부 변경으로 파일이 사라진 경우에는 즉시 삭제 확정하지 않고 먼저 `sync_status=missing`으로 표시한다.
- 재스캔에서 계속 없거나 사용자가 확인하면 `is_deleted=1`로 전환한다.

## 11. 검색 정책

검색 API는 FTS5 trigram 인덱스를 사용한다.
FTS5 trigram tokenizer는 v1 검색의 필수 기능이다.
지원되지 않는 런타임에서는 검색 API를 조용히 degrade하지 않고 `search_unavailable` 상태를 반환하며, 파일 트리 기본 조회만 유지한다.

```http
GET /api/projects/{project_id}/files/search?q=report
```

기본 응답 필드:

```json
{
  "items": [
    {
      "path": "/playground/users/zerry/30_outputs/drafts/report.md",
      "name": "report.md",
      "item_type": "file",
      "language": "markdown",
      "room": "playground",
      "access_policy": "writable",
      "summary_status": "fresh",
      "summary_snippet": "A광고주 주간 성과 보고서 초안..."
    }
  ]
}
```

v1 필터:

- `room`
- `item_type`
- `language`
- `extension`
- `access_policy`
- `chat_id`

성능 기준:

- 3,000개 파일과 요약 텍스트가 있는 워크스페이스에서 파일명/요약 검색이 UI 상호작용을 막지 않아야 한다.
- 일반 파일 트리 조회는 전체 filesystem scan 없이 DB의 `parent_path` index를 우선 사용한다.
- 한국어 파일명 부분 검색과 요약 텍스트 부분 검색이 동작해야 한다.
- 1~2글자 query는 FTS 결과가 비어도 `name/path LIKE` fallback으로 파일명 검색이 동작해야 한다.

## 12. 요약 텍스트 정책

`summary_text`는 검색을 위한 짧은 설명이다.

생성 후보:

- 파일 업로드 후 자동 요약
- 사용자가 파일을 열거나 에이전트가 읽은 뒤 생성한 요약
- 채팅 요약에서 나온 파일 설명
- `file_summaries`에 저장된 기존 요약

저장 원칙:

- 파일 본문 전체를 DB에 넣지 않는다.
- 요약은 검색과 파일 선택 보조에 필요한 수준으로 제한한다.
- 민감 정보가 많은 파일은 summary 생성 자체를 생략하거나 제한한다.
- `summary_status=stale`인 요약은 UI에 “요약 갱신 필요”로 표시할 수 있다.
- stale 요약은 FTS 검색 대상에서 제외하고, 새 요약이 생성된 뒤 다시 검색 대상에 넣는다.

## 13. EFS와 SQLite 운영 정책

실제 서비스에서는 워크스페이스가 EFS에 있을 수 있다.

v1 구현 전제:

- 프로젝트 단위 writer lock을 둔다.
- 동시에 여러 worker가 같은 `workspace.db`에 쓰지 않게 한다.
- 읽기는 여러 요청에서 허용하되, 쓰기는 직렬화한다.
- EFS 안정성을 우선해 WAL을 기본값으로 두지 않고 `journal_mode=DELETE`를 기본으로 둔다.
- `busy_timeout`을 설정해 짧은 lock 충돌은 재시도한다.
- 여러 backend process가 같은 workspace를 다룰 수 있다면 process-local lock만으로는 부족하다.
- v1은 단일 writer process를 전제로 하거나, `.haro/locks/workspace-db.lock` 같은 파일 lock으로 workspace 단위 쓰기를 보호한다.

장기적으로 파일 수와 동시성이 커지면 다음 선택지를 검토한다.

- workspace DB를 별도 metadata service로 승격
- 검색 전용 OpenSearch/Meilisearch 분리
- 대용량 object metadata는 `.haro/objects` 또는 별도 object store와 연결

## 14. 채팅세션과의 연결

채팅 폴더는 filesystem에 존재하지만, 관계 검색은 workspace DB가 담당한다.

예:

```text
채팅에서 파일 읽음
  -> workspace_item_relations.relation_type = chat_input

채팅에서 보고서 생성
  -> workspace_item_relations.relation_type = chat_output

채팅 산출물을 다른 폴더로 복사
  -> workspace_item_relations.relation_type = exported_to
```

`linked-files.json`과 `artifacts.json`은 사용자가 읽기 쉬운 mirror다.
검색, 필터, 관계 조회의 기준은 workspace DB로 둔다.

## 15. 구현 범위 분리

이번 스펙은 설계 문서다.

코드 구현 주기에서는 다음 순서로 나누는 것이 좋다.

1. workspace DB 생성과 schema migration
2. SQLite FTS5 trigram 지원 확인
3. 기존 파일 트리 backfill
4. 파일 목록 조회를 DB 우선으로 전환
5. 파일 생성/업로드/저장/삭제 동기화
6. FTS5 trigram 검색 API
7. UI 검색 입력과 결과 패널
8. 채팅 파일 관계 기록

## 16. 성공 기준

- 3,000개 파일이 있어도 파일명 검색이 즉시 가능하다.
- 요약 텍스트로도 파일을 찾을 수 있다.
- 새 파일을 업로드하면 검색 결과에 바로 나타난다.
- 파일을 저장하면 `summary_text`와 FTS가 갱신될 수 있다.
- 파일을 저장하면 기존 요약이 stale 처리되고 stale 요약은 검색 대상에서 제외된다.
- 파일을 삭제하면 검색 결과에서 사라진다.
- Clean Room 파일은 DB에서도 `read_only`로 표시된다.
- `.haro` 내부 파일은 v1 workspace item 색인 대상에서 제외되고 사용자 검색에는 노출되지 않는다.
- 채팅 입력/산출물 관계를 DB에서 찾을 수 있다.
