#!/usr/bin/env python3
"""دروازه (لایه‌ی ۳ ارزیابی؛ docs/۰۳-سیستم-ارزیابی.md بخش ۳ و ۴).

چرا کد: تصمیم قبول یا رد باید قابل‌پیش‌بینی و قابل‌آزمون باشد. داور فقط نمره‌ی ردیف را می‌دهد؛ سقف‌ها از چک‌های قطعی و
داور ادعا می‌آیند و جمع‌بندی فقط اینجا انجام می‌شود، با فرمول ثابت و بدون گرد کردن. هیچ ایجنتی عدد نهایی نمی‌نویسد.

  gate.py <run> --version n
  gate.py --checks f --rubric f --claims f --veto f [-o out]

حساب با Fraction است (نه float) تا مرزهایی مثل «۹۰٫۰ هدف را برآورده نمی‌کند» به خطای ممیز شناور وابسته نباشد.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from fractions import Fraction

import common

KAPPA_MIN = Fraction(6, 10)  # docs/۰۳ بخش ۵: κ < ۰٫۶ ← نمره‌ی داور «فرضیه»
MD_REASON = "چک ساختاری اجرا نشد (سند ساخت‌یافته نیست)؛ بدون آن، قبولی راهنما گواهی نمی‌شود"


def fr(x) -> Fraction:
    return Fraction(str(x))


def judges_valid(doc_type: str) -> bool:
    """نبودن فایل کالیبراسیون یا κ زیر حد ← false. فایل را kappa.py (فاز D) می‌سازد: {"kappa": {"<type>": عدد}}."""
    path = common.CALIBRATION
    if not path.exists():
        return False
    k = common.load_json(path).get("kappa", {}).get(doc_type)
    return k is not None and fr(k) >= KAPPA_MIN


def fa(x) -> str:
    """عدد در متن‌های تولیدی gate فارسی است (قاعده‌ی CHK-DIGITS)؛ ۷٫۵ نه 7.5."""
    return common.to_fa_digits(f"{x:g}" if isinstance(x, float) else x).replace(".", "٫")


def first_section(locations: list[str]) -> str | None:
    return next((m.group() for loc in locations if (m := re.search(r"S[0-9]{2}", loc))), None)


def compute(card: dict, checks: dict, rubric: dict, claims: dict, veto: dict) -> dict:
    doc_type = card["doc_type"]
    text_mode = checks["mode"] == "text"
    judge = {c["id"]: c for c in rubric["criteria"]}
    veto_text = {v["id"]: v["text"] for v in card["veto"]}

    # --- سقف‌ها ---
    caps: dict[str, list[dict]] = {c["id"]: [] for c in card["criteria"]}
    for r in checks["results"]:
        for c in r["caps"]:
            caps[c["criterion"]].append({"max": c["max"], "source": r["id"], "detail": r["detail"]})
    ledger_row = card["claims_criterion"]
    for status, mx in (("contradicts_ledger", 0), ("unsupported", 1)):
        bad = [c for c in claims["claims"] if c["status"] == status]
        if bad:
            caps[ledger_row].append({"max": mx, "source": "judge-claims",
                                     "detail": f"{fa(len(bad))} ادعای {status}: «{bad[0]['quote'][:60]}»" + (" …" if len(bad) > 1 else "")})

    # --- امتیاز ---
    rows, total = [], Fraction(0)
    for c in card["criteria"]:
        if c["id"] not in judge:
            common.fail(f"گزارش داور ردیف {c['id']} را ندارد")
        j = judge[c["id"]]
        final = min([j["score"]] + [x["max"] for x in caps[c["id"]]])
        pts = fr(c["weight"]) * final / 4
        total += pts
        rows.append({"id": c["id"], "title": c["title"], "weight": c["weight"], "judge_score": j["score"], "caps": caps[c["id"]],
                     "final_score": final, "points": float(pts), "limited_by_input": j["limited_by_input"], "fix": j["fix"],
                     "_pts": pts, "_sections": c["sections"]})

    # --- رد فوری ---
    vetoes = [{"id": v, "source": r["id"], "detail": r["detail"], "_sec": first_section(r["locations"])}
              for r in checks["results"] for v in r["veto"]]
    vetoes += [{"id": h["veto_id"], "source": "judge-veto", "detail": f"{h['reason']} — «{h['quote']}» ({h['section']})",
                "_sec": h["section"]} for h in veto["hits"]]

    # --- قبولی راهنما ---
    gate = card["gate"]
    reasons = []
    if total < fr(gate["min_total"]):
        reasons.append(f"total {fa(float(total))} کمتر از حداقل {fa(float(gate['min_total']))}")
    crit = gate["critical"]
    for r in rows:
        if r["final_score"] < gate["min_row"]:
            reasons.append(f"ردیف {r['id']} ({r['title']}) نمره‌ی {fa(r['final_score'])} دارد؛ حداقل {fa(gate['min_row'])}")
        elif crit and r["id"] in crit["criteria"] and r["final_score"] < crit["min"]:
            reasons.append(f"ردیف حیاتی {r['id']} ({r['title']}) نمره‌ی {fa(r['final_score'])} دارد؛ حداقل {fa(crit['min'])}")
    for v in sorted({x["id"] for x in vetoes}):
        reasons.append(f"رد فوری {v}: {veto_text.get(v, '')}")
    if text_mode:
        reasons.append(MD_REASON)
    passed = not reasons

    band = next(b["label"] for b in sorted(card["bands"], key=lambda b: -b["min"]) if total >= fr(b["min"]))
    target = card["loop_target"]["total_gt"]
    out = {"version": checks["version"], "doc_type": doc_type,
           "criteria": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
           "total": float(total), "veto": [{k: v for k, v in x.items() if not k.startswith("_")} for x in vetoes],
           "guide": {"pass": passed, "band": band, "fail_reasons": reasons},
           "target": {"met": passed and total > fr(target), "threshold": target, "score10": float(total / 10)},
           "issues": build_issues(card, rows, checks, vetoes, veto_text, text_mode),
           "judges_valid": judges_valid(doc_type),
           "bottom_line": rubric.get("bottom_line"), "biggest_weakness": rubric.get("biggest_weakness")}
    return out


def build_issues(card, rows, checks, vetoes, veto_text, text_mode) -> list[dict]:
    """ترتیب docs/۰۴ بخش ۳: رد فوری ← حیاتی ← زیر حداقل ردیف ← بقیه به ترتیب امتیاز از دست‌رفته ← هشدار."""
    gate = card["gate"]
    crit_rows = set(gate["critical"]["criteria"]) if gate["critical"] else set()
    crit_min = gate["critical"]["min"] if gate["critical"] else 0
    groups: list[list[dict]] = [[], [], [], [], []]

    for v in vetoes:
        groups[0].append({"source": f"{v['id']}/{v['source']}", "severity": "veto", "section": v["_sec"],
                          "text": f"رد فوری {v['id']} ({veto_text.get(v['id'], '')}): {v['detail']}", "points_at_stake": None})
    for r in checks["results"]:
        if r["status"] == "fail" and r["severity"] == "critical" and not r["veto"]:
            groups[1].append({"source": r["id"], "severity": "critical", "section": first_section(r["locations"]),
                              "text": f"{r['id']}: {r['detail']}", "points_at_stake": None})
    for r in rows:
        lost = fr(r["weight"]) * (4 - r["final_score"]) / 4
        if lost == 0:
            continue
        # علت سقف همان چیزی است که نویسنده باید رفع کند؛ پس detail چک عیناً می‌آید
        cap_note = "؛ علت سقف: " + "؛ ".join(f"{c['source']} ≤ {fa(c['max'])} ({c['detail']})" for c in r["caps"]) if r["caps"] else ""
        advice = r["fix"] or ("" if r["caps"] else "داور توصیه‌ای ثبت نکرده؛ گزارش داور را ببینید")
        limited = " (محدود به ورودی: بدون اطلاعات تازه بهتر نمی‌شود)" if r["limited_by_input"] else ""
        item = {"source": r["id"], "section": r["_sections"][0] if r["_sections"] else None, "points_at_stake": float(lost),
                "text": f"{r['id']} {r['title']}: نمره {fa(r['final_score'])} از ۴" + (f". {advice}" if advice else "") + f"{cap_note}{limited}"}
        if r["id"] in crit_rows and r["final_score"] < crit_min:
            groups[1].append({**item, "severity": "critical", "_lost": lost})
        elif r["final_score"] < gate["min_row"]:
            groups[2].append({**item, "severity": "below_min", "_lost": lost})
        else:
            groups[3].append({**item, "severity": "below_target", "_lost": lost})
    for r in checks["results"]:
        if r["status"] in ("warn", "fail") and r["severity"] == "warn":
            groups[4].append({"source": r["id"], "severity": "warn", "section": first_section(r["locations"]),
                              "text": f"{r['id']}: {r['detail']}", "points_at_stake": None})
    if text_mode:
        groups[4].append({"source": "checks", "severity": "warn", "section": None, "points_at_stake": None,
                          "text": "سند ساخت‌یافته نیست؛ چک‌های ساختاری اجرا نشده‌اند"})
    out = []
    for g in groups:
        # ترتیب داخل گروه: امتیاز از دست‌رفته‌ی بیشتر اول (پایدار برای مساوی‌ها)
        g.sort(key=lambda i: -(i.get("_lost") or 0))
        out += g
    for n, i in enumerate(out, 1):
        i.pop("_lost", None)
        i["id"] = f"I-{n:02d}"
    return out


def load_validated(path, schema: str):
    data = common.load_json(path)
    errors = common.schema_errors(data, schema)
    if errors:
        common.fail(f"{path} با schema {schema} نمی‌خواند:\n" + "\n".join(errors[:5]))
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?")
    ap.add_argument("--version", type=int)
    for k in ("checks", "rubric", "claims", "veto"):
        ap.add_argument(f"--{k}")
    ap.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    if args.checks:
        paths = {k: getattr(args, k) for k in ("checks", "rubric", "claims", "veto")}
        if not all(paths.values()):
            common.fail("با --checks هر چهار فایل لازم است: --checks --rubric --claims --veto")
        out = args.out
    else:
        if args.version is None:
            common.fail("--version لازم است")
        d = common.resolve_run(args.run)
        n = args.version
        paths = {"checks": d / f"checks.v{n}.json", "rubric": d / f"judges/v{n}/rubric.json",
                 "claims": d / f"judges/v{n}/claims.json", "veto": d / f"judges/v{n}/veto.json"}
        out = args.out or str(d / f"gate.v{n}.json")
    checks = load_validated(paths["checks"], "checks")
    if any(r["id"] == "CHK-SCHEMA" and r["status"] == "fail" for r in checks["results"]):
        common.fail("CHK-SCHEMA رد شده؛ سند نمره نمی‌گیرد (اجرا failed)", 2)
    rubric = load_validated(paths["rubric"], "judge-rubric")
    claims = load_validated(paths["claims"], "judge-claims")
    veto = load_validated(paths["veto"], "judge-veto")
    for name, rep in (("rubric", rubric), ("claims", claims), ("veto", veto)):
        if rep["version"] != checks["version"]:
            common.fail(f"نسخه‌ی گزارش {name} ({rep['version']}) با checks ({checks['version']}) نمی‌خواند")
    data = compute(common.load_card(checks["doc_type"]), checks, rubric, claims, veto)
    errors = common.schema_errors(data, "gate")
    if errors:
        common.fail("خروجی gate با schema نمی‌خواند (باگ gate.py):\n" + "\n".join(errors[:5]))
    if out:
        common.dump_json(data, out)
        print(out)
    g = data["guide"]
    print(f"total={data['total']:g}  score10={data['target']['score10']:g}  band={g['band']}  "
          f"pass={g['pass']}  target={data['target']['met']}  veto={len(data['veto'])}", file=sys.stderr)
    for r in g["fail_reasons"]:
        print(f"✗ {r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
