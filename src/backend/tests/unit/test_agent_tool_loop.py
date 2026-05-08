import asyncio
from types import SimpleNamespace

import app.services.agent_tool_loop as tool_loop
from app.services.agent_tool_loop import build_model_contents


class FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        pass


class FakeEmitter:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event: str, data) -> None:
        self.events.append((event, data))


def _project() -> SimpleNamespace:
    return SimpleNamespace(id="project-1", user_id="user-1", workspace_path="workspace")


def _chat_session() -> SimpleNamespace:
    return SimpleNamespace(id="chat-1", folder_path="/chat")


def _route() -> SimpleNamespace:
    return SimpleNamespace(routing_context={})


def _invalid_tool_call_text() -> str:
    return r"""```tool_call
{"tool": "file_write", "args": {"content": ".card {\ padding: 1rem; }"}}
```"""


def _valid_tool_call_text() -> str:
    return """```tool_call
{"tool": "file_read", "args": {"path": "내 폴더/결과/report.md"}}
```"""


def _patch_loop_basics(monkeypatch, responses, executed, traces):
    async def fake_build_context(*args, **kwargs):
        return ["system"]

    async def fake_recent_messages(*args, **kwargs):
        return []

    async def fake_stream(*args, **kwargs):
        return next(responses)

    async def fake_execute(
        db,
        project,
        chat_session,
        intent_turn,
        turn_message_id,
        full_text,
        tool_call,
        selected_tools,
        emitter,
        round_num,
        *,
        debug_enabled,
    ):
        executed.append(tool_call)
        return "도구 실행 완료"

    async def fake_record_debug_trace(
        db,
        project,
        chat_session,
        turn_message_id,
        round_index,
        event_type,
        payload,
        duration_ms=None,
    ):
        traces.append((event_type, payload))

    monkeypatch.setattr(tool_loop, "build_context", fake_build_context)
    monkeypatch.setattr(tool_loop, "get_recent_messages", fake_recent_messages)
    monkeypatch.setattr(tool_loop, "_stream_llm_round", fake_stream)
    monkeypatch.setattr(tool_loop, "_execute_tool_call", fake_execute)
    monkeypatch.setattr(tool_loop, "record_debug_trace", fake_record_debug_trace)
    monkeypatch.setattr(tool_loop, "append_conversation_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool_loop, "get_client", lambda: SimpleNamespace())


def test_build_model_contents_reuses_recent_user_message_when_it_matches() -> None:
    recent = [
        {"role": "user", "text": "안녕"},
        {"role": "model", "text": "무엇을 도와드릴까요?"},
        {"role": "user", "text": "파일 목록 보여줘"},
    ]

    contents = build_model_contents(recent, "파일 목록 보여줘")

    assert contents == [
        {"role": "user", "parts": [{"text": "안녕"}]},
        {"role": "model", "parts": [{"text": "무엇을 도와드릴까요?"}]},
        {"role": "user", "parts": [{"text": "파일 목록 보여줘"}]},
    ]


def test_build_model_contents_appends_current_user_message_when_recent_is_stale() -> None:
    recent = [{"role": "model", "text": "이전 응답"}]

    contents = build_model_contents(recent, "새 요청")

    assert contents[-1] == {"role": "user", "parts": [{"text": "새 요청"}]}


def test_run_tool_call_loop_repairs_invalid_tool_call_once(monkeypatch) -> None:
    responses = iter([
        (_invalid_tool_call_text(), 1.0),
        (_valid_tool_call_text(), 1.0),
        ("작업이 완료되었습니다.", 1.0),
    ])
    executed = []
    traces = []
    _patch_loop_basics(monkeypatch, responses, executed, traces)
    db = FakeDb()

    status = asyncio.run(tool_loop.run_tool_call_loop(
        db,
        _project(),
        _chat_session(),
        None,
        "message-1",
        "파일을 수정해줘",
        _route(),
        ["file_read"],
        FakeEmitter(),
        debug_enabled=True,
    ))

    assert status == "completed"
    assert executed == [{"tool": "file_read", "args": {"path": "내 폴더/결과/report.md"}}]
    assert not any(_invalid_tool_call_text() in getattr(obj, "content", "") for obj in db.added)
    assert any(event == "tool_call_parse_error" for event, _payload in traces)


def test_run_tool_call_loop_fails_after_repeated_invalid_tool_call(monkeypatch) -> None:
    responses = iter([
        (_invalid_tool_call_text(), 1.0),
        (_invalid_tool_call_text(), 1.0),
    ])
    executed = []
    traces = []
    _patch_loop_basics(monkeypatch, responses, executed, traces)
    saved_messages = []
    intent_events = []
    intent_turn = SimpleNamespace(status=None)

    async def fake_emit_and_save(db, chat_session, workspace, emitter, content):
        saved_messages.append(content)
        return SimpleNamespace(id="assistant-1")

    async def fake_set_intent_status(db, turn, status):
        turn.status = status

    async def fake_record_intent_event(db, turn, event_type, payload, **kwargs):
        intent_events.append((event_type, payload, kwargs.get("debug_payload")))

    monkeypatch.setattr(tool_loop, "emit_and_save_assistant", fake_emit_and_save)
    monkeypatch.setattr(tool_loop, "set_intent_status", fake_set_intent_status)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)

    status = asyncio.run(tool_loop.run_tool_call_loop(
        FakeDb(),
        _project(),
        _chat_session(),
        intent_turn,
        "message-1",
        "파일을 수정해줘",
        _route(),
        ["file_write"],
        FakeEmitter(),
        debug_enabled=True,
    ))

    assert status == "failed"
    assert executed == []
    assert intent_turn.status == "failed"
    assert saved_messages == [tool_loop._tool_call_parse_failure_message()]
    assert any(event == "failed" for event, _payload, _debug in intent_events)
    assert any(event == "tool_call_parse_error" for event, _payload in traces)
