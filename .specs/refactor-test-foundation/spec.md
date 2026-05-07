# Refactor Test Foundation Spec

작성일: 2026-05-07

## 문제

현재 `src` 구현은 기능이 빠르게 누적되면서 일부 파일에 책임이 과도하게 몰려 있다. 특히 프론트엔드의 `ProjectWorkspace.svelte`와 백엔드의 `agent.py`, `workspace_file_db.py`, `intent_turns.py`는 파일 길이와 함수 크기가 커서 변경 영향 범위를 판단하기 어렵다.

테스트 파일과 테스트 실행 명령도 아직 명확하지 않다. 리팩토링을 바로 시작하면 기존 동작을 보존했는지 확인하기 어렵고, 에이전트 실행, 워크스페이스 인덱스, 파일 API 같은 핵심 흐름에서 회귀가 생길 위험이 있다.

## 목표

- 장황한 구조 중 먼저 분리해도 동작 위험이 낮은 순수 로직을 식별한다.
- 백엔드 단위 테스트 기반을 추가한다.
- 에이전트 도구 호출 파싱, 라우팅 보조 로직, 워크스페이스 파일 인덱스 같은 핵심 순수 로직부터 테스트한다.
- 리팩토링은 테스트 가능한 작은 단위로 진행한다.
- 프론트엔드 대형 컴포넌트 분리는 별도 단계로 남겨, 첫 패치의 위험을 낮춘다.

## 비목표

- 전체 아키텍처를 한 번에 재설계하지 않는다.
- `ProjectWorkspace.svelte`를 첫 패치에서 대규모로 분해하지 않는다.
- API 계약, SSE 이벤트 이름, DB 스키마, 워크스페이스 정책을 변경하지 않는다.
- Gemini 호출이나 Docker 샌드박스 실행을 실제 네트워크/컨테이너 의존 테스트로 만들지 않는다.
- 레거시 `Session`, `Todo`, `Chat.svelte` 제거는 이 스펙의 범위가 아니다.

## 현재 관찰

- 테스트 파일 검색 결과, 현재 저장소에는 명확한 백엔드/프론트엔드 테스트 파일이 없다.
- 가장 큰 구현 파일:
  - `src/frontend/src/routes/ProjectWorkspace.svelte`: 약 2123줄
  - `src/backend/app/services/workspace_file_db.py`: 약 877줄
  - `src/backend/app/services/intent_turns.py`: 약 616줄
  - `src/backend/app/services/agent.py`: 약 598줄
- 가장 큰 백엔드 함수:
  - `agent.py::run_agent`: 약 474줄
  - `main.py::_migrate_sessions_to_projects`: 약 182줄
  - `agent_tools.py::execute_tool`: 약 176줄
  - `intent_turns.py::_rule_route`: 약 121줄

## 권장 1차 범위

1차 패치는 백엔드 테스트 기반과 낮은 위험의 순수 함수 테스트에 집중한다.

- `pytest`와 필요한 테스트 설정 추가
- `tests/unit/` 구조 추가
- `agent.py`의 순수 함수 테스트
  - `parse_tool_call`
  - `extract_text_without_tool_call`
  - `_blocked_tool_result`
  - `_blocked_tool_message`
  - `_compact_text`
- `workspace_file_db.py`의 경로/검색 보조 함수 또는 임시 워크스페이스 기반 인덱스 테스트
- 코드 변경은 테스트 가능성을 높이는 범위에서만 작게 추출

## 성공 기준

- 로컬에서 백엔드 단위 테스트를 실행할 수 있다.
- 첫 테스트 묶음이 외부 LLM, Docker, 네트워크, 실제 사용자 워크스페이스 데이터에 의존하지 않는다.
- 기존 서버 실행 명령과 주요 API 계약은 바뀌지 않는다.
- 리팩토링 후 `parse_tool_call` 같은 기존 동작은 테스트로 고정된다.
- 후속 단계에서 `run_agent`, `workspace_file_db`, `ProjectWorkspace.svelte`를 더 안전하게 나눌 수 있는 기준이 생긴다.

## 전략 검증 루프

질문: 이 전략에 100% 확신이 있나요?

초기 답: 아직 아니다. 가능한 허점은 다음과 같다.

- 허점: 프론트엔드가 가장 큰 파일인데 1차 범위에서 제외하면 사용자가 기대한 "장황한 구조" 개선이 부족해 보일 수 있다.
  - 수정: 1차 패치는 테스트 기반을 먼저 만들고, `ProjectWorkspace.svelte` 분리는 후속 스펙 또는 2차 단계로 명시한다.
- 허점: `agent.py::run_agent`가 가장 큰 핵심 함수지만 바로 쪼개면 SSE/DB side effect가 섞여 회귀 위험이 크다.
  - 수정: 먼저 주변 순수 함수와 도구 호출 파싱 규칙을 테스트로 고정한 뒤, 실행 루프 분리는 별도 커밋으로 진행한다.
- 허점: 테스트 의존성을 추가하면 개발 환경이 바뀐다.
  - 수정: 백엔드 가상환경 안에서만 설치하도록 `requirements-dev.txt` 또는 명시 문서로 관리하고, 운영 의존성에는 최소 영향만 준다.
- 허점: 실제 워크스페이스 데이터로 테스트하면 사용자 데이터 손상 위험이 있다.
  - 수정: `tmp_path` 기반 임시 워크스페이스만 사용하고, `src/backend/data`에는 접근하지 않는다.
- 허점: private helper 테스트가 리팩토링을 경직시킬 수 있다.
  - 수정: 공개 API 성격이 있는 순수 함수부터 테스트하고, private helper는 동작 계약이 중요한 경우에만 최소 테스트한다.

수정 후 전략: 1차 패치는 테스트 기반과 순수 로직 동작 고정에 한정한다. 실제 에이전트 오케스트레이션이나 프론트 대형 컴포넌트 분해는 테스트 기반이 생긴 뒤 별도 작은 패치로 진행한다.

사실상 확신 수준: 높음. 이 전략은 회귀 위험이 낮고, 이후 리팩토링의 안전망을 먼저 만든다.
