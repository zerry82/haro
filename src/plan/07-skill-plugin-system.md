# 스킬/플러그인 시스템 현재 구현

## 1. 현재 범위

현재 PoC에는 완전한 MCP 스킬 실행 시스템이 없다.
구현되어 있는 것은 **스킬 목록 조회용 레지스트리**와 `file_ops` seed 데이터다.

실제 도구 실행은 `backend/app/services/agent.py`의 `execute_tool(...)` 함수가 직접 처리한다.

## 2. 현재 데이터 모델

테이블: `installed_skills`

| 컬럼 | 설명 |
|------|------|
| `name` | 스킬 이름 |
| `version` | 버전 |
| `type` | `builtin` 등 |
| `description` | 설명 |
| `status` | `enabled` 등 |
| `manifest` | JSON 문자열 |
| `config` | JSON 문자열, 현재 미사용 |

앱 시작 시 `main.py`의 `_seed_builtin_skills()`가 `file_ops`를 넣는다.

```json
{
  "tools": [
    "file_create",
    "file_read",
    "file_write",
    "file_delete",
    "dir_list",
    "dir_create"
  ]
}
```

## 3. 현재 API

### GET `/api/skills`

설치된 스킬 목록을 읽기 전용으로 반환한다.

```json
{
  "skills": [
    {
      "name": "file_ops",
      "version": "1.0.0",
      "type": "builtin",
      "status": "enabled",
      "description": "파일 시스템 도구 — 파일/디렉토리 생성, 읽기, 수정, 삭제",
      "tools": [
        "file_create",
        "file_read",
        "file_write",
        "file_delete",
        "dir_list",
        "dir_create"
      ]
    }
  ]
}
```

현재 구현되지 않은 API:

- `POST /api/skills/install`
- `DELETE /api/skills/{skill_name}`
- `PATCH /api/skills/{skill_name}`

## 4. 현재 에이전트 도구와 스킬 목록의 관계

`GET /api/skills`는 UI/확인용 목록이다.
에이전트가 이 목록을 읽어서 도구를 발견하거나 호출하지 않는다.

현재 에이전트가 실제로 사용할 수 있는 도구:

| 도구 | 구현 위치 |
|------|-----------|
| `file_create` | `agent.py` |
| `file_read` | `agent.py` |
| `file_write` | `agent.py` |
| `file_delete` | `agent.py` |
| `dir_list` | `agent.py` |
| `dir_create` | `agent.py` |
| `code_run` | `agent.py` + `container_manager.py` |
| `web_preview` | `agent.py` + `container_manager.py` |

스킬 목록의 manifest에는 아직 `code_run`, `web_preview`가 포함되어 있지 않다.

## 5. MCP/FastMCP의 현재 상태

`requirements.txt`에는 `fastmcp`가 남아 있지만, 현재 코드 경로에서는 MCP 서버나 MCP 클라이언트를 사용하지 않는다.
초기 설계에서 목표로 했던 구조는 향후 확장 방향이다.

## 6. 향후 MCP 확장 방향

Phase 2에서 MCP를 붙인다면 목표 구조는 다음과 같다.

```
에이전트
  ↓
SkillManager
  ├─ builtin file_ops MCP server
  ├─ code/sandbox MCP server
  └─ installed external MCP servers
```

필요한 변경:

1. `InstalledSkill.manifest`를 실제 MCP 실행 정보로 확장
2. 앱 시작 시 enabled 스킬의 MCP 서버 연결
3. `tools/list` 결과를 LLM tool schema나 현재 `TOOL_DESCRIPTIONS`에 반영
4. `execute_tool(...)` 직접 분기 대신 `SkillManager.call_tool(...)` 사용
5. 스킬 설치/삭제/활성화 API 추가

## 7. 현재 구현 기준 체크리스트

| 항목 | 상태 |
|------|------|
| `InstalledSkill` 모델 | 구현됨 |
| `file_ops` seed | 구현됨 |
| `GET /api/skills` | 구현됨 |
| MCP 서버 실행 | 미구현 |
| MCP 클라이언트 연결 | 미구현 |
| 외부 스킬 설치 | 미구현 |
| 에이전트의 스킬 레지스트리 기반 도구 발견 | 미구현 |
