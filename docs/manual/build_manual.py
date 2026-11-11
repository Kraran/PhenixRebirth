"""
Build the player manuals (docs/PhenixRebirth-Manuel-FR.pdf, docs/PhenixRebirth-Manual-EN.pdf) from their sources.

    python -m pip install reportlab        (only this tool needs it, not the game)
    python docs/manual/build_manual.py      (both languages)
    python docs/manual/build_manual.py fr   (one of them)

The text lives in docs/manual/manual_FR.txt and manual_EN.txt, in a small markup (one block per paragraph, blank lines
between blocks):

    @key value        metadata at the top: pdf_title, cover_title, cover_version, cover_tag, header, footer, closing
    # 1. Title        a section heading (orange)
    ### Title         a sub-heading
    - text            a bullet
    > text            a note, in grey italics
    | a | b | c |     a table, its first row is the header; "@cols 20,30,50" just before it sets the column widths (%)
    ```  ...  ```     a block of commands (monospace)
    ===               a page break
    **bold**  *italic*  `code`   inside a line

The look is the one of the first manuals (v1.1.0): A4, a dark page, the cover picture, orange headings, purple tables,
Helvetica. Only the characters of Windows-1252 are drawn by the standard PDF fonts: the build stops on any other one.
"""

import os
import re
import sys

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
ROOT = os.path.dirname(DOCS)
OUTPUTS = {"fr": ("manual_FR.txt", "PhenixRebirth-Manuel-FR.pdf"), "en": ("manual_EN.txt", "PhenixRebirth-Manual-EN.pdf")}
COVER = os.path.join(HERE, "cover.jpg")
AUTHOR = "Franck Fornasari (Kraran)"

# colours of the v1.1.0 manuals
BG = HexColor("#0B0A12")
ORANGE = HexColor("#FF8A1A")
TEXT = HexColor("#F2F0F6")
MUTED = HexColor("#B8B6BC")
RULE = HexColor("#3A3048")
HEAD_ROW = HexColor("#2A1848")
ROW_A = HexColor("#16121F")
ROW_B = HexColor("#1E1830")
CODE_TXT = HexColor("#E0A060")
CODE_BG = HexColor("#120F1A")

PAGE_W, PAGE_H = A4
MARGIN = 51
TOP = 58
BOTTOM = 62

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=14.2, textColor=TEXT, spaceAfter=3)
NOTE = ParagraphStyle("note", parent=BODY, fontName="Helvetica-Oblique", fontSize=8.6, leading=12, textColor=MUTED)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=13, bulletIndent=3, spaceAfter=2)
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=ORANGE, spaceBefore=11,
                    spaceAfter=5)
H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.6, leading=14, textColor=TEXT, spaceBefore=6,
                    spaceAfter=2)
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.8, leading=10, textColor=TEXT)
CELL_HEAD = ParagraphStyle("cellh", parent=CELL, fontName="Helvetica-Bold")
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=11.5, textColor=CODE_TXT, leftIndent=4)
TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=ORANGE,
                       alignment=TA_CENTER)
CLOSING = ParagraphStyle("closing", parent=NOTE, fontSize=9.4, textColor=TEXT, alignment=TA_CENTER)


def check_chars(text, where):
    """The standard fonts are drawn in Windows-1252: anything else would be a black box in the PDF."""
    for n, line in enumerate(text.splitlines(), 1):
        for ch in line:
            try:
                ch.encode("cp1252")
            except UnicodeEncodeError:
                raise SystemExit("%s:%d: the character %r (U+%04X) has no glyph in the PDF fonts" % (where, n, ch, ord(ch)))


def inline(text):
    """Escape a line and turn **bold**, *italic* and `code` into ReportLab markup."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" color="#E0A060">\1</font>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return text


def parse(path):
    """The metadata and the list of blocks of a source file."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    check_chars(raw, os.path.basename(path))
    meta, blocks, cur, code = {}, [], [], None

    def flush():
        if cur:
            blocks.append(list(cur))
            cur.clear()

    for line in raw.splitlines():
        if code is not None:
            if line.strip() == "```":
                blocks.append(["```"] + code)
                code = None
            else:
                code.append(line)
            continue
        if line.strip() == "```":
            flush()
            code = []
            continue
        if line.startswith("@") and not blocks and not cur and " " in line:
            k, v = line[1:].split(" ", 1)
            if k != "cols":
                meta[k] = v.strip()
                continue
        if not line.strip():
            flush()
            continue
        kind = _kind(line)
        if kind in ("h1", "h3", "break"):
            flush()
            blocks.append([line.rstrip()])
            continue
        if cur:
            prev = _kind(cur[0])
            same = (prev == kind or (prev == "cols" and kind == "table")
                    or (prev in ("bullet", "note") and kind == "text"))
            if not same or kind == "cols":
                flush()
        cur.append(line.rstrip())
    flush()
    return meta, blocks


def _kind(line):
    """The kind of a source line: a heading starts its own block, a change of kind starts a new one."""
    if line.startswith("# "):
        return "h1"
    if line.startswith("### "):
        return "h3"
    if line.strip() == "===":
        return "break"
    if line.startswith("@cols"):
        return "cols"
    if line.startswith("|"):
        return "table"
    if line.startswith("- "):
        return "bullet"
    if line.startswith("> "):
        return "note"
    return "text"


def table(rows, cols):
    width = PAGE_W - 2 * MARGIN
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    n = max(len(r) for r in cells)
    cells = [r + [""] * (n - len(r)) for r in cells]
    if not cols or len(cols) != n:
        cols = [100.0 / n] * n
    widths = [width * c / sum(cols) for c in cols]
    data = [[Paragraph(inline(c), CELL_HEAD if i == 0 else CELL) for c in r] for i, r in enumerate(cells)]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), HEAD_ROW), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 4.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.2),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    for i in range(1, len(data)):
        style.append(("BACKGROUND", (0, i), (-1, i), ROW_A if i % 2 else ROW_B))
    t.setStyle(TableStyle(style))
    return t


def flowables(meta, blocks):
    story = [NextPageTemplate("content"), PageBreak(),
             HRFlowable(width="100%", thickness=2, color=ORANGE, spaceBefore=0, spaceAfter=6),
             Paragraph(inline(meta.get("header", "PHENIX REBIRTH")), TITLE),
             HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=8, spaceAfter=4)]
    cols = None
    for b in blocks:
        first = b[0]
        if first == "```":
            lines = [inline(x) if x.strip() else " " for x in b[1:]]
            p = Paragraph("<br/>".join(x.replace(" ", "&nbsp;") for x in lines), CODE)
            box = Table([[p]], colWidths=[PAGE_W - 2 * MARGIN])
            box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODE_BG), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            story += [box, Spacer(1, 4)]
        elif first == "===":
            story.append(PageBreak())
        elif first.startswith("@cols"):
            cols = [float(x) for x in first.split(None, 1)[1].split(",")]
            if len(b) > 1:
                story += [table(b[1:], cols), Spacer(1, 5)]
                cols = None
        elif first.startswith("|"):
            story += [table(b, cols), Spacer(1, 5)]
            cols = None
        elif first.startswith("# "):
            story += [CondPageBreak(90), Paragraph(inline(first[2:]), H1)]
            if len(b) > 1:
                story.append(Paragraph(inline(" ".join(b[1:])), BODY))
        elif first.startswith("### "):
            story += [CondPageBreak(60), Paragraph(inline(first[4:]), H3)]
            if len(b) > 1:
                story.append(Paragraph(inline(" ".join(b[1:])), BODY))
        elif first.startswith("- "):
            items, cur = [], []
            for x in b:
                if x.startswith("- "):
                    if cur:
                        items.append(" ".join(cur))
                    cur = [x[2:]]
                else:
                    cur.append(x.strip())
            items.append(" ".join(cur))
            for it in items:
                story.append(Paragraph(inline(it), BULLET, bulletText="\u2022"))
            story.append(Spacer(1, 2))
        elif first.startswith("> "):
            story.append(Paragraph(inline(" ".join(x[2:] if x.startswith("> ") else x for x in b)), NOTE))
        else:
            story.append(Paragraph(inline(" ".join(b)), BODY))
    # a heading never stays alone at the bottom of a page, and a short table is never cut in two: a conditional page
    # break asks for the room of the heading and of (the start of) what follows it
    width = PAGE_W - 2 * MARGIN
    kept = []
    for i, f in enumerate(story):
        if isinstance(f, CondPageBreak):
            continue
        need = None
        if isinstance(f, Paragraph) and f.style in (H1, H3):
            need = f.wrap(width, PAGE_H)[1] + f.style.spaceBefore
            nxt = story[i + 1] if i + 1 < len(story) else None
            if nxt is not None:
                h = nxt.wrap(width, PAGE_H)[1]
                need += h if (isinstance(nxt, Table) and h < 330) else min(h, 60)
        elif isinstance(f, Table) and not (i and isinstance(story[i - 1], Paragraph) and story[i - 1].style in (H1, H3)):
            h = f.wrap(width, PAGE_H)[1]
            if h < 330:
                need = h
        if need:
            kept.append(CondPageBreak(need + 4))
        kept.append(f)
    story = kept
    if meta.get("closing"):
        story.append(KeepTogether([HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=14, spaceAfter=10),
                                   Paragraph(inline(meta["closing"]), CLOSING)]))
    return story


def build(lang):
    src, out = OUTPUTS[lang]
    meta, blocks = parse(os.path.join(HERE, src))
    out_path = os.path.join(DOCS, out)
    footer = meta.get("footer", "Phenix Rebirth")

    def background(c):
        c.setFillColor(BG)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    def foot(c, doc):
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN, BOTTOM - 22, PAGE_W - MARGIN, BOTTOM - 22)
        c.setFont("Helvetica", 7)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, BOTTOM - 34, footer)
        c.drawRightString(PAGE_W - MARGIN, BOTTOM - 34, str(doc.page))

    def on_cover(c, doc):
        c.saveState()
        background(c)
        img = ImageReader(COVER)
        iw, ih = img.getSize()
        w = 354.0
        h = w * ih / iw
        x, y = (PAGE_W - w) / 2, PAGE_H - 84 - h
        c.drawImage(img, x, y, w, h)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(PAGE_W / 2, y - 28, meta.get("cover_title", ""))
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.6)
        c.drawCentredString(PAGE_W / 2, y - 44, meta.get("cover_version", ""))
        c.setFont("Helvetica", 7.6)
        c.drawCentredString(PAGE_W / 2, y - 58, meta.get("cover_tag", ""))
        foot(c, doc)
        c.restoreState()

    def on_page(c, doc):
        c.saveState()
        background(c)
        if doc.page > 2:
            c.setStrokeColor(RULE)
            c.setLineWidth(0.5)
            c.line(MARGIN, PAGE_H - TOP + 14, PAGE_W - MARGIN, PAGE_H - TOP + 14)
        foot(c, doc)
        c.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=A4, title=meta.get("pdf_title", ""), author=AUTHOR,
                          subject=meta.get("pdf_subject", ""), creator="docs/manual/build_manual.py",
                          leftMargin=MARGIN, rightMargin=MARGIN, topMargin=TOP, bottomMargin=BOTTOM)
    frame = Frame(MARGIN, BOTTOM, PAGE_W - 2 * MARGIN, PAGE_H - TOP - BOTTOM, id="f", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("cover", [frame], onPage=on_cover),
                          PageTemplate("content", [frame], onPage=on_page)])
    doc.build([Spacer(1, 1)] + flowables(meta, blocks))
    return out_path


def main(argv):
    langs = [a.lower() for a in argv] or list(OUTPUTS)
    for lang in langs:
        if lang not in OUTPUTS:
            raise SystemExit("unknown language %r (fr, en)" % lang)
        print(build(lang))


if __name__ == "__main__":
    main(sys.argv[1:])
