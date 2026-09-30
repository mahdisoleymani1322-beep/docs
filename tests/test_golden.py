"""آزمون D2: گلدن‌ست `evals/golden/` فقط با کد (بدون مدل).

چرا: هر سند خراب باید **تک‌علتی** باشد؛ اگر یک جهش دو چک را بشکند، نمی‌دانیم داور را با کدام علت سنجیده‌ایم.
و `human` باید null بماند: برچسب انسان را فقط انسان می‌دهد و کد نباید چیزی جایش بسازد.
"""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import checks  # noqa: E402
import common  # noqa: E402
import make_golden  # noqa: E402

GOLD = ROOT / "evals" / "golden"
LABELS = common.load_json(GOLD / "labels.json")["docs"]


def run(name):
    data, _ = checks.build(GOLD / f"{name}.json", str(GOLD / "claims.json"), "mahdiyar", 1, None, None)
    return data["results"]


class GoldenTest(unittest.TestCase):
    def test_set_has_two_good_and_four_bad(self):
        self.assertEqual(set(LABELS), set(make_golden.DOCS))
        self.assertEqual(sorted(k for k in LABELS if k.startswith("good")), ["good-1", "good-2"])
        self.assertEqual(len([k for k in LABELS if k.startswith("bad")]), 4)

    def test_every_doc_is_schema_valid(self):
        for name in LABELS:
            self.assertEqual(common.schema_errors(common.load_json(GOLD / f"{name}.json"), "document"), [], name)

    def test_each_doc_breaks_exactly_the_expected_critical_checks(self):
        for name, lab in LABELS.items():
            failed = sorted(r["id"] for r in run(name) if r["status"] == "fail")
            self.assertEqual(failed, sorted(lab["expect_failed_checks"]), name)

    def test_code_vetoes_match_the_label(self):
        for name, lab in LABELS.items():
            got = sorted({v for r in run(name) if r["status"] == "fail" for v in r.get("veto", [])})
            self.assertEqual(got, sorted(lab["expect_veto_code"]), name)

    def test_good_docs_have_no_veto_and_no_failed_check(self):
        for name in ("good-1", "good-2"):
            self.assertFalse([r["id"] for r in run(name) if r["status"] == "fail"], name)

    def test_good_2_really_differs_from_good_1(self):
        a, b = (common.load_json(GOLD / f"{n}.json") for n in ("good-1", "good-2"))
        self.assertNotEqual(a["data"]["pricing"]["payments"], b["data"]["pricing"]["payments"])
        self.assertEqual(sum(p["percent"] for p in b["data"]["pricing"]["payments"]), 100)

    def test_labels_are_designed_and_human_is_never_invented(self):
        for name, lab in LABELS.items():
            self.assertEqual(lab["kind"], "designed", name)
            self.assertIsNone(lab["human"], f"{name}: برچسب انسان را فقط انسان می‌دهد")
            self.assertTrue(lab["mutation"], name)

    def test_files_are_reproducible_from_the_generator(self):
        with tempfile.TemporaryDirectory() as t:
            make_golden.build(pathlib.Path(t))
            for f in sorted(pathlib.Path(t).glob("*.json")):
                self.assertEqual(f.read_text(encoding="utf-8"), (GOLD / f.name).read_text(encoding="utf-8"), f.name)


if __name__ == "__main__":
    unittest.main()
