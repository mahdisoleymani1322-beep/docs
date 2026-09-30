#!/usr/bin/env python3
"""بازخورد انسانی و چرخه‌ی عمر سند (docs/۰۶ بخش ۱): تنها راه تغییر `lifecycle` در run.json.

  feedback.py add <اجرا> --author نام [--version n] [--section S06] [--vote up|down] [--note متن]
                         [--action review|request_changes|approve|decline] [--override دلیل]
  feedback.py status <اجرا>

چرا کد: «انسان چه کرد» باید ثبت‌شدنی و قابل‌ممیزی باشد و هیچ ایجنتی نتواند سند را تأیید کند؛ `approved` یعنی «انسان پذیرفت»، نه «ارسال شد».
هر انتقال غیرمجاز رد می‌شود و **هیچ فایلی** تغییر نمی‌کند: همه‌چیز پیش از نوشتن بررسی می‌شود.
`request_changes` اجرای تازه (revision+1، parent_run) می‌سازد و یادداشت‌های انسان را در `issues.v0.json` آن می‌گذارد تا نویسنده در دور ۱ تک‌تک پاسخ دهد.
"""
from __future__ import annotations

import argparse
import json
import sys

import common
import run as runmod

ACTIONS = ("review", "request_changes", "approve", "decline")
TERMINAL = ("approved", "declined", "changes_requested")
NEXT = {"review": "in_review", "request_changes": "changes_requested", "approve": "approved", "decline": "declined"}


def feedback_file(run_id: str):
    return common.FEEDBACK / f"{run_id}.jsonl"


def read_feedback(run_id: str) -> list[dict]:
    f = feedback_file(run_id)
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def plan(run: dict, rec: dict, prior: list[dict]) -> str:
    """لایه‌ی خالص: lifecycle بعدی یا SystemExit با دلیل. هیچ فایلی را نمی‌خواند و نمی‌نویسد."""
    cur = run["lifecycle"]
    if cur in TERMINAL:
        common.fail(f"lifecycle «{cur}» پایانی است؛ هیچ کنش تازه‌ای پذیرفته نمی‌شود (برای ادامه اجرای تازه بسازید)")
    action = rec["action"]
    if action is None:
        if rec["vote"] is None and not rec["note"]:
            common.fail("رکورد خالی است: دست‌کم یکی از رأی، یادداشت یا کنش لازم است")
        return "in_review"
    if action == "request_changes":
        if not (rec["note"] or any(p.get("note") for p in prior)):
            common.fail("درخواست تغییر دست‌کم یک یادداشت می‌خواهد (چه بخواهید عوض شود؟)")
    if action == "approve" and run["status"] != "ready_for_review" and not (rec.get("override_reason") or "").strip():
        common.fail(f"سند «{run['status']}» است، نه ready_for_review؛ تأیید فقط با --override و دلیل صریح ثبت می‌شود")
    return NEXT[action]


def build_issues(records: list[dict]) -> dict:
    """یادداشت‌های انسان ← ایرادهای issues.v0.json برای اجرای تازه (رأی مثبتِ بی‌اثر و یادداشت خالی نمی‌آید)."""
    issues = []
    for r in records:
        if r.get("note") and r.get("vote") != "up":
            issues.append({"id": f"I-{len(issues) + 1:02d}", "source": "human", "severity": "human",
                           "section": r["section"], "text": r["note"]})
    return {"for_round": 1, "base_version": None, "issues": issues, "regressions": []}


def cmd_add(args) -> int:
    run_dir = common.resolve_run(args.run)
    run = common.load_json(run_dir / "run.json")
    if args.version is not None:
        doc = run_dir / f"document.v{args.version}.json"
        if not (doc.exists() or (run_dir / f"document.v{args.version}.md").exists()):
            common.fail(f"نسخه‌ی {args.version} در {run_dir.name} نیست")
        if args.section and doc.exists() and args.section not in {s["id"] for s in common.load_json(doc)["sections"]}:
            common.fail(f"بخش {args.section} در نسخه‌ی {args.version} نیست")
    rec = {"ts": common.now_iso(), "run_id": run["run_id"], "version": args.version, "section": args.section,
           "vote": args.vote, "note": (args.note or "").strip() or None, "action": args.action, "author": args.author.strip()}
    if args.override:
        rec["override_reason"] = args.override.strip()
    errors = common.schema_errors(rec, "feedback")
    if errors:
        common.fail("رکورد بازخورد نامعتبر:\n" + "\n".join(errors))
    prior = read_feedback(run["run_id"])
    new_state = plan(run, rec, prior)
    child_input = run_dir / "input.json"
    if args.action == "request_changes":
        if (common.RUNS / ".lock").exists():
            common.fail("اجرای دیگری قفل را دارد؛ اول آن را ببندید (run.py finish) تا اجرای تازه‌ی درخواست تغییر ساخته شود")
        if not child_input.exists():
            common.fail(f"{child_input} نیست؛ اجرای تازه بدون ورودی ساخته نمی‌شود")
    # --- از این‌جا به بعد فقط نوشتن
    f = feedback_file(run["run_id"])
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    changed = new_state != run["lifecycle"]
    if changed:
        old = run["lifecycle"]
        run["lifecycle"] = new_state
        runmod.event(run, "lifecycle", f"{old} ← {new_state} ({rec['author']})")
        runmod.save_run(run_dir, run)
    print(f"lifecycle: {run['lifecycle']}" + ("" if changed else " (بدون تغییر)"))
    if args.action == "request_changes":
        ns = argparse.Namespace(doc_type=run["doc_type"], input=str(child_input), parent=str(run_dir))
        runmod.cmd_new(ns)
        new_dir = common.current_run()
        common.dump_json(build_issues(prior + [rec]), new_dir / "issues.v0.json")
        print(f"اجرای تازه: {new_dir.name} (revision {runmod.load_run(new_dir)['revision']}؛ ایرادهای انسان در issues.v0.json)")
    return 0


def cmd_status(args) -> int:
    run_dir = common.resolve_run(args.run)
    run = common.load_json(run_dir / "run.json")
    recs = read_feedback(run["run_id"])
    votes = {v: sum(1 for r in recs if r["vote"] == v) for v in ("up", "down")}
    print(json.dumps({"run_id": run["run_id"], "status": run["status"], "lifecycle": run["lifecycle"],
                      "revision": run["revision"], "feedback": len(recs), "votes": votes}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("run")
    a.add_argument("--author", required=True)
    a.add_argument("--version", type=int)
    a.add_argument("--section")
    a.add_argument("--vote", choices=("up", "down"))
    a.add_argument("--note")
    a.add_argument("--action", choices=ACTIONS)
    a.add_argument("--override")
    a.set_defaults(fn=cmd_add)
    s = sub.add_parser("status")
    s.add_argument("run")
    s.set_defaults(fn=cmd_status)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
