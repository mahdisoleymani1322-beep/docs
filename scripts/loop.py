#!/usr/bin/env python3
"""Loop اصلی (L4؛ docs/۰۴-تکنیک-Loop.md بخش ۳): تصمیم بعد از هر دور، بهترین نسخه، برگشت و گزارش.

چرا کد: «ادامه بدهیم یا نه» و «کدام نسخه بهتر است» باید از نمره‌ی gate و قاعده‌ی ثابت بیاید، نه از قضاوت مدل که وسط کار
معیار را با نتیجه تنظیم می‌کند. هر عدد گزارش به فایلی قابل‌ردیابی (gate.v<n>.json) وصل است و هیچ عددی دستی نوشته نمی‌شود.

  loop.py init <run>                 loop.json: قرارداد و پیکربندی از کارت نوع سند
  loop.py record <run> --version n   دور n را از gate.v<n>.json ثبت و تصمیم بگیر (+ issues.v<n>.json برای دور بعد)
  loop.py finalize <run>             بهترین نسخه ← final/ و گزارش نهایی
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
from fractions import Fraction

import common
import run as runmod

# وضعیت run بعد از هر تصمیم (docs/۰۴ نمودار حالت)
RUN_STATUS = {"continue": "running", "stop_target_met": "ready_for_review", "stop_input_limited": "needs_human",
              "stop_max_rounds": "needs_human", "stop_plateau": "needs_human"}
DECISION_FA = {"continue": "ادامه", "stop_target_met": "توقف: هدف برآورده شد", "stop_input_limited": "توقف: محدود به ورودی",
               "stop_max_rounds": "توقف: سقف دور", "stop_plateau": "توقف: درجا زدن"}


SEVERITY_FA = {"veto": "رد فوری", "critical": "بحرانی", "below_min": "زیر حداقل", "below_target": "زیر هدف", "warn": "هشدار",
               "human": "درخواست انسان"}


def fr(x) -> Fraction:
    return Fraction(str(x))


def fa(x) -> str:
    return common.to_fa_digits(f"{x:g}" if isinstance(x, float) else x).replace(".", "٫")


# ---------------------------------------------------------------- قرارداد

def contract(card: dict) -> dict:
    t = card["loop_target"]["total_gt"]
    return {
        "goal": f"document.json که همه‌ی ردیف‌های روبریک «{card['title']}» را با شاهد پوشش دهد و هیچ رد فوری نداشته باشد",
        "criteria": f"نمره‌ی Loop = total ÷ ۱۰ از gate.v<n>.json؛ هدف: قبولی راهنما و total > {fa(float(t))}",
        "acceptable_risks": ["[نامعلوم]هایی که در gaps.json ثبت شده‌اند (به شرط اعلام نکردن «آماده امضا»)"],
        "unacceptable_risks": ["هر رد فوری", "ادعای واقعی بی‌منبع", "جمع قیمت غلط"],
        "authority_system": ["بازنویسی", "انتخاب نسخه‌ی پایه", "توقف"],
        "authority_human": ["ارسال", "تأیید نهایی", "تغییر روبریک یا گلدن‌ست", "پذیرش سند زیر هدف"]}


def init_loop(run_dir: pathlib.Path) -> dict:
    run = runmod.load_run(run_dir)
    card = common.load_card(run["doc_type"])
    t = card["loop_target"]
    loop = {"run_id": run["run_id"], "doc_type": run["doc_type"], "contract": contract(card),
            "config": {"max_rounds": t["max_rounds"], "total_gt": t["total_gt"], "plateau_rounds": t["plateau_rounds"],
                       "plateau_min_gain": t["plateau_min_gain"]},
            "rounds": [], "best_version": None, "state": "running", "stop_reason": None}
    save_loop(run_dir, loop)
    return loop


def load_loop(run_dir) -> dict:
    p = run_dir / "loop.json"
    if not p.exists():
        common.fail("loop.json نیست؛ اول: loop.py init")
    return common.load_json(p)


def save_loop(run_dir, loop: dict) -> None:
    errors = common.schema_errors(loop, "loop")
    if errors:
        common.fail("loop.json نامعتبر شد (باگ loop.py):\n" + "\n".join(errors[:5]))
    common.dump_json(loop, run_dir / "loop.json")


def load_gate(run_dir, n: int) -> dict:
    p = run_dir / f"gate.v{n}.json"
    if not p.exists():
        common.fail(f"{p.name} نیست؛ اول gate.py")
    g = common.load_json(p)
    errors = common.schema_errors(g, "gate")
    if errors:
        common.fail(f"{p.name} با schema نمی‌خواند:\n" + "\n".join(errors[:5]))
    return g


# ---------------------------------------------------------------- منطق تصمیم (خالص؛ آزمون مستقیم)

def rank(r: dict) -> tuple:
    """بهترین نسخه، به ترتیب اولویت: بدون رد فوری ← قبولی راهنما ← total بالاتر ← دور جدیدتر."""
    return (not r["veto"], r["guide_pass"], fr(r["total"]), r["version"])


def best_of(rounds: list[dict]) -> int:
    return max(rounds, key=rank)["version"]


def summarize(gate: dict, n: int, base: int | None) -> dict:
    below = [c for c in gate["criteria"] if c["final_score"] < 4]
    # «محدود به ورودی» فقط وقتی معنی دارد که ردیفی زیر ۴ باشد؛ وگرنه شرط تهی و همیشه درست می‌شد
    limited = bool(below) and all(c["limited_by_input"] for c in below)
    return {"round": n, "version": n, "base_version": base, "total": gate["total"], "score10": gate["target"]["score10"],
            "guide_pass": gate["guide"]["pass"], "target_met": gate["target"]["met"],
            "veto": sorted({v["id"] for v in gate["veto"]}), "below_target": [c["id"] for c in below],
            "limited_by_input": limited}


def decide(loop: dict, rnd: dict) -> tuple[str, str, int]:
    """پنج قاعده‌ی docs/۰۴ به همان ترتیب. rnd هنوز در loop['rounds'] نیست."""
    cfg = loop["config"]
    rounds = loop["rounds"] + [rnd]
    best = best_of(rounds)
    best_total = fr(next(r for r in rounds if r["version"] == best)["total"])
    if rnd["target_met"]:
        return "stop_target_met", f"قبولی راهنما و total {fa(rnd['total'])} > {fa(cfg['total_gt'])}", best
    if not rnd["veto"] and rnd["limited_by_input"]:
        return "stop_input_limited", "همه‌ی ردیف‌های زیر ۴ محدود به ورودی‌اند؛ بازنویسی بدون ورودی تازه کمکی نمی‌کند", best
    if rnd["round"] >= cfg["max_rounds"]:
        return "stop_max_rounds", f"دور {fa(rnd['round'])} = سقف {fa(cfg['max_rounds'])}؛ بهترین نسخه‌ی {fa(best)} می‌ماند", best
    p = cfg["plateau_rounds"]
    if len(rounds) > p:
        before = best_of(rounds[:-p])
        before_total = fr(next(r for r in rounds if r["version"] == before)["total"])
        gain = best_total - before_total
        if gain < fr(cfg["plateau_min_gain"]):
            return ("stop_plateau", f"بهترین total در {fa(p)} دور اخیر فقط {fa(float(gain))} امتیاز بهتر شد (کمتر از "
                    f"{fa(cfg['plateau_min_gain'])})؛ بهترین نسخه‌ی {fa(best)} می‌ماند", best)
    return "continue", f"هدف برآورده نشد؛ دور بعد روی نسخه‌ی پایه‌ی {fa(best)}", best


def regressions(gate: dict, base_gate: dict | None, n: int, base: int | None) -> list[str]:
    """ردیف‌هایی که نسبت به نسخه‌ی پایه‌ی همین دور افت کرده‌اند؛ تا دور بعد دوباره خرابشان نکند."""
    if base_gate is None:
        return []
    old = {c["id"]: c["final_score"] for c in base_gate["criteria"]}
    return [f"{c['id']}: نمره‌ی {fa(old[c['id']])} ← {fa(c['final_score'])} در نسخه‌ی {fa(n)} (پایه: نسخه‌ی {fa(base)})"
            for c in gate["criteria"] if c["final_score"] < old.get(c["id"], 0)]


# ---------------------------------------------------------------- فرمان‌ها

def record(run_dir: pathlib.Path, n: int) -> dict:
    loop = load_loop(run_dir)
    if loop["state"] != "running":
        common.fail(f"Loop متوقف است ({loop['stop_reason']})؛ دور تازه ثبت نمی‌شود")
    if n != len(loop["rounds"]) + 1:
        common.fail(f"نسخه‌ی {n} نوبت این دور نیست؛ انتظار نسخه‌ی {len(loop['rounds']) + 1}")
    gate = load_gate(run_dir, n)
    if gate["doc_type"] != loop["doc_type"]:
        common.fail("doc_type gate با loop نمی‌خواند")
    prev_issues = run_dir / f"issues.v{n - 1}.json"
    base = common.load_json(prev_issues)["base_version"] if n > 1 and prev_issues.exists() else None
    rnd = summarize(gate, n, base)
    decision, reason, best = decide(loop, rnd)
    rnd.update(decision=decision, reason=reason, best_version_after=best)
    loop["rounds"].append(rnd)
    loop["best_version"] = best
    if decision != "continue":
        loop["state"], loop["stop_reason"] = "stopped", reason
    save_loop(run_dir, loop)
    if decision == "continue":
        # ایرادهای نسخه‌ی پایه‌ی دور بعد = بهترین نسخه، نه لزوماً همین دور
        best_gate = gate if best == n else load_gate(run_dir, best)
        base_gate = load_gate(run_dir, base) if base else None
        common.dump_json({"for_round": n + 1, "base_version": best, "issues": best_gate["issues"],
                          "regressions": regressions(gate, base_gate, n, base)},
                         run_dir / f"issues.v{n}.json")
    runmod.set_run(run_dir, status=RUN_STATUS[decision], round_=n, note=f"دور {n}: {DECISION_FA[decision]}")
    write_log(run_dir, loop)
    return loop


def revision_lines(run_dir: pathlib.Path, n: int) -> list[str]:
    p = run_dir / f"revision.v{n}.json"
    if not p.exists():
        return []
    rev = common.load_json(p)
    out = [f"- رفع‌شده: {i['issue']} — {i['change']}" for i in rev["addressed"]]
    out += [f"- رفع‌نشده: {i['issue']} — {i.get('reason', '')}" for i in rev["not_addressed"]]
    return out


def write_log(run_dir: pathlib.Path, loop: dict) -> str:
    L = ["# ثبت Loop", "", f"اجرا: `{loop['run_id']}` · نوع: {loop['doc_type']} · هدف: total > {fa(loop['config']['total_gt'])}", "",
         "| دور | نسخه‌ی پایه | total | نمره‌ی Loop | قبولی راهنما | رد فوری | ردیف‌های زیر هدف | تصمیم | دلیل |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in loop["rounds"]:
        L.append(f"| {fa(r['round'])} | {fa(r['base_version']) if r['base_version'] else '—'} | {fa(r['total'])} | {fa(r['score10'])} | "
                 f"{'بله' if r['guide_pass'] else 'خیر'} | {'، '.join(r['veto']) or '—'} | {'، '.join(r['below_target']) or '—'} | "
                 f"{DECISION_FA[r['decision']]} | {r['reason']} |")
    L.append("")
    for r in loop["rounds"]:
        n = r["round"]
        L += [f"## دور {fa(n)}", "", f"- فایل‌های شاهد: `gate.v{n}.json`، `checks.v{n}.json`، `judges/v{n}/`"]
        L += revision_lines(run_dir, n) + [""]
    text = "\n".join(L)
    (run_dir / "loop-log.md").write_text(text, encoding="utf-8")
    return text


def finalize(run_dir: pathlib.Path) -> pathlib.Path:
    loop = load_loop(run_dir)
    if loop["state"] != "stopped" or loop["best_version"] is None:
        common.fail("Loop هنوز متوقف نشده؛ finalize فقط بعد از تصمیم توقف")
    b = loop["best_version"]
    gate = load_gate(run_dir, b)
    out = run_dir / "final"
    out.mkdir(exist_ok=True)
    copied = []
    for name in (f"document.v{b}.json", f"document.v{b}.md", f"gate.v{b}.json", f"checks.v{b}.json", "claims.json", "loop.json", "loop-log.md"):
        if (run_dir / name).exists():
            shutil.copyfile(run_dir / name, out / name)
            copied.append(name)
    if (run_dir / "judges" / f"v{b}").exists():
        shutil.copytree(run_dir / "judges" / f"v{b}", out / "judges", dirs_exist_ok=True)
    (out / "report.md").write_text(report(run_dir, loop, gate, copied), encoding="utf-8")
    runmod.set_run(run_dir, stage="finalize", note=f"final/ از نسخه‌ی {b}")
    return out


def report(run_dir, loop: dict, gate: dict, files: list[str]) -> str:
    b = loop["best_version"]
    run = runmod.load_run(run_dir)
    status_fa = {"ready_for_review": "آماده‌ی بررسی انسان", "needs_human": "نیازمند تصمیم انسان"}.get(run["status"], run["status"])
    L = ['<div dir="rtl">', "", "# گزارش نهایی", "",
         f"- **وضعیت:** {status_fa} (بالاترین وضعیتی که سیستم می‌دهد؛ ارسال و تأیید نهایی فقط با انسان است)",
         f"- **بهترین نسخه:** {fa(b)} با total {fa(gate['total'])} (نمره‌ی Loop {fa(gate['target']['score10'])})",
         f"- **قبولی راهنما:** {'بله' if gate['guide']['pass'] else 'خیر'} · باند: {gate['guide']['band']}",
         f"- **هدف Loop (> {fa(gate['target']['threshold'])}):** {'برآورده شد' if gate['target']['met'] else 'برآورده نشد'}",
         f"- **دلیل توقف:** {loop['stop_reason']}"]
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
    L += ["", "## تاریخچه‌ی Loop", ""] + (run_dir / "loop-log.md").read_text(encoding="utf-8").splitlines()[2:]
    L += ["", "## فایل‌های شاهد", ""] + [f"- `{f}`" for f in files] + ["", "</div>", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "record", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("run", nargs="?")
        if name == "record":
            p.add_argument("--version", type=int, required=True)
    args = ap.parse_args(argv)
    run_dir = common.resolve_run(args.run)
    if args.cmd == "init":
        init_loop(run_dir)
        print(run_dir / "loop.json")
    elif args.cmd == "record":
        loop = record(run_dir, args.version)
        r = loop["rounds"][-1]
        print(f"دور {r['round']}: {r['decision']} — {r['reason']}")
    else:
        print(finalize(run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
