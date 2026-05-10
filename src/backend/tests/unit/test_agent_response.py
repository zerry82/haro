from types import SimpleNamespace

from app.services.agent_response import (
    blocked_tool_message,
    blocked_tool_result,
    compact_text,
    executor_routing_context,
    extract_text_without_tool_call,
    parse_tool_call,
    parse_tool_call_result,
    routing_context_instruction,
)


def test_parse_tool_call_reads_json_block() -> None:
    text = """작업을 시작합니다.

```tool_call
{"tool": "file_read", "args": {"path": "/docs/guide.md"}}
```
"""

    assert parse_tool_call(text) == {
        "tool": "file_read",
        "args": {"path": "/docs/guide.md"},
    }


def test_parse_tool_call_returns_none_for_invalid_json() -> None:
    text = """```tool_call
{"tool": "file_read", "args": }
```"""

    assert parse_tool_call(text) is None


def test_parse_tool_call_result_detects_missing_block() -> None:
    result = parse_tool_call_result("일반 답변입니다.")

    assert result.has_block is False
    assert result.tool_call is None
    assert result.error is None
    assert result.raw_block is None


def test_parse_tool_call_result_reads_json_block() -> None:
    text = """```tool_call
{"tool": "file_read", "args": {"path": "/docs/guide.md"}}
```"""

    result = parse_tool_call_result(text)

    assert result.has_block is True
    assert result.tool_call == {"tool": "file_read", "args": {"path": "/docs/guide.md"}}
    assert result.error is None
    assert result.raw_block is not None


def test_parse_tool_call_result_reports_invalid_json_block() -> None:
    text = r"""```tool_call
{"tool": "file_write", "args": {"content": ".card {\ padding: 1rem; }"}}
```"""

    result = parse_tool_call_result(text)

    assert result.has_block is True
    assert result.tool_call is None
    assert result.error is not None
    assert "line" in result.error
    assert "column" in result.error
    assert result.raw_block is not None


def test_parse_tool_call_result_rejects_non_object_json() -> None:
    result = parse_tool_call_result("""```tool_call
["file_read"]
```""")

    assert result.has_block is True
    assert result.tool_call is None
    assert result.error == "tool_call JSON must be an object"


def test_extract_text_without_tool_call_removes_tool_block() -> None:
    text = """먼저 확인하겠습니다.

```tool_call
{"tool": "dir_list", "args": {"path": "/"}}
```

결과를 기다립니다.
"""

    assert extract_text_without_tool_call(text) == "먼저 확인하겠습니다.\n\n\n\n결과를 기다립니다."


def test_blocked_tool_result_lists_selected_tools() -> None:
    result = blocked_tool_result("file_delete", ["file_read", "dir_list"])

    assert "file_delete" in result
    assert "file_read, dir_list" in result


def test_blocked_tool_message_describes_file_write_risk() -> None:
    message = blocked_tool_message("file_write", ["file_read"])

    assert "`file_write`" in message
    assert "파일 또는 폴더 변경" in message
    assert "`file_read`" in message
    assert "실제로 수행된 변경은 없습니다" in message


def test_blocked_tool_message_describes_partial_edit_as_file_change() -> None:
    message = blocked_tool_message("file_edit", ["file_read", "file_stats"])

    assert "`file_edit`" in message
    assert "파일 또는 폴더 변경" in message
    assert "`file_stats`" in message


def test_compact_text_collapses_whitespace_and_truncates() -> None:
    assert compact_text("  alpha\n beta   gamma  ", 20) == "alpha beta gamma"
    assert compact_text("abcdef", 3) == "abc..."


def test_executor_routing_context_keeps_only_executor_fields() -> None:
    context = executor_routing_context({
        "current_user_message": "파일 읽어줘",
        "routing_text": "파일 읽어줘",
        "unused": "ignored",
        "gate_context": {
            "decision": "new_task",
            "reason": "x" * 500,
            "confidence": 0.9,
            "unused": "ignored",
        },
        "latest_artifact": {},
        "latest_preview": None,
    })

    assert context["current_user_message"] == "파일 읽어줘"
    assert context["gate_context"]["decision"] == "new_task"
    assert context["gate_context"]["confidence"] == 0.9
    assert context["gate_context"]["reason"].endswith("...")
    assert "unused" not in context
    assert "latest_artifact" not in context


def test_routing_context_instruction_embeds_compact_json() -> None:
    route = SimpleNamespace(routing_context={
        "current_user_message": "목록 보여줘",
        "gate_context": {"decision": "new_task"},
    })

    instruction = routing_context_instruction(route)

    assert "[현재 턴 라우팅 맥락]" in instruction
    assert '"current_user_message": "목록 보여줘"' in instruction
    assert '"decision": "new_task"' in instruction


def test_routing_context_instruction_is_empty_without_context() -> None:
    route = SimpleNamespace(routing_context={})

    assert routing_context_instruction(route) == ""
