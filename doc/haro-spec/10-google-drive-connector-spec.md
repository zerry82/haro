# Google Drive 데이터소스 연동 스펙

## 1. 목적

Google Drive 연동은 haro 내부 파일시스템을 Drive로 대체하는 기능이 아니다.
Drive는 외부 데이터소스이며, haro는 사용자가 선택한 Drive 파일을 snapshot으로 가져와 하네스 안에서 관리한다.

v1 원칙:

- Drive 원본은 외부 원천으로 남긴다.
- haro는 선택 파일을 사용자 Playground로 가져온다.
- Clean Room 반영은 별도 승격 흐름으로 처리한다.
- Drive 원본 수정과 양방향 동기화는 v1 범위에서 제외한다.

```text
Google Drive
  -> 데이터소스 연결
  -> 선택 파일 snapshot import
  -> playground/users/{user_id}/00_inbox
  -> 검토/정리
  -> Clean Room 승격 요청
```

## 2. 연결 모델

Google Drive 연결은 프로젝트의 `데이터소스` 탭에서 관리한다.

지원 대상:

- 개인 Google Drive 폴더
- Shared Drive 폴더
- 사용자가 선택한 파일 묶음

v1에서는 전체 Drive를 자동 스캔하지 않는다.
사용자가 명시적으로 연결한 폴더나 선택한 파일만 haro에 노출한다.

연결 상태:

| 상태 | 의미 |
| --- | --- |
| `connected` | OAuth 연결과 폴더 접근이 정상 |
| `needs_reauth` | 토큰 만료 또는 권한 변경 |
| `permission_lost` | Drive 폴더 접근 권한 상실 |
| `refreshing` | 파일 목록 갱신 중 |
| `error` | 연결 오류 |

## 3. 가져오기 위치

Drive에서 가져온 파일의 기본 위치는 사용자별 Playground inbox다.

```text
playground/users/{user_id}/00_inbox/google-drive/{connection_name}/
```

예:

```text
playground/users/jiyoon/00_inbox/google-drive/a-client-drive/media-report.xlsx
playground/users/jiyoon/00_inbox/google-drive/a-client-drive/brief.md
```

가져온 파일은 기본적으로 `editable`이다.
팀 공식 자료로 쓰려면 Data Clean Room 승격 요청을 거쳐야 한다.

## 4. 원본 메타데이터

haro는 가져온 파일에 Drive 원본 정보를 남긴다.

권장 저장 위치:

```text
.haro/datasources/google-drive/connections.json
.haro/datasources/google-drive/imports.jsonl
```

import 기록 예:

```json
{
  "provider": "google_drive",
  "connection_id": "gd-a-client",
  "connection_name": "A광고주 Drive",
  "drive_file_id": "1abc...",
  "web_url": "https://drive.google.com/file/d/1abc/view",
  "name": "media-report.xlsx",
  "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "modified_time": "2026-04-29T10:00:00+09:00",
  "checksum_or_etag": "etag-123",
  "imported_at": "2026-04-29T10:05:00+09:00",
  "imported_by": "jiyoon",
  "imported_to": "/playground/users/jiyoon/00_inbox/google-drive/a-client-drive/media-report.xlsx"
}
```

이 메타데이터는 다음에 사용한다.

- 원본 출처 추적
- 재가져오기 시 변경 여부 확인
- 산출물의 근거 파일 표시
- Clean Room 승격 시 출처 기록

## 5. Google Native 파일 변환

Google native 파일은 haro 파일로 가져올 때 변환한다.

| Drive 유형 | v1 가져오기 형식 |
| --- | --- |
| Google Sheets | `.xlsx` 또는 `.csv` |
| Google Docs | `.docx` 또는 `.md` |
| Google Slides | `.pptx` 또는 `.pdf` |
| 일반 파일 | 원본 확장자 유지 |

Sheets는 사용자가 선택하면 시트별 CSV로 펼칠 수 있다.
이때 기존 Excel 업로드와 같은 원본/변환본 관계를 사용한다.

## 6. Clean Room 반영 흐름

Drive에서 가져온 파일은 Clean Room에 직접 쓰지 않는다.

```text
Drive 파일 import
  -> User Playground inbox
  -> haro가 파일 종류와 출처 추정
  -> 사용자가 검토/정리
  -> Data Clean Room 반영 요청
  -> data-clean-room feature branch 생성
  -> 검증
  -> 승인 후 merge
```

승격 요청에는 Drive 원본 메타데이터를 함께 포함한다.

```json
{
  "source_provider": "google_drive",
  "source_drive_file_id": "1abc...",
  "source_web_url": "https://drive.google.com/file/d/1abc/view",
  "playground_path": "/playground/users/jiyoon/00_inbox/google-drive/a-client-drive/media-report.xlsx",
  "target_path": "/clean-room/data/10_sources/media-reports/a-client/media-report.xlsx"
}
```

## 7. 변경 감지와 충돌

v1은 수동 새로고침과 주기 polling을 기본으로 한다.
Drive webhook은 후속 단계에서 검토한다.

파일 목록 새로고침 시 haro는 다음을 표시한다.

- 새 파일
- 삭제된 파일
- Drive에서 수정된 파일
- 이미 가져온 파일과 원본이 달라진 파일

충돌 정책:

- Drive 원본이 바뀌어도 haro 파일을 자동 덮어쓰지 않는다.
- 사용자가 “다시 가져오기”를 선택하면 새 snapshot을 만든다.
- 기존 haro 파일에 로컬 수정이 있으면 새 버전 또는 별도 파일로 가져온다.

## 8. Trigger 연동

Google Drive 연결은 workflow trigger가 될 수 있다.

Trigger 초안:

```json
{
  "type": "google_drive_folder_changed",
  "datasource_id": "gd-a-client",
  "folder_id": "drive-folder-id",
  "event": "file_added",
  "extensions": [".xlsx", ".csv"]
}
```

v1에서는 즉시 webhook보다 polling 기반 감지를 우선한다.
새 파일이 감지되면 haro는 자동 실행 전에 사용자의 확인을 요청할 수 있다.

## 9. Project Fork와 보안

Project Fork는 Drive 연결의 실제 인증 정보를 복제하지 않는다.

fork 제외 대상:

- OAuth access token
- refresh token
- 실제 Drive file id
- 실제 연결 폴더 id
- 가져온 원본 파일
- 고객/개인/계약/성과 데이터

선택적으로 포함 가능한 것:

- “이 template은 Drive에서 주간 리포트 폴더를 연결한다”는 connector template
- 필요한 파일 종류와 폴더 이름 가이드
- 가져오기 후 정리 규칙

fork된 프로젝트는 새 Google Drive 연결을 다시 만들어야 한다.

## 10. API 초안

```http
POST /api/projects/{project_id}/datasources/google-drive/connect
GET  /api/projects/{project_id}/datasources
POST /api/projects/{project_id}/datasources/{datasource_id}/refresh
POST /api/projects/{project_id}/datasources/{datasource_id}/import
```

`import` 요청 예:

```json
{
  "files": [
    {
      "drive_file_id": "1abc...",
      "export_as": "xlsx"
    }
  ],
  "target_dir": "/playground/users/jiyoon/00_inbox/google-drive/a-client-drive"
}
```

## 11. UI 초안

왼쪽 `데이터소스` 탭:

- Google Drive 연결 목록
- 연결 상태
- 마지막 새로고침 시각
- Drive 폴더/파일 목록
- 검색
- 선택 가져오기
- 다시 가져오기
- 원본 열기

파일 뷰어 메타 패널:

- 원본: Google Drive
- Drive 파일명
- 마지막 import 시각
- Drive 원본 수정 여부
- Clean Room 승격 상태

## 12. 성공 기준

- 사용자가 Google Drive 폴더를 프로젝트 데이터소스로 연결할 수 있다.
- 연결된 Drive 파일 목록을 `데이터소스` 탭에서 볼 수 있다.
- 선택 파일을 사용자 Playground inbox로 가져올 수 있다.
- Google Sheets를 `.xlsx` 또는 `.csv`로 가져올 수 있다.
- 가져온 파일의 Drive 원본 메타데이터가 남는다.
- Clean Room에는 직접 쓰지 않고 승격 요청을 통해서만 반영된다.
- Project Fork 시 Drive token, 실제 file id, 실제 데이터가 복제되지 않는다.
