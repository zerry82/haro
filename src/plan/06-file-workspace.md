# 파일 작업 공간 현재 구현

## 1. 워크스페이스 구조

현재 파일 작업 공간은 채팅 세션이 아니라 프로젝트에 속한다.

```
{WORKSPACE_ROOT}/
└── {user_id}/
    └── {project_id}/
        ├── .openclaw/
        │   ├── workspace.md
        │   └── file_summaries/
        │       └── README.md.md
        ├── README.md
        └── src/
            └── main.ts
```

기본값:

| 설정 | 기본값 |
|------|--------|
| `WORKSPACE_ROOT` | `./data/workspaces` |
| 물리 경로 | `./data/workspaces/{user_id}/{project_id}` |
| API 경로 | 프로젝트 루트 기준 `/README.md`, `/src/main.ts` |

## 2. 생성과 삭제

프로젝트 생성 시:

1. `{workspace_root}/{user_id}/{project_id}` 생성
2. `.openclaw/file_summaries` 생성
3. `Project.workspace_path`에 물리 경로 저장
4. 가능한 경우 Docker 컨테이너 생성 후 이 경로를 `/workspace`로 마운트

프로젝트 삭제 시:

1. 연결된 Docker 컨테이너 제거 시도
2. 메시지/로그/채팅 삭제
3. 워크스페이스 디렉토리를 `shutil.rmtree`로 삭제
4. 프로젝트 레코드 삭제

## 3. 경로 검증

파일 API와 에이전트 도구는 요청 경로를 워크스페이스 내부 물리 경로로 변환한다.

```python
full = os.path.realpath(os.path.join(workspace, requested.lstrip("/")))
if not full.startswith(os.path.realpath(workspace)):
    raise PermissionError("워크스페이스 외부 접근 불가")
```

현재 코드는 `startswith` 방식이다.
운영 품질로 올릴 때는 `os.path.commonpath` 기반 검증이 더 안전하다.

## 4. 파일 API 동작

### 디렉토리 목록

`GET /api/projects/{project_id}/files?path=/`

- `os.scandir`로 한 단계만 조회
- 디렉토리는 `children_count` 포함
- 파일은 `size` 포함
- `.openclaw`로 시작하는 항목은 숨김
- 디렉토리 먼저, 그다음 파일을 이름순 정렬

### 파일 내용

`GET /api/projects/{project_id}/files/content?path=/README.md`

- UTF-8로 읽고, 오류 문자는 replacement 처리
- 확장자로 `language` 값을 추론

현재 언어 매핑:

| 확장자 | language |
|--------|----------|
| `.py` | `python` |
| `.js` | `javascript` |
| `.ts` | `typescript` |
| `.html` | `html` |
| `.css` | `css` |
| `.json` | `json` |
| `.md` | `markdown` |
| `.yaml`, `.yml` | `yaml` |
| `.txt` | `plaintext` |
| `.svg` | `xml` |
| 기타 | `plaintext` |

## 5. 에이전트 파일 도구

현재 구현 위치: `backend/app/services/agent.py`

| 도구 | 현재 동작 |
|------|-----------|
| `file_create` | 부모 디렉토리를 만들고 파일을 새 내용으로 씀. 이미 있어도 덮어씀 |
| `file_read` | 파일 내용을 문자열로 반환 |
| `file_write` | 파일을 새 내용으로 덮어씀 |
| `file_delete` | 파일 삭제 |
| `dir_list` | 디렉토리의 한 단계 목록을 텍스트로 반환 |
| `dir_create` | 디렉토리 생성 |

파일 생성/수정/삭제와 디렉토리 생성은 `file_changed` SSE 이벤트를 발행한다.
파일 생성/수정/삭제는 `.openclaw` 워크스페이스 인덱스도 갱신한다.

## 6. 워크스페이스 인덱스

현재 구현 위치: `backend/app/services/workspace_index.py`

파일 변경 시:

```
file_create / file_write / file_delete
    ↓
update_file_summary(workspace, path, action)
    ↓
.openclaw/file_summaries/{path}.md 갱신 또는 삭제
    ↓
rebuild_workspace_index(workspace)
    ↓
.openclaw/workspace.md 재생성
```

현재 파일 요약은 LLM을 쓰지 않고 간단히 생성한다.

```text
- {line_count}줄, 첫 줄: `{first_line}`
```

`workspace.md` 형식:

````markdown
# 워크스페이스 인덱스

## 파일 트리
```
├── README.md  [120B]
└── src/
    └── main.ts  [80B]
```

## 파일별 요약

### /README.md
- 3줄, 첫 줄: `# Title`
````

## 7. Docker 샌드박스와 워크스페이스

프로젝트 샌드박스 컨테이너 생성 시 워크스페이스를 `/workspace`에 read-write로 마운트한다.

```python
volumes={
    os.path.abspath(workspace_path): {
        "bind": "/workspace",
        "mode": "rw",
    }
}
```

`code_run`은 전달받은 코드를 워크스페이스 파일로 저장한 뒤 컨테이너에서 실행한다.

실행 명령:

| 파일 확장자 | 명령 |
|-------------|------|
| `.ts`, `.js` | `deno run --allow-all /workspace/{filename}` |
| `.py` | `python3 /workspace/{filename}` |
| 기타 | `cat /workspace/{filename}` |

## 8. 현재 제한 사항

- 사용자 직접 파일 편집 API는 없다.
- 파일 크기/파일 수 제한은 문서상 정책으로만 존재하고 코드에는 명시적 검사가 없다.
- 바이너리 파일 미리보기는 구현되어 있지 않다.
- 파일 변경 감지는 watchdog이 아니라 에이전트 도구 실행 시 직접 이벤트를 보내는 방식이다.
