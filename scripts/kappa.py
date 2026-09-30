#!/usr/bin/env python3
"""κ ی Cohen بین نمره‌ی داور و برچسب انسان (docs/۰۳ بخش ۵) و ساخت `evals/calibration.json`.

  kappa.py --labels evals/golden/labels.json --judged <پوشه> [--type proposal] [--write]

`<پوشه>/<سند>/rubric.json` (یا `<سند>/judges/rubric.json`) خروجی داور روبریک هر سند گلدن‌ست است. فقط اسنادی که `human.rows` ({"R01": 0..4, …}) دارند سنجیده می‌شوند.
چرا سخت‌گیرانه: κ از برچسب انسان می‌آید؛ برچسب `designed` (خرابیِ عمدی) انسان نیست و هیچ‌وقت κ نمی‌سازد.
بدون برچسب انسانی، فایل کالیبراسیون **ساخته نمی‌شود** و نمره‌ها «فرضیه» می‌مانند؛ کمتر از ۲۰ جفت نمره هم برای نوشتن کافی نیست.
κ وزنی خطی روی مقیاس ۰ تا ۴ و با Fraction است تا گرد شدن مرز ۰٫۶ را جابه‌جا نکند.
"""
from __future__ import annotations

import argparse
import sys
from fractions import Fraction

import common

LEVELS = 5           # نمره‌ی ۰ تا ۴
MIN_PAIRS = 20


def kappa(a: list[int], b: list[int], weighted: bool = True) -> Fraction:
    """κ ی Cohen (وزنی خطی یا ساده). خطای صریح وقتی κ تعریف‌شده نیست (بدون تغییرپذیری)."""
    if len(a) != len(b) or not a:
        raise ValueError("دو فهرست باید هم‌طول و غیرخالی باشند")
    if any(not isinstance(x, int) or isinstance(x, bool) or not 0 <= x < LEVELS for x in a + b):
        raise ValueError(f"نمره‌ها باید عدد صحیح ۰ تا {LEVELS - 1} باشند")
    n = len(a)
    w = (lambda i, j: Fraction(abs(i - j), LEVELS - 1)) if weighted else (lambda i, j: Fraction(int(i != j)))
    observed = sum(w(x, y) for x, y in zip(a, b)) / n
    pa = [Fraction(a.count(i), n) for i in range(LEVELS)]
    pb = [Fraction(b.count(i), n) for i in range(LEVELS)]
    expected = sum(w(i, j) * pa[i] * pb[j] for i in range(LEVELS) for j in range(LEVELS))
    if expected == 0:
        raise ValueError("κ تعریف‌شده نیست: یکی از دو داور همه‌جا یک نمره داده (توافق تصادفی کامل)")
    return 1 - observed / expected


def pairs(labels: dict, judged_dir) -> tuple[list[int], list[int], list[str]]:
    human, judge, used = [], [], []
    for name, lab in labels["docs"].items():
        rows = (lab.get("human") or {}).get("rows")
        if not rows:
            continue
        f = next((c for c in (judged_dir / name / "rubric.json", judged_dir / name / "judges" / "rubric.json") if c.exists()),
                 judged_dir / name / "rubric.json")   # چیدمان results/ گلدن‌ست: <سند>/judges/rubric.json
        if not f.exists():
            raise ValueError(f"برچسب انسان برای {name} هست ولی {f} نیست")
        scores = {c["id"]: c["score"] for c in common.load_json(f)["criteria"]}
        missing = sorted(set(rows) - set(scores))
        if missing:
            raise ValueError(f"{name}: داور این ردیف‌ها را نمره نداده: {', '.join(missing)}")
        for rid in sorted(rows):
            human.append(rows[rid])
            judge.append(scores[rid])
        used.append(name)
    return human, judge, used


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--judged", required=True)
    ap.add_argument("--type", default="proposal", choices=common.DOC_TYPES)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    import pathlib
    try:
        human, judge, used = pairs(common.load_json(args.labels), pathlib.Path(args.judged))
        if not human:
            common.fail("برچسب انسانی نیست (human همه null)؛ κ ساخته نمی‌شود و نمره‌ی داورها «فرضیه» می‌ماند. "
                        "برچسب designed جای برچسب انسان نمی‌نشیند.")
        k = kappa(human, judge)
    except ValueError as e:
        common.fail(str(e))
    print(f"κ وزنی = {float(k):.3f} روی {len(human)} جفت نمره از {len(used)} سند ({', '.join(used)})")
    if args.write:
        if len(human) < MIN_PAIRS:
            common.fail(f"{len(human)} جفت نمره برای نوشتن کالیبراسیون کافی نیست (حداقل {MIN_PAIRS})")
        cal = common.load_json(common.CALIBRATION) if common.CALIBRATION.exists() else {"kappa": {}}
        cal.setdefault("kappa", {})[args.type] = float(k)
        common.dump_json(cal, common.CALIBRATION)
        print(common.CALIBRATION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
