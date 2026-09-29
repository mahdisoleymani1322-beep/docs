#!/usr/bin/env python3
"""اجبار به‌روز بودن handoff.md پیش از هر کامیت و پوش (خواسته‌ی کاربر).

چرا کد و نه قول: قاعده‌ای که فقط در متن نوشته شود فراموش می‌شود. این اسکریپت در دو لایه اجرا می‌شود:
hook گیت (.githooks) برای هر کسی که کامیت می‌کند، و hook پروژه‌ی Claude Code برای ایجنت‌ها.

  check_handoff.py --structure      شش تیتر به ترتیب و هرکدام غیرخالی
  check_handoff.py --staged         + handoff.md جزو تغییرات stage‌شده باشد (hook pre-commit گیت)
  check_handoff.py --push           + آخرین کامیت handoff.md را تغییر داده باشد (hook pre-push گیت)
  check_handoff.py --hook           حالت PreToolUse در Claude Code: فرمان Bash از stdin؛ فقط git commit/push چک می‌شود
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

HEADINGS = ["## 1) Goal", "## 2) Current state", "## 3) Active files",
            "## 4) Changes made", "## 5) Failed attempts", "## 6) Next steps"]
FILE = "handoff.md"


def git(*args: str, cwd: pathlib.Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


def root(cwd: pathlib.Path | None = None) -> pathlib.Path:
    top = git("rev-parse", "--show-toplevel", cwd=cwd).strip()
    return pathlib.Path(top) if top else pathlib.Path.cwd()


def structure_errors(text: str) -> list[str]:
    errors, positions = [], []
    for h in HEADINGS:
        m = re.search(r"(?m)^" + re.escape(h) + r"\s*$", text)
        if not m:
            errors.append(f"تیتر «{h}» در handoff.md نیست")
            continue
        positions.append((m.start(), m.end(), h))
    if [p[2] for p in sorted(positions)] != [p[2] for p in positions]:
        errors.append("ترتیب شش تیتر handoff.md به‌هم خورده است")
    ordered = sorted(positions)
    for i, (_, end, h) in enumerate(ordered):
        nxt = ordered[i + 1][0] if i + 1 < len(ordered) else len(text)
        body = re.sub(r"</?div[^>]*>", "", text[end:nxt]).strip()
        if not body:
            errors.append(f"بخش «{h}» خالی است")
    return errors


def check(mode: str, cwd: pathlib.Path | None = None) -> list[str]:
    top = root(cwd)
    path = top / FILE
    if not path.exists():
        return [f"{FILE} در ریشه‌ی ریپو وجود ندارد"]
    errors = structure_errors(path.read_text(encoding="utf-8"))
    if mode == "staged":
        if FILE not in git("diff", "--cached", "--name-only", cwd=top).split():
            errors.append(f"{FILE} در این کامیت به‌روز نشده (stage نشده است)")
    elif mode == "commit-intent":
        # hook ایجنت پیش از اجرای «git add … && git commit» صدا زده می‌شود؛ پس تغییرِ هنوز stage‌نشده هم پذیرفته است
        # status و نه diff: فایل تازه (untracked) هم تغییر حساب شود
        if not git("status", "--porcelain", "--", FILE, cwd=top).strip():
            errors.append(f"{FILE} نسبت به آخرین کامیت تغییری ندارد؛ به‌روزش کن. این hook پیش از اجرای فرمان چک می‌کند، پس "
                          "ویرایشِ handoff داخل همان فرمان کامیت دیده نمی‌شود؛ اول handoff را در یک فرمان جدا ویرایش کن، "
                          "بعد کامیت را در فرمان بعدی بزن")
    elif mode == "push":
        if FILE not in git("diff", "--name-only", "HEAD~1", "HEAD", cwd=top).split():
            errors.append(f"آخرین کامیت {FILE} را به‌روز نکرده است؛ پیش از پوش به‌روزش کن و کامیت کن")
    return errors


HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?:\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
# git در ابتدای فرمان یا بعد از جداکننده‌ی فرمان؛ با متغیر محیطی و گزینه‌های سراسری (-C dir، -c k=v) پیش از زیرفرمان
GIT_CMD = r"(?:^|[;&|(\n])\s*(?:\w+=\S*\s+)*git\s+(?:(?:-C|-c)\s+\S+\s+|--[\w-]+(?:=\S+)?\s+)*"


def git_action(command: str) -> str | None:
    """«commit» یا «push» فقط اگر واقعاً فرمان git باشد، نه متنی داخل رشته یا heredoc.

    چرا: نسخه‌ی اول کل متن فرمان را با regex می‌گشت و فرمانی که فقط «git commit» را در یک رشته‌ی پایتون یا پیام
    می‌نوشت (مثل ویرایش CLAUDE.md) به‌اشتباه رد می‌شد.
    """
    bare = QUOTED.sub("''", HEREDOC.sub("\n", command))
    for action in ("commit", "push"):
        if re.search(GIT_CMD + action + r"\b", bare):
            return action
    return None


def hook() -> int:
    """PreToolUse: فقط وقتی فرمان Bash واقعاً git commit یا git push اجرا می‌کند دخالت می‌کند."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    action = git_action(command)
    if action == "commit":
        mode = "commit-intent"
    elif action == "push":
        mode = "push"
    else:
        return 0
    errors = check(mode, pathlib.Path(data.get("cwd") or "."))
    if not errors:
        return 0
    reason = "قاعده‌ی handoff.md (CLAUDE.md بخش ۴): " + "؛ ".join(errors)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--structure", action="store_true")
    g.add_argument("--staged", action="store_true")
    g.add_argument("--push", action="store_true")
    g.add_argument("--hook", action="store_true")
    args = ap.parse_args(argv)
    if args.hook:
        return hook()
    mode = "staged" if args.staged else "push" if args.push else "structure"
    errors = check(mode)
    for e in errors:
        print(f"✗ {e}", file=sys.stderr)
    if not errors:
        print(f"✓ {FILE}: {mode}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
