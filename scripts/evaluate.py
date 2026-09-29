#!/usr/bin/env python3
"""ارزیابی یک سند موجود، بدون Loop و بدون نویسنده (docs/۰۱-معماری.md بخش ۶؛ اسکیل evaluate-doc).

چرا دو فرمان: بین آماده‌سازی و جمع‌بندی، سه داور (ایجنت) اجرا می‌شوند و فقط جلسه‌ی اصلی می‌تواند ایجنت صدا بزند.
هر چیزی که قطعی است (ساخت اجرا، رندر، چک‌ها، اعتبارسنجی، gate، گزارش) این‌جاست تا اسکیل فقط ترتیب را بگوید.

  evaluate.py prepare <نوع سند> <سند.json|سند.md> [--claims f] [--input f]
      اجرای تازه ← (رندر) ← checks.v1.json؛ مسیر اجرا و کار داورها را چاپ می‌کند
  evaluate.py finish [run]
      هر سه گزارش داور را اعتبارسنجی، gate.v1.json و report.md را بساز؛ قفل را بردار

خروجی: runs/<run>/gate.v1.json و runs/<run>/report.md. نمره‌ای که این اسکریپت چاپ می‌کند فقط از gate می‌آید.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import pathlib
import sys

import checks as checks_mod
import common
import gate as gate_mod
import gate_report
import render
import run as runmod
import validate

JUDGES = (("judge-rubric", "rubric"), ("judge-claims", "claims"), ("judge-veto", "veto"))


def release_lock(run_dir: pathlib.Path) -> None:
    lock = common.RUNS / ".lock"
    if lock.exists() and lock.read_text(encoding="utf-8").strip() == run_dir.name:
        lock.unlink()


def prepare(doc_type: str, doc: str, claims: str | None = None, inp: str | None = None) -> pathlib.Path:
    ns = argparse.Namespace(doc_type=doc_type, doc=doc, claims=claims, input=inp)
    before = set(common.RUNS.iterdir()) if common.RUNS.exists() else set()
    with contextlib.redirect_stdout(io.StringIO()):  # مسیر را خود prepare یک بار و با برچسب چاپ می‌کند
        runmod.cmd_new_eval(ns)
    run_dir = next(p for p in common.RUNS.iterdir() if p.is_dir() and p not in before)
    run = runmod.load_run(run_dir)
    if (run_dir / "document.v1.json").exists():
        document = common.load_json(run_dir / "document.v1.json")
        errors = common.schema_errors(document, "document")
        if errors:
            runmod.set_run(run_dir, status="failed", error="CHK-SCHEMA: " + "؛ ".join(errors[:3]))
            release_lock(run_dir)  # اجرای شکست‌خورده نباید اجرای بعدی را قفل نگه دارد
            common.fail("سند با schema نمی‌خواند؛ ارزیابی ممکن نیست:\n" + "\n".join(errors[:8]), 2)
        claims_data = common.load_json(run_dir / "claims.json") if (run_dir / "claims.json").exists() else None
        (run_dir / "document.v1.md").write_text(render.render(document, claims_data), encoding="utf-8")
    data, code = checks_mod.build(next(p for p in (run_dir / "document.v1.json", run_dir / "document.v1.md") if p.exists()),
                                  run_dir / "claims.json", run["brand"], 1, doc_type)
    common.dump_json(data, run_dir / "checks.v1.json")
    runmod.set_run(run_dir, stage="checks")
    return run_dir


def judge_errors(run_dir: pathlib.Path) -> dict[str, list[str]]:
    return {agent: errs for agent, short in JUDGES if (errs := validate.validate_stage(run_dir, f"judge-{short}"))}


def report_md(run_dir: pathlib.Path, gate: dict, checks: dict) -> str:
    run = runmod.load_run(run_dir)
    L = ['<div dir="rtl">', "", "# گزارش ارزیابی سند", "",
         f"- **اجرا:** `{run['run_id']}` · نوع سند: {gate['doc_type']} · حالت: {'ساخت‌یافته (JSON)' if checks['mode'] == 'structured' else 'متنی (Markdown)'}",
         f"- **وضعیت:** {gate_report.STATUS_FA['ready_for_review']} (سیستم چیزی ارسال یا تأیید نمی‌کند)",
         f"- **نمره:** total {gate_report.fa(gate['total'])} از ۱۰۰ (معادل {gate_report.fa(gate['target']['score10'])} از ۱۰)"]
    L += gate_report.sections(gate, "هدف کیفیت")
    L += gate_report.tail(gate)
    fails = [r for r in checks["results"] if r["status"] in ("fail", "warn", "skip")]
    if fails:
        L += ["", "## چک‌های قطعی که پاس نشدند", "", "| چک | وضعیت | توضیح |", "|---|---|---|"]
        st = {"fail": "رد", "warn": "هشدار", "skip": "اجرا نشد"}
        L += [f"| {r['id']} | {st[r['status']]} | {r['detail'].replace('|', '/') or '—'} |" for r in fails]
    L += ["", "## نمره‌ی هر ردیف", ""] + gate_report.score_table(gate)
    L += ["## فایل‌های شاهد", "", "- `checks.v1.json`", "- `judges/v1/rubric.json`، `claims.json`، `veto.json`", "- `gate.v1.json`", "", "</div>", ""]
    return "\n".join(L)


def finish(run_dir: pathlib.Path) -> pathlib.Path:
    missing = [f"judges/v1/{s}.json" for _, s in JUDGES if not (run_dir / "judges" / "v1" / f"{s}.json").exists()]
    if missing:
        common.fail("گزارش داور نیست: " + "، ".join(missing))
    bad = judge_errors(run_dir)
    if bad:
        lines = [f"{agent}: {len(e)} خطا" for agent, e in bad.items()] + [f"  - {x}" for e in bad.values() for x in e[:8]]
        common.fail("گزارش داور قرارداد را نقض می‌کند؛ همان داور یک بار اصلاح می‌کند و دوباره finish:\n" + "\n".join(lines))
    d = run_dir
    args = ["--checks", str(d / "checks.v1.json"), "--rubric", str(d / "judges/v1/rubric.json"),
            "--claims", str(d / "judges/v1/claims.json"), "--veto", str(d / "judges/v1/veto.json"), "-o", str(d / "gate.v1.json")]
    if gate_mod.main(args) != 0:
        common.fail("gate شکست خورد")
    gate = common.load_json(d / "gate.v1.json")
    (d / "report.md").write_text(report_md(d, gate, common.load_json(d / "checks.v1.json")), encoding="utf-8")
    runmod.set_run(d, status="ready_for_review", stage="done", note="ارزیابی تمام شد")
    release_lock(d)
    return d / "report.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("doc_type", choices=common.DOC_TYPES)
    p.add_argument("doc")
    p.add_argument("--claims")
    p.add_argument("--input")
    p = sub.add_parser("finish")
    p.add_argument("run", nargs="?")
    args = ap.parse_args(argv)
    if args.cmd == "prepare":
        run_dir = prepare(args.doc_type, args.doc, args.claims, args.input)
        c = common.load_json(run_dir / "checks.v1.json")
        bad = [f"{r['id']}={r['status']}" for r in c["results"] if r["status"] in ("fail", "warn")]
        print(f"اجرا: {run_dir}\nحالت: {c['mode']}\nچک‌های ناموفق: {'، '.join(bad) or 'هیچ'}\n"
              f"مرحله‌ی بعد: سه داور (judge-rubric، judge-claims، judge-veto) روی نسخه‌ی ۱، بعد: evaluate.py finish {run_dir}")
    else:
        print(finish(common.resolve_run(args.run)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
