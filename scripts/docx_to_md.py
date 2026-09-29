#!/usr/bin/env python3
"""استخراج متن docx به Markdown ساده، فقط با کتابخانه‌ی استاندارد.

چرا: ایجنت‌ها docx را نمی‌خوانند و برند گاید docx است. تیترها ← ##، هر ردیف جدول ← یک خط با جداکننده‌ی |.
قالب‌بندی بصری حذف می‌شود؛ منبع اصلی همان docx است و این فایل فقط نسخه‌ی قابل خواندن آن است.

  docx_to_md.py <in.docx> > out.md
"""
from __future__ import annotations

import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def para_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(W + "t")).strip()


def style(p) -> str:
    s = p.find(f"{W}pPr/{W}pStyle")
    return s.get(W + "val") if s is not None else ""


def cell_text(tc) -> str:
    parts = []
    for child in tc:
        if child.tag == W + "p":
            t = para_text(child)
            if t:
                parts.append(t)
        elif child.tag == W + "tbl":
            parts.extend(line.strip("| ") for line in table_lines(child))
    return " · ".join(parts)


def table_lines(tbl) -> list[str]:
    lines = []
    for tr in tbl.findall(W + "tr"):
        cells = [cell_text(tc) for tc in tr.findall(W + "tc")]
        cells = [c for c in cells if c]
        if cells:
            lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return lines


def convert(path: str) -> str:
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    body = root.find(W + "body")
    out = []
    for el in body:
        if el.tag == W + "p":
            t = para_text(el)
            if not t:
                continue
            st = style(el)
            if st.startswith("Heading"):
                level = st[len("Heading"):] or "2"
                out += ["", "#" * (int(level) + 1 if level.isdigit() else 2) + " " + t, ""]
            else:
                out.append(t)
        elif el.tag == W + "tbl":
            out += [""] + table_lines(el) + [""]
    text = "\n".join(out)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.stdout.write(convert(sys.argv[1]))
