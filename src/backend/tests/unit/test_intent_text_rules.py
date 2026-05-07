from app.services.intent_text_rules import (
    as_bool,
    looks_like_artifact_reference,
    normalize,
    parse_json_object,
    summarize_text,
)


def test_parse_json_object_accepts_fenced_json() -> None:
    assert parse_json_object('```json\n{"intent": "file_read"}\n```') == {"intent": "file_read"}


def test_parse_json_object_extracts_surrounded_object() -> None:
    assert parse_json_object('result: {"can_execute": true}') == {"can_execute": True}


def test_as_bool_handles_korean_values() -> None:
    assert as_bool("가능") is True
    assert as_bool("불가능") is False


def test_normalize_compacts_whitespace() -> None:
    assert normalize("  파일   찾아줘\n") == "파일 찾아줘"


def test_artifact_reference_detects_path_question() -> None:
    assert looks_like_artifact_reference("방금 만든 파일 경로 알려줘") is True


def test_summarize_text_limits_single_line_summary() -> None:
    result = summarize_text(("a\nb" * 100))
    assert "\n" not in result
    assert len(result) == 120
