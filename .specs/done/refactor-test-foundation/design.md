# Refactor Test Foundation Design

작성일: 2026-05-07

## 설계 방향

리팩토링은 "동작을 바꾸지 않는 작은 추출"과 "단위 테스트로 기존 계약 고정"을 한 쌍으로 진행한다. 첫 단계에서는 외부 시스템 의존성이 적고 실패 원인이 분명한 백엔드 순수 로직을 우선한다.

구현 과정에서 백엔드 안전망이 먼저 확보되어, 같은 스펙 안에서 프론트엔드 순수 helper 테스트와 `ProjectWorkspace.svelte`의 낮은 위험 컴포넌트 분리까지 범위를 확장했다.

## 테스트 구조

권장 구조:

```text
src/backend/
  requirements-dev.txt
  pytest.ini
  tests/
    unit/
      test_agent_response.py
      test_agent_tool_loop.py
      test_workspace_file_db.py
      test_workspace_file_helpers.py
src/frontend/
  src/
    lib/
      workspaceUtils.ts
      workspaceUtils.test.ts
```

대안:

- 루트 `tests/backend/`에 둘 수 있지만, 백엔드 가상환경과 import 경로가 `src/backend`에 묶여 있으므로 첫 단계에서는 `src/backend/tests`가 단순하다.
- 프론트엔드 테스트는 `vitest`를 도입하되, DOM 없는 순수 utility 테스트부터 시작한다.

## 백엔드 테스트 실행

권장 명령:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

`pytest.ini`에는 `pythonpath = .`를 두어 `app.*` import를 단순화한다.

## 리팩토링 후보

### 1차 후보: `agent.py`

현재 `run_agent`가 메시지 저장, intent gate, 라우팅, LLM 스트리밍, tool call 파싱, 도구 실행, 로그 저장, SSE emit을 한 함수에서 처리한다.

첫 패치에서는 `run_agent` 본문을 크게 분해하지 않고, 이미 분리된 순수 함수의 테스트를 먼저 만든다.

테스트 대상:

- tool call fenced block 파싱
- tool call 제거 후 사용자 표시 텍스트 추출
- 선택되지 않은 도구 차단 메시지
- 라우팅 컨텍스트 compact 처리

후속 분리 후보:

- 사용자 메시지 저장과 `user_message_saved` emit
- gate 결과 처리
- clarification/casual response 처리
- LLM round 실행
- tool call 검증과 실행
- 완료/오류 처리

### 1차 후보: `workspace_file_db.py`

워크스페이스 인덱스는 파일 시스템과 SQLite를 함께 다룬다. 따라서 순수 경로 함수와 `tmp_path` 기반 통합에 가까운 단위 테스트를 섞는다.

테스트 대상:

- `_parent_path`
- `_workspace_path_from_full`
- `_full_path`
- `_classify_path`
- `list_workspace_directory_page`
- `search_workspace_files`
- `count_workspace_items`

주의:

- 실제 `src/backend/data/workspaces`를 읽거나 쓰지 않는다.
- 테스트 중 생성되는 `.haro/db/workspace.db`는 `tmp_path` 내부에만 만든다.
- `.haro` 메타 경로는 사용자 파일 목록에서 제외되는지 확인한다.

## API/SSE 영향

1차 패치는 API 계약과 SSE 이벤트 계약을 바꾸지 않는다. 테스트 추가와 작은 함수 추출만 허용한다.

## 데이터 모델 영향

DB 모델과 마이그레이션은 변경하지 않는다.

## UI 영향

UI 동작과 API 계약은 바꾸지 않는다. `ProjectWorkspace.svelte` 분해는 다음처럼 낮은 위험 단위부터 진행한다.

- 순수 helper는 `workspaceUtils.ts`로 분리한다.
- debug trace 모달은 `DebugTraceModal.svelte`로 분리한다.
- 파일 viewer/editor 패널은 `FileViewerPanel.svelte`로 분리한다.
- 파일 탐색기와 채팅 패널은 상호작용 상태가 더 넓으므로 후속 개선 후보로 남긴다.

## 대안과 결정

- 대안: 가장 큰 `ProjectWorkspace.svelte`부터 분해한다.
  - 보류 이유: 현재 프론트 테스트 기반이 없고, 파일 탐색기/채팅/뷰어/디버그/배포 UI가 강하게 결합되어 있어 회귀 확인이 어렵다.
- 대안: `run_agent`를 바로 여러 서비스로 나눈다.
  - 보류 이유: DB commit, SSE, LLM streaming, tool execution이 섞여 있어 테스트 없이 분리하면 동작 보존을 확인하기 어렵다.
- 결정: 테스트 기반을 먼저 만들고, 순수 함수와 임시 워크스페이스 기반 테스트로 핵심 동작을 고정한다.
- 결정: 백엔드 테스트가 안정화된 뒤, 프론트엔드는 순수 helper와 독립 UI 패널부터 분리한다.
