#!/usr/bin/env python3
"""برش یک فصل از راهنما برای کانتکست یک ایجنت.

چرا: سیاست کانتکست (CLAUDE.md بخش ۳) — هیچ ایجنتی کل راهنما را نمی‌خواند. نام برش‌ها و تیتر
دقیق هر فصل در کلید slices کارت نوع سند است؛ این اسکریپت فقط همان را برش می‌دهد.

  slice_guide.py <doc_type> <slice>     متن فصل (از تیتر تا پیش از تیتر سطح‌اول بعدی)
  slice_guide.py <doc_type> --list      نام برش‌های موجود
"""
from __future__ import annotations

import argparse
import sys

import common


def guide_text(card: dict) -> str:
    # راهنماها با پایان‌خط ویندوز آپلود شده‌اند؛ برش باید مستقل از آن باشد
    return (common.ROOT / card["guide"]).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def slice_chapter(doc_type: str, name: str) -> str:
    card = common.load_card(doc_type)
    if name not in card["slices"]:
        raise KeyError(f"برش «{name}» برای {doc_type} تعریف نشده؛ موجود: {', '.join(card['slices'])}")
    heading = card["slices"][name]
    text = guide_text(card)
    start = text.find(heading + "\n")
    if start == -1:
        raise ValueError(f"تیتر «{heading}» در {card['guide']} پیدا نشد")
    end = text.find("\n## ", start + 1)
    return text[start: end if end != -1 else len(text)].rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc_type", choices=common.DOC_TYPES)
    ap.add_argument("slice", nargs="?")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    card = common.load_card(args.doc_type)
    if args.list or not args.slice:
        for name, heading in card["slices"].items():
            print(f"{name}\t{heading}")
        return 0
    try:
        sys.stdout.write(slice_chapter(args.doc_type, args.slice))
    except (KeyError, ValueError) as exc:
        common.fail(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
