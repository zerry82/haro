from app.routers.messages import DebugTraceResponse, _prompt_macros_from_payload


def test_prompt_macros_from_debug_macro_payload() -> None:
    payload = {
        "prompt_macros": {
            "system_prompt.full": {
                "id": "system_prompt.full",
                "sha256": "sha256:abc",
                "chars": 10,
                "text": "full prompt",
            },
            "system_prompt.cached_system": {
                "id": "system_prompt.cached_system",
                "sha256": "sha256:def",
                "chars": 6,
                "text": "cached",
            },
            "system_prompt.runtime_context": {
                "id": "system_prompt.runtime_context",
                "sha256": "sha256:ghi",
                "chars": 7,
                "text": "runtime",
            },
        }
    }

    assert _prompt_macros_from_payload(payload) == payload["prompt_macros"]


def test_debug_trace_response_accepts_top_level_prompt_macros() -> None:
    response = DebugTraceResponse(
        message_id="message-1",
        has_trace=True,
        prompt_macros={
            "system_prompt.full": {"text": "full prompt"},
            "system_prompt.cached_system": {"text": "cached"},
            "system_prompt.runtime_context": {"text": "runtime"},
        },
        events=[],
    )

    assert response.model_dump()["prompt_macros"] == {
        "system_prompt.full": {"text": "full prompt"},
        "system_prompt.cached_system": {"text": "cached"},
        "system_prompt.runtime_context": {"text": "runtime"},
    }
