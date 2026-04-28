# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "haro-features-and-user-scenarios.pdf"
SOURCE_DOCS = [
    BASE_DIR / "haro-main-features.md",
    BASE_DIR / "user-scenario-haro.md",
    BASE_DIR / "user-scenario-haro-advertiser.md",
]

FONT_REGULAR = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"


pdfmetrics.registerFont(TTFont("Malgun", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("MalgunBold", FONT_BOLD))

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="KTitle",
        fontName="MalgunBold",
        fontSize=24,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=16,
    )
)
styles.add(
    ParagraphStyle(
        name="KSubtitle",
        fontName="Malgun",
        fontSize=11,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="DocTitle",
        fontName="MalgunBold",
        fontSize=20,
        leading=28,
        textColor=colors.HexColor("#111827"),
        spaceBefore=6,
        spaceAfter=14,
    )
)
styles.add(
    ParagraphStyle(
        name="H1",
        fontName="MalgunBold",
        fontSize=16,
        leading=24,
        textColor=colors.HexColor("#111827"),
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="H2",
        fontName="MalgunBold",
        fontSize=13,
        leading=20,
        textColor=colors.HexColor("#1f2937"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="H3",
        fontName="MalgunBold",
        fontSize=11.5,
        leading=18,
        textColor=colors.HexColor("#374151"),
        spaceBefore=9,
        spaceAfter=5,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyK",
        fontName="Malgun",
        fontSize=9.7,
        leading=16,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=5,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="SmallK",
        fontName="Malgun",
        fontSize=8.5,
        leading=13,
        textColor=colors.HexColor("#374151"),
    )
)
styles.add(
    ParagraphStyle(
        name="CodeK",
        fontName="Malgun",
        fontSize=8.2,
        leading=12.5,
        textColor=colors.HexColor("#111827"),
    )
)
styles.add(
    ParagraphStyle(
        name="TocItem",
        fontName="Malgun",
        fontSize=10.5,
        leading=17,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=3,
    )
)

USABLE_WIDTH = A4[0] - 36 * mm


def inline_md(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="MalgunBold">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r'<font name="MalgunBold">\1</font>', text)
    return text


def add_paragraph(story: list, buffer: list[str]) -> None:
    if not buffer:
        return
    paragraph = " ".join(line.strip() for line in buffer if line.strip())
    if paragraph:
        story.append(Paragraph(inline_md(paragraph), styles["BodyK"]))
    buffer.clear()


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|").strip()
    if not stripped:
        return False
    return all(set(part.strip()) <= set("-: ") and "-" in part for part in stripped.split("|"))


def parse_table(lines: list[str]) -> Table | None:
    rows = []
    for line in lines:
        if is_table_separator(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return None

    max_cols = max(len(row) for row in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    col_width = USABLE_WIDTH / max_cols
    data = [[Paragraph(inline_md(cell), styles["SmallK"]) for cell in row] for row in rows]
    table = Table(data, colWidths=[col_width] * max_cols, repeatRows=1 if len(rows) > 1 else 0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (-1, 0), "MalgunBold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def code_block_flowable(lines: list[str]) -> Table:
    escaped = "<br/>".join(html.escape(line).replace(" ", "&nbsp;") for line in lines)
    para = Paragraph(escaped or "&nbsp;", styles["CodeK"])
    table = Table([[para]], colWidths=[USABLE_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def read_first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^#\s+(.*)$", line.strip())
        if match:
            return match.group(1).strip()
    return path.stem


def parse_markdown(path: Path) -> list:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    story = []
    buffer: list[str] = []
    table_lines: list[str] = []
    in_code = False
    code_lines: list[str] = []
    saw_title = False

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            table = parse_table(table_lines)
            if table:
                story.append(table)
                story.append(Spacer(1, 5))
            table_lines = []

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                story.append(code_block_flowable(code_lines))
                story.append(Spacer(1, 7))
                code_lines = []
                in_code = False
            else:
                add_paragraph(story, buffer)
                flush_table()
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if is_table_line(line):
            add_paragraph(story, buffer)
            table_lines.append(line)
            continue

        flush_table()

        if not line.strip():
            add_paragraph(story, buffer)
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            add_paragraph(story, buffer)
            level = len(heading.group(1))
            content = heading.group(2).strip()
            if level == 1 and not saw_title:
                story.append(Paragraph(inline_md(content), styles["DocTitle"]))
                saw_title = True
            elif level == 2:
                story.append(Paragraph(inline_md(content), styles["H1"]))
            elif level == 3:
                story.append(Paragraph(inline_md(content), styles["H2"]))
            else:
                story.append(Paragraph(inline_md(content), styles["H3"]))
            continue

        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        numbered = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if bullet:
            add_paragraph(story, buffer)
            story.append(Paragraph("- " + inline_md(bullet.group(1).strip()), styles["BodyK"]))
            continue
        if numbered:
            add_paragraph(story, buffer)
            story.append(
                Paragraph(
                    numbered.group(1) + ". " + inline_md(numbered.group(2).strip()),
                    styles["BodyK"],
                )
            )
            continue

        buffer.append(line)

    add_paragraph(story, buffer)
    flush_table()
    if in_code:
        story.append(code_block_flowable(code_lines))

    return story


def on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Malgun", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(18 * mm, 12 * mm, "하로 주요 기능과 사용자 시나리오")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(doc.page))
    canvas.restoreState()


def build_pdf() -> None:
    doc_titles = [read_first_heading(path) for path in SOURCE_DOCS]

    story = []
    story.append(Spacer(1, 55 * mm))
    story.append(Paragraph("하로 주요 기능과 사용자 시나리오", styles["KTitle"]))
    story.append(Paragraph("업무규칙 학습과 기억을 중심으로 정리한 통합 문서", styles["KSubtitle"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(datetime.now().strftime("생성일: %Y-%m-%d"), styles["KSubtitle"]))
    story.append(Spacer(1, 28 * mm))
    story.append(Paragraph("포함 문서", styles["H1"]))
    for idx, title in enumerate(doc_titles, 1):
        story.append(Paragraph(f"{idx}. {inline_md(title)}", styles["TocItem"]))
    story.append(PageBreak())

    for idx, path in enumerate(SOURCE_DOCS):
        if idx > 0:
            story.append(PageBreak())
        story.extend(parse_markdown(path))

    pdf = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="haro-features-and-user-scenarios",
        author="Codex",
    )
    pdf.build(story, onFirstPage=on_page, onLaterPages=on_page)


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT_PATH)
