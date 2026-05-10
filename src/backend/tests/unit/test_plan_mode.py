from types import SimpleNamespace

from app.services.plan_mode import (
    PLAN_ALLOWED_TOOLS,
    REQUIREMENTS_CLARIFYING,
    build_execution_instruction,
    build_plan_mode_instruction,
    can_write_path_in_plan_mode,
    default_plan_file_path,
    is_plan_allowed_tool,
    is_evidence_required_plan,
    should_enter_plan_mode_for_text,
    validate_plan_for_approval,
)


def test_should_enter_plan_mode_for_explicit_plan_request() -> None:
    should_plan, reason = should_enter_plan_mode_for_text("먼저 스펙과 계획을 세워줘")

    assert should_plan is True
    assert reason


def test_should_not_enter_plan_mode_for_implementation_request() -> None:
    should_plan, reason = should_enter_plan_mode_for_text("PLEASE IMPLEMENT THIS PLAN: 파일 수정")

    assert should_plan is False
    assert reason is None


def test_plan_mode_tool_allowlist_blocks_execution_tools() -> None:
    assert is_plan_allowed_tool("file_read") is True
    assert is_plan_allowed_tool("file_stats") is True
    assert is_plan_allowed_tool("file_search_content") is True
    assert is_plan_allowed_tool("file_read_range") is True
    assert is_plan_allowed_tool("plan_file_update") is True
    assert is_plan_allowed_tool("file_edit") is False
    assert is_plan_allowed_tool("file_write") is False
    assert "web_preview" not in PLAN_ALLOWED_TOOLS


def test_plan_mode_write_path_is_limited_to_plan_tools() -> None:
    plan_session = SimpleNamespace(plan_file_path="/chat/working/plan.md")

    assert can_write_path_in_plan_mode(plan_session, "plan_file_update", "/other.md") is True
    assert can_write_path_in_plan_mode(plan_session, "plan_approval_request", None) is True
    assert can_write_path_in_plan_mode(plan_session, "file_stats", "/chat/outputs/result.md") is True
    assert can_write_path_in_plan_mode(plan_session, "file_edit", "/chat/outputs/result.md") is False
    assert can_write_path_in_plan_mode(plan_session, "file_write", "/chat/outputs/result.md") is False


def test_default_plan_file_path_uses_chat_working_folder() -> None:
    chat_session = SimpleNamespace(folder_path="/50_chats/chat-1")

    assert default_plan_file_path(chat_session) == "/50_chats/chat-1/working/plan.md"


def test_plan_mode_instruction_blocks_silent_web_search_fallback() -> None:
    plan_session = SimpleNamespace(plan_file_path="/chat/working/plan.md")

    instruction = build_plan_mode_instruction(plan_session)

    assert "web_search가 실패하거나 사용할 수 없으면" in instruction
    assert "내부 지식 기반 계획으로 조용히 대체하지 말고" in instruction


def test_plan_mode_instruction_requires_requirements_template() -> None:
    plan_session = SimpleNamespace(plan_file_path="/chat/working/plan.md")

    instruction = build_plan_mode_instruction(plan_session)

    assert "요구사항 명확화 -> 근거 수집 -> 계획 승인" in instruction
    assert "Requirements, Open Questions, Evidence Ledger, Execution Plan, Acceptance Checks" in instruction


def test_approved_plan_execution_instruction_bans_code_run_file_mutation() -> None:
    instruction = build_execution_instruction("# Plan\n\n폴더를 정리한다.")

    assert "code_run으로 워크스페이스 파일을 직접 조작하지 마세요" in instruction


def test_requirements_clarifying_is_current_plan_status() -> None:
    assert REQUIREMENTS_CLARIFYING == "requirements_clarifying"


def test_validate_plan_blocks_missing_requirements_sections() -> None:
    plan_session = SimpleNamespace(plan_title="보고서 작성", plan_file_path="/chat/working/plan.md")

    result = validate_plan_for_approval(plan_session, "# Plan\n\n바로 실행")

    assert result.ok is False
    assert "요구사항 명확화 섹션이 부족" in (result.reason or "")


def test_validate_research_plan_requires_successful_web_search_evidence() -> None:
    plan_session = SimpleNamespace(plan_title="최신 투자 리서치 보고서", plan_file_path="/chat/working/plan.md")
    plan = """# 투자 리서치 계획

## Requirements
- 2026년 기준 투자 리서치 보고서를 작성한다.

## Open Questions
없음

## Evidence Ledger
- 기준일: 2026-05-10
- 출처: https://example.com/source
- 핵심 수치: 매출 데이터

## Execution Plan
- 근거 기반 보고서를 작성한다.

## Acceptance Checks
- 모든 수치에 출처가 있다.
"""

    result = validate_plan_for_approval(plan_session, plan, has_successful_evidence=False)

    assert result.ok is False
    assert "성공한 web_search 근거" in (result.reason or "")
    assert is_evidence_required_plan(plan_session, plan) is True


def test_folder_organization_plan_does_not_require_web_search_evidence() -> None:
    plan_session = SimpleNamespace(plan_title="30_outputs 폴더 정리", plan_file_path="/chat/working/plan.md")
    plan = """# 폴더 정리 계획

## Requirements
- 내 폴더/결과(30_outputs)의 13개 폴더를 01_리서치_및_분석, 02_대시보드, 03_문서_및_자료로 분류한다.

## Open Questions
없음

## Evidence Ledger
해당 없음: 외부 자료 조사가 아닌 로컬 폴더 구조 정리 작업이다.

## Execution Plan
- dir_create로 대분류 폴더를 만든다.
- file_move로 기존 폴더 내용을 이동한다.
- dir_delete로 빈 폴더를 삭제한다.

## Acceptance Checks
- 30_outputs 루트에는 승인된 대분류 폴더만 남는다.
"""

    result = validate_plan_for_approval(plan_session, plan, has_successful_evidence=False)

    assert result.ok is True
    assert is_evidence_required_plan(plan_session, plan) is False


def test_validate_research_plan_accepts_evidence_ledger_and_web_search() -> None:
    plan_session = SimpleNamespace(plan_title="최신 투자 리서치 보고서", plan_file_path="/chat/working/plan.md")
    plan = """# 투자 리서치 계획

## Requirements
- 2026년 기준 투자 리서치 보고서를 작성한다.

## Open Questions
없음

## Evidence Ledger
- 기준일: 2026-05-10
- 출처: https://example.com/source
- 핵심 수치: 매출 데이터

## Execution Plan
- 근거 기반 보고서를 작성한다.

## Acceptance Checks
- 모든 수치에 출처가 있다.
"""

    result = validate_plan_for_approval(plan_session, plan, has_successful_evidence=True)

    assert result.ok is True
