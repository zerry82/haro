import asyncio
import time
from types import SimpleNamespace

import pytest

import app.services.agent_tool_loop as tool_loop
from app.services.agent_tool_loop import build_model_contents
from app.services.prompt_bundle import PromptBundle, PromptSection


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


def _valid_web_search_tool_call_text() -> str:
    return """```tool_call
{"tool": "web_search", "args": {"query": "최신 뉴스", "limit": 3}}
```"""


def _fake_client_with_stream(stream_factory):
    def generate_content_stream(**kwargs):
        return stream_factory()

    return SimpleNamespace(models=SimpleNamespace(generate_content_stream=generate_content_stream))


def _patch_loop_basics(monkeypatch, responses, executed, traces):
    async def fake_build_context_sections(*args, **kwargs):
        return [
            PromptSection(
                id="system_prompt.static_core",
                kind="static_core",
                text="system",
                cache_scope="static",
            )
        ]

    async def fake_recent_messages(*args, **kwargs):
        return []

    async def fake_stream(*args, **kwargs):
        result = next(responses)
        if len(result) == 2:
            return result[0], result[1], None
        return result

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
        plan_session=None,
        block_web_search_failure=False,
        tool_state=None,
        seen_tool_call_signatures=None,
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

    async def fake_ensure_gemini_prompt_cache(prompt_bundle, model_name):
        return SimpleNamespace(
            use_cached_content=False,
            debug_summary=lambda: {
                "strategy": "gemini_explicit_stable_system",
                "cache_state": "failed_fallback",
                "cache_key": "test-cache-key",
                "cache_name": None,
                "ttl_seconds": 300,
                "cached_system_hash": prompt_bundle.cached_system_sha256,
                "cached_system_chars": prompt_bundle.cached_system_chars,
                "runtime_context_hash": prompt_bundle.runtime_context_sha256,
                "runtime_context_chars": prompt_bundle.runtime_context_chars,
                "full_hash": prompt_bundle.sha256,
                "full_chars": prompt_bundle.chars,
            },
            generation_config=lambda fallback_system_instruction, temperature=0.7: {
                "system_instruction": fallback_system_instruction,
                "temperature": temperature,
            },
        )

    monkeypatch.setattr(tool_loop, "build_context_sections", fake_build_context_sections)
    monkeypatch.setattr(tool_loop, "get_recent_messages", fake_recent_messages)
    monkeypatch.setattr(tool_loop, "_stream_llm_round", fake_stream)
    monkeypatch.setattr(tool_loop, "_execute_tool_call", fake_execute)
    monkeypatch.setattr(tool_loop, "record_debug_trace", fake_record_debug_trace)
    monkeypatch.setattr(tool_loop, "append_conversation_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool_loop, "get_client", lambda: SimpleNamespace())
    monkeypatch.setattr(tool_loop, "ensure_gemini_prompt_cache", fake_ensure_gemini_prompt_cache)


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


def test_prompt_bundle_keeps_static_prefix_stable_across_runtime_context() -> None:
    static_section = PromptSection(
        id="system_prompt.static_core",
        kind="static_core",
        text="stable system prompt",
        cache_scope="static",
    )
    runtime_a = PromptSection(
        id="system_prompt.runtime_context",
        kind="runtime_context",
        text="chat A",
        cache_scope="runtime",
    )
    runtime_b = PromptSection(
        id="system_prompt.runtime_context",
        kind="runtime_context",
        text="chat B",
        cache_scope="runtime",
    )

    bundle_a = tool_loop._build_prompt_bundle([static_section, runtime_a], ["file_read"], _route())
    bundle_b = tool_loop._build_prompt_bundle([static_section, runtime_b], ["web_search"], _route())

    assert bundle_a.cached_system_sha256 == bundle_b.cached_system_sha256
    assert bundle_a.cached_system_chars > len("stable system prompt")
    assert bundle_a.runtime_context_sha256 != bundle_b.runtime_context_sha256
    assert bundle_a.sha256 != bundle_b.sha256


def test_stream_llm_chunks_nonblocking_keeps_event_loop_responsive(monkeypatch) -> None:
    def blocking_stream():
        time.sleep(0.2)
        yield SimpleNamespace(text="늦은 응답")

    monkeypatch.setattr(tool_loop, "get_client", lambda: _fake_client_with_stream(blocking_stream))

    async def run_check():
        async def collect():
            chunks = []
            async for chunk in tool_loop.stream_llm_chunks_nonblocking([], {}):
                chunks.append(chunk)
            return chunks

        started = time.perf_counter()
        task = asyncio.create_task(collect())
        await asyncio.sleep(0.02)
        heartbeat_elapsed = time.perf_counter() - started
        chunks = await task
        return heartbeat_elapsed, chunks

    heartbeat_elapsed, chunks = asyncio.run(run_check())

    assert heartbeat_elapsed < 0.15
    assert chunks == ["늦은 응답"]


def test_stream_llm_chunks_nonblocking_preserves_chunk_order(monkeypatch) -> None:
    def ordered_stream():
        yield SimpleNamespace(text="A")
        yield SimpleNamespace(text=None)
        yield SimpleNamespace(text="B")
        yield SimpleNamespace(text="C")

    monkeypatch.setattr(tool_loop, "get_client", lambda: _fake_client_with_stream(ordered_stream))

    async def collect():
        chunks = []
        async for chunk in tool_loop.stream_llm_chunks_nonblocking([], {}):
            chunks.append(chunk)
        return chunks

    assert asyncio.run(collect()) == ["A", "B", "C"]


def test_stream_llm_chunks_nonblocking_propagates_worker_error(monkeypatch) -> None:
    def broken_stream():
        raise RuntimeError("stream boom")
        yield SimpleNamespace(text="unreachable")

    monkeypatch.setattr(tool_loop, "get_client", lambda: _fake_client_with_stream(broken_stream))

    async def collect():
        chunks = []
        async for chunk in tool_loop.stream_llm_chunks_nonblocking([], {}):
            chunks.append(chunk)
        return chunks

    with pytest.raises(RuntimeError, match="stream boom"):
        asyncio.run(collect())


def test_stream_llm_chunks_nonblocking_collects_usage_metadata(monkeypatch) -> None:
    def usage_stream():
        yield SimpleNamespace(
            text="A",
            usage_metadata=SimpleNamespace(
                prompt_token_count=100,
                cached_content_token_count=90,
                candidates_token_count=5,
                total_token_count=105,
            ),
        )

    monkeypatch.setattr(tool_loop, "get_client", lambda: _fake_client_with_stream(usage_stream))

    async def collect():
        chunks = []
        usage_metadata = []
        async for chunk in tool_loop.stream_llm_chunks_nonblocking(
            [],
            {},
            usage_metadata_collector=usage_metadata,
        ):
            chunks.append(chunk)
        return chunks, usage_metadata

    chunks, usage_metadata = asyncio.run(collect())

    assert chunks == ["A"]
    assert usage_metadata == [{
        "prompt_token_count": 100,
        "cached_content_token_count": 90,
        "candidates_token_count": 5,
        "total_token_count": 105,
    }]


def test_stream_llm_round_records_prompt_macro_request_and_usage(monkeypatch) -> None:
    traces = []

    def usage_stream():
        yield SimpleNamespace(
            text="응답",
            usage_metadata=SimpleNamespace(
                prompt_token_count=200,
                cached_content_token_count=150,
                candidates_token_count=10,
                total_token_count=210,
            ),
        )

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

    prompt_bundle = PromptBundle.from_sections([
        PromptSection(
            id="system_prompt.static_core",
            kind="static_core",
            text="large stable prompt",
            cache_scope="static",
        )
    ])
    monkeypatch.setattr(tool_loop, "get_client", lambda: _fake_client_with_stream(usage_stream))
    monkeypatch.setattr(tool_loop, "record_debug_trace", fake_record_debug_trace)

    full_text, _duration_ms, usage_metadata = asyncio.run(tool_loop._stream_llm_round(
        FakeDb(),
        _project(),
        _chat_session(),
        "message-1",
        [{"role": "user", "parts": [{"text": "hello"}]}],
        {"system_instruction": prompt_bundle.text, "temperature": 0.7},
        FakeEmitter(),
        0,
        debug_enabled=True,
        prompt_bundle=prompt_bundle,
    ))

    request_payload = traces[0][1]
    assert full_text == "응답"
    assert request_payload["system_instruction"] == {"$macro": "system_prompt.full"}
    assert request_payload["config"]["system_instruction"] == {"$macro": "system_prompt.full"}
    assert "large stable prompt" not in str(request_payload)
    assert usage_metadata == {
        "prompt_token_count": 200,
        "cached_content_token_count": 150,
        "candidates_token_count": 10,
        "total_token_count": 210,
        "cache_hit_ratio": 0.75,
    }


def test_stream_llm_round_records_explicit_cache_request_without_system_instruction(monkeypatch) -> None:
    traces = []

    def usage_stream():
        yield SimpleNamespace(text="응답")

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

    prompt_bundle = PromptBundle.from_sections([
        PromptSection(
            id="system_prompt.static_core",
            kind="static_core",
            text="large stable prompt",
            cache_scope="static",
        ),
        PromptSection(
            id="system_prompt.runtime_context",
            kind="runtime_context",
            text="selected tool: file_read",
            cache_scope="runtime",
        ),
    ])
    contents = prompt_bundle.model_contents(
        [{"role": "user", "parts": [{"text": "hello"}]}],
        include_runtime_context=True,
    )
    monkeypatch.setattr(tool_loop, "get_client", lambda: _fake_client_with_stream(usage_stream))
    monkeypatch.setattr(tool_loop, "record_debug_trace", fake_record_debug_trace)

    asyncio.run(tool_loop._stream_llm_round(
        FakeDb(),
        _project(),
        _chat_session(),
        "message-1",
        contents,
        {"cached_content": "cachedContents/1", "temperature": 0.7},
        FakeEmitter(),
        0,
        debug_enabled=True,
        prompt_bundle=prompt_bundle,
        prompt_cache={
            "strategy": "gemini_explicit_stable_system",
            "cache_state": "reused",
            "cache_name": "cachedContents/1",
        },
    ))

    request_payload = traces[0][1]
    assert "system_instruction" not in request_payload["config"]
    assert request_payload["config"]["cached_content"] == "cachedContents/1"
    assert request_payload["contents"][0]["parts"][0]["text"] == {"$macro": "system_prompt.runtime_context"}
    assert "selected tool: file_read" not in str(request_payload)


def test_usage_metadata_debug_defaults_missing_cached_tokens_to_zero() -> None:
    assert tool_loop._usage_metadata_debug({
        "prompt_token_count": 100,
        "candidates_token_count": 5,
        "total_token_count": 105,
    }) == {
        "prompt_token_count": 100,
        "candidates_token_count": 5,
        "total_token_count": 105,
        "cached_content_token_count": 0,
        "cache_hit_ratio": 0,
    }


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


def test_run_tool_call_loop_records_debug_macros_once(monkeypatch) -> None:
    responses = iter([
        ("작업이 완료되었습니다.", 1.0),
    ])
    executed = []
    traces = []
    _patch_loop_basics(monkeypatch, responses, executed, traces)

    status = asyncio.run(tool_loop.run_tool_call_loop(
        FakeDb(),
        _project(),
        _chat_session(),
        None,
        "message-1",
        "완료해줘",
        _route(),
        ["file_read"],
        FakeEmitter(),
        debug_enabled=True,
    ))

    macro_events = [payload for event, payload in traces if event == "debug_macros"]
    assert status == "completed"
    assert len(macro_events) == 1
    assert "system_prompt.full" in macro_events[0]["prompt_macros"]
    assert "system_prompt.cached_system" in macro_events[0]["prompt_macros"]
    assert "system_prompt.runtime_context" in macro_events[0]["prompt_macros"]
    assert macro_events[0]["prompt_cache"]["strategy"] == "gemini_explicit_stable_system"


def test_run_tool_call_loop_executes_web_search_tool_call(monkeypatch) -> None:
    responses = iter([
        (_valid_web_search_tool_call_text(), 1.0),
        ("검색 결과를 바탕으로 답변했습니다.", 1.0),
    ])
    executed = []
    traces = []
    _patch_loop_basics(monkeypatch, responses, executed, traces)

    status = asyncio.run(tool_loop.run_tool_call_loop(
        FakeDb(),
        _project(),
        _chat_session(),
        None,
        "message-1",
        "최신 뉴스 검색해줘",
        _route(),
        ["web_search"],
        FakeEmitter(),
        debug_enabled=True,
    ))

    assert status == "completed"
    assert executed == [{"tool": "web_search", "args": {"query": "최신 뉴스", "limit": 3}}]


def test_execute_tool_call_blocks_unselected_web_search(monkeypatch) -> None:
    saved_messages = []
    intent_events = []
    intent_turn = SimpleNamespace(status=None)
    emitter = FakeEmitter()

    async def fake_emit_and_save(db, chat_session, workspace, emitter, content):
        saved_messages.append(content)
        return SimpleNamespace(id="assistant-1")

    async def fake_record_intent_event(db, turn, event_type, payload, **kwargs):
        intent_events.append((event_type, payload))

    async def fake_set_intent_status(db, turn, status):
        turn.status = status

    monkeypatch.setattr(tool_loop, "emit_and_save_assistant", fake_emit_and_save)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)
    monkeypatch.setattr(tool_loop, "set_intent_status", fake_set_intent_status)

    result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        intent_turn,
        "message-1",
        _valid_web_search_tool_call_text(),
        {"tool": "web_search", "args": {"query": "최신 뉴스"}},
        [],
        emitter,
        0,
        debug_enabled=False,
    ))

    assert result == "blocked"
    assert intent_turn.status == "blocked"
    assert saved_messages
    assert any(event == "blocked" for event, _payload in intent_events)
    assert ("done", {"summary": "선택되지 않은 도구 호출로 작업이 중단되었습니다."}) in emitter.events


def test_execute_tool_call_blocks_write_tool_in_plan_mode(monkeypatch) -> None:
    saved_messages = []
    plan_events = []
    intent_turn = SimpleNamespace(status=None)
    plan_session = SimpleNamespace(id="plan-1", plan_file_path="/chat/working/plan.md")
    emitter = FakeEmitter()

    async def fake_emit_and_save(db, chat_session, workspace, emitter, content):
        saved_messages.append(content)
        return SimpleNamespace(id="assistant-1")

    async def fake_record_plan_event(db, session, event_type, payload, **kwargs):
        plan_events.append((event_type, payload))

    async def fake_set_intent_status(db, turn, status):
        turn.status = status

    async def fake_record_intent_event(*args, **kwargs):
        pass

    monkeypatch.setattr(tool_loop, "emit_and_save_assistant", fake_emit_and_save)
    monkeypatch.setattr(tool_loop, "record_plan_event", fake_record_plan_event)
    monkeypatch.setattr(tool_loop, "set_intent_status", fake_set_intent_status)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)

    result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        intent_turn,
        "message-1",
        "```tool_call\n{\"tool\":\"file_write\",\"args\":{\"path\":\"/x.md\"}}\n```",
        {"tool": "file_write", "args": {"path": "/x.md"}},
        ["file_write"],
        emitter,
        0,
        debug_enabled=False,
        plan_session=plan_session,
    ))

    assert result == "blocked"
    assert intent_turn.status == "blocked"
    assert saved_messages
    assert any(event == "execution_blocked" for event, _payload in plan_events)
    assert any(event == "execution_blocked" for event, _payload in emitter.events)


def test_execute_tool_call_blocks_web_search_failure_for_approved_plan(monkeypatch) -> None:
    saved_messages = []
    intent_events = []
    intent_turn = SimpleNamespace(status=None)
    emitter = FakeEmitter()

    async def fake_execute_tool(*args, **kwargs):
        return "웹 검색을 사용할 수 없습니다: WEB_SEARCH_BASE_URL이 설정되어 있지 않습니다."

    async def fake_emit_and_save(db, chat_session, workspace, emitter, content):
        saved_messages.append(content)
        return SimpleNamespace(id="assistant-1")

    async def fake_set_intent_status(db, turn, status):
        turn.status = status

    async def fake_record_intent_event(db, turn, event_type, payload, **kwargs):
        intent_events.append((event_type, payload))

    monkeypatch.setattr(tool_loop, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(tool_loop, "emit_and_save_assistant", fake_emit_and_save)
    monkeypatch.setattr(tool_loop, "set_intent_status", fake_set_intent_status)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)

    result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        intent_turn,
        "message-1",
        _valid_web_search_tool_call_text(),
        {"tool": "web_search", "args": {"query": "최신 뉴스"}},
        ["web_search"],
        emitter,
        0,
        debug_enabled=False,
        block_web_search_failure=True,
    ))

    assert result == "blocked"
    assert intent_turn.status == "blocked"
    assert saved_messages
    assert "내부 지식으로 대체하지 않았습니다" in saved_messages[0]
    assert any(event == "execution_blocked" for event, _payload in intent_events)
    assert ("done", {"summary": "웹 검색 실패로 작업이 중단되었습니다."}) in emitter.events


def test_execute_tool_call_skips_duplicate_file_search(monkeypatch) -> None:
    executed = []

    async def fake_execute_tool(*args, **kwargs):
        executed.append(args[1])
        return "검색 결과"

    async def fake_record_intent_event(*args, **kwargs):
        pass

    monkeypatch.setattr(tool_loop, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)

    seen: set[str] = set()
    first = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        SimpleNamespace(),
        "message-1",
        """```tool_call
{"tool": "file_search", "args": {"query": "서울 날씨", "limit": 10}}
```""",
        {"tool": "file_search", "args": {"query": "서울   날씨", "limit": 10}},
        ["file_search"],
        FakeEmitter(),
        0,
        debug_enabled=False,
        seen_tool_call_signatures=seen,
    ))
    second = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        SimpleNamespace(),
        "message-1",
        """```tool_call
{"tool": "file_search", "args": {"query": "서울 날씨", "limit": 10}}
```""",
        {"tool": "file_search", "args": {"query": "서울 날씨", "limit": 10}},
        ["file_search"],
        FakeEmitter(),
        1,
        debug_enabled=False,
        seen_tool_call_signatures=seen,
    ))

    assert first == "검색 결과"
    assert second.startswith("중복 탐색 생략:")
    assert executed == ["file_search"]


def test_execute_tool_call_guards_write_before_read(monkeypatch) -> None:
    executed = []
    intent_events = []

    async def fake_execute_tool(*args, **kwargs):
        executed.append(args[1])
        return "수정 완료"

    async def fake_record_intent_event(db, turn, event_type, payload, **kwargs):
        intent_events.append((event_type, payload))

    monkeypatch.setattr(tool_loop, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)

    result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        SimpleNamespace(),
        "message-1",
        """```tool_call
{"tool": "file_edit", "args": {"path": "내 폴더/결과/report.md", "old_string": "a", "new_string": "b"}}
```""",
        {"tool": "file_edit", "args": {"path": "내 폴더/결과/report.md", "old_string": "a", "new_string": "b"}},
        ["file_read", "file_edit"],
        FakeEmitter(),
        0,
        debug_enabled=False,
    ))

    assert result.startswith("도구 상태 가드:")
    assert executed == []
    assert any(event == "tool_state_guard" for event, _payload in intent_events)


def test_execute_tool_call_allows_write_after_same_turn_read(monkeypatch) -> None:
    executed = []

    async def fake_execute_tool(*args, **kwargs):
        executed.append(args[1])
        return "도구 실행 완료"

    async def fake_record_intent_event(*args, **kwargs):
        pass

    monkeypatch.setattr(tool_loop, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(tool_loop, "record_intent_event", fake_record_intent_event)

    state = tool_loop.TurnToolState()
    read_result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        SimpleNamespace(),
        "message-1",
        """```tool_call
{"tool": "file_read", "args": {"path": "내 폴더/결과/report.md"}}
```""",
        {"tool": "file_read", "args": {"path": "내 폴더/결과/report.md"}},
        ["file_read", "file_edit"],
        FakeEmitter(),
        0,
        debug_enabled=False,
        tool_state=state,
    ))
    write_result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        SimpleNamespace(),
        "message-1",
        """```tool_call
{"tool": "file_edit", "args": {"path": "내 폴더/결과/report.md", "old_string": "a", "new_string": "b"}}
```""",
        {"tool": "file_edit", "args": {"path": "내 폴더/결과/report.md", "old_string": "a", "new_string": "b"}},
        ["file_read", "file_edit"],
        FakeEmitter(),
        1,
        debug_enabled=False,
        tool_state=state,
    ))

    assert read_result == "도구 실행 완료"
    assert write_result == "도구 실행 완료"
    assert executed == ["file_read", "file_edit"]


def test_execute_tool_call_returns_awaiting_approval_for_plan_approval_tool(monkeypatch) -> None:
    executed = []
    plan_session = SimpleNamespace(id="plan-1", plan_file_path="/chat/working/plan.md")

    async def fake_execute_tool(*args, **kwargs):
        executed.append(kwargs.get("plan_session"))
        return "계획 승인 요청 완료"

    monkeypatch.setattr(tool_loop, "execute_tool", fake_execute_tool)

    result = asyncio.run(tool_loop._execute_tool_call(
        FakeDb(),
        _project(),
        _chat_session(),
        None,
        "message-1",
        "```tool_call\n{\"tool\":\"plan_approval_request\",\"args\":{\"summary\":\"OK\"}}\n```",
        {"tool": "plan_approval_request", "args": {"summary": "OK"}},
        ["plan_approval_request"],
        FakeEmitter(),
        0,
        debug_enabled=False,
        plan_session=plan_session,
    ))

    assert result == tool_loop.PLAN_AWAITING_APPROVAL
    assert executed == [plan_session]


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
