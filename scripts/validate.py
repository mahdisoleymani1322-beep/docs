#!/usr/bin/env python3
"""اعتبارسنجی خروجی‌ها: schema + چک‌های متقاطع قرارداد (docs/۰۲-قرارداد-ایجنت‌ها.md بخش ۳).

چرا جدا از checks.py: این‌جا «قرارداد» چک می‌شود (شکل درست، ارجاع موجود، نقل‌قول واقعی)؛ خطایش یعنی خروجی
قابل استفاده نیست و ایجنت باید اصلاحش کند. کیفیت سند (جمع قیمت، عبارت ممنوع) کار checks.py است و نمره می‌گیرد.

  validate.py <file> [<file> ...] [--schema name]   فقط schema، بر اساس نام فایل (یا --schema)
  validate.py --run <run> --stage <stage>           schema + چک متقاطع خروجی یک مرحله (نسخه = round در run.json)
  validate.py --hook --stage <stage>                حالت hook توقف ایجنت: خطا ← یک بار block با فهرست خطا
مرحله‌ها: intake | brief | claims | write | judge-rubric | judge-claims | judge-veto | critic
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import common

STAGES = ("intake", "brief", "claims", "write", "judge-rubric", "judge-claims", "judge-veto", "critic")
MAX_HOOK_RETRIES = 1  # یک اصلاح و بعد توقف (الگوی arkan: یک retry با فیدبک خطا)
CLAIM_REF = re.compile(r"\[(C-[0-9]{2})\]")


def _load(run_dir: pathlib.Path, name: str, schema: str, errors: list[str]):
    path = run_dir / name
    if not path.exists():
        errors.append(f"{name}: فایل وجود ندارد")
        return None
    try:
        data = common.load_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"{name}: JSON خراب است ({exc})")
        return None
    schema_errs = common.schema_errors(data, schema)
    if schema_errs:
        # چک متقاطع روی داده‌ی بدشکل معنا ندارد و ممکن است خودش خطا بدهد؛ اول شکل درست شود
        errors.extend(f"{name}: {e}" for e in schema_errs)
        return None
    return data


def _dupes(ids) -> list[str]:
    seen, dup = set(), []
    for i in ids:
        if i in seen:
            dup.append(i)
        seen.add(i)
    return dup


def _doc_text(run_dir: pathlib.Path, version: int, errors: list[str]) -> str | None:
    md = run_dir / f"document.v{version}.md"
    if not md.exists():
        errors.append(f"document.v{version}.md وجود ندارد؛ نقل‌قول‌ها قابل بررسی نیستند")
        return None
    return common.normalize(common.strip_markdown(md.read_text(encoding="utf-8")))


def _check_quotes(items, text_norm: str, label: str, errors: list[str]) -> None:
    for i, item in enumerate(items):
        if not common.quote_in_text(item["quote"], text_norm):
            errors.append(f"{label}[{i}]: نقل‌قول در متن سند پیدا نشد (شاهد ساختگی؟): «{item['quote'][:80]}»")


# ---------------------------------------------------------------- مرحله‌ها

def check_intake(run_dir, run, card, errors):
    import run as runmod
    gaps = _load(run_dir, "gaps.json", "gaps", errors)
    questions = _load(run_dir, "questions.json", "questions", errors)
    if gaps is None or questions is None:
        return
    gap_ids = [g["id"] for g in gaps["gaps"]]
    errors.extend(f"gaps.json: شناسه‌ی تکراری {d}" for d in _dupes(gap_ids))
    keys = {f["key"] for f in card["intake_fields"]} | {"general"}
    for g in gaps["gaps"]:
        if g["field"] not in keys:
            errors.append(f"gaps.json: {g['id']} به فیلد ناشناخته‌ی «{g['field']}» اشاره می‌کند")
    state = runmod.intake_state(run_dir)
    by_field = {}
    for g in gaps["gaps"]:
        by_field.setdefault(g["field"], []).append(g)
    for key in state["missing"]:
        if key not in by_field:
            errors.append(f"gaps.json: فیلد الزامیِ خالی «{key}» در کمبودها نیامده (کمبود نباید پنهان شود)")
    for key in state["blocking_missing"]:
        if key in by_field and not any(g["blocking"] for g in by_field[key]):
            errors.append(f"gaps.json: «{key}» در کارت مسدودکننده است؛ gap آن باید blocking: true باشد")
    q_ids = [q["id"] for q in questions["questions"]]
    errors.extend(f"questions.json: شناسه‌ی تکراری {d}" for d in _dupes(q_ids))
    for q in questions["questions"]:
        if q["gap"] not in gap_ids:
            errors.append(f"questions.json: {q['id']} به gap ناموجود {q['gap']} اشاره می‌کند")


def check_brief(run_dir, run, card, errors):
    brief = _load(run_dir, "brief.json", "brief", errors)
    if brief is None:
        return
    if brief["doc_type"] != run["doc_type"]:
        errors.append(f"brief.json: doc_type={brief['doc_type']} با اجرا ({run['doc_type']}) نمی‌خواند")
    card_secs = {s["id"]: s["title"] for s in card["sections"]}
    ids = [s["id"] for s in brief["sections"]]
    errors.extend(f"brief.json: بخش تکراری {d}" for d in _dupes(ids))
    for s in brief["sections"]:
        if s["id"] not in card_secs:
            errors.append(f"brief.json: بخش {s['id']} در کارت نوع سند نیست")
        elif s["title"] != card_secs[s["id"]]:
            errors.append(f"brief.json: عنوان {s['id']} باید «{card_secs[s['id']]}» باشد، نه «{s['title']}»")
    for s in card["sections"]:
        if s["required"] and s["id"] not in ids:
            errors.append(f"brief.json: بخش الزامی {s['id']} («{s['title']}») در بریف نیست")
    gaps_path = run_dir / "gaps.json"
    gap_ids = {g["id"] for g in common.load_json(gaps_path)["gaps"]} if gaps_path.exists() else set()
    for s in brief["sections"]:
        for g in s["gaps"]:
            if g not in gap_ids:
                errors.append(f"brief.json: {s['id']} به gap ناموجود {g} اشاره می‌کند")
    lw = brief["length_budget"]
    if lw["min_words"] > lw["max_words"]:
        errors.append("brief.json: min_words بزرگ‌تر از max_words است")


def check_claims(run_dir, run, card, errors):
    claims = _load(run_dir, "claims.json", "claims", errors)
    if claims is None:
        return
    inp = common.load_json(run_dir / "input.json")
    errors.extend(f"claims.json: شناسه‌ی تکراری {d}" for d in _dupes(c["id"] for c in claims["claims"]))
    urls = {u for s in claims["searches"] for u in s["urls"]}
    answers = {a["question"] for a in inp["answers"]}
    attachments = {a["name"] for a in inp["attachments"]}
    brand_proof = {p["id"] for p in common.load_brand(run.get("brand"))["proof"]}
    sec_ids = {s["id"] for s in card["sections"]}
    import run as runmod
    for c in claims["claims"]:
        src = c["source"]
        if src:
            if src["kind"] == "input":
                if src["ref"] in answers:
                    pass
                elif src["ref"] not in inp["fields"]:
                    errors.append(f"claims.json: {c['id']} به فیلد ناموجود «{src['ref']}» استناد می‌کند")
                elif not runmod._filled(inp["fields"][src["ref"]]):
                    errors.append(f"claims.json: {c['id']} به فیلد خالی «{src['ref']}» استناد می‌کند")
            elif src["kind"] == "url" and src["ref"] not in urls:
                errors.append(f"claims.json: {c['id']} به URL استناد می‌کند که در searches نیست: {src['ref']}")
            elif src["kind"] == "attachment" and src["ref"] not in attachments:
                errors.append(f"claims.json: {c['id']} به پیوست ناموجود «{src['ref']}» استناد می‌کند")
            elif src["kind"] == "brand" and src["ref"] not in brand_proof:
                errors.append(f"claims.json: {c['id']} به شاهد برند ناموجود «{src['ref']}» استناد می‌کند")
        for s in c["used_in"]:
            if s not in sec_ids:
                errors.append(f"claims.json: {c['id']} در بخش ناموجود {s} استفاده شده")


def cost_benefit_errors(data: dict) -> list[str]:
    """فقط یکپارچگی ارجاع؛ کیفیت (منفعت بی‌پشتوانه، نبود سناریو) کار CHK-COST-BENEFIT و امتیاز است."""
    cb = data.get("cost_benefit")
    if not cb:
        return []
    prices = {i["id"]: i["amount"] for i in data["pricing"]["items"]}
    metrics = {m["id"] for m in data["metrics"]}
    errors = [f"شناسه‌ی تکراری {d} در cost_benefit"
              for d in _dupes([c["id"] for c in cb["costs"]] + [b["id"] for b in cb["benefits"]])]
    for c in cb["costs"]:
        ref = c.get("price_ref")
        if ref and ref not in prices:
            errors.append(f"{c['id']} به قلم قیمت ناموجود {ref} ارجاع می‌دهد")
        elif ref and prices[ref] != c["amount"]:
            errors.append(f"مبلغ {c['id']} با قلم قیمت {ref} یکی نیست")
    for b in cb["benefits"]:
        if b.get("metric") and b["metric"] not in metrics:
            errors.append(f"{b['id']} به شاخص ناموجود {b['metric']} ارجاع می‌دهد")
    if len({x["name"] for x in cb["scenarios"]}) != len(cb["scenarios"]):
        errors.append("سناریوهای cost_benefit باید low، base و high باشند، هرکدام یک بار")
    return errors


def check_write(run_dir, run, card, errors):
    n = run["round"]
    doc = _load(run_dir, f"document.v{n}.json", "document", errors)
    rev = _load(run_dir, f"revision.v{n}.json", "revision", errors)
    if doc is not None:
        if doc["doc_type"] != run["doc_type"]:
            errors.append(f"document.v{n}.json: doc_type با اجرا نمی‌خواند")
        if doc["meta"]["revision"] != run["revision"]:
            errors.append(f"document.v{n}.json: meta.revision باید {run['revision']} باشد")
        inp = common.load_json(run_dir / "input.json")
        if inp["sample"] and not doc["meta"]["sample"]:
            errors.append(f"document.v{n}.json: ورودی نمونه است، پس meta.sample باید true باشد")
        errors.extend(f"document.v{n}.json: بخش تکراری {d}" for d in _dupes(s["id"] for s in doc["sections"]))
        data = doc["data"]
        for key in ("deliverables", "acceptance", "timeline", "metrics", "risks", "unknowns"):
            errors.extend(f"document.v{n}.json: شناسه‌ی تکراری {d} در {key}" for d in _dupes(x["id"] for x in data[key]))
        errors.extend(f"document.v{n}.json: شناسه‌ی تکراری {d} در pricing"
                      for d in _dupes([x["id"] for x in data["pricing"]["items"]] + [p["id"] for p in data["pricing"]["payments"]]))
        errors.extend(f"document.v{n}.json: {e}" for e in cost_benefit_errors(data))
    if rev is not None:
        if rev["version"] != n:
            errors.append(f"revision.v{n}.json: version باید {n} باشد")
        issues_path = run_dir / f"issues.v{n - 1}.json"
        if issues_path.exists():
            issues = common.load_json(issues_path)
            if rev["base_version"] != issues["base_version"]:
                errors.append(f"revision.v{n}.json: base_version باید {issues['base_version']} باشد (نسخه‌ی پایه‌ی تعیین‌شده در Loop)")
            answered = {a["issue"] for a in rev["addressed"]} | {a["issue"] for a in rev["not_addressed"]}
            for issue in issues["issues"]:
                if issue["id"] not in answered:
                    errors.append(f"revision.v{n}.json: ایراد {issue['id']} نه در addressed آمده نه در not_addressed")


def check_judge_rubric(run_dir, run, card, errors):
    n = run["round"]
    rep = _load(run_dir, f"judges/v{n}/rubric.json", "judge-rubric", errors)
    if rep is None:
        return
    if rep["version"] != n:
        errors.append(f"judges/v{n}/rubric.json: version باید {n} باشد")
    ids = [c["id"] for c in rep["criteria"]]
    expected = [c["id"] for c in card["criteria"]]
    errors.extend(f"rubric: ردیف تکراری {d}" for d in _dupes(ids))
    for missing in sorted(set(expected) - set(ids)):
        errors.append(f"rubric: ردیف {missing} نمره نگرفته")
    for extra in sorted(set(ids) - set(expected)):
        errors.append(f"rubric: ردیف ناشناخته {extra}")
    text = _doc_text(run_dir, n, errors)
    if text is not None:
        for c in rep["criteria"]:
            _check_quotes(c["evidence"], text, f"rubric {c['id']} evidence", errors)
    # حالت truth: مهم‌ترین ضعف باید یک ردیف واقعاً ناقص باشد؛ «بدون ضعف» فقط وقتی همه ۴ گرفته‌اند
    scores = {c["id"]: c["score"] for c in rep["criteria"]}
    bw = rep["biggest_weakness"]
    if bw is None and any(v < 4 for v in scores.values()):
        errors.append("rubric: biggest_weakness خالی است اما ردیفی زیر ۴ وجود دارد")
    if bw is not None:
        if bw["criterion"] not in scores:
            errors.append(f"rubric: biggest_weakness به ردیف ناموجود {bw['criterion']} اشاره می‌کند")
        elif scores[bw["criterion"]] == 4:
            errors.append(f"rubric: biggest_weakness ردیف {bw['criterion']} است که نمره‌ی کامل ۴ گرفته")
    gaps_path = run_dir / "gaps.json"
    gap_ids = {g["id"] for g in common.load_json(gaps_path)["gaps"]} if gaps_path.exists() else set()
    for c in rep["criteria"]:
        for g in c["gap_refs"]:
            if g not in gap_ids:
                errors.append(f"rubric {c['id']}: gap ناموجود {g}")
        if c["limited_by_input"] and not c["gap_refs"]:
            errors.append(f"rubric {c['id']}: «محدود به ورودی» بدون ارجاع به gap")


def check_judge_claims(run_dir, run, card, errors):
    n = run["round"]
    rep = _load(run_dir, f"judges/v{n}/claims.json", "judge-claims", errors)
    if rep is None:
        return
    if rep["version"] != n:
        errors.append(f"judges/v{n}/claims.json: version باید {n} باشد")
    ledger = {c["id"] for c in common.load_json(run_dir / "claims.json")["claims"]}
    for i, c in enumerate(rep["claims"]):
        if c["ledger_ref"] and c["ledger_ref"] not in ledger:
            errors.append(f"claims[{i}]: ارجاع به ادعای ناموجود {c['ledger_ref']}")
    counts = {k: 0 for k in rep["summary"]}
    for c in rep["claims"]:
        counts[c["status"]] += 1
    if counts != rep["summary"]:
        errors.append(f"claims: summary {rep['summary']} با شمارش فهرست {counts} نمی‌خواند")
    text = _doc_text(run_dir, n, errors)
    if text is not None:
        _check_quotes(rep["claims"], text, "claims", errors)


def check_judge_veto(run_dir, run, card, errors):
    n = run["round"]
    rep = _load(run_dir, f"judges/v{n}/veto.json", "judge-veto", errors)
    if rep is None:
        return
    if rep["version"] != n:
        errors.append(f"judges/v{n}/veto.json: version باید {n} باشد")
    card_ids = {v["id"]: v for v in card["veto"]}
    responsible = {v["id"] for v in card["veto"] if v["detector"] in ("judge", "both")}
    na = {x["veto_id"] for x in rep.get("not_applicable", [])}
    for missing in sorted(responsible - set(rep["checked"]) - na):
        errors.append(f"veto: {missing} بررسی نشده (در checked نیست)")
    for vid in set(rep["checked"]) | na | {h["veto_id"] for h in rep["hits"]}:
        if vid not in card_ids:
            errors.append(f"veto: شناسه‌ی ناشناخته {vid}")
    for vid in na:
        if vid in card_ids and not card_ids[vid].get("applies_if"):
            errors.append(f"veto: {vid} شرط ندارد و نمی‌تواند «نامربوط» اعلام شود")
    text = _doc_text(run_dir, n, errors)
    if text is not None:
        _check_quotes(rep["hits"], text, "veto hits", errors)


def check_critic(run_dir, run, card, errors):
    data = _load(run_dir, "lessons.proposed.json", "lessons-proposed", errors)
    if data:
        import lessons
        for item in data["lessons"]:   # همان فیلتر تزریق lessons.py؛ خطا به خود critic برمی‌گردد و یک بار اصلاح می‌کند
            for why in lessons.problems(item["text"]):
                errors.append(f"lessons.proposed.json: درس «{item['text']}»: {why}")


CHECKERS = {"intake": check_intake, "brief": check_brief, "claims": check_claims, "write": check_write,
            "judge-rubric": check_judge_rubric, "judge-claims": check_judge_claims,
            "judge-veto": check_judge_veto, "critic": check_critic}


def validate_stage(run_dir: pathlib.Path, stage: str) -> list[str]:
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    run = common.load_json(run_dir / "run.json")
    card = common.load_card(run["doc_type"])
    errors: list[str] = []
    CHECKERS[stage](run_dir, run, card, errors)
    return errors


def hook(stage: str) -> int:
    """حالت hook توقف ایجنت. خروجی JSON روی stdout؛ خروج ۰ همیشه (تصمیم در JSON است)."""
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass  # ورودی hook لازم نیست؛ اجرای جاری از runs/.current خوانده می‌شود
    run_dir = common.current_run()
    if run_dir is None:
        return 0
    errors = validate_stage(run_dir, stage)
    if not errors:
        return 0
    run = common.load_json(run_dir / "run.json")
    counter = run_dir / ".retries" / f"{stage}.v{run['round']}"
    counter.parent.mkdir(exist_ok=True)
    used = int(counter.read_text()) if counter.exists() else 0
    if used >= MAX_HOOK_RETRIES:
        # بار دوم دیگر برنمی‌گردانیم؛ ارکستریتور با validate صریح خطا را می‌بیند و اجرا failed می‌شود
        (counter.parent / f"{stage}.v{run['round']}.errors.txt").write_text("\n".join(errors), encoding="utf-8")
        return 0
    counter.write_text(str(used + 1))
    reason = ("خروجی تو قرارداد را نقض می‌کند. همین فایل(ها) را اصلاح کن و دوباره بنویس؛ فقط یک فرصت داری:\n"
              + "\n".join(f"{i}. {e}" for i, e in enumerate(errors[:25], 1)))
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--run")
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--hook", action="store_true")
    ap.add_argument("--schema", help="نام schema برای حالت فایل، وقتی از نام فایل معلوم نیست")
    args = ap.parse_args(argv)
    if args.hook:
        if not args.stage:
            common.fail("--hook به --stage نیاز دارد")
        return hook(args.stage)
    if args.stage:
        run_dir = common.resolve_run(args.run)
        errors = validate_stage(run_dir, args.stage)
        if errors:
            print(f"✗ {args.stage}: {len(errors)} خطا", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print(f"✓ {args.stage}: معتبر")
        return 0
    if not args.files:
        ap.print_help()
        return 2
    bad = 0
    for f in args.files:
        path = pathlib.Path(f)
        schema = args.schema or common.schema_for_path(path)
        if schema is None:
            print(f"? {f}: schema از روی نام فایل معلوم نیست", file=sys.stderr)
            bad += 1
            continue
        errors = common.schema_errors(common.load_json(path), schema)
        if errors:
            bad += 1
            print(f"✗ {f} ({schema}):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
        else:
            print(f"✓ {f} ({schema})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
