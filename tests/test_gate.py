"""آزمون C2: دروازه.

چرا: تصمیم قبول و رد فقط از این کد می‌آید. مرزها (۸۵٫۰۰، ۹۰٫۰) و سقف‌ها باید دقیق باشند و هر شکست دلیل مشخص بدهد.
"""
import copy
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import checks as checks_mod  # noqa: E402
import common  # noqa: E402
import gate  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
CARD = common.load_card("proposal")
DOC = common.load_json(FIX / "document.good.json")
LEDGER = common.load_json(FIX / "claims.good.json")
BRAND = common.load_brand("mahdiyar")
RUBRIC = common.load_json(FIX / "judges" / "rubric.good.json")
CLAIMS = common.load_json(FIX / "judges" / "claims.good.json")
VETO = common.load_json(FIX / "judges" / "veto.good.json")


def checks_ok(mutate=None):
    doc = copy.deepcopy(DOC)
    if mutate:
        mutate(doc)
    return {"version": 1, "doc_type": "proposal", "mode": "structured", "results": checks_mod.run_structured(doc, LEDGER, BRAND)}


def rubric(**scores):
    r = copy.deepcopy(RUBRIC)
    for c in r["criteria"]:
        if c["id"] in scores:
            c["score"] = scores[c["id"]]
    return r


def all_scores(n):
    return rubric(**{c["id"]: n for c in CARD["criteria"]})


def go(checks=None, rub=None, claims=CLAIMS, veto=VETO):
    return gate.compute(CARD, checks or checks_ok(), rub or RUBRIC, claims, veto)


def row(out, rid):
    return next(c for c in out["criteria"] if c["id"] == rid)


class ArithmeticTest(unittest.TestCase):
    def test_good_fixture_total_and_no_rounding(self):
        out = go()
        # همه ۴ به‌جز R05=۳: ۱۰۰ − ۱۰×۱÷۴ = ۹۷٫۵
        self.assertEqual(out["total"], 97.5)
        self.assertEqual((out["guide"]["pass"], out["target"]["met"], out["target"]["score10"]), (True, True, 9.75))
        self.assertEqual(out["guide"]["band"], "آماده ارسال")
        self.assertEqual(common.schema_errors(out, "gate"), [])

    def test_points_are_weight_times_score_over_four(self):
        out = go(rub=all_scores(3))
        self.assertEqual(row(out, "R01")["points"], 11.25)  # ۱۵×۳÷۴: بدون گرد کردن
        self.assertEqual(out["total"], 75.0)

    def test_boundaries_85_and_90(self):
        # R06=۳(۱۱٫۲۵) و R01=۳(۱۱٫۲۵) و R03=۳ و R04=۳ و R05=۳ → ۱۰۰−۳٫۷۵−۲٫۵−۳٫۷۵−۲٫۵−۲٫۵−۳٫۷۵ = ۸۱٫۲۵؛ مرز را با ترکیب می‌سازیم
        def with_total(target):
            # نمره‌ها را از ۴ کم می‌کنیم تا دقیقاً به target برسیم؛ کمینه‌ی ترکیب با وزن‌ها
            import itertools
            ids = [c["id"] for c in CARD["criteria"]]
            for combo in itertools.product((4, 3, 2), repeat=len(ids)):
                pts = sum(c["weight"] * s for c, s in zip(CARD["criteria"], combo)) / 4
                if pts == target and min(combo) >= 2:
                    return rubric(**dict(zip(ids, combo)))
            raise AssertionError(target)
        for total, passed, met in ((85.0, True, False), (90.0, True, False), (91.25, True, True), (87.5, True, False)):
            with self.subTest(total=total):
                out = go(rub=with_total(total))
                self.assertEqual((out["total"], out["guide"]["pass"], out["target"]["met"]), (total, passed, met))

    def test_below_85_needs_revision_band_and_reason(self):
        out = go(rub=all_scores(3))
        self.assertFalse(out["guide"]["pass"])
        self.assertEqual(out["guide"]["band"], "نیازمند اصلاح")
        self.assertTrue(any("کمتر از حداقل" in r for r in out["guide"]["fail_reasons"]))
        self.assertEqual(go(rub=all_scores(2))["guide"]["band"], "نیازمند بازتعریف پیشنهاد")

    def test_exact_arithmetic_beats_float_noise(self):
        c = copy.deepcopy(CARD)
        for x in c["criteria"]:
            x["weight"] = 0.1  # ۱۰ ردیف ۰٫۱ ← float خام ۰٫۹۹۹۹۹۹… می‌دهد
        out = gate.compute(c, checks_ok(), all_scores(4), CLAIMS, VETO)
        self.assertEqual(out["total"], 1.0)


class CapsTest(unittest.TestCase):
    def test_cap_is_minimum_of_all_caps(self):
        def two(d):
            d["data"]["pricing"]["totals"]["one_time"] = 1
            d["data"]["pricing"]["payments"][0]["percent"] = 10
        out = go(checks=checks_ok(two))
        r = row(out, "R06")
        self.assertEqual((r["judge_score"], r["final_score"]), (4, 1))
        self.assertEqual({c["source"] for c in r["caps"]}, {"CHK-PRICE-SUM", "CHK-PAY-PERCENT"})
        self.assertEqual(r["points"], 15 * 1 / 4)

    def test_cap_never_raises_a_low_judge_score(self):
        def cost_missing(d):
            d["data"].pop("cost_benefit")
        out = go(checks=checks_ok(cost_missing), rub=rubric(R06=1))
        self.assertEqual(row(out, "R06")["final_score"], 1)

    def test_missing_cost_benefit_caps_commercial_row_at_two(self):
        def gone(d):
            d["data"].pop("cost_benefit")
            for s in d["sections"]:
                s["blocks"] = [b for b in s["blocks"] if b.get("data") != "cost_benefit"]
        out = go(checks=checks_ok(gone))
        self.assertEqual(row(out, "R06")["final_score"], 2)
        self.assertIn("CHK-COST-BENEFIT", {c["source"] for c in row(out, "R06")["caps"]})
        self.assertFalse(out["guide"]["pass"], "ردیف حیاتی R06 با نمره‌ی ۲ زیر ۳ است")

    def test_brand_word_caps_writing_row_at_three(self):
        def word(d):
            d["sections"][0]["blocks"][0]["text"] += " راه‌حلی انقلابی."
        out = go(checks=checks_ok(word))
        self.assertEqual(row(out, "R09")["final_score"], 3)
        self.assertTrue(out["guide"]["pass"], "سقف ۳ روی ردیف نگارش قبولی را نمی‌شکند")

    def test_claims_judge_caps_honesty_row(self):
        def claims(status):
            c = copy.deepcopy(CLAIMS)
            c["claims"][0]["status"] = status
            return c
        self.assertEqual(row(go(claims=claims("unsupported")), "R08")["final_score"], 1)
        self.assertEqual(row(go(claims=claims("contradicts_ledger")), "R08")["final_score"], 0)
        self.assertEqual(row(go(claims=claims("labeled_assumption")), "R08")["final_score"], 4)
        out = go(claims=claims("contradicts_ledger"))
        self.assertEqual(row(out, "R08")["caps"][0]["source"], "judge-claims")
        self.assertFalse(out["guide"]["pass"], "R08=۰ زیر min_row است")


class PassRulesTest(unittest.TestCase):
    def reasons(self, out):
        return " | ".join(out["guide"]["fail_reasons"])

    def test_row_below_min_row(self):
        out = go(rub=rubric(R10=1))
        self.assertFalse(out["guide"]["pass"])
        self.assertIn("R10", self.reasons(out))
        self.assertGreaterEqual(out["total"], 85)

    def test_critical_row_below_three_even_with_high_total(self):
        out = go(rub=rubric(R03=2))
        self.assertGreaterEqual(out["total"], 85)
        self.assertFalse(out["guide"]["pass"])
        self.assertIn("ردیف حیاتی R03", self.reasons(out))

    def test_critical_row_at_exactly_three_passes(self):
        out = go(rub=rubric(R03=3, R04=3, R06=3))
        self.assertTrue(out["guide"]["pass"], out["guide"]["fail_reasons"])

    def test_generated_texts_use_persian_digits(self):
        out = go(rub=rubric(R03=2, R02=2))
        for r in out["guide"]["fail_reasons"] + [i["text"] for i in out["issues"]]:
            self.assertNotRegex(re.sub(r"\b[A-Za-z][A-Za-z0-9-]*\b", " ", r), "[0-9]", r)  # شناسه‌ها (R03، CHK-…) لاتین می‌مانند

    def test_non_critical_row_at_two_is_fine(self):
        out = go(rub=rubric(R08=2))
        self.assertTrue(out["guide"]["pass"])

    def test_check_veto_blocks_pass_and_carries_source(self):
        out = go(checks=checks_ok(lambda d: d["data"]["pricing"]["totals"].update(one_time=1)))
        self.assertEqual([(v["id"], v["source"]) for v in out["veto"]], [("V03", "CHK-PRICE-SUM")])
        self.assertFalse(out["guide"]["pass"])
        self.assertIn("رد فوری V03: جمع قیمت غلط", self.reasons(out))

    def test_judge_veto_blocks_pass(self):
        v = copy.deepcopy(VETO)
        v["hits"] = [{"veto_id": "V01", "quote": "مشتری قبلی ما بانک بزرگ", "section": "S14", "reason": "مشتری ساختگی"}]
        out = go(veto=v)
        self.assertEqual([(x["id"], x["source"]) for x in out["veto"]], [("V01", "judge-veto")])
        self.assertIn("«مشتری قبلی ما بانک بزرگ»", out["veto"][0]["detail"])
        self.assertFalse(out["guide"]["pass"])
        self.assertFalse(out["target"]["met"])

    def test_same_veto_from_two_sources_is_listed_twice_but_reasoned_once(self):
        v = copy.deepcopy(VETO)
        v["hits"] = [{"veto_id": "V03", "quote": "جمع یک‌باره ۱ تومان", "section": "S09", "reason": "جمع غلط"}]
        out = go(checks=checks_ok(lambda d: d["data"]["pricing"]["totals"].update(one_time=1)), veto=v)
        self.assertEqual(len(out["veto"]), 2)
        self.assertEqual(sum("V03" in r for r in out["guide"]["fail_reasons"]), 1)

    def test_target_needs_pass_even_if_total_is_high(self):
        out = go(rub=rubric(R03=2, R05=4))
        self.assertGreater(out["total"], 90)
        self.assertFalse(out["target"]["met"])


class MarkdownModeTest(unittest.TestCase):
    def test_text_mode_scores_but_never_passes(self):
        checks = {"version": 1, "doc_type": "proposal", "mode": "text",
                  "results": checks_mod.run_text("متن سند", "proposal", LEDGER, BRAND)}
        out = go(checks=checks, rub=all_scores(4))
        self.assertEqual(out["total"], 100.0)
        self.assertEqual(out["guide"]["band"], "آماده ارسال")
        self.assertEqual((out["guide"]["pass"], out["target"]["met"]), (False, False))
        self.assertIn("ساخت‌یافته نیست", " ".join(out["guide"]["fail_reasons"]))
        self.assertEqual([r["caps"] for r in out["criteria"]], [[]] * 10, "سقفی اضافه نمی‌شود")
        self.assertTrue(any(i["severity"] == "warn" and "ساخت‌یافته" in i["text"] for i in out["issues"]))


class JudgesValidTest(unittest.TestCase):
    def valid(self, content):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "cal.json"
            if content is not None:
                p.write_text(json.dumps(content), encoding="utf-8")
            with mock.patch.object(common, "CALIBRATION", p):
                return go()["judges_valid"]

    def test_calibration_states(self):
        self.assertFalse(self.valid(None), "بدون کالیبراسیون، نمره فرضیه است")
        self.assertTrue(self.valid({"kappa": {"proposal": 0.7}}))
        self.assertTrue(self.valid({"kappa": {"proposal": 0.6}}))
        self.assertFalse(self.valid({"kappa": {"proposal": 0.59}}))
        self.assertFalse(self.valid({"kappa": {"pitch": 0.9}}), "κ نوع دیگر معتبر نیست")

    def test_truth_fields_pass_through(self):
        out = go()
        self.assertEqual(out["bottom_line"], RUBRIC["bottom_line"])
        self.assertEqual(out["biggest_weakness"]["criterion"], "R05")


class IssuesTest(unittest.TestCase):
    def test_order_veto_critical_below_min_then_by_lost_points(self):
        def bad(d):
            d["data"]["pricing"]["totals"]["one_time"] = 1
        out = go(checks=checks_ok(bad), rub=rubric(R03=2, R10=1, R02=3, R09=2))
        sev = [i["severity"] for i in out["issues"]]
        self.assertEqual(sev, sorted(sev, key=["veto", "critical", "below_min", "below_target", "warn"].index))
        self.assertEqual(out["issues"][0]["severity"], "veto")
        self.assertEqual([i["id"] for i in out["issues"]], [f"I-{n:02d}" for n in range(1, len(out["issues"]) + 1)])
        below_target = [i for i in out["issues"] if i["severity"] == "below_target"]
        lost = [i["points_at_stake"] for i in below_target]
        self.assertEqual(lost, sorted(lost, reverse=True))
        self.assertEqual({i["source"] for i in out["issues"] if i["severity"] == "below_min"}, {"R10"})

    def test_within_a_group_the_biggest_loss_comes_first_not_card_order(self):
        # R02 (وزن ۱۰، نمره ۳ ← ۲٫۵ از دست رفته) در کارت پیش از R07 (وزن ۱۰، نمره ۲ ← ۵) است
        out = go(rub=rubric(R02=3, R07=2))
        order = [i["source"] for i in out["issues"] if i["severity"] == "below_target"]
        self.assertLess(order.index("R07"), order.index("R02"))
        self.assertEqual([i["points_at_stake"] for i in out["issues"] if i["source"] in ("R07", "R02")], [5.0, 2.5])

    def test_points_at_stake_and_sections(self):
        out = go(rub=rubric(R02=2))
        i = next(x for x in out["issues"] if x["source"] == "R02")
        self.assertEqual((i["points_at_stake"], i["section"]), (5.0, "S04"))  # ۱۰×(۴−۲)÷۴
        self.assertIn("نمره ۲ از ۴", i["text"])

    def test_limited_by_input_is_labeled(self):
        r = rubric(R02=2)
        next(c for c in r["criteria"] if c["id"] == "R02")["limited_by_input"] = True
        i = next(x for x in go(rub=r)["issues"] if x["source"] == "R02")
        self.assertIn("محدود به ورودی", i["text"])

    def test_perfect_document_has_no_row_issues(self):
        out = go(rub=all_scores(4))
        self.assertEqual([i for i in out["issues"] if i["severity"] != "warn"], [])

    def test_critical_check_failure_without_veto_is_an_issue(self):
        out = go(checks=checks_ok(lambda d: d["data"]["risks"][1].update(id="K-01")))
        i = next(x for x in out["issues"] if x["source"] == "CHK-IDS")
        self.assertEqual(i["severity"], "critical")
        self.assertIn("K-01", i["text"])

    def test_schema_valid_issue_shape(self):
        out = go(checks=checks_ok(lambda d: d["data"]["pricing"]["totals"].update(one_time=1)), rub=rubric(R03=2))
        self.assertEqual(common.schema_errors(out, "gate"), [])


class CliTest(unittest.TestCase):
    def files(self, d, version=1, mode_text=False):
        d = pathlib.Path(d)
        (d / "judges" / f"v{version}").mkdir(parents=True)
        checks = checks_ok()
        checks["version"] = version
        (d / f"checks.v{version}.json").write_text(json.dumps(checks, ensure_ascii=False), encoding="utf-8")
        for name, rep in (("rubric", RUBRIC), ("claims", CLAIMS), ("veto", VETO)):
            rep = dict(rep, version=version)
            (d / "judges" / f"v{version}" / f"{name}.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")

    def call(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "gate.py"), *args], capture_output=True, text=True)

    def test_run_mode_writes_gate_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.files(d)
            r = self.call(d, "--version", "1")
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads((pathlib.Path(d) / "gate.v1.json").read_text(encoding="utf-8"))
            self.assertEqual(out["total"], 97.5)
            self.assertIn("pass=True", r.stderr)

    def test_version_mismatch_between_reports_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.files(d)
            p = pathlib.Path(d) / "judges" / "v1" / "veto.json"
            p.write_text(json.dumps(dict(VETO, version=2), ensure_ascii=False), encoding="utf-8")
            r = self.call(d, "--version", "1")
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((pathlib.Path(d) / "gate.v1.json").exists())

    def test_schema_failed_document_stops_with_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.files(d)
            c = pathlib.Path(d) / "checks.v1.json"
            data = json.loads(c.read_text(encoding="utf-8"))
            data["results"] = [checks_mod.result("CHK-SCHEMA", "fail", "critical", "x")]
            c.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(self.call(d, "--version", "1").returncode, 2)

    def test_missing_criterion_in_judge_report_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.files(d)
            p = pathlib.Path(d) / "judges" / "v1" / "rubric.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            data["criteria"] = data["criteria"][:-1]
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            r = self.call(d, "--version", "1")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("R10", r.stderr)


if __name__ == "__main__":
    unittest.main()
