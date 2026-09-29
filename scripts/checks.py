#!/usr/bin/env python3
"""چک‌های قطعی سند (لایه‌ی ۱ ارزیابی؛ docs/۰۳-سیستم-ارزیابی.md بخش ۱).

چرا کد: شمردن، جمع‌زدن و تطبیق شناسه کار کد است: رایگان، فوری و تکرارپذیر. داور فقط قضاوت می‌کند.
هر چک یک نتیجه‌ی کامل می‌دهد (وضعیت، وزن ایراد، جای مشکل، رد فوری و سقف ردیف)؛ تصمیم نهایی با gate.py است.
سقف‌ها و ردیف‌ها همه از کارت نوع سند می‌آیند، نه از عدد ثابت در این فایل.

  checks.py <run> --version n           document.v<n>.json (یا .md ← حالت متنی) ← checks.v<n>.json
  checks.py --doc f.json|f.md [--claims f] [--brand id] [-o out]

حالت متنی (فقط Markdown): چک‌های ساختاری skip و دلیلشان «سند ساخت‌یافته نیست» ثبت می‌شود.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import common
import render

# ---------------------------------------------------------------- ابزار

ID_KEYS = {"id", "doc_id", "deliverable", "acceptance", "price_ref", "claim", "metric", "gap", "ref", "name", "kind",
           "type", "data", "calendar", "variant", "format"}
VAGUE_EVENT = re.compile(r"(میانه|نیمه|وسط)\s*(ی\s*)?(کار|پروژه)")
TIME_UNIT = re.compile(r"ساعت|دقیقه|روز|هفته|ماه|زمان")
FINAL_LABEL = re.compile(r"(نسخه|سند|پیشنهاد|متن|قرارداد)\s*(ی\s*)?نهایی|آماده\s*(ی\s*)?امضا|\bfinal\b")
CLAIM_REF = re.compile(r"\[(C-[0-9]{2,3})\]")


def result(cid: str, status: str, severity: str, detail: str = "", locations=None, veto=None, caps=None) -> dict:
    return {"id": cid, "status": status, "severity": severity, "detail": detail, "locations": sorted(set(locations or [])),
            "veto": sorted(set(veto or [])), "caps": caps or []}


def skip(cid: str, why: str, severity: str = "critical") -> dict:
    return result(cid, "skip", severity, why)


def cap(criterion: str | None, mx: int) -> list[dict]:
    return [{"criterion": criterion, "max": mx}] if criterion else []


def row_for_section(card: dict, section: str) -> str | None:
    return next((c["id"] for c in card["criteria"] if section in c["sections"]), None)


def text_fields(doc: dict, skip_keys=ID_KEYS) -> list[tuple[str, str]]:
    """رشته‌های سند با مسیرشان؛ فیلدهای شناسه‌ای حذف می‌شوند (کد و شناسه متن مشتری نیستند)."""
    out = []
    for path, value in common.iter_text_fields(doc):
        last = re.sub(r"\[[0-9]+\]", "", path).split(".")[-1]
        if last not in skip_keys:
            out.append((path, value))
    return out


def sec_of(path: str, doc: dict) -> str:
    m = re.match(r"sections\[([0-9]+)\]", path)
    return doc["sections"][int(m.group(1))]["id"] if m else path.split(".")[0] + (("." + path.split(".")[1]) if "." in path else "")


# ---------------------------------------------------------------- چک‌های ساختاری

def block_has_content(b: dict) -> bool:
    """ref همیشه محتواست (جدول ساخت‌یافته)؛ بقیه باید متن یا ردیف غیرخالی داشته باشند."""
    if b["kind"] == "ref":
        return True
    return any(t.strip() for _, t in common.iter_text_fields({k: v for k, v in b.items() if k != "kind"}))


def chk_sections(doc, card):
    have = {s["id"]: s for s in doc["sections"]}
    missing = []
    for s in card["sections"]:
        if not s["required"]:
            continue
        sec = have.get(s["id"])
        blank = sec is None or not any(block_has_content(b) for b in sec["blocks"])
        if blank:
            missing.append(s["id"])
    caps = [{"criterion": c["id"], "max": 0} for c in card["criteria"] if set(c["sections"]) & set(missing)]
    if missing:
        return result("CHK-SECTIONS", "fail", "critical", "بخش الزامی غایب یا خالی: " + "، ".join(missing), missing, caps=caps)
    return result("CHK-SECTIONS", "pass", "critical")


def chk_ids(doc, card):
    data = doc["data"]
    groups = {"D": [x["id"] for x in data["deliverables"]], "A": [x["id"] for x in data["acceptance"]],
              "P": [x["id"] for x in data["pricing"]["items"]] + [x["id"] for x in data["pricing"]["payments"]],
              "T": [x["id"] for x in data["timeline"]], "M": [x["id"] for x in data["metrics"]],
              "K": [x["id"] for x in data["risks"]], "U": [x["id"] for x in data["unknowns"]],
              "S": [s["id"] for s in doc["sections"]]}
    cb = data.get("cost_benefit")
    if cb:
        groups["CC/CB"] = [c["id"] for c in cb["costs"]] + [b["id"] for b in cb["benefits"]]
    dupes = [f"{k}:{i}" for k, ids in groups.items() for i in sorted({x for x in ids if ids.count(x) > 1})]
    if dupes:
        return result("CHK-IDS", "fail", "critical", "شناسه‌ی تکراری: " + "، ".join(dupes), dupes)
    return result("CHK-IDS", "pass", "critical")


def chk_d_a(doc, card):
    acc = {a["id"]: a for a in doc["data"]["acceptance"]}
    dels = {d["id"]: d for d in doc["data"]["deliverables"]}
    bad = []
    for d in dels.values():
        a = acc.get(d["acceptance"])
        if d["acceptance"] is None:
            bad.append(f"{d['id']} بدون معیار پذیرش")
        elif a is None:
            bad.append(f"{d['id']} به معیار ناموجود {d['acceptance']} اشاره می‌کند")
        elif a["deliverable"] != d["id"]:
            bad.append(f"{d['id']} به {a['id']} اشاره می‌کند ولی آن معیار برای {a['deliverable']} است")
    bad += [f"{a['id']} برای تحویل ناموجود {a['deliverable']}" for a in acc.values() if a["deliverable"] not in dels]
    bad += [f"{a['id']} به هیچ تحویلی وصل نیست" for a in acc.values()
            if a["deliverable"] in dels and dels[a["deliverable"]]["acceptance"] != a["id"]]
    if bad:
        return result("CHK-D-A", "fail", "critical", "؛ ".join(bad), [b.split()[0] for b in bad], ["V05"],
                      cap(row_for_section(card, "S13"), 1))
    return result("CHK-D-A", "pass", "critical")


def chk_price_sum(doc, card):
    p = doc["data"]["pricing"]
    bad = []
    for kind in ("one_time", "recurring"):
        items = [i for i in p["items"] if i["kind"] == kind]
        declared = p["totals"][kind]
        if any(i["amount"] is None for i in items):
            if declared is not None:
                bad.append(f"جمع {kind} اعلام شده ولی قلمی نامعلوم است")
        elif items:
            real = sum(i["amount"] for i in items)
            if declared is None:
                bad.append(f"جمع {kind} نامعلوم اعلام شده ولی مجموع اقلام {real} است")
            elif round(real, 2) != round(declared, 2):
                bad.append(f"جمع {kind}: اقلام {real} ولی اعلام‌شده {declared}")
        elif declared not in (None, 0):
            bad.append(f"جمع {kind} {declared} اعلام شده ولی هیچ قلمی نیست")
    if bad:
        return result("CHK-PRICE-SUM", "fail", "critical", "؛ ".join(bad), ["S09"], ["V03"], cap(row_for_section(card, "S09"), 1))
    return result("CHK-PRICE-SUM", "pass", "critical")


def chk_pay_percent(doc, card):
    pay = doc["data"]["pricing"]["payments"]
    total = round(sum(x["percent"] for x in pay), 6)
    if total != 100:
        return result("CHK-PAY-PERCENT", "fail", "critical", f"جمع درصد پرداخت‌ها {total} است، نه ۱۰۰", ["S09"], caps=cap(row_for_section(card, "S09"), 1))
    return result("CHK-PAY-PERCENT", "pass", "critical")


def chk_pay_event(doc, card):
    dels = {d["id"] for d in doc["data"]["deliverables"]}
    bad = []
    for x in doc["data"]["pricing"]["payments"]:
        if x.get("deliverable") and x["deliverable"] not in dels:
            bad.append(f"{x['id']} به تحویل ناموجود {x['deliverable']} وصل است")
        elif not x.get("deliverable") and VAGUE_EVENT.search(common.normalize(x["event"])):
            bad.append(f"{x['id']}: رویداد مبهم «{x['event']}»")
    if bad:
        return result("CHK-PAY-EVENT", "fail", "critical", "؛ ".join(bad), ["S09"], caps=cap(row_for_section(card, "S09"), 2))
    return result("CHK-PAY-EVENT", "pass", "critical")


# ---------------------------------------------------------------- چک‌های متنی (ساختاری و متنی)

def chk_banned(fields, card, banned):
    veto, caps, warn, locs, seen = set(), [], False, [], []
    for path, text in fields:
        for h in common.banned_hits(common.normalize(text), banned):
            eff = card["banned_effects"].get(h["category"], {})
            veto |= set(eff.get("veto", []))
            caps += eff.get("caps", [])
            warn = warn or bool(eff.get("warn")) and not eff.get("veto") and not eff.get("caps")
            locs.append(path)
            seen.append(f"«{h['match']}» ({h['category']}) در {path}")
    if not seen:
        return result("CHK-BANNED", "pass", "critical")
    only_warn = not veto and not caps
    return result("CHK-BANNED", "warn" if only_warn else "fail", "warn" if only_warn else "critical", "؛ ".join(seen), locs, veto, caps)


def chk_brand_words(fields, card, brand):
    neg = common.load_banned()["negation"]
    seen, locs = [], []
    for path, text in fields:
        for h in common.phrase_hits(common.normalize(text), brand["forbidden_words"], neg):
            seen.append(f"«{h['match']}» در {path}")
            locs.append(path)
    caps = card["banned_effects"].get("brand_voice", {}).get("caps", [])
    if seen:
        return result("CHK-BRAND-WORDS", "fail", "warn", "واژه‌ی ممنوع برند: " + "؛ ".join(seen), locs, caps=caps)
    return result("CHK-BRAND-WORDS", "pass", "warn")


def chk_claim_refs(fields, card, claims):
    ledger = {c["id"] for c in claims["claims"]} if claims else set()
    refs = {}
    for path, text in fields:
        for r in CLAIM_REF.findall(text):
            refs.setdefault(r, []).append(path)
    bad = sorted(r for r in refs if r not in ledger)
    if bad:
        why = "دفتر ادعا نیست" if claims is None else "در دفتر ادعا نیست"
        return result("CHK-CLAIM-REFS", "fail", "critical", "ارجاع " + "، ".join(bad) + f": {why}",
                      [p for r in bad for p in refs[r]], caps=cap(card["claims_criterion"], 1))
    return result("CHK-CLAIM-REFS", "pass", "critical")


def chk_unknown_final(doc, fields):
    neg = common.load_banned()["negation"]
    has_unknown = any("[نامعلوم" in t for _, t in fields) or any(
        i["amount"] is None for i in doc["data"]["pricing"]["items"]) or any(
        t["duration_workdays"] is None for t in doc["data"]["timeline"])
    labels = [("meta.status_note", doc["meta"]["status_note"]), ("meta.title", doc["meta"]["title"])]
    found = []
    for path, text in labels:
        for h in common.phrase_hits(common.normalize(text), [{"pattern": FINAL_LABEL.pattern, "negation_cancels": True}], neg):
            found.append(f"«{h['match']}» در {path}")
    if has_unknown and found:
        return result("CHK-UNKNOWN-FINAL", "fail", "warn", "برچسب نهایی روی متن دارای مجهول: " + "؛ ".join(found), ["meta.status_note"])
    return result("CHK-UNKNOWN-FINAL", "pass", "warn")


def chk_digits(fields):
    bad = []
    for path, text in fields:
        cleaned = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+|\b[A-Za-z][A-Za-z0-9._/-]*\b", " ", text)  # نشانی و کد لاتین
        if re.search(r"[0-9٠-٩]", cleaned):
            bad.append(path)
    if bad:
        return result("CHK-DIGITS", "warn", "warn", f"عدد غیرفارسی در {len(bad)} فیلد", bad)
    return result("CHK-DIGITS", "pass", "warn")


def chk_length(doc, card, brief):
    md = render.render(doc)
    body = re.split(r"<!-- section: (?:APPENDIX|CLAIMS) -->", md)[0]
    words = len(re.findall(r"[^\s|#>*\-]+", re.sub(r"<!--.*?-->", "", body)))
    lo, hi = (brief["length_budget"]["min_words"], brief["length_budget"]["max_words"]) if brief else (
        card["length_words"]["min"], card["length_words"]["max"])
    if not lo <= words <= hi:
        return result("CHK-LENGTH", "warn", "warn", f"{words} کلمه؛ بودجه {lo} تا {hi}", ["sections"])
    return result("CHK-LENGTH", "pass", "warn", f"{words} کلمه")


def chk_length_text(text, card, brief):
    words = len(re.findall(r"[^\s|#>*\-]+", re.sub(r"<!--.*?-->", "", text)))
    lo, hi = (brief["length_budget"]["min_words"], brief["length_budget"]["max_words"]) if brief else (
        card["length_words"]["min"], card["length_words"]["max"])
    if not lo <= words <= hi:
        return result("CHK-LENGTH", "warn", "warn", f"{words} کلمه؛ بودجه {lo} تا {hi}", ["md"])
    return result("CHK-LENGTH", "pass", "warn", f"{words} کلمه")


# ---------------------------------------------------------------- هزینه در برابر منفعت (الزام کاربر)

def _cb_refs(doc):
    return [(s["id"], b.get("variant", "full")) for s in doc["sections"] for b in s["blocks"]
            if b["kind"] == "ref" and b["data"] == "cost_benefit"]


def chk_cost_benefit(doc, card):
    el = card["required_elements"]["cost_benefit"]
    cb = doc["data"].get("cost_benefit")
    refs = _cb_refs(doc)
    problems = []
    if not cb:
        problems.append("data.cost_benefit نیست")
    elif not any(v == "full" for _, v in refs):
        problems.append("جدول کامل در متن ارجاع نشده (ref با variant=full)")
    if problems:
        return result("CHK-COST-BENEFIT", "fail", el["missing"]["severity"], "؛ ".join(problems) + f"؛ جای مورد انتظار: {el['placement']}",
                      [s for s, _ in refs] or ["data.cost_benefit"], caps=el["missing"]["caps"])
    if not any(v == "headline" for _, v in refs):
        return result("CHK-COST-BENEFIT", "warn", "warn", "جمله‌ی خلاصه‌ی cost-to-benefit (variant=headline) در خلاصه‌ی اجرایی نیست",
                      [s for s, _ in refs])
    return result("CHK-COST-BENEFIT", "pass", "critical")


def chk_cb_support(doc, card, claims):
    cb = doc["data"].get("cost_benefit")
    if not cb:
        return skip("CHK-CB-SUPPORT", "cost_benefit وجود ندارد (CHK-COST-BENEFIT آن را ثبت کرده)")
    ledger = {c["id"] for c in claims["claims"]} if claims else set()
    bad = []
    for b in cb["benefits"]:
        if b["value"] is None:
            continue
        if b.get("claim"):
            if b["claim"] not in ledger:
                bad.append(f"{b['id']}: {b['claim']} در دفتر ادعا نیست")
        elif not b.get("assumption"):
            bad.append(f"{b['id']}: مقدار عددی بدون claim و بدون assumption")
    if bad:
        return result("CHK-CB-SUPPORT", "fail", "critical", "؛ ".join(bad), [x.split(":")[0] for x in bad],
                      caps=cap(card["claims_criterion"], 1))
    return result("CHK-CB-SUPPORT", "pass", "critical")


def chk_cb_type(doc, card):
    cb = doc["data"].get("cost_benefit")
    if not cb:
        return skip("CHK-CB-TYPE", "cost_benefit وجود ندارد (CHK-COST-BENEFIT آن را ثبت کرده)")
    bad = []
    for b in cb["benefits"]:
        if b["type"] == "cash_saving" and TIME_UNIT.search(common.normalize(b.get("unit") or "")):
            bad.append(f"{b['id']}: واحد زمان است ولی «صرفه‌جویی نقدی» نامیده شده (باید «ظرفیت آزادشده» باشد)")
        if b["type"] == "revenue_potential" and not b.get("assumption"):
            bad.append(f"{b['id']}: درآمد بالقوه بدون فرض (نرخ تبدیل و حاشیه) منفعت قطعی گرفته شده")
    if bad:
        return result("CHK-CB-TYPE", "fail", "critical", "؛ ".join(bad), [x.split(":")[0] for x in bad],
                      caps=card["required_elements"]["cost_benefit"]["missing"]["caps"])
    return result("CHK-CB-TYPE", "pass", "critical")


def chk_cb_caveat(doc, card):
    cb = doc["data"].get("cost_benefit")
    if not cb:
        return skip("CHK-CB-CAVEAT", "cost_benefit وجود ندارد (CHK-COST-BENEFIT آن را ثبت کرده)", "warn")
    if cb["scenarios"]:
        neg = common.load_banned()["negation"]
        c = common.normalize(cb["caveat"])
        ok = any(True for m in re.finditer("تضمین", c) if any(k in c[m.end(): m.end() + neg["after_window"]] for k in neg["after_markers"]))
        if not ok:
            return result("CHK-CB-CAVEAT", "fail", "warn", "سناریوی عددی هست ولی caveat نمی‌گوید «تضمین نیست»", ["data.cost_benefit.caveat"])
    return result("CHK-CB-CAVEAT", "pass", "warn")


# ---------------------------------------------------------------- اجرا

STRUCTURAL = ("CHK-SECTIONS", "CHK-IDS", "CHK-D-A", "CHK-PRICE-SUM", "CHK-PAY-PERCENT", "CHK-PAY-EVENT", "CHK-UNKNOWN-FINAL",
              "CHK-COST-BENEFIT", "CHK-CB-SUPPORT", "CHK-CB-TYPE", "CHK-CB-CAVEAT")


def run_structured(doc: dict, claims, brand, brief=None) -> list[dict]:
    card = common.load_card(doc["doc_type"])
    banned = common.load_banned()
    fields = text_fields(doc)
    return [
        result("CHK-SCHEMA", "pass", "critical"),
        chk_sections(doc, card), chk_ids(doc, card), chk_d_a(doc, card), chk_price_sum(doc, card),
        chk_pay_percent(doc, card), chk_pay_event(doc, card), chk_banned(fields, card, banned),
        chk_brand_words(fields, card, brand), chk_claim_refs(fields, card, claims), chk_unknown_final(doc, fields),
        chk_cost_benefit(doc, card), chk_cb_support(doc, card, claims), chk_cb_type(doc, card), chk_cb_caveat(doc, card),
        chk_digits(fields), chk_length(doc, card, brief)]


def run_text(text: str, doc_type: str, claims, brand, brief=None) -> list[dict]:
    card = common.load_card(doc_type)
    fields = [("md", text)]
    out = [skip(c, "سند ساخت‌یافته نیست؛ چک ساختاری اجرا نشد (نمره‌ی چنین سندی محدودتر است)",
                "warn" if c in ("CHK-UNKNOWN-FINAL", "CHK-CB-CAVEAT") else "critical") for c in ("CHK-SCHEMA",) + STRUCTURAL]
    out += [chk_banned(fields, card, common.load_banned()), chk_brand_words(fields, card, brand),
            chk_claim_refs(fields, card, claims), chk_digits(fields), chk_length_text(text, card, brief)]
    return out


def build(path: pathlib.Path, claims_path, brand_id, version: int, doc_type: str | None, brief=None) -> tuple[dict, int]:
    brand = common.load_brand(brand_id)
    claims = common.load_json(claims_path) if claims_path and pathlib.Path(claims_path).exists() else None
    if path.suffix == ".json":
        doc = common.load_json(path)
        errors = common.schema_errors(doc, "document")
        if errors:
            res = [result("CHK-SCHEMA", "fail", "critical", "؛ ".join(errors[:5]))]
            return {"version": version, "doc_type": doc.get("doc_type", doc_type or "proposal"), "mode": "structured", "results": res}, 2
        return {"version": version, "doc_type": doc["doc_type"], "mode": "structured",
                "results": run_structured(doc, claims, brand, brief)}, 0
    if not doc_type:
        common.fail("برای سند Markdown نوع سند لازم است (--type)")
    return {"version": version, "doc_type": doc_type, "mode": "text",
            "results": run_text(path.read_text(encoding="utf-8"), doc_type, claims, brand, brief)}, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?")
    ap.add_argument("--version", type=int)
    ap.add_argument("--doc")
    ap.add_argument("--claims")
    ap.add_argument("--brand")
    ap.add_argument("--type", choices=common.DOC_TYPES)
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    brief = None
    if args.doc:
        path, claims, out, version, brand = pathlib.Path(args.doc), args.claims, args.out, 1, args.brand
    else:
        if args.version is None:
            common.fail("--version لازم است")
        run_dir = common.resolve_run(args.run)
        path = run_dir / f"document.v{args.version}.json"
        if not path.exists():
            path = run_dir / f"document.v{args.version}.md"
        claims, version = run_dir / "claims.json", args.version
        out = args.out or str(run_dir / f"checks.v{args.version}.json")
        brand = args.brand or common.load_json(run_dir / "run.json").get("brand")
        if (run_dir / "brief.json").exists():
            brief = common.load_json(run_dir / "brief.json")
    data, code = build(path, claims, brand, version, args.type, brief)
    errors = common.schema_errors(data, "checks")
    if errors:
        common.fail("خروجی checks با schema نمی‌خواند (باگ checks.py):\n" + "\n".join(errors[:5]))
    if out:
        common.dump_json(data, out)
        print(out)
    for r in data["results"]:
        if r["status"] in ("fail", "warn"):
            print(f"{'✗' if r['status'] == 'fail' else '!'} {r['id']}: {r['detail']}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
