"""آزمون C1: چک‌های قطعی.

چرا: هر چک باید هم سند سالم را رد نکند و هم سند عمداً خراب را با دلیل، رد فوری و سقفِ دقیقِ مشخصات بگیرد.
سقف‌ها را از کارت می‌خوانیم، ولی ردیف مورد انتظار (R06 برای قیمت و …) عمداً ثابت نوشته شده تا تغییر کارت دیده شود.
"""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import checks  # noqa: E402
import common  # noqa: E402
import render  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
DOC = common.load_json(FIX / "document.good.json")
CLAIMS = common.load_json(FIX / "claims.good.json")
BRAND = common.load_brand("mahdiyar")


def run(mutate=None, claims=CLAIMS):
    doc = copy.deepcopy(DOC)
    if mutate:
        mutate(doc)
    return {r["id"]: r for r in checks.run_structured(doc, claims, BRAND)}


def para(doc, extra, section=0):
    doc["sections"][section]["blocks"][0]["text"] += " " + extra


def caps(r):
    return {(c["criterion"], c["max"]) for c in r["caps"]}


class GoodDocTest(unittest.TestCase):
    def test_good_document_passes_everything(self):
        for cid, r in run().items():
            self.assertEqual(r["status"], "pass", f"{cid}: {r['detail']}")

    def test_output_matches_schema_and_covers_the_catalog(self):
        data = {"version": 1, "doc_type": "proposal", "mode": "structured",
                "results": checks.run_structured(DOC, CLAIMS, BRAND)}
        self.assertEqual(common.schema_errors(data, "checks"), [])
        catalog = (ROOT / "docs" / "۰۳-سیستم-ارزیابی.md").read_text(encoding="utf-8")
        for r in data["results"]:
            self.assertIn(f"`{r['id']}`", catalog, f"{r['id']} در داک ۰۳ نیست")
        documented = {l.split("`")[1] for l in catalog.splitlines() if l.startswith("| `CHK-")}
        self.assertEqual(documented, {r["id"] for r in data["results"]}, "چک بی‌پیاده‌سازی یا پیاده‌سازی بی‌مستند")

    def test_severity_is_required(self):
        data = {"version": 1, "doc_type": "proposal", "mode": "structured", "results": [checks.result("CHK-IDS", "pass", "critical")]}
        del data["results"][0]["severity"]
        self.assertNotEqual(common.schema_errors(data, "checks"), [])


class StructureTest(unittest.TestCase):
    def test_price_sum_wrong_is_veto_v03_and_cap_on_price_row(self):
        r = run(lambda d: d["data"]["pricing"]["totals"].update(one_time=999))["CHK-PRICE-SUM"]
        self.assertEqual((r["status"], r["veto"], caps(r)), ("fail", ["V03"], {("R06", 1)}))
        self.assertIn("150000000", r["detail"])

    def test_unknown_item_forces_unknown_total(self):
        r = run(lambda d: d["data"]["pricing"]["items"][0].update(amount=None))["CHK-PRICE-SUM"]
        self.assertEqual(r["status"], "fail")
        def ok(d):
            d["data"]["pricing"]["items"][0].update(amount=None)
            d["data"]["pricing"]["totals"]["one_time"] = None
        self.assertEqual(run(ok)["CHK-PRICE-SUM"]["status"], "pass")

    def test_known_items_with_unknown_total_fails(self):
        r = run(lambda d: d["data"]["pricing"]["totals"].update(one_time=None))["CHK-PRICE-SUM"]
        self.assertEqual(r["status"], "fail")

    def test_deliverable_without_acceptance_is_veto_v05(self):
        r = run(lambda d: d["data"]["deliverables"][0].update(acceptance=None))["CHK-D-A"]
        self.assertEqual((r["status"], r["veto"], caps(r)), ("fail", ["V05"], {("R04", 1)}))

    def test_acceptance_pointing_at_wrong_deliverable(self):
        r = run(lambda d: d["data"]["acceptance"][0].update(deliverable="D-03"))["CHK-D-A"]
        self.assertEqual(r["status"], "fail")
        r = run(lambda d: d["data"]["acceptance"].append(dict(d["data"]["acceptance"][0], id="A-09")))["CHK-D-A"]
        self.assertIn("A-09", r["detail"])

    def test_payment_percent(self):
        r = run(lambda d: d["data"]["pricing"]["payments"][0].update(percent=30))["CHK-PAY-PERCENT"]
        self.assertEqual((r["status"], r["veto"], caps(r)), ("fail", [], {("R06", 1)}))

    def test_vague_payment_event(self):
        def vague(d):
            p = d["data"]["pricing"]["payments"][0]
            p.update(event="میانه‌ی پروژه", deliverable=None)
        r = run(vague)["CHK-PAY-EVENT"]
        self.assertEqual((r["status"], caps(r)), ("fail", {("R06", 2)}))
        r = run(lambda d: d["data"]["pricing"]["payments"][0].update(deliverable="D-09"))["CHK-PAY-EVENT"]
        self.assertEqual(r["status"], "fail")

    def test_duplicate_ids_are_critical_no_cap(self):
        r = run(lambda d: d["data"]["risks"][1].update(id="K-01"))["CHK-IDS"]
        self.assertEqual((r["status"], r["severity"], r["caps"], r["veto"]), ("fail", "critical", [], []))
        self.assertIn("K:K-01", r["detail"])

    def test_missing_section_caps_every_related_row_at_zero(self):
        r = run(lambda d: d.update(sections=[s for s in d["sections"] if s["id"] != "S09"]))["CHK-SECTIONS"]
        self.assertEqual((r["status"], caps(r)), ("fail", {("R06", 0)}))
        r = run(lambda d: d.update(sections=[s for s in d["sections"] if s["id"] != "S10"]))["CHK-SECTIONS"]
        self.assertEqual(caps(r), {("R04", 0), ("R07", 0)})  # S10 در دو ردیف است

    def test_blank_section_counts_as_missing(self):
        def blank(d):
            for s in d["sections"]:
                if s["id"] == "S11":
                    s["blocks"] = [{"kind": "para", "text": "   "}]
        self.assertEqual(run(blank)["CHK-SECTIONS"]["status"], "fail")


class TextRulesTest(unittest.TestCase):
    def test_guarantee_is_veto_v02_but_negation_is_fine(self):
        r = run(lambda d: para(d, "این پایلوت تضمین درآمد برای تیم فروش شماست."))["CHK-BANNED"]
        self.assertEqual((r["status"], r["veto"]), ("fail", ["V02"]))
        self.assertEqual(run(lambda d: para(d, "سناریوی مالی، تضمین درآمد نیست."))["CHK-BANNED"]["status"], "pass")

    def test_absolute_security_caps_risk_row(self):
        r = run(lambda d: para(d, "این راه‌حل امنیت کامل دارد."))["CHK-BANNED"]
        self.assertEqual((r["status"], r["veto"], caps(r)), ("fail", [], {("R07", 1)}))

    def test_hype_is_only_a_warning(self):
        banned = common.load_banned()
        hype = next(p for p in banned["phrases"] if p["category"] == "hype")
        word = hype["pattern"].split("|")[0].replace("\\", "")
        r = run(lambda d: para(d, f"{word} است."))["CHK-BANNED"]
        if r["status"] != "pass":
            self.assertEqual((r["status"], r["veto"], r["caps"]), ("warn", [], []))

    def test_brand_forbidden_word_caps_writing_row_at_three(self):
        r = run(lambda d: para(d, "راه‌حلی انقلابی برای شماست."))["CHK-BRAND-WORDS"]
        self.assertEqual((r["status"], r["veto"], caps(r)), ("fail", [], {("R09", 3)}))
        self.assertEqual(run(lambda d: para(d, "این راه‌حل انقلابی نیست."))["CHK-BRAND-WORDS"]["status"], "pass")

    def test_every_brand_word_is_detected(self):
        for w in BRAND["forbidden_words"]:
            with self.subTest(w=w["text"]):
                r = run(lambda d: para(d, f"ما {w['text']} هستیم."))["CHK-BRAND-WORDS"]
                self.assertEqual(r["status"], "fail")

    def test_claim_ref_missing_from_ledger(self):
        r = run(lambda d: para(d, "[C-09]"))["CHK-CLAIM-REFS"]
        self.assertEqual((r["status"], caps(r)), ("fail", {("R08", 1)}))
        self.assertEqual(run(claims=None)["CHK-CLAIM-REFS"]["status"], "fail")

    def test_final_label_on_incomplete_text(self):
        def final(d):
            d["meta"]["status_note"] = "نسخه نهایی و آماده امضا"
            d["data"]["pricing"]["items"][0].update(amount=None)
            d["data"]["pricing"]["totals"]["one_time"] = None
        r = run(final)["CHK-UNKNOWN-FINAL"]
        self.assertEqual((r["status"], r["severity"], r["caps"]), ("fail", "warn", []))
        def complete(d):
            d["meta"]["status_note"] = "نسخه نهایی"
        self.assertEqual(run(complete)["CHK-UNKNOWN-FINAL"]["status"], "pass")  # مجهول ندارد
        def negated(d):
            final(d)
            d["meta"]["status_note"] = "این نسخه نهایی نیست"
        self.assertEqual(run(negated)["CHK-UNKNOWN-FINAL"]["status"], "pass")

    def test_digits_warn_but_codes_do_not(self):
        r = run(lambda d: para(d, "حدود 12 کاربر"))["CHK-DIGITS"]
        self.assertEqual((r["status"], r["caps"], r["veto"]), ("warn", [], []))
        self.assertEqual(run(lambda d: para(d, "با API v2 و نشانی https://x.ir/a1 و D-01"))["CHK-DIGITS"]["status"], "pass")

    def test_length_budget_from_card_and_from_brief(self):
        card = common.load_card("proposal")
        words = int(run()["CHK-LENGTH"]["detail"].split()[0])
        self.assertTrue(card["length_words"]["min"] <= words <= card["length_words"]["max"])
        for lo, hi, status in ((words, words, "pass"), (words + 1, words + 9, "warn"), (1, words - 1, "warn")):
            brief = {"length_budget": {"min_words": lo, "max_words": hi}}
            r = checks.chk_length(DOC, card, brief)
            self.assertEqual((r["status"], r["caps"], r["veto"]), (status, [], []), (lo, hi))

    def test_appendix_words_do_not_count(self):
        card = common.load_card("proposal")
        base = int(checks.chk_length(DOC, card, None)["detail"].split()[0])
        big = copy.deepcopy(DOC)
        big["data"]["unknowns"] += [dict(big["data"]["unknowns"][0], id=f"U-{i:02d}", item="مورد بلند " * 200) for i in range(2, 6)]
        self.assertEqual(int(checks.chk_length(big, card, None)["detail"].split()[0]), base)


class CostBenefitTest(unittest.TestCase):
    def test_missing_cost_benefit_caps_commercial_row_at_two(self):
        def gone(d):
            d["data"].pop("cost_benefit")
            for s in d["sections"]:
                s["blocks"] = [b for b in s["blocks"] if b.get("data") != "cost_benefit"]
        rs = run(gone)
        r = rs["CHK-COST-BENEFIT"]
        self.assertEqual((r["status"], r["severity"], caps(r), r["veto"]), ("fail", "critical", {("R06", 2)}, []))
        self.assertIn("خلاصه", r["detail"] + "S02")
        for cid in ("CHK-CB-SUPPORT", "CHK-CB-TYPE", "CHK-CB-CAVEAT"):
            self.assertEqual(rs[cid]["status"], "skip", cid)

    def test_data_present_but_not_shown_is_still_missing(self):
        def hidden(d):
            for s in d["sections"]:
                s["blocks"] = [b for b in s["blocks"] if b.get("data") != "cost_benefit"]
        r = run(hidden)["CHK-COST-BENEFIT"]
        self.assertEqual((r["status"], caps(r)), ("fail", {("R06", 2)}))

    def test_missing_headline_is_only_a_warning(self):
        def nohead(d):
            for s in d["sections"]:
                s["blocks"] = [b for b in s["blocks"] if b.get("variant") != "headline"]
        r = run(nohead)["CHK-COST-BENEFIT"]
        self.assertEqual((r["status"], r["caps"]), ("warn", []))

    def test_numeric_benefit_needs_claim_or_assumption(self):
        def numeric(d):
            b = d["data"]["cost_benefit"]["benefits"][0]
            b.update(value=40, assumption=None, claim=None)
        r = run(numeric)["CHK-CB-SUPPORT"]
        self.assertEqual((r["status"], caps(r)), ("fail", {("R08", 1)}))
        def with_claim(d):
            d["data"]["cost_benefit"]["benefits"][0].update(value=40, assumption=None, claim="C-02")
        self.assertEqual(run(with_claim)["CHK-CB-SUPPORT"]["status"], "pass")
        def ghost(d):
            d["data"]["cost_benefit"]["benefits"][0].update(value=40, assumption=None, claim="C-77")
        self.assertEqual(run(ghost)["CHK-CB-SUPPORT"]["status"], "fail")

    def test_time_saving_is_not_cash(self):
        def cash(d):
            d["data"]["cost_benefit"]["benefits"][0].update(type="cash_saving", unit="ساعت در ماه")
        r = run(cash)["CHK-CB-TYPE"]
        self.assertEqual((r["status"], caps(r)), ("fail", {("R06", 2)}))
        self.assertIn("ظرفیت آزادشده", r["detail"])

    def test_revenue_needs_assumption(self):
        def rev(d):
            d["data"]["cost_benefit"]["benefits"][1].update(type="revenue_potential", assumption=None)
        self.assertEqual(run(rev)["CHK-CB-TYPE"]["status"], "fail")

    def test_scenarios_need_a_no_guarantee_caveat(self):
        def scen(caveat):
            def f(d):
                cb = d["data"]["cost_benefit"]
                cb["scenarios"] = [{"name": n, "assumptions": "فرض نمونه", "net_value": None} for n in ("low", "base", "high")]
                cb["caveat"] = caveat
            return f
        self.assertEqual(run(scen("درآمد قطعی است"))["CHK-CB-CAVEAT"]["status"], "fail")
        self.assertEqual(run(scen("سناریوی مالی، تضمین درآمد نیست."))["CHK-CB-CAVEAT"]["status"], "pass")


class ModesTest(unittest.TestCase):
    def test_text_mode_skips_structure_and_says_why(self):
        md = render.render(DOC, CLAIMS)
        rs = {r["id"]: r for r in checks.run_text(md, "proposal", CLAIMS, BRAND)}
        self.assertEqual(rs["CHK-PRICE-SUM"]["status"], "skip")
        self.assertIn("ساخت‌یافته نیست", rs["CHK-PRICE-SUM"]["detail"])
        self.assertEqual(rs["CHK-BANNED"]["status"], "pass")
        bad = {r["id"]: r for r in checks.run_text(md + "\nتضمین درآمد و راه‌حلی انقلابی [C-50]", "proposal", CLAIMS, BRAND)}
        self.assertEqual(bad["CHK-BANNED"]["veto"], ["V02"])
        self.assertEqual(bad["CHK-BRAND-WORDS"]["status"], "fail")
        self.assertEqual(bad["CHK-CLAIM-REFS"]["status"], "fail")
        data = {"version": 1, "doc_type": "proposal", "mode": "text", "results": list(rs.values())}
        self.assertEqual(common.schema_errors(data, "checks"), [])

    def test_cli_schema_invalid_doc_stops_with_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            doc = copy.deepcopy(DOC)
            del doc["meta"]["title"]
            (pathlib.Path(d) / "x.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "checks.py"), "--doc", f"{d}/x.json", "-o", f"{d}/o.json"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            out = json.loads((pathlib.Path(d) / "o.json").read_text(encoding="utf-8"))
            self.assertEqual([x["id"] for x in out["results"]], ["CHK-SCHEMA"])
            self.assertEqual(out["results"][0]["status"], "fail")

    def test_cli_run_mode_reads_brief_budget_and_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = pathlib.Path(d)
            (run_dir / "document.v1.json").write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
            (run_dir / "claims.json").write_text(json.dumps(CLAIMS, ensure_ascii=False), encoding="utf-8")
            (run_dir / "run.json").write_text(json.dumps({"brand": "mahdiyar"}), encoding="utf-8")
            (run_dir / "brief.json").write_text(json.dumps({"length_budget": {"min_words": 10, "max_words": 20}}), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "checks.py"), str(run_dir), "--version", "1"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads((run_dir / "checks.v1.json").read_text(encoding="utf-8"))
            length = next(x for x in out["results"] if x["id"] == "CHK-LENGTH")
            self.assertEqual(length["status"], "warn")
            self.assertIn("10 تا 20", length["detail"])


if __name__ == "__main__":
    unittest.main()
