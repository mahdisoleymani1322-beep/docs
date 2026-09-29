"""بخش مشترک گزارش‌های مبتنی بر gate.v<n>.json (گزارش Loop و گزارش ارزیابی سند موجود).

چرا جدا: دو گزارش نباید دو نسخه‌ی متفاوت از «چرا قبول نشد» و «ایرادهای باقی‌مانده» داشته باشند؛ هر عدد و جمله فقط از gate می‌آید.
"""
from __future__ import annotations

import common

SEVERITY_FA = {"veto": "رد فوری", "critical": "بحرانی", "below_min": "زیر حداقل", "below_target": "زیر هدف", "warn": "هشدار",
               "human": "درخواست انسان"}
STATUS_FA = {"ready_for_review": "آماده‌ی بررسی انسان", "needs_human": "نیازمند تصمیم انسان"}


def fa(x) -> str:
    return common.to_fa_digits(f"{x:g}" if isinstance(x, float) else x).replace(".", "٫")


def sections(gate: dict, target_label: str = "هدف Loop") -> list[str]:
    """خطوط قبولی و هدف؛ بقیه‌ی گزارش (هشدار، دلیل رد، ایرادها) در tail()."""
    L = [f"- **قبولی راهنما:** {'بله' if gate['guide']['pass'] else 'خیر'} · باند: {gate['guide']['band']}",
         f"- **{target_label} (> {fa(gate['target']['threshold'])}):** {'برآورده شد' if gate['target']['met'] else 'برآورده نشد'}"]
    return L


def tail(gate: dict) -> list[str]:
    L = []
    if not gate["judges_valid"]:
        L.append("- **هشدار:** داورها کالیبره نشده‌اند (یا κ < ۰٫۶)؛ نمره‌ها **فرضیه**‌اند، نه اندازه‌گیری تأییدشده.")
    if gate["guide"]["fail_reasons"]:
        L += ["", "## چرا قبول نشد", ""] + [f"- {x}" for x in gate["guide"]["fail_reasons"]]
    if gate.get("bottom_line"):
        L += ["", "## خط پایانی داور", "", gate["bottom_line"]]
    w = gate.get("biggest_weakness")
    if w:
        L += ["", f"**بزرگ‌ترین ضعف ({w['criterion']}):** {w['what']} — {w['why']}. راه‌حل: {w['fix']}"]
    if gate["issues"]:
        L += ["", "## ایرادهای باقی‌مانده (به ترتیب اثر)", ""] + [f"- ({SEVERITY_FA[i['severity']]}) {i['text']}" for i in gate["issues"]]
    return L


def score_table(gate: dict) -> list[str]:
    """ردیف‌های روبریک با نمره‌ی داور، سقف‌ها و نمره‌ی نهایی؛ شاهد هر عدد همین جدول است."""
    L = ["| ردیف | معیار | وزن | نمره‌ی داور | سقف‌ها | نمره‌ی نهایی | امتیاز |", "|---|---|---|---|---|---|---|"]
    for c in gate["criteria"]:
        caps = "؛ ".join(f"{x['source']} ≤ {fa(x['max'])}" for x in c["caps"]) or "—"
        L.append(f"| {c['id']} | {c['title']} | {fa(c['weight'])} | {fa(c['judge_score'])} | {caps} | {fa(c['final_score'])} | {fa(c['points'])} |")
    return L + [""]
