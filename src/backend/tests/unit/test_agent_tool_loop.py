from app.services.agent_tool_loop import build_model_contents


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
