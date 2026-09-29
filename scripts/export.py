#!/usr/bin/env python3
"""خروجی نهایی سند در فرمت‌هایی که کاربر خواسته (md | html | pdf | docx | pptx).

چرا PDF از Chromium: متن فارسی باید انتخاب‌پذیر و قابل‌جست‌وجو بماند (کمیته‌ی خرید در سند جست‌وجو می‌کند)،
و چیدمان چاپ همان HTML طراحی‌شده است، نه بازسازی دوم. Chromium مستقیم صدا زده می‌شود (بدون پکیج Playwright)
تا وابستگی پروژه فقط پایتون استاندارد + jsonschema بماند.
docx و pptx هنوز ساخته نشده‌اند (ROADMAP H2)؛ درخواستشان خطای صریح می‌دهد، نه رد شدن بی‌صدا.

  export.py --doc <file.json> --formats pdf,html [--claims f] [--brand id] [-o outdir]
  export.py <run> --version n --formats pdf,md
"""
from __future__ import annotations

import argparse
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import common
import render
import render_html

FORMATS = ("md", "html", "pdf", "docx", "pptx")
NOT_BUILT = ("docx", "pptx")


def find_chrome() -> str:
    env = os.environ.get("STUDIO_CHROME")
    if env:
        return env
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if shutil.which(name):
            return shutil.which(name)
    common.fail("Chromium پیدا نشد؛ مسیرش را در STUDIO_CHROME بگذارید")


def html_to_pdf(html_path: pathlib.Path, pdf_path: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory() as profile:
        cmd = [find_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
               f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        common.fail(f"ساخت PDF شکست خورد ({r.returncode}): {r.stderr.strip()[-400:]}")


def export(doc: dict, claims: dict | None, brand: dict, formats: list[str], out_dir: pathlib.Path, stem: str) -> list[pathlib.Path]:
    bad = [f for f in formats if f not in FORMATS]
    if bad:
        common.fail(f"فرمت ناشناخته: {', '.join(bad)}؛ مجاز: {', '.join(FORMATS)}")
    todo = [f for f in formats if f in NOT_BUILT]
    if todo:
        common.fail(f"فرمت {', '.join(todo)} هنوز ساخته نشده (ROADMAP H2)؛ فرمت‌های آماده: md، html، pdf")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if "md" in formats:
        p = out_dir / f"{stem}.md"
        p.write_text(render.render(doc, claims), encoding="utf-8")
        written.append(p)
    if "html" in formats or "pdf" in formats:
        html_path = out_dir / f"{stem}.html"
        html_path.write_text(render_html.build(doc, claims, brand), encoding="utf-8")
        if "html" in formats:
            written.append(html_path)
        if "pdf" in formats:
            pdf_path = out_dir / f"{stem}.pdf"
            html_to_pdf(html_path, pdf_path)
            written.append(pdf_path)
            if "html" not in formats:
                html_path.unlink()  # HTML میانی است؛ کاربر نخواسته
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?")
    ap.add_argument("--version", type=int)
    ap.add_argument("--doc")
    ap.add_argument("--claims")
    ap.add_argument("--brand")
    ap.add_argument("--formats", required=True, help="فهرست جداشده با کاما: md,html,pdf")
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    if args.doc:
        doc_path = pathlib.Path(args.doc)
        claims_path = pathlib.Path(args.claims) if args.claims else None
        out_dir = pathlib.Path(args.out) if args.out else doc_path.parent
        brand_id, stem = args.brand, doc_path.stem
    else:
        if args.version is None:
            common.fail("--version لازم است")
        run_dir = common.resolve_run(args.run)
        doc_path = run_dir / f"document.v{args.version}.json"
        claims_path = run_dir / "claims.json"
        out_dir = pathlib.Path(args.out) if args.out else run_dir / "export"
        brand_id = args.brand or common.load_json(run_dir / "run.json").get("brand")
        stem = f"document.v{args.version}"
    doc = common.load_json(doc_path)
    errors = common.schema_errors(doc, "document")
    if errors:
        common.fail(f"{doc_path} با schema نمی‌خواند؛ خروجی ساخته نمی‌شود:\n" + "\n".join(errors[:10]))
    claims = common.load_json(claims_path) if claims_path and claims_path.exists() else None
    for p in export(doc, claims, common.load_brand(brand_id), formats, out_dir, stem):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
