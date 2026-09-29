#!/usr/bin/env python3
"""چرخه‌ی عمر یک اجرا: ساخت پوشه، کانتکست، بررسی ورودی و وضعیت.

چرا کد و نه ارکستریتور: نام پوشه، برش کانتکست و انتقال وضعیت باید در هر اجرا دقیقاً یکسان باشد
(docs/۰۱-معماری.md بخش ۳ و ۵).

  run.py template <doc_type>                          فرم خالی ورودی
  run.py new <doc_type> <input.json>                  اجرای تازه‌ی استودیو
  run.py new-eval <doc_type> <doc.json|doc.md> [--claims f] [--input f]   اجرای فقط ارزیابی
  run.py intake-check [run]                           L1: پوشش فیلدها و کمبود مسدودکننده (کد)
  run.py answer <run> <Q-01> "<متن>" [--field key]    ثبت پاسخ انسان
  run.py set <run> [--status s] [--stage s] [--round n] [--error msg]
  run.py finish [run]                                 برداشتن قفل اجرا
  run.py status [run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys

import common
import slice_guide

# انتقال‌های مجاز status (docs/۰۱-معماری.md بخش ۵-الف)؛ وضعیت‌های پایانی به جایی نمی‌روند
STATUS_NEXT = {
    "running": {"running", "blocked_on_input", "needs_human", "ready_for_review", "failed"},
    "blocked_on_input": {"blocked_on_input", "running", "failed"},
    "needs_human": set(),
    "ready_for_review": set(),
    "failed": set(),
}
MAX_INTAKE_ROUNDS = 2  # docs/۰۴-تکنیک-Loop.md بخش ۴
AGENTS_WITH_LESSONS = ("intake-analyst", "strategist", "researcher", "writer", "judge-rubric", "judge-claims", "judge-veto")
# برش‌هایی که به context می‌روند؛ rubric_text و checklist مرجع انسان‌اند و کارت نسخه‌ی ساخت‌یافته‌ی آن‌ها را دارد
CONTEXT_SLICES = ("intake_form", "doc_types", "architecture", "operations", "writing_rules", "evidence_rules")
UNKNOWN_WORDS = ("نامعلوم", "نمی‌دانم", "نمیدانم", "؟")


# ---------------------------------------------------------------- run.json

def load_run(run_dir) -> dict:
    return common.load_json(run_dir / "run.json")


def save_run(run_dir, run: dict) -> None:
    errors = common.schema_errors(run, "run")
    if errors:
        common.fail("run.json نامعتبر شد:\n" + "\n".join(errors))
    common.dump_json(run, run_dir / "run.json")


def event(run: dict, name: str, detail: str | None = None) -> None:
    run["history"].append({"ts": common.now_iso(), "event": name, "detail": detail})


def set_run(run_dir, status=None, stage=None, round_=None, error=None, note=None) -> dict:
    run = load_run(run_dir)
    if status and status != run["status"]:
        if status not in STATUS_NEXT[run["status"]]:
            common.fail(f"انتقال غیرمجاز status: {run['status']} ← {status}")
        event(run, "status", f"{run['status']} ← {status}")
        run["status"] = status
    if stage and stage != run["stage"]:
        event(run, "stage", stage)
        run["stage"] = stage
    if round_ is not None and round_ != run["round"]:
        event(run, "round", str(round_))
        run["round"] = round_
    if error:
        run["errors"].append(error)
        event(run, "error", error)
    if note:
        event(run, "note", note)
    save_run(run_dir, run)
    return run


# ---------------------------------------------------------------- ورودی

def template(doc_type: str) -> dict:
    card = common.load_card(doc_type)
    return {"doc_type": doc_type, "brand": common.DEFAULT_BRAND, "fields": {f["key"]: None for f in card["intake_fields"]},
            "attachments": [], "answers": [], "sample": False,
            "output_formats": ["pdf"]}


def load_input(path, doc_type: str) -> tuple[dict, list[str]]:
    data = common.load_json(path)
    errors = common.schema_errors(data, "input")
    if errors:
        common.fail(f"فرم ورودی {path} نامعتبر است:\n" + "\n".join(errors))
    if data["doc_type"] != doc_type:
        common.fail(f"نوع سند فرم ({data['doc_type']}) با {doc_type} نمی‌خواند")
    common.load_brand(data.get("brand"))  # کارت برند باید وجود داشته باشد
    keys = [f["key"] for f in common.load_card(doc_type)["intake_fields"]]
    unknown = sorted(set(data["fields"]) - set(keys))
    if unknown:
        common.fail("کلیدهای ناشناخته در فرم: " + "، ".join(unknown) + "\nفرم درست: run.py template " + doc_type)
    warnings = []
    for k in keys:
        if k not in data["fields"]:
            data["fields"][k] = None
            warnings.append(f"فیلد {k} در فرم نبود و null گذاشته شد")
    return data, warnings


def _filled(value) -> bool:
    if value is None:
        return False
    v = value.strip()
    return bool(v) and not any(v == w or v.startswith(w + " ") or v.startswith(w + ":") for w in UNKNOWN_WORDS)


def required_fields(card: dict, fields: dict) -> list[dict]:
    out = []
    for f in card["intake_fields"]:
        cond = f.get("required_if")
        if f["required"] or (cond and cond["contains"] in (fields.get(cond["field"]) or "")):
            out.append(f)
    return out


def intake_state(run_dir) -> dict:
    """L1: نمره = ۱۰ × پرشده‌ها ÷ الزامی‌ها. پاسخ ثبت‌شده برای یک فیلد، آن را پرشده حساب می‌کند."""
    inp = common.load_json(run_dir / "input.json")
    card = common.load_card(inp["doc_type"])
    answered = {a["field"] for a in inp["answers"] if a.get("field")}
    req = required_fields(card, inp["fields"])
    missing = [f["key"] for f in req if not (_filled(inp["fields"].get(f["key"])) or f["key"] in answered)]
    blocking = [k for k in missing if next(f for f in card["intake_fields"] if f["key"] == k)["blocking"]]
    n = len(req)
    return {"required": n, "filled": n - len(missing), "score10": round(10 * (n - len(missing)) / n, 1) if n else 10.0,
            "missing": missing, "blocking_missing": blocking}


# ---------------------------------------------------------------- کانتکست

def rubric_md(card: dict) -> str:
    lines = [f"# روبریک {card['title']} (از rubrics/{card['doc_type']}.json)", "",
             "از همین شناسه‌ها دقیقاً استفاده کن. نمره‌ی هر ردیف یک عدد صحیح ۰ تا ۴ است؛ امتیاز = وزن × نمره ÷ ۴.", "",
             "## سطح‌ها", ""]
    lines += [f"- **{k}**: {v}" for k, v in card["scale"].items()]
    lines += ["", "## ردیف‌ها", "", "| شناسه | معیار | وزن | بخش‌های مرتبط |", "|---|---|---:|---|"]
    lines += [f"| {c['id']} | {c['title']} | {c['weight']} | {'، '.join(c['sections']) or 'کل سند'} |" for c in card["criteria"]]
    lines += ["", "## دروازه (فقط برای اطلاع؛ تصمیم را gate.py می‌گیرد، نه داور)", "", f"> {card['gate_source']}", ""]
    return "\n".join(lines) + "\n"


def veto_md(card: dict, banned: dict) -> str:
    lines = [f"# رد فوری‌های {card['title']} (از rubrics/{card['doc_type']}.json)", "",
             f"> {card['veto_source']}", "",
             "| شناسه | مورد | کشف با | شرط |", "|---|---|---|---|"]
    names = {"code": "کد", "judge": "داور", "both": "داور و کد"}
    for v in card["veto"]:
        lines.append(f"| {v['id']} | {v['text']} | {names[v['detector']]} | {v.get('applies_if') or '—'} |")
    lines += ["", "داور رد فوری مسئول ردیف‌های «داور» و «داور و کد» است و همه را باید در `checked` بیاورد.",
              "مورد «کد» را checks.py می‌سنجد؛ داور لازم نیست آن را تکرار کند.", "",
              "## عبارت‌های ممنوع (checks.py با کد می‌سنجد؛ برای آگاهی)", ""]
    for p in banned["phrases"]:
        eff = card["banned_effects"].get(p["category"], {})
        effect = ("رد فوری " + "، ".join(eff["veto"])) if eff.get("veto") else (
            "سقف " + "، ".join(f"{c['criterion']}≤{c['max']}" for c in eff.get("caps", []))) if eff.get("caps") else "هشدار"
        lines.append(f"- `{p['pattern']}` — {p['category']} — {effect}")
    return "\n".join(lines) + "\n"


def brand_md(brand: dict) -> str:
    """خلاصه‌ی کارت برند برای ایجنت‌ها؛ توکن‌های طراحی عمداً نیامده (فقط برای خروجی بصری، فاز H)."""
    L = [f"# برند: {brand['name_fa']} (از brand/{brand['id']}.json)", "",
         "سند از طرف این برند نوشته می‌شود. این قواعد صدا و شواهد برند است؛ قواعد راهنمای نوع سند مقدم‌اند.", "",
         f"- **جایگاه‌یابی:** {brand['positioning']}", f"- **ارزش پیشنهادی:** {brand['usp']}",
         f"- **تعهدها:** {'، '.join(brand['commitments'])}", "", "## صدا", ""]
    for v in brand["voice"]:
        L.append(f"- **{v['principle']}** ({v['meaning']}): ✓ «{v['do']}» ✗ «{v['dont']}»"
                 + (f" — ⚠️ {v['caution']}" if v.get("caution") else ""))
    L += ["", "## واژه‌ها", "", "- **مجاز:** " + "، ".join(brand["approved_words"]),
          "- **ممنوع (checks.py با کد می‌سنجد؛ سقف ردیف نگارش ۳):** " + "، ".join(w["text"] for w in brand["forbidden_words"]),
          "- **CTA ترجیحی:** " + "، ".join(brand["cta"]["preferred"]),
          "- **CTA ممنوع:** " + "، ".join(brand["cta"]["avoid"]), "",
          "## قواعد نگارش (Design System)", ""] + [f"- {r}" for r in brand["copy_rules"]]
    L += ["", "## شواهد برند (فقط با ارجاع به همین شناسه‌ها در دفتر ادعا، منبع kind=brand)", "",
          "| شناسه | ادعا | وضعیت | مجوز انتشار | محدودیت |", "|---|---|---|---|---|"]
    status = {"self_reported": "ادعای خود برند", "verified": "تأییدشده"}
    perm = {"unknown": "نامعلوم — پیش از نام‌بردن تأیید لازم است", "granted": "دارد", "not_needed": "لازم نیست"}
    for p in brand["proof"]:
        L.append(f"| {p['id']} | {p['claim']} | {status[p['status']]} | {perm[p['publish_permission']]} | {p['limits']} |")
    L += ["", "## پکیج‌ها (قیمت «از»؛ تاریخ منبع قدیمی است و بدون تأیید تازه قیمت قطعی نیست)", "",
          "| شناسه | پکیج | از (تومان) | شامل | تاریخ | نیاز به تأیید |", "|---|---|---|---|---|---|"]
    for k in brand["packages"]:
        L.append(f"| {k['id']} | {k['name']} | {common.fa_number(k['from_amount'])} | {k['includes']} | {k['as_of']} | {'بله' if k['needs_confirmation'] else 'خیر'} |")
    L += ["", "## مشکلات شناخته‌شده‌ی منابع برند", ""] + [f"- **{i['issue']}** — {i['handling']}" for i in brand["known_issues"]]
    return "\n".join(L) + "\n"


def build_context(run_dir, doc_type: str, brand_id: str | None = None) -> list[str]:
    ctx = run_dir / "context"
    ctx.mkdir(parents=True, exist_ok=True)
    card = common.load_card(doc_type)
    (ctx / "brand.md").write_text(brand_md(common.load_brand(brand_id)), encoding="utf-8")
    written = []
    for name in CONTEXT_SLICES:
        (ctx / f"{name}.md").write_text(slice_guide.slice_chapter(doc_type, name), encoding="utf-8")
        written.append(f"{name}.md")
    (ctx / "rubric.md").write_text(rubric_md(card), encoding="utf-8")
    (ctx / "veto.md").write_text(veto_md(card, common.load_banned()), encoding="utf-8")
    written += ["rubric.md", "veto.md", "brand.md"]
    written += write_lessons_context(ctx)
    return written


def write_lessons_context(ctx) -> list[str]:
    """درس‌های فعال هر ایجنت (حداکثر ۵، جدیدترین) — منطق کامل در lessons.py (فاز F)."""
    try:
        import lessons  # noqa: WPS433 — فقط اگر فاز F ساخته شده باشد
        return lessons.inject(ctx)
    except ImportError:
        out = []
        for agent in AGENTS_WITH_LESSONS + ("all",):
            (ctx / f"lessons.{agent}.md").write_text("# درس‌های آموخته‌شده\n\n(درسی ثبت نشده)\n", encoding="utf-8")
            out.append(f"lessons.{agent}.md")
        return out


# ---------------------------------------------------------------- فرمان‌ها

def _new_run_dir(doc_type: str):
    common.RUNS.mkdir(parents=True, exist_ok=True)
    lock = common.RUNS / ".lock"
    if lock.exists():
        common.fail(f"اجرای دیگری قفل را دارد: {lock.read_text(encoding='utf-8').strip()} — اول «run.py finish» یا بررسی دستی")
    base = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{doc_type}"
    run_id, n = base, 1
    while (common.RUNS / run_id).exists():
        n += 1
        run_id = f"{base}-{n}"
    run_dir = common.RUNS / run_id
    run_dir.mkdir()
    return run_id, run_dir


def _init_run(run_id: str, mode: str, doc_type: str, stage: str, round_: int, brand: str) -> dict:
    run = {"run_id": run_id, "mode": mode, "doc_type": doc_type, "brand": brand, "created": common.now_iso(), "status": "running",
           "stage": stage, "round": round_, "intake_rounds": 0, "lifecycle": "draft", "revision": 1,
           "parent_run": None, "errors": [], "history": []}
    event(run, "created", mode)
    return run


def _activate(run_dir, run_id: str) -> None:
    (common.RUNS / ".current").write_text(run_id, encoding="utf-8")
    (common.RUNS / ".lock").write_text(run_id, encoding="utf-8")


def cmd_new(args) -> int:
    inp, warnings = load_input(args.input, args.doc_type)
    run_id, run_dir = _new_run_dir(args.doc_type)
    common.dump_json(inp, run_dir / "input.json")
    brand = inp.get("brand") or common.DEFAULT_BRAND
    run = _init_run(run_id, "studio", args.doc_type, "init", 0, brand)
    for w in warnings:
        event(run, "warning", w)
    if args.parent:
        parent = load_run(common.resolve_run(args.parent))
        run["parent_run"] = parent["run_id"]
        run["revision"] = parent["revision"] + 1
    save_run(run_dir, run)
    build_context(run_dir, args.doc_type, brand)
    _activate(run_dir, run_id)
    print(run_dir)
    return 0


def cmd_new_eval(args) -> int:
    src = common.pathlib.Path(args.doc)
    if src.suffix not in (".json", ".md"):
        common.fail("سند باید .json (ساخت‌یافته) یا .md باشد")
    run_id, run_dir = _new_run_dir(args.doc_type)
    shutil.copyfile(src, run_dir / f"document.v1{src.suffix}")
    if args.claims:
        shutil.copyfile(args.claims, run_dir / "claims.json")
    else:
        common.dump_json({"claims": [], "searches": []}, run_dir / "claims.json")
    if args.input:
        inp, _ = load_input(args.input, args.doc_type)
    else:
        inp = template(args.doc_type)
    common.dump_json(inp, run_dir / "input.json")
    common.dump_json({"gaps": []}, run_dir / "gaps.json")
    brand = inp.get("brand") or common.DEFAULT_BRAND
    run = _init_run(run_id, "evaluate", args.doc_type, "checks", 1, brand)
    event(run, "source", f"{src.name}؛ دفتر ادعا: {'دارد' if args.claims else 'ندارد'}؛ فرم ورودی: {'دارد' if args.input else 'ندارد'}")
    save_run(run_dir, run)
    build_context(run_dir, args.doc_type, brand)
    _activate(run_dir, run_id)
    print(run_dir)
    return 0


def cmd_intake_check(args) -> int:
    run_dir = common.resolve_run(args.run)
    state = intake_state(run_dir)
    run = load_run(run_dir)
    run["intake_rounds"] += 1
    event(run, "intake-check", json.dumps(state, ensure_ascii=False))
    save_run(run_dir, run)
    if state["blocking_missing"]:
        state["status"] = "blocked_on_input"
        state["rounds_left"] = max(0, MAX_INTAKE_ROUNDS - run["intake_rounds"])
        set_run(run_dir, status="blocked_on_input", stage="intake")
    else:
        state["status"] = "running"
        state["rounds_left"] = max(0, MAX_INTAKE_ROUNDS - run["intake_rounds"])
        if run["status"] == "blocked_on_input":
            set_run(run_dir, status="running")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_answer(args) -> int:
    run_dir = common.resolve_run(args.run)
    path = run_dir / "input.json"
    inp = common.load_json(path)
    card = common.load_card(inp["doc_type"])
    if args.field and args.field not in {f["key"] for f in card["intake_fields"]}:
        common.fail(f"فیلد ناشناخته: {args.field}")
    inp["answers"].append({"question": args.question, "field": args.field, "text": args.text, "ts": common.now_iso()})
    if args.field and not _filled(inp["fields"].get(args.field)):
        inp["fields"][args.field] = args.text
    errors = common.schema_errors(inp, "input")
    if errors:
        common.fail("\n".join(errors))
    common.dump_json(inp, path)
    set_run(run_dir, note=f"پاسخ {args.question}" + (f" ← {args.field}" if args.field else ""))
    return 0


def cmd_set(args) -> int:
    run_dir = common.resolve_run(args.run)
    set_run(run_dir, status=args.status, stage=args.stage, round_=args.round, error=args.error)
    return 0


def cmd_finish(args) -> int:
    run_dir = common.resolve_run(args.run)
    lock = common.RUNS / ".lock"
    if lock.exists() and lock.read_text(encoding="utf-8").strip() == run_dir.name:
        lock.unlink()
        set_run(run_dir, note="قفل برداشته شد")
    return 0


def cmd_status(args) -> int:
    run_dir = common.resolve_run(args.run)
    run = load_run(run_dir)
    out = {k: run[k] for k in ("run_id", "mode", "doc_type", "brand", "status", "stage", "round", "lifecycle", "revision", "errors")}
    out["locked"] = (common.RUNS / ".lock").exists()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("template"); p.add_argument("doc_type", choices=common.DOC_TYPES)
    p = sub.add_parser("new"); p.add_argument("doc_type", choices=common.DOC_TYPES); p.add_argument("input")
    p.add_argument("--parent", help="اجرای قبلی، برای درخواست تغییر (revision+1)")
    p = sub.add_parser("new-eval"); p.add_argument("doc_type", choices=common.DOC_TYPES); p.add_argument("doc")
    p.add_argument("--claims"); p.add_argument("--input")
    p = sub.add_parser("intake-check"); p.add_argument("run", nargs="?")
    p = sub.add_parser("answer"); p.add_argument("run"); p.add_argument("question"); p.add_argument("text")
    p.add_argument("--field")
    p = sub.add_parser("set"); p.add_argument("run"); p.add_argument("--status"); p.add_argument("--stage")
    p.add_argument("--round", type=int); p.add_argument("--error")
    p = sub.add_parser("finish"); p.add_argument("run", nargs="?")
    p = sub.add_parser("status"); p.add_argument("run", nargs="?")
    args = ap.parse_args(argv)
    if args.cmd == "template":
        print(json.dumps(template(args.doc_type), ensure_ascii=False, indent=2))
        return 0
    return {"new": cmd_new, "new-eval": cmd_new_eval, "intake-check": cmd_intake_check, "answer": cmd_answer,
            "set": cmd_set, "finish": cmd_finish, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
