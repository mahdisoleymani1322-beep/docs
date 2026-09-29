#!/usr/bin/env python3
"""خواندن توکن‌های DESIGN.md (front matter به سبک YAML) بدون کتابخانه‌ی بیرونی.

چرا: DESIGN.md تنها منبع توکن‌های طراحی است و خروجی‌ساز (render_html.py) و آزمون‌ها هر دو از آن می‌خوانند.
پشتیبانی عمداً محدود به زیرمجموعه‌ای است که DESIGN.md استفاده می‌کند: نگاشت تو‌در‌تو با تورفتگی دو فاصله،
مقدار عدد یا رشته (با یا بی نقل‌قول)، توضیح با #. فهرست پشتیبانی نمی‌شود و خطا می‌دهد.

  design_tokens.py [DESIGN.md]            توکن‌ها به JSON
  design_tokens.py --css [DESIGN.md]      متغیرهای CSS (--mh-color-*، --mh-space-* …)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "DESIGN.md"
REF = re.compile(r"^\{([a-z0-9-]+)\.([a-z0-9-]+)\}$")


def _scalar(raw: str):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if re.fullmatch(r"-?[0-9]+", raw):
        return int(raw)
    if re.fullmatch(r"-?[0-9]*\.[0-9]+", raw):
        return float(raw)
    if raw in ("true", "false"):
        return raw == "true"
    return raw


def _strip_comment(raw: str) -> str:
    # «#» داخل نقل‌قول بخشی از مقدار است (رنگ hex)، نه توضیح
    raw = raw.strip()
    if raw and raw[0] in "\"'":
        end = raw.find(raw[0], 1)
        if end == -1:
            raise ValueError(f"نقل‌قول بسته نشده: {raw!r}")
        return raw[:end + 1]
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def parse_front_matter(text: str) -> dict:
    if not text.startswith("---\n"):
        raise ValueError("DESIGN.md باید با front matter (---) شروع شود")
    block = text[4: text.index("\n---", 4)]
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for n, line in enumerate(block.splitlines(), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- "):
            raise ValueError(f"خط {n}: فهرست YAML پشتیبانی نمی‌شود")
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            raise ValueError(f"خط {n} قابل‌خواندن نیست: {line!r}")
        key, value = m.group(1), _strip_comment(m.group(2))
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            parent[key] = {}
            stack.append((indent, parent[key]))
        else:
            parent[key] = _scalar(value)
    return root


def resolve(tokens: dict, value):
    """«{colors.ink}» ← مقدار واقعی؛ ارجاع ناموجود خطاست (پیشگیری از رنگ خیالی)."""
    if isinstance(value, str):
        m = REF.match(value)
        if m:
            group, name = m.groups()
            if group not in tokens or name not in tokens[group]:
                raise KeyError(f"ارجاع ناموجود: {value}")
            return resolve(tokens, tokens[group][name])
    return value


def load(path: pathlib.Path | str = DESIGN) -> dict:
    return parse_front_matter(pathlib.Path(path).read_text(encoding="utf-8"))


def luminance(hex_color: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    """نسبت کنتراست WCAG 2؛ هم آزمون‌ها و هم خروجی‌ساز از همین یک تعریف استفاده می‌کنند."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def css_variables(tokens: dict) -> str:
    lines = [":root {"]
    for name, hexv in tokens["colors"].items():
        lines.append(f"  --mh-color-{name}: {hexv};")
    for name, v in tokens["spacing"].items():
        lines.append(f"  --mh-space-{name}: {v}px;")
    for name, v in tokens["rounded"].items():
        lines.append(f"  --mh-radius-{name}: {v}px;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def component_css(tokens: dict, prefix: str = "c-") -> str:
    """هر جزء components ← یک کلاس (.c-<name>)؛ چیدمان کار خروجی‌ساز است و رنگ و اندازه فقط از DESIGN.md می‌آید."""
    props = {"backgroundColor": "background-color", "textColor": "color", "borderColor": "border-color",
             "rounded": "border-radius"}
    rules = []
    for name, comp in tokens["components"].items():
        decl = []
        for key, css in props.items():
            if key in comp:
                v = resolve(tokens, comp[key])
                decl.append(f"{css}: {v}px" if key == "rounded" else f"{css}: {v}")
        if "typography" in comp:
            t = resolve(tokens, comp["typography"])
            decl += [f"font-family: {t['fontFamily']}", f"font-size: {t['fontSize']}", f"font-weight: {t['fontWeight']}",
                     f"line-height: {t['lineHeight']}"]
        if "height" in comp:
            decl.append(f"min-height: {comp['height']}px")
        rules.append(f".{prefix}{name} {{ " + "; ".join(decl) + "; }")
    return "\n".join(rules) + "\n"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tokens = load(args[0] if args else DESIGN)
    if "--css" in sys.argv:
        sys.stdout.write(css_variables(tokens))
    else:
        print(json.dumps(tokens, ensure_ascii=False, indent=2))
