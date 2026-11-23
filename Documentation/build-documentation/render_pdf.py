from __future__ import annotations

import re
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

SOURCE = Path(__file__).resolve().parent
OUTPUT = SOURCE.parent / "build-documentation.pdf"
WIKI_ROOT = "https://github.com/amosproj/amos2026ws01-legacy-migrator/wiki/"

PAGE_NAMES = [
    "Index",
    "Prerequisites",
    "Dependencies",
    "Environment-variables",
    "Clone-and-setup",
    "Build",
    "Automated-tests",
    "Start",
    "Deployment",
    "Verification-log",
    "Troubleshooting",
]

PAGE_W, PAGE_H = A4
LEFT = RIGHT = 16 * mm
TOP = 17 * mm
BOTTOM = 17 * mm
CONTENT_W = PAGE_W - LEFT - RIGHT

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="DocTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=23, leading=27, textColor=colors.HexColor("#142c46"),
    alignment=TA_LEFT, spaceAfter=8 * mm,
))
styles.add(ParagraphStyle(
    name="H1Doc", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=17, leading=21, textColor=colors.HexColor("#142c46"),
    spaceBefore=0, spaceAfter=6 * mm, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="H2Doc", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=12.5, leading=16, textColor=colors.HexColor("#1d4868"),
    spaceBefore=4 * mm, spaceAfter=2.5 * mm, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="H3Doc", parent=styles["Heading3"], fontName="Helvetica-Bold",
    fontSize=10.3, leading=13, textColor=colors.HexColor("#1d4868"),
    spaceBefore=3 * mm, spaceAfter=2 * mm, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="BodyDoc", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.8, leading=12.2, textColor=colors.HexColor("#252d36"),
    spaceAfter=2.4 * mm, alignment=TA_LEFT,
))
styles.add(ParagraphStyle(
    name="SmallDoc", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.6, leading=9.6, textColor=colors.HexColor("#252d36"),
    spaceAfter=0,
))
styles.add(ParagraphStyle(
    name="TableHeadDoc", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=7.4, leading=9, textColor=colors.white, spaceAfter=0,
))
styles.add(ParagraphStyle(
    name="CodeDoc", fontName="Courier", fontSize=7.3, leading=9.2,
    textColor=colors.HexColor("#1c2733"), leftIndent=0, rightIndent=0,
    spaceAfter=0, spaceBefore=0,
))
styles.add(ParagraphStyle(
    name="MetaDoc", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.4, leading=12, textColor=colors.HexColor("#526273"),
    spaceAfter=3 * mm,
))

bt = chr(96)
inline_tokens = re.compile(r"(\[[^]]+\]\([^)]+\)|\*\*.*?\*\*|" + bt + r"[^" + bt + r"]+" + bt + r")")

def safe_url(target: str) -> str:
    if target.startswith(("https://", "http://", "mailto:")):
        return target
    target = target.split("#", 1)[0].strip()
    return WIKI_ROOT + target.replace(" ", "-")

def inline_markup(value: str) -> str:
    pieces = []
    cursor = 0
    for match in inline_tokens.finditer(value):
        pieces.append(escape(value[cursor:match.start()]))
        token = match.group(0)
        if token.startswith("["):
            link = re.fullmatch(r"\[([^]]+)\]\(([^)]+)\)", token)
            label, target = link.groups()
            pieces.append(f'<link href="{escape(safe_url(target), {chr(34): "&quot;"})}" color="#1769aa">{escape(label)}</link>')
        elif token.startswith(bt):
            pieces.append(f'<font name="Courier" size="7.5">{escape(token[1:-1])}</font>')
        else:
            pieces.append("<b>" + escape(token[2:-2]) + "</b>")
        cursor = match.end()
    pieces.append(escape(value[cursor:]))
    return "".join(pieces)

def split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]

def is_table_separator(line: str) -> bool:
    cells = split_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)

def make_table(lines: list[str]) -> Table:
    rows = [split_cells(line) for line in lines]
    if len(rows) > 1 and is_table_separator(lines[1]):
        rows.pop(1)
    count = max(len(row) for row in rows)
    data = []
    for row_number, row in enumerate(rows):
        cells = row + [""] * (count - len(row))
        style = styles["TableHeadDoc"] if row_number == 0 else styles["SmallDoc"]
        data.append([Paragraph(inline_markup(cell), style) for cell in cells])
    first_header = rows[0][0].strip().lower()
    if count == 4 and first_header == "service":
        widths = [78, 105, 72, CONTENT_W - 255]
    elif count == 4:
        widths = [112, 58, 104, CONTENT_W - 274]
    elif count == 3 and first_header == "tool":
        widths = [125, 95, CONTENT_W - 220]
    elif count == 3 and first_header == "variable":
        widths = [180, 90, CONTENT_W - 270]
    elif count == 3:
        widths = [CONTENT_W * 0.54, CONTENT_W * 0.10, CONTENT_W * 0.36]
    elif count == 2:
        widths = [CONTENT_W * 0.27, CONTENT_W * 0.73]
    else:
        widths = [CONTENT_W / count] * count
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#234968")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b9c6d1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table

def code_block(lines: list[str]) -> Table:
    text = "\n".join(lines)
    block = Preformatted(text, styles["CodeDoc"], maxLineLength=120)
    table = Table([[block]], colWidths=[CONTENT_W], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f4f6")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#c6d0d8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table

def parse_page(text: str, page_index: int) -> list:
    lines = text.splitlines()
    story = []
    if page_index:
        story.append(PageBreak())
    in_code = False
    code_lines = []
    paragraph_lines = []
    i = 0

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            content = " ".join(part.strip() for part in paragraph_lines if part.strip())
            if content:
                story.append(Paragraph(inline_markup(content), styles["BodyDoc"]))
            paragraph_lines = []

    while i < len(lines):
        line = lines[i]
        if line.startswith("~~~"):
            flush_paragraph()
            if in_code:
                story.append(code_block(code_lines))
                story.append(Spacer(1, 2.2 * mm))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            flush_paragraph()
            i += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            story.append(make_table(table_lines))
            story.append(Spacer(1, 2.5 * mm))
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            style = {1: styles["H1Doc"], 2: styles["H2Doc"], 3: styles["H3Doc"]}[level]
            story.append(Paragraph(inline_markup(heading.group(2)), style))
            i += 1
            continue
        bullet = re.match(r"^\s*-\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            story.append(Paragraph("&#8226;&nbsp;&nbsp;" + inline_markup(bullet.group(1)), styles["BodyDoc"]))
            i += 1
            continue
        numbered = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if numbered:
            flush_paragraph()
            story.append(Paragraph(numbered.group(1) + ".&nbsp;&nbsp;" + inline_markup(numbered.group(2)), styles["BodyDoc"]))
            i += 1
            continue
        paragraph_lines.append(line)
        i += 1
    flush_paragraph()
    if in_code and code_lines:
        story.append(code_block(code_lines))
    return story

def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d7e0e7"))
    canvas.setLineWidth(0.5)
    canvas.line(LEFT, PAGE_H - 10 * mm, PAGE_W - RIGHT, PAGE_H - 10 * mm)
    canvas.setFont("Helvetica", 7.3)
    canvas.setFillColor(colors.HexColor("#526273"))
    canvas.drawString(LEFT, PAGE_H - 7.5 * mm, "SunsetTracker | Build documentation")
    canvas.drawRightString(PAGE_W - RIGHT, 8 * mm, f"sprint-05-release | Page {doc.page}")
    canvas.restoreState()

class GuideDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename, pagesize=A4,
            leftMargin=LEFT, rightMargin=RIGHT, topMargin=TOP, bottomMargin=BOTTOM,
            title="SunsetTracker Build Documentation",
            subject="Build, test, start, and local deployment guide",
        )
        frame = Frame(LEFT, BOTTOM, CONTENT_W, PAGE_H - TOP - BOTTOM, id="normal")
        self.addPageTemplates([PageTemplate(id="guide", frames=[frame], onPage=draw_page)])

doc = GuideDocTemplate(str(OUTPUT))
story = []
for index, page_name in enumerate(PAGE_NAMES):
    source_path = SOURCE / f"{page_name}.md"
    story.extend(parse_page(source_path.read_text(encoding="utf-8"), index))
doc.build(story)
print(OUTPUT)

