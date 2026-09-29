"""آزمون B1 و B2: هر schema یک نمونه‌ی معتبر را می‌پذیرد و نمونه‌ی نامعتبر را رد می‌کند.

چرا: schema قرارداد بین ایجنت‌ها و کد است؛ اگر نمونه‌ی خراب را بپذیرد، خطای ایجنت به مرحله‌ی بعد نشت می‌کند.
"""
import copy
import json
import pathlib
import sys
import unittest

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402

FIX = ROOT / "tests" / "fixtures"

VALID = {
    "input": {"doc_type": "proposal", "fields": {"client_identity": "شرکت نمونه", "budget": None},
              "attachments": [], "answers": [], "sample": True},
    "gaps": {"gaps": [{"id": "G-01", "field": "budget", "kind": "missing", "detail": "بودجه خالی است",
                       "impact": "price", "blocking": False}]},
    "questions": {"questions": [{"id": "Q-01", "gap": "G-01", "text": "بودجه‌ی مصوب چقدر است؟",
                                 "why": "قیمت بدون آن قطعی نمی‌شود", "blocking": False}]},
    "brief": {"doc_type": "proposal", "variant": "sales",
              "audience": {"decision_maker": "مدیر فروش", "readers": ["IT"]},
              "decision_sought": "تأیید دامنه‌ی پایلوت", "key_message": "اول بسنجیم، بعد توسعه دهیم",
              "sections": [{"id": "S01", "title": "مشخصات", "purpose": "هویت نسخه", "must_include": [],
                            "inputs": ["client_identity"], "gaps": []}],
              "length_budget": {"min_words": 1000, "max_words": 3200}, "out_of_scope": ["CRM"]},
    "claims": {"claims": [{"id": "C-01", "text": "بازبینی دستی است", "type": "fact",
                           "source": {"kind": "input", "ref": "discovery_notes", "date": None, "quote": None},
                           "used_in": ["S03"], "limits": "", "impact": "none"}], "searches": []},
    "revision": {"version": 2, "base_version": 1, "addressed": [{"issue": "I-01", "change": "جمع قیمت اصلاح شد"}],
                 "not_addressed": [], "summary": "دور دوم"},
    "checks": {"version": 1, "doc_type": "proposal", "mode": "structured",
               "results": [{"id": "CHK-PRICE-SUM", "status": "pass", "detail": "", "locations": [], "veto": [], "caps": []}]},
    "judge-rubric": {"judge": "rubric", "version": 1, "criteria": [
        {"id": "R01", "score": 3, "evidence": [{"section": "S03", "quote": "طبق صورت‌جلسه‌ی کشف نیاز"}],
         "reason": "مسئله با شاهد", "fix": "", "limited_by_input": False, "gap_refs": []}],
        "bottom_line": "تشخیص مستند است اما خط مبنا ندارد.",
        "biggest_weakness": {"criterion": "R01", "what": "خط مبنا نیست", "why": "هدف قابل سنجش نیست", "fix": "خط مبنا را در فاز کشف بسازید"},
        "would_change": "خط مبنای اندازه‌گیری‌شده"},
    "judge-claims": {"judge": "claims", "version": 1, "claims": [
        {"quote": "بازبینی دستی گلوگاه است", "section": "S02", "ledger_ref": "C-01", "status": "supported", "note": ""}],
        "summary": {"supported": 1, "labeled_assumption": 0, "unsupported": 0, "contradicts_ledger": 0},
        "bottom_line": "همه‌ی ادعاهای بررسی‌شده منبع دارند."},
    "judge-veto": {"judge": "veto", "version": 1, "checked": ["V01"], "not_applicable": [], "hits": [],
                   "bottom_line": "هیچ مورد رد فوری پیدا نشد."},
    "issues": {"for_round": 2, "base_version": 1, "issues": [
        {"id": "I-01", "source": "V03", "severity": "veto", "section": "S09", "text": "جمع قیمت را اصلاح کن"}],
        "regressions": []},
    "loop": {"run_id": "20260929-120000-proposal", "doc_type": "proposal",
             "contract": {"goal": "g", "criteria": "c", "acceptable_risks": [], "unacceptable_risks": [],
                          "authority_system": [], "authority_human": []},
             "config": {"max_rounds": 4, "total_gt": 90.0, "plateau_rounds": 2, "plateau_min_gain": 1.0},
             "rounds": [], "best_version": None, "state": "running", "stop_reason": None},
    "run": {"run_id": "20260929-120000-proposal", "mode": "studio", "doc_type": "proposal", "brand": "mahdiyar", "created": "t",
            "status": "running", "stage": "init", "round": 0, "intake_rounds": 0, "lifecycle": "draft",
            "revision": 1, "parent_run": None, "errors": [], "history": []},
    "feedback": {"ts": "t", "run_id": "r", "version": 1, "section": "S06", "vote": "down",
                 "note": "دامنه مبهم است", "action": None, "author": "بازبین"},
    "lessons": {"lessons": [{"id": "L-001", "agent": "writer", "text": "در مقدمه با مسئله‌ی ملموس شروع کن.",
                             "source_run": "r", "source_kind": "loop", "created": "t", "active": True}]},
    "lessons-proposed": {"lessons": [], "rationale": "اجرا بدون ایراد تکراری بود"},
    "labels": {"doc_type": "proposal", "items": [
        {"doc": "docs/good.json", "claims": "docs/good.claims.json",
         "expected": {"guide_pass": True, "veto": [], "checks_fail": []},
         "reason": "همه‌ی ردیف‌ها مستند", "labeled_by": "بازبین", "date": "2026-09-29"}]},
}

# هر جهش یک قاعده‌ی مشخص schema را می‌شکند
INVALID = {
    "input": lambda d: d.pop("sample"),
    "gaps": lambda d: d["gaps"][0].update(kind="guess"),
    "questions": lambda d: d.update(questions=[dict(d["questions"][0], id=f"Q-0{i}") for i in range(1, 7)]),
    "brief": lambda d: d["sections"][0].update(id="S1"),
    "claims": lambda d: d["claims"][0].update(source=None),  # fact بدون منبع
    "revision": lambda d: d["addressed"][0].update(issue="X-1"),
    "checks": lambda d: d["results"][0].update(status="ok"),
    "judge-rubric": lambda d: d["criteria"][0].update(evidence=[]),  # نمره ≥ ۱ بدون شاهد
    "judge-claims": lambda d: d["claims"][0].update(status="probably"),
    "judge-veto": lambda d: d.update(hits=[{"veto_id": "V01", "quote": "کوتاه", "section": "S01", "reason": "x"}]),
    "issues": lambda d: d["issues"][0].update(severity="minor"),
    "loop": lambda d: d.update(state="paused"),
    "run": lambda d: d.update(status="done"),  # status و lifecycle دو محور جدا هستند
    "feedback": lambda d: d.update(action="send"),  # هیچ کنش «ارسال» وجود ندارد
    "lessons": lambda d: d["lessons"][0].update(agent="ceo"),
    "lessons-proposed": lambda d: d.update(lessons=[{"agent": "writer", "text": "درس شماره‌ی " + str(i) + " برای آزمون",
                                                      "evidence": "دور ۲", "source_kind": "loop"} for i in range(4)]),
    "labels": lambda d: d["items"][0]["expected"].update(veto=["X1"]),
}


class SchemaTest(unittest.TestCase):
    def test_all_schemas_meta_valid(self):
        for p in sorted((ROOT / "schemas").glob("*.schema.json")):
            with self.subTest(schema=p.name):
                jsonschema.Draft202012Validator.check_schema(common.load_json(p))

    def test_every_schema_has_cases(self):
        names = {p.name[: -len(".schema.json")] for p in (ROOT / "schemas").glob("*.schema.json")}
        covered = set(VALID) | {"document", "gate", "rubric", "banned", "brand"}
        self.assertEqual(names - covered, set(), "schema بدون آزمون")

    def test_valid_and_invalid_samples(self):
        for name, sample in VALID.items():
            with self.subTest(schema=name, case="valid"):
                self.assertEqual(common.schema_errors(sample, name), [])
            with self.subTest(schema=name, case="invalid"):
                bad = copy.deepcopy(sample)
                INVALID[name](bad)
                self.assertNotEqual(common.schema_errors(bad, name), [], f"{name}: نمونه‌ی خراب پذیرفته شد")

    def test_document_good_fixture(self):
        doc = common.load_json(FIX / "document.good.json")
        self.assertEqual(common.schema_errors(doc, "document"), [])

    def test_document_invalid_mutations(self):
        base = common.load_json(FIX / "document.good.json")
        mutations = {
            "بدون برچسب نمونه": lambda d: d["meta"].pop("sample"),
            "شناسه‌ی تحویل بد": lambda d: d["data"]["deliverables"][0].update(id="D1"),
            "بلوک ناشناخته": lambda d: d["sections"][0]["blocks"].append({"kind": "image", "src": "x"}),
            "پاراگراف خالی": lambda d: d["sections"][0]["blocks"].append({"kind": "para", "text": ""}),
            "مبلغ منفی": lambda d: d["data"]["pricing"]["items"][0].update(amount=-1),
            "درصد صفر": lambda d: d["data"]["pricing"]["payments"][0].update(percent=0),
            "نوع سند پشتیبانی‌نشده": lambda d: d.update(doc_type="pitch"),
            "دو سناریو": lambda d: d["data"]["cost_benefit"]["scenarios"].extend(
                [{"name": "low", "assumptions": "x", "net_value": None}, {"name": "base", "assumptions": "x", "net_value": None}]),
            "منفعت بی‌نوع": lambda d: d["data"]["cost_benefit"]["benefits"][0].update(type="roi"),
            "بدون هشدار": lambda d: d["data"]["cost_benefit"].pop("caveat"),
            "بدون هزینه": lambda d: d["data"]["cost_benefit"].update(costs=[]),
        }
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                d = copy.deepcopy(base)
                mutate(d)
                self.assertNotEqual(common.schema_errors(d, "document"), [], label)

    def test_document_allows_missing_cost_benefit_for_checks(self):
        """نبود cost_benefit خطای schema نیست تا CHK-COST-BENEFIT آن را با سقف امتیاز ثبت کند."""
        d = common.load_json(FIX / "document.good.json")
        d["data"].pop("cost_benefit")
        self.assertEqual(common.schema_errors(d, "document"), [])

    def test_document_allows_null_acceptance_for_checks(self):
        """پذیرش null باید از schema عبور کند تا CHK-D-A آن را رد فوری V05 ثبت کند، نه خطای schema."""
        d = common.load_json(FIX / "document.good.json")
        d["data"]["deliverables"][0]["acceptance"] = None
        self.assertEqual(common.schema_errors(d, "document"), [])

    def test_gate_cross_file_ref(self):
        gate = {"version": 1, "doc_type": "proposal", "criteria": [], "total": 0, "veto": [],
                "guide": {"pass": False, "band": "x", "fail_reasons": []},
                "target": {"met": False, "threshold": 90.0, "score10": 0},
                "issues": [{"id": "I-01", "source": "R01", "severity": "wrong", "section": None, "text": "abc"}],
                "judges_valid": False}
        self.assertNotEqual(common.schema_errors(gate, "gate"), [], "ref به issues.schema حل نشد")
        gate["issues"][0]["severity"] = "below_target"
        self.assertEqual(common.schema_errors(gate, "gate"), [])


if __name__ == "__main__":
    unittest.main()
