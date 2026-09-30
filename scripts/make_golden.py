#!/usr/bin/env python3
"""ساخت گلدن‌ست D2 از سند خوبِ آزمون‌ها: `evals/golden/*.json` + `claims.json` + `labels.json`.

چرا اسکریپت و نه فایل دستی: هر سند خراب دقیقاً **یک** جهش از پایه‌ی خوب است؛ با این اسکریپت علتِ هر انتظار روشن و قابل بازتولید می‌ماند.
مسیر `evals/golden/` قفل است (CLAUDE.md بخش ۲)؛ اجرا فقط با درخواست صریح انسان و `STUDIO_ALLOW_LOCKED=1`، بیرون از هر اجرای استودیو.
برچسب‌ها `designed` هستند (خرابیِ عمدیِ ساخته‌ی همین اسکریپت)؛ `human` تا وقتی انسان پر نکرده `null` می‌ماند و هیچ نمره‌ی ردیفی جعلی ساخته نمی‌شود.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import common

BASE = common.ROOT / "tests" / "fixtures" / "document.good.json"
CLAIMS = common.ROOT / "tests" / "fixtures" / "claims.good.json"
OUT = common.ROOT / "evals" / "golden"


def golden_input() -> dict:
    """ورودی مشترک گلدن‌ست: منبعِ ادعاهای C-01 تا C-03 (`input: discovery_notes`) باید واقعاً در ورودی باشد.

    چرا: اولین اجرای زنده‌ی داورها روی good-1 بدون ورودی، همه‌ی ادعاها را «بی‌منبع» و V01 گرفت؛ داورها درست می‌دیدند و ایراد از خودِ
    گلدن‌ست بود (ورودی خالی)، پس ورودی جزو مجموعه شد. دور دوم: نسخه‌ی کپی‌شده از proposal-complete با سند نمی‌خواند (بتا/آلفا، ۳۰/۳۰/۴۰ در برابر ۴۰/۶۰)؛
    داور veto ناسازگاری را گزارش کرد. پس ورودی فقط فیلدهای پشتوانه‌ی ادعاها را دارد.
    """
    d = common.load_json(common.ROOT / "examples" / "inputs" / "proposal-complete.json")
    keep = {"client_identity", "discovery_notes"}
    d["fields"] = {k: (v if k in keep else None) for k, v in d["fields"].items()}   # بقیه‌ی فیلدها با سند نمی‌خواند؛ ورودی فقط پشتوانه‌ی ادعاهاست
    d["fields"]["client_identity"] = "شرکت نمونه‌ی آلفا (مشتری نمونه)"
    d["fields"]["discovery_notes"] = ("در جلسه‌ی کشف مورخ ۱۴۰۵/۰۶/۳۰ (داده‌ی نمایشی) مدیر فروش گفت بازبینی دستی پیش‌نویس‌ها گلوگاه پاسخ‌گویی است؛ "
                                     "هر پیش‌نویس پاسخ پیش از ارسال توسط یک کارشناس فروش بازبینی می‌شود؛ نمونه‌ی قابل بررسی در همان جلسه نمایش داده شد.")
    return d


def clean_base(d):
    """دو جمله‌ی پایه‌ی آزمون‌ها ادعای واقعی بی‌پشتوانه بودند (داور ادعا در اجرای زنده‌ی good-1 unsupported داد)؛ گلدنِ «خوب» نباید آن‌ها را داشته باشد.

    فقط نسخه‌ی گلدن پاک می‌شود؛ fixture آزمون‌ها همان می‌ماند.
    """
    section(d, "S03")["blocks"][1]["text"] = "وضعیت کانال‌های دیگر هنوز بررسی نشده و در این پیشنهاد فرض نمی‌شود."
    section(d, "S14")["blocks"][0]["text"] = "نمونه‌ی قابل بررسی در جلسه‌ی کشف نمایش داده شد [C-03]. نتایج تجاری مشتریان قبلی در این سند ادعا نمی‌شود."
    return d


def section(doc, sid):
    return next(s for s in doc["sections"] if s["id"] == sid)


def good_1(d):
    return d


def good_2(d):
    """فقط پرداخت سه‌مرحله‌ای؛ باز هم بی‌عیب (جمع ۱۰۰٪، هر رویداد به تحویل وصل).

    تغییر مدت مرحله را برداشتیم: داور veto دید جمع مدت‌ها با موعد تحویل‌ها نمی‌خواند (اجرای زنده)؛ گلدن خوب نباید ناسازگاری بسازد.
    """
    d["data"]["pricing"]["payments"] = [
        {"id": "PAY-01", "event": "امضای توافق دامنه", "deliverable": None, "percent": 30},
        {"id": "PAY-02", "event": "پذیرش سند معیارهای ارزیابی", "deliverable": "D-01", "percent": 30},
        {"id": "PAY-03", "event": "پذیرش گزارش ارزیابی پایلوت", "deliverable": "D-02", "percent": 40}]
    return d


def bad_guarantee(d):
    section(d, "S02")["blocks"].insert(1, {"kind": "para", "text": "این پایلوت بی‌خطا اجرا می‌شود و افزایش درآمد را تضمین می‌کنیم."})
    return d


def bad_price_sum(d):
    d["data"]["pricing"]["totals"]["one_time"] += 10_000_000
    return d


def bad_unsourced(d):
    section(d, "S03")["blocks"].append({"kind": "para", "text": "مشتریان مشابه ما زمان بازبینی را در پایلوت به‌طور میانگین ۴۰ درصد کم کرده‌اند [C-99]."})
    return d


def bad_no_acceptance(d):
    d["data"]["deliverables"][0]["acceptance"] = None
    d["data"]["acceptance"] = [a for a in d["data"]["acceptance"] if a["id"] != "A-01"]
    return d


# شناسه ← (تابع جهش، شرح، چک‌هایی که باید بشکنند، veto مورد انتظار کد، veto مورد انتظار داور)
DOCS = {
    "good-1": (good_1, "پایه‌ی خوب بدون جهش", [], [], []),
    "good-2": (good_2, "پایه‌ی خوب فقط با پرداخت سه‌مرحله‌ای (۳۰/۳۰/۴۰)", [], [], []),
    "bad-guarantee": (bad_guarantee, "جمله‌ی «بی‌خطا اجرا می‌شود … تضمین می‌کنیم» در خلاصه‌ی اجرایی", ["CHK-BANNED"], ["V02"], ["V02"]),
    "bad-price-sum": (bad_price_sum, "جمع یک‌باره ۱۰ میلیون بیشتر از مجموع اقلام", ["CHK-PRICE-SUM"], ["V03"], []),
    "bad-unsourced": (bad_unsourced, "ادعای عددی درباره‌ی مشتریان مشابه با ارجاع C-99 که در دفتر ادعا نیست", ["CHK-CLAIM-REFS"], [], []),
    "bad-no-acceptance": (bad_no_acceptance, "حذف معیار پذیرش A-01 از تحویل D-01", ["CHK-D-A"], ["V05"], ["V05"]),
}


def build(out: pathlib.Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    base = clean_base(common.load_json(BASE))
    labels = {"note": "kind=designed یعنی خرابی عمدیِ ساخته‌ی make_golden.py، نه برچسب انسان؛ human را فقط انسان پر می‌کند",
              "docs": {}}
    for name, (fn, why, checks, veto_code, veto_judge) in DOCS.items():
        common.dump_json(fn(copy.deepcopy(base)), out / f"{name}.json")
        labels["docs"][name] = {"kind": "designed", "mutation": why, "expect_failed_checks": checks,
                                "expect_veto_code": veto_code, "expect_veto_judge": veto_judge, "human": None}
    common.dump_json(common.load_json(CLAIMS), out / "claims.json")
    common.dump_json(golden_input(), out / "input.json")
    common.dump_json(labels, out / "labels.json")
    return labels


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
