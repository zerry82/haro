from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.services.file_conversion import (
    dedupe_name,
    excel_to_csv_outputs,
    get_language,
    is_excel_file,
    sanitize_file_segment,
)


def test_file_segment_sanitization_removes_unsafe_characters() -> None:
    assert sanitize_file_segment('  a<b>:c?.csv  ', "fallback") == "a_b__c_.csv"
    assert sanitize_file_segment("..", "fallback") == "fallback"


def test_dedupe_name_adds_stable_suffixes() -> None:
    used: set[str] = set()

    assert dedupe_name("sheet.csv", used) == "sheet.csv"
    assert dedupe_name("sheet.csv", used) == "sheet_2.csv"
    assert dedupe_name("sheet.csv", used) == "sheet_3.csv"


def test_language_and_excel_detection_use_extensions() -> None:
    assert get_language("/src/app.py") == "python"
    assert get_language("/docs/readme.md") == "markdown"
    assert get_language("/unknown/file.bin") == "plaintext"
    assert is_excel_file("report.xlsx") is True
    assert is_excel_file("report.csv") is False


def test_excel_to_csv_outputs_converts_each_sheet() -> None:
    workbook = Workbook()
    first = workbook.active
    first.title = "Data"
    first.append(["name", "value"])
    first.append(["A", 1])
    second = workbook.create_sheet("Data")
    second.append(["other"])

    stream = BytesIO()
    workbook.save(stream)

    outputs = excel_to_csv_outputs("Report.xlsx", stream.getvalue())

    assert outputs == [
        ("Report/Data.csv", b"name,value\nA,1\n"),
        ("Report/Data1.csv", b"other\n"),
    ]


def test_excel_to_csv_outputs_ignores_non_excel_files() -> None:
    assert excel_to_csv_outputs("notes.txt", b"hello") == []
