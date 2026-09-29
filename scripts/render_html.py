#!/usr/bin/env python3
"""رندر قطعی document.json ← HTML طراحی‌شده‌ی برند (A4، راست‌به‌چپ، آماده‌ی چاپ).

چرا از Markdown می‌سازد: متن HTML باید عیناً همان متنی باشد که داورها دیده‌اند. پس document.json ← render.render() ←
Markdown، و این اسکریپت فقط همان زیرمجموعه‌ی Markdown را به اجزای DESIGN.md نگاشت می‌کند (نه یک رندر دوم از JSON).
رنگ، اندازه و فاصله فقط از DESIGN.md می‌آید (design_tokens.py)؛ لوگو و مجوز جای آن از کارت برند.
فونت و لوگو داخل فایل می‌نشینند، پس HTML مستقل است و در چاپ هم همان می‌ماند.

  render_html.py --doc <file.json> [--claims f] [--brand id] [-o out.html]
  render_html.py <run> --version n            runs/<run>/document.v<n>.html
"""
from __future__ import annotations

import argparse
import base64
import html
import pathlib
import re
import sys

import common
import design_tokens
import render

FONT_DIR = common.ROOT / "brand" / "assets" / "fonts"
FONT_WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}
WIDE_TABLE_COLUMNS = 9  # از این تعداد ستون به بالا صفحه‌ی افقی؛ با ۸ ستون هنوز در A4 عمودی خوانا است (دیده شد)
ID_CELL = re.compile(r"^[A-Z]{1,3}-[0-9]{2,3}$")


def _b64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def font_face_css() -> str:
    return "".join(
        "@font-face { font-family: Vazirmatn; font-style: normal; font-weight: %d; "
        "src: url(data:font/woff2;base64,%s) format('woff2'); }\n" % (w, _b64(FONT_DIR / f"Vazirmatn-{n}.woff2"))
        for w, n in FONT_WEIGHTS.items())


def logo_data_uri(brand: dict) -> str:
    """فایل اصلی (WebP) از کارت برند؛ قواعد جا و اندازه در brand/LOGO.md."""
    f = next(f for f in brand["assets"]["logo"]["files"] if f["format"] == "webp")
    return "data:image/webp;base64," + _b64(common.ROOT / f["path"])


# ---------------------------------------------------------------- Markdown ← HTML

def inline(text: str) -> str:
    t = html.escape(text.replace("\\|", "|"), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # مجهول عمداً دیده می‌شود (DESIGN.md: unknown-marker)؛ ارجاع ادعا ریز و بی‌سروصدا (claim-ref)
    t = re.sub(r"\[(نامعلوم[^\]]*|بدون پشتوانه|بدون معیار پذیرش)\]", r'<span class="c-unknown-marker">[\1]</span>', t)
    t = re.sub(r"\[(C-[0-9]{2,3})\]", r'<span class="c-claim-ref">[\1]</span>', t)
    return t


def split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
    return [c.strip() for c in cells]


def table_html(rows: list[list[str]], caption: str | None, meta: bool = False) -> str:
    head, body = rows[0], rows[1:]
    wide = len(head) >= WIDE_TABLE_COLUMNS
    # ستون شناسه (K-01) نباید وسط خط تیره بشکند؛ فقط وقتی همه‌ی سلول‌های ستون اول شناسه‌اند
    id_col = bool(body) and all(ID_CELL.match(r[0]) for r in body)
    out = [f'<figure class="tbl{" wide" if wide else ""}{" meta" if meta else ""}">']
    if caption:
        out.append(f"<figcaption>{inline(caption)}</figcaption>")
    nowrap = lambda j: ' data-nowrap' if id_col and j == 0 else ""  # noqa: E731
    out.append("<table><thead><tr>" + "".join(f'<th class="c-table-header"{nowrap(j)}>{inline(c)}</th>'
                                              for j, c in enumerate(head)) + "</tr></thead><tbody>")
    for i, r in enumerate(body):
        cls = "c-table-row-alt" if i % 2 else "c-table-row"
        out.append("<tr>" + "".join(f'<td class="{cls}"{nowrap(j)}>{inline(c)}</td>' for j, c in enumerate(r)) + "</tr>")
    out.append("</tbody></table></figure>")
    return "".join(out)


def quote_html(text: str) -> str:
    """نقل‌قول‌های Markdown ← اجزای DESIGN.md بر پایه‌ی برچسب پررنگ اولشان."""
    if text.startswith("**نمونه:**"):
        return f'<aside class="c-sample-banner box">{inline(text)}</aside>'
    if text.startswith("**هزینه در برابر منفعت:**"):
        label, rest = text.split("**", 2)[1], text.split("**", 2)[2]
        return (f'<aside class="c-cost-benefit-block box"><strong class="c-cost-benefit-positive">{inline(label)}</strong>'
                f"{inline(rest)}</aside>")
    if text.startswith("**هشدار:**"):
        return f'<aside class="c-cost-benefit-caveat note">{inline(text)}</aside>'
    return f'<aside class="c-callout box">{inline(text)}</aside>'


def body_html(md: str) -> tuple[str, str, str]:
    """(عنوان، HTML جلد، HTML بدنه). جلد = هرچه پیش از اولین «## » می‌آید."""
    lines = [l for l in md.splitlines() if l.strip() not in ('<div dir="rtl">', "</div>")]
    title = next(l[2:].strip() for l in lines if l.startswith("# "))
    cover, main, cur = [], [], None
    cur = cover
    i, pending_caption, para = 0, None, []

    def flush():
        if para:
            cur.append(f'<p class="c-body-text">{inline(" ".join(para))}</p>')
            para.clear()

    while i < len(lines):
        l = lines[i]
        if l.startswith("# "):
            flush()
        elif l.startswith("## "):
            flush()
            cur = main
            cur.append(f'<h2 class="c-section-heading">{inline(l[3:].strip())}</h2>')
        elif re.match(r"^<!-- section: [A-Z0-9]+ -->$", l.strip()):
            flush()
        elif l.startswith("|"):
            flush()
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            rows = [split_row(r) for r in block if not re.fullmatch(r"\|(-+\|)+", r.strip())]
            cur.append(table_html(rows, pending_caption, meta=cur is cover))
            pending_caption = None
            continue
        elif re.fullmatch(r"\*\*[^*]+\*\*", l.strip()):
            flush()
            pending_caption = l.strip()[2:-2]
        elif l.startswith(">"):
            flush()
            text = []
            while i < len(lines) and lines[i].startswith(">"):
                text.append(lines[i][1:].strip())
                i += 1
            cur.append(quote_html(" ".join(text)))
            continue
        elif re.match(r"^(- |[0-9]+\. )", l):
            flush()
            ordered = bool(re.match(r"^[0-9]+\. ", l))
            items = []
            while i < len(lines) and re.match(r"^(- |[0-9]+\. )", lines[i]):
                items.append(re.sub(r"^(- |[0-9]+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            cur.append(f'<{tag} class="c-body-text">' + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        elif not l.strip():
            flush()
        else:
            para.append(l.strip())
        i += 1
    flush()
    return title, "\n".join(cover), "\n".join(main)


# ---------------------------------------------------------------- صفحه

def page_css(tokens: dict, title: str) -> str:
    c = tokens["colors"]
    sp = tokens["spacing"]
    ph = design_tokens.resolve(tokens, tokens["components"]["page-header"]["typography"])
    esc = title.replace("\\", "\\\\").replace('"', '\\"')
    side = tokens["layout"]["safe-area-max"]  # درصد عرض؛ V2: حاشیه‌ی امن ۵ تا ۷٪
    return f"""{design_tokens.css_variables(tokens)}
@page {{ size: A4; background: {c['canvas']}; margin: 24mm {side}% 22mm {side}%;
  @top-right {{ content: "مهدیار / رشد هوشمند"; font: {ph['fontWeight']} {ph['fontSize']} {ph['fontFamily']}; color: {c['ink']}; }}
  @top-left {{ content: "{esc}"; font: 400 {ph['fontSize']} {ph['fontFamily']}; color: {c['body']}; }}
  @bottom-center {{ content: counter(page, persian); font: 400 {ph['fontSize']} {ph['fontFamily']}; color: {c['body']}; }}
}}
@page :first {{ margin: {side}%; @top-right {{ content: none; }} @top-left {{ content: none; }} @bottom-center {{ content: none; }} }}
@page wide {{ size: A4 landscape; }}
* {{ box-sizing: border-box; }}
html {{ background: {c['canvas']}; }}
body {{ margin: 0; direction: rtl; }}
main {{ max-width: 210mm; margin: 0 auto; }}
.cover {{ break-after: page; min-height: 250mm; }}
.cover .logo {{ display: block; width: 50mm; min-width: 200px; margin: 0 0 {sp['3xl']}px 0; }}
.cover h1 {{ margin: 0 0 {sp['l']}px; font: inherit; }}
.cover .c-body-text {{ margin: {sp['m']}px 0; }}
h2 {{ margin: {sp['2xl']}px 0 {sp['m']}px; break-after: avoid; }}
p, ul, ol {{ margin: 0 0 {sp['m']}px; }}
ul, ol {{ padding-inline-start: {sp['l']}px; }}
li {{ margin-bottom: {sp['xs']}px; }}
.tbl {{ margin: 0 0 {sp['l']}px; }}
.tbl.wide {{ page: wide; }}
figcaption {{ font-weight: 600; color: {c['ink']}; margin-bottom: {sp['s']}px; break-after: avoid; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: {sp['s']}px {sp['s']}px; text-align: right; vertical-align: top; border-bottom: 1px solid {c['border-sand']}; overflow-wrap: anywhere; }}
th {{ font-weight: 600; }}
tr {{ break-inside: avoid; }}
.cover table td {{ background: transparent; color: {c['body']}; }}
[data-nowrap], .meta th, .meta td {{ white-space: nowrap; }}
.meta th:last-child, .meta td:last-child {{ white-space: normal; }}
.box {{ padding: {sp['m']}px; margin: 0 0 {sp['m']}px; border: 1px solid {c['border-sand']}; }}
.note {{ margin: 0 0 {sp['l']}px; }}
.c-unknown-marker {{ padding: 0 {sp['xs']}px; }}
.c-claim-ref {{ font-size: 0.75em; }}
.closing {{ margin-top: {sp['4xl']}px; break-inside: avoid; }}
.closing img {{ display: block; width: 40mm; min-width: 200px; }}
@media screen {{ main {{ padding: {sp['xl']}px {sp['m']}px; }} }}
@media print {{ main {{ max-width: none; }} }}
@media print {{ .c-cover, .c-table-row, .c-table-row-alt, .c-table-header, .c-callout, .c-unknown-marker, .c-sample-banner
  {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
"""


def build(doc: dict, claims: dict | None, brand: dict) -> str:
    md = render.render(doc, claims)
    title, cover, main = body_html(md)
    tokens = design_tokens.load()
    logo = logo_data_uri(brand)
    # لوگوی پایانی در انتهای بدنه (گام بعد و تماس) می‌نشیند، نه بعد از پیوست‌ها؛ وگرنه پیوستِ پرِ صفحه آن را تنها به صفحه‌ی بعد می‌راند
    marker = '<h2 class="c-section-heading">پیوست'
    cut = main.find(marker)
    main_before, appendix = (main, "") if cut == -1 else (main[:cut], main[cut:])
    alt = f"لوگوی {brand['name_fa']}"
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
{font_face_css()}{page_css(tokens, title)}
{design_tokens.component_css(tokens)}</style>
</head>
<body class="c-body-text">
<main>
<section class="cover c-cover">
<img class="logo" src="{logo}" alt="{html.escape(alt)}">
<h1>{html.escape(title)}</h1>
{cover}
</section>
{main_before}
<footer class="closing"><img src="{logo}" alt="{html.escape(alt)}"></footer>
{appendix}
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?")
    ap.add_argument("--version", type=int)
    ap.add_argument("--doc")
    ap.add_argument("--claims")
    ap.add_argument("--brand")
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    if args.doc:
        doc_path = pathlib.Path(args.doc)
        claims_path = pathlib.Path(args.claims) if args.claims else None
        out_path = pathlib.Path(args.out) if args.out else doc_path.with_suffix(".html")
        brand_id = args.brand
    else:
        if args.version is None:
            common.fail("--version لازم است")
        run_dir = common.resolve_run(args.run)
        doc_path = run_dir / f"document.v{args.version}.json"
        claims_path = run_dir / "claims.json"
        out_path = run_dir / f"document.v{args.version}.html"
        brand_id = args.brand or common.load_json(run_dir / "run.json").get("brand")
    doc = common.load_json(doc_path)
    errors = common.schema_errors(doc, "document")
    if errors:
        common.fail(f"{doc_path} با schema نمی‌خواند؛ رندر نمی‌شود:\n" + "\n".join(errors[:10]))
    claims = common.load_json(claims_path) if claims_path and claims_path.exists() else None
    out_path.write_text(build(doc, claims, common.load_brand(brand_id)), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
