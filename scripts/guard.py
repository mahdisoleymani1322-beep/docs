#!/usr/bin/env python3
"""گاردریل‌های نوشتن و بودجه به‌صورت hook `PreToolUse` (docs/۰۵-ابزارها-و-گاردریل‌ها.md، G2 و G3 و G5).

چرا کد: «فقط این فایل را بنویس» و «مشخصات منجمدند» تا وقتی فقط در پرامپت باشند، خواهش‌اند نه قاعده. این hook نوشتن را
پیش از اجرا می‌بیند و با دلیلِ عملی به ایجنت برمی‌گرداند. ورودی JSON hook از stdin می‌آید؛ خروج همیشه ۰ و تصمیم در JSON است.

  guard.py --locked                  G3: نوشتن در guides/ rubrics/ schemas/ evals/golden/ رد می‌شود اگر runs/.lock هست یا
                                     فراخوانی از داخل یک ایجنت است؛ عبور فقط با STUDIO_ALLOW_LOCKED=1 (تصمیم انسان)
  guard.py --allow <الگو> [...]      G2: فقط فایل‌هایی که با الگو نسبت به پوشه‌ی اجرای جاری می‌خوانند؛ {n} = دور فعلی
  guard.py --budget نام=N            G5: فراخوانی N+۱ام رد می‌شود؛ شمارنده‌ی هر اجرا در runs/<id>/.budget/<نام>

مسیر هدف با realpath یکسان می‌شود تا «..» و symlink دورش نزنند. فقط ابزارهای نوشتن بررسی می‌شوند (به‌جز --budget که ابزار را matcher
تعیین می‌کند). ورودی نامعتبر ← عبور، مثل check_handoff (Claude Code همیشه JSON معتبر می‌فرستد). فقط پوسیکس (flock)؛ داک ۰۵ بخش ۵.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import re
import sys

import common

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
LOCKED = ("guides", "rubrics", "schemas", "evals/golden")


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))


def target_path(data: dict) -> pathlib.Path | None:
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not fp:
        return None
    base = pathlib.Path(data.get("cwd") or os.getcwd())
    return pathlib.Path(os.path.realpath(base / fp))


def locked_dirs() -> list[pathlib.Path]:
    return [common.ROOT / d for d in LOCKED]  # ROOT با Path.resolve() ساخته شده و همیشه واقعی است


def check_locked(data: dict, target: pathlib.Path) -> str | None:
    hit = next((d for d in locked_dirs() if target == d or d in target.parents), None)
    if hit is None or os.environ.get("STUDIO_ALLOW_LOCKED") == "1":
        return None
    in_run = (common.RUNS / ".lock").exists()
    from_agent = bool(data.get("agent_id"))
    if not (in_run or from_agent):
        return None
    who = "ایجنت" if from_agent else "اجرای جاری"
    return (f"نوشتن در «{hit.relative_to(common.ROOT)}» رد شد: مشخصات (راهنما، روبریک، schema، گلدن‌ست) "
            f"در طول اجرا منجمدند و {who} نباید آن‌ها را عوض کند، وگرنه اولین نمره‌ی پایین به‌جای رفع مشکل، معیار را عوض می‌کند. "
            "اگر در راهنما یا روبریک ایرادی می‌بینی، در خروجی خودت گزارش کن، نه اصلاح. تغییر مشخصات فقط با درخواست صریح انسان و STUDIO_ALLOW_LOCKED=1 است.")


def match_parts(rel: tuple[str, ...], pattern: str) -> bool:
    import fnmatch
    pat = pathlib.PurePosixPath(pattern).parts
    return len(rel) == len(pat) and all(fnmatch.fnmatchcase(a, b) for a, b in zip(rel, pat))


def check_allow(target: pathlib.Path, patterns: list[str]) -> str | None:
    run_dir = common.current_run()
    if run_dir is None:
        return "هیچ اجرای فعالی نیست (runs/.current)؛ ایجنت بیرون از اجرا چیزی نمی‌نویسد."
    run = common.load_json(run_dir / "run.json")
    allowed = [p.format(n=run["round"]) for p in patterns]
    real_run = pathlib.Path(os.path.realpath(run_dir))
    if real_run in target.parents:
        rel = target.relative_to(real_run).parts
        if any(match_parts(rel, a) for a in allowed):
            return None
    return (f"نوشتن در «{target.name}» رد شد: تو فقط اجازه‌ی نوشتن این فایل‌ها را داری: {'، '.join(allowed)} (داخل پوشه‌ی اجرای جاری). "
            "فایل دیگری را ننویس؛ نتیجه‌ی کارت فقط همان فایل خروجی است.")


def parse_budget(spec: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Za-z][\w-]*)=([0-9]+)", spec)
    if not m:
        common.fail(f"--budget باید به شکل نام=عدد باشد، نه «{spec}»", 2)
    return m.group(1), int(m.group(2))


def check_budget(name: str, limit: int) -> str | None:
    run_dir = common.current_run()
    if run_dir is None:
        return "هیچ اجرای فعالی نیست؛ بودجه‌ای برای مصرف وجود ندارد."
    d = run_dir / ".budget"
    d.mkdir(exist_ok=True)
    with open(d / name, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)  # فراخوانی‌های موازی نباید هر دو آخرین سهم را بگیرند
        fh.seek(0)
        used = int(fh.read().strip() or 0)
        if used >= limit:
            return (f"بودجه‌ی «{name}» تمام شد ({used} از {limit}). با همان چیزی که داری ادامه بده و در خروجی بنویس کدام موضوع "
                    "بی‌منبع ماند؛ چیزی نساز.")
        fh.seek(0)
        fh.truncate()
        fh.write(str(used + 1))
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locked", action="store_true")
    ap.add_argument("--allow", nargs="+", metavar="الگو")
    ap.add_argument("--budget", metavar="نام=N")
    args = ap.parse_args(argv)
    if not (args.locked or args.allow or args.budget):
        ap.error("دست‌کم یکی از --locked، --allow، --budget لازم است")
    budget = parse_budget(args.budget) if args.budget else None  # آرگومان خراب پیش از هر ورودی و صریح رد می‌شود
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reasons = []
    if data.get("tool_name") in WRITE_TOOLS and (args.locked or args.allow):
        target = target_path(data)
        if target is not None:
            if args.locked:
                reasons.append(check_locked(data, target))
            if args.allow:
                reasons.append(check_allow(target, args.allow))
    reason = next((r for r in reasons if r), None)
    if reason is None and budget:
        reason = check_budget(*budget)
    if reason:
        deny("گاردریل (docs/۰۵): " + reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
