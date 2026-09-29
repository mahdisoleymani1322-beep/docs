#!/usr/bin/env python3
"""رندر قطعی document.json ← Markdown.

چرا: Markdown هرگز دستی نوشته نمی‌شود (docs/۰۱-معماری.md). هر عدد فقط یک جا در data است و بلوک ref آن را
در جای خودش جدول می‌کند؛ پس متن و جدول نمی‌توانند با هم تناقض داشته باشند. رندر قطعی است: JSON یکسان ← Markdown یکسان.
شناسه‌ی هر بخش به‌صورت توضیح HTML (<!-- section: S01 -->) می‌آید: برای انسان پنهان، برای داور قابل استناد.

  render.py <run> --version n                 runs/<run>/document.v<n>.json ← document.v<n>.md
  render.py --doc <file.json> [--claims f] [-o out.md]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import common

TYPE_FA = {"fact": "واقعی", "assumption": "فرض", "target": "هدف"}
KIND_FA = {"one_time": "یک‌باره", "recurring": "دوره‌ای"}
DATA_ORDER = ("deliverables", "acceptance", "pricing", "payments", "timeline", "metrics", "risks", "roles", "unknowns")
DATA_TITLE = {"deliverables": "تحویل‌دادنی‌ها", "acceptance": "معیار پذیرش", "pricing": "قیمت", "payments": "پرداخت",
              "timeline": "برنامه", "metrics": "شاخص‌ها", "risks": "ریسک‌ها", "roles": "نقش‌ها", "unknowns": "موارد نامعلوم"}


def cell(value) -> str:
    if value is None:
        return "—"
    return str(value).replace("\n", " ").replace("|", "\\|").strip() or "—"


def table(columns: list[str], rows: list[list], caption: str | None = None) -> list[str]:
    out = [f"**{caption}**", ""] if caption else []
    out.append("| " + " | ".join(columns) + " |")
    out.append("|" + "---|" * len(columns))
    for r in rows:
        out.append("| " + " | ".join(cell(c) for c in r) + " |")
    return out + [""]


def fa(v) -> str:
    return "[نامعلوم]" if v is None else common.to_fa_digits(v)


def render_data(kind: str, data: dict, currency: str | None, caption: str | None) -> list[str]:
    if kind == "deliverables":
        return table(["شناسه", "تحویل", "شرح", "قالب", "موعد", "پذیرش"],
                     [[d["id"], d["title"], d["detail"], d["format"], d["due"], d["acceptance"] or "[بدون معیار پذیرش]"]
                      for d in data["deliverables"]], caption)
    if kind == "acceptance":
        return table(["شناسه", "تحویل", "آزمون", "داده", "آستانه", "خطای بحرانی", "بازبین", "فرصت اصلاح", "بازآزمون"],
                     [[a["id"], a["deliverable"], a["test"], a.get("data"), a["threshold"], a.get("critical_error"),
                       a["reviewer"], a["fix_window"], a.get("retest")] for a in data["acceptance"]], caption)
    if kind == "pricing":
        p = data["pricing"]
        cur = p["currency"] or currency or ""
        rows = [[i["id"], i["title"], i["basis"], KIND_FA[i["kind"]], i.get("period"), common.fa_number(i["amount"]), i.get("note")]
                for i in p["items"]]
        out = table(["شناسه", "قلم", "مبنا", "نوع", "دوره", f"مبلغ ({cur})", "توضیح"], rows, caption)
        out += [f"- **جمع یک‌باره:** {common.fa_number(p['totals']['one_time'])} {cur}",
                f"- **جمع دوره‌ای:** {common.fa_number(p['totals']['recurring'])} {cur}",
                f"- **مالیات:** {p['tax_note']}"]
        if p.get("usage_cap"):
            out.append(f"- **سقف مصرف:** {p['usage_cap']}")
        for c in p.get("separate_costs", []):
            out.append(f"- **هزینه‌ی جدا:** {c}")
        if p.get("tariff_assumption"):
            out.append(f"- **فرض تعرفه:** {p['tariff_assumption']}")
        out.append(f"- **اعتبار قیمت:** {p['validity'] or '[نامعلوم]'}")
        return out + [""]
    if kind == "payments":
        return table(["شناسه", "رویداد پرداخت", "تحویل مرتبط", "درصد"],
                     [[x["id"], x["event"], x.get("deliverable"), common.to_fa_digits(x["percent"]) + "٪"]
                      for x in data["pricing"]["payments"]], caption)
    if kind == "timeline":
        return table(["شناسه", "مرحله", "پیش‌نیاز", "مدت (روز کاری)", "خروجی", "تأییدکننده", "اثر تأخیر"],
                     [[t["id"], t["stage"], t["prerequisite"], fa(t["duration_workdays"]), t["output"], t["approver"],
                       t["delay_effect"]] for t in data["timeline"]], caption)
    if kind == "metrics":
        return table(["شناسه", "شاخص", "فرمول", "خط مبنا", "هدف", "دوره", "روش سنجش", "مالک"],
                     [[m["id"], m["name"], m.get("formula"), m["baseline"], m["target"], m["period"], m["method"], m["owner"]]
                      for m in data["metrics"]], caption)
    if kind == "risks":
        return table(["شناسه", "محرک", "اثر", "کنترل", "مالک", "مسیر جایگزین"],
                     [[r["id"], r["trigger"], r["effect"], r["control"], r["owner"], r["fallback"]] for r in data["risks"]], caption)
    if kind == "roles":
        return table(["کار", "مجری", "تأییدکننده", "زمان پاسخ"],
                     [[r["task"], r["executor"], r["approver"], r["response_time"]] for r in data["roles"]], caption)
    if kind == "unknowns":
        return table(["شناسه", "مورد", "سؤال", "مالک", "موعد"],
                     [[u["id"], u["item"], u["question"], u["owner"], u["due"]] for u in data["unknowns"]], caption)
    raise ValueError(kind)


def _is_empty(kind: str, data: dict) -> bool:
    if kind == "pricing":
        return not data["pricing"]["items"]
    if kind == "payments":
        return not data["pricing"]["payments"]
    return not data[kind]


def render(doc: dict, claims: dict | None = None) -> str:
    m = doc["meta"]
    cal = {"jalali": "شمسی", "gregorian": "میلادی"}[m["calendar"]]
    out = ['<div dir="rtl">', "", f"# {m['title']}", ""]
    if m["sample"]:
        out += ["> **نمونه:** داده‌ی نمایشی؛ مشتری، عدد و نتیجه واقعی نیستند.", ""]
    out += table(["شناسه", "ویرایش", "تاریخ", "اعتبار", "وضعیت"],
                 [[m["doc_id"], common.to_fa_digits(m["revision"]), f"{m['date']} ({cal})", m.get("valid_until"), m["status_note"]]])
    out += [f"**برای:** {m['client_name']}" + (f" · **تهیه‌کننده:** {m['prepared_by']}" if m.get("prepared_by") else ""), ""]

    referenced = set()
    for i, sec in enumerate(doc["sections"], 1):
        out += [f"## {common.to_fa_digits(i)}. {sec['title']}", f"<!-- section: {sec['id']} -->", ""]
        for b in sec["blocks"]:
            k = b["kind"]
            if k == "para":
                out += [b["text"], ""]
            elif k == "list":
                out += [(f"{j}. " if b.get("ordered") else "- ") + item for j, item in enumerate(b["items"], 1)] + [""]
            elif k == "table":
                out += table(b["columns"], b["rows"], b.get("caption"))
            elif k == "callout":
                out += [f"> **{b['title']}:** {b['text']}" if b.get("title") else f"> {b['text']}", ""]
            elif k == "ref":
                referenced.add(b["data"])
                out += render_data(b["data"], doc["data"], m.get("currency"), b.get("caption"))

    # هر جدول ساخت‌یافته‌ای که در متن ارجاع نشده، در پیوست می‌آید تا داور و انسان همه‌ی داده را ببینند
    leftover = [k for k in DATA_ORDER if k not in referenced and not _is_empty(k, doc["data"])]
    if leftover:
        out += ["## پیوست: جدول‌های تکمیلی", "<!-- section: APPENDIX -->", ""]
        for k in leftover:
            out += render_data(k, doc["data"], m.get("currency"), DATA_TITLE[k])

    if claims and claims["claims"]:
        out += ["## پیوست: دفتر ادعا", "<!-- section: CLAIMS -->", ""]
        rows = []
        for c in claims["claims"]:
            src = c["source"]
            src_txt = "—" if not src else f"{src['kind']}: {src['ref']}" + (f" ({src['date']})" if src.get("date") else "")
            rows.append([c["id"], c["text"], TYPE_FA[c["type"]], src_txt])
        out += table(["شناسه", "ادعا", "نوع", "منبع"], rows)

    out += ["</div>", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?")
    ap.add_argument("--version", type=int)
    ap.add_argument("--doc")
    ap.add_argument("--claims")
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    if args.doc:
        doc_path = pathlib.Path(args.doc)
        claims_path = pathlib.Path(args.claims) if args.claims else None
        out_path = pathlib.Path(args.out) if args.out else None
    else:
        if args.version is None:
            common.fail("--version لازم است")
        run_dir = common.resolve_run(args.run)
        doc_path = run_dir / f"document.v{args.version}.json"
        claims_path = run_dir / "claims.json"
        out_path = run_dir / f"document.v{args.version}.md"
    doc = common.load_json(doc_path)
    errors = common.schema_errors(doc, "document")
    if errors:
        common.fail(f"{doc_path} با schema نمی‌خواند؛ رندر نمی‌شود:\n" + "\n".join(errors[:10]))
    claims = common.load_json(claims_path) if claims_path and claims_path.exists() else None
    text = render(doc, claims)
    if out_path:
        out_path.write_text(text, encoding="utf-8")
        print(out_path)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
