"""آزمون D1: ورودی‌های نمونه‌ی `examples/inputs/` معتبرند، «نمونه» برچسب دارند و هرکدام کارِ خودش را می‌کنند.

چرا: نمونه‌ای که برچسب «نمونه» نداشته باشد ممکن است با مشتری واقعی اشتباه شود، و نمونه‌ی «کامل» باید واقعاً همه‌ی فیلدها را پر کند
وگرنه راهی برای دیدن سقف بالای نمره نداریم.
"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = ROOT / "examples" / "inputs"


def load(name):
    return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))


class SampleInputsTest(unittest.TestCase):
    def test_all_validate_and_are_marked_sample(self):
        files = sorted(DIR.glob("*.json"))
        self.assertGreaterEqual(len(files), 3)
        for f in files:
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py"), "--schema", "input", str(f)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{f.name}: {r.stdout}{r.stderr}")
            d = json.loads(f.read_text(encoding="utf-8"))
            self.assertIs(d["sample"], True, f.name)
            self.assertIn("نمونه", d["fields"]["client_identity"], f.name)

    def test_complete_has_every_required_business_field_filled_and_no_injection(self):
        d = load("proposal-complete")["fields"]
        empty = [k for k, v in d.items() if not v and k != "rfp"]  # rfp فقط برای پیشنهادِ پاسخ به فراخوان است، نه «فروش»
        self.assertEqual(empty, [], "نمونه‌ی کامل نباید فیلد خالی داشته باشد")
        self.assertNotIn("نمره‌ی کامل", json.dumps(d, ensure_ascii=False))
        self.assertEqual(sum(int(x) for x in re.findall(r"(\d+)٪", d["payment_terms"])), 100)

    def test_conflict_really_conflicts(self):
        d = load("proposal-conflict")["fields"]
        self.assertIn("ارسال خودکار", d["scope"])
        self.assertIn("خارج از دامنه", d["scope"])
        self.assertIn("ارسال خودکار", d["deliverables"])      # دامنه و تحویل با هم نمی‌خوانند
        self.assertNotEqual(sum(int(x) for x in re.findall(r"(\d+)٪", d["payment_terms"])), 100)
        weeks = set(re.findall(r"(\d+) هفته", d["schedule"] + d["discovery_notes"]))
        self.assertGreater(len(weeks), 1)                    # ۶ هفته در برابر ۴ هفته

    def test_incomplete_sample_still_has_the_e7_gaps(self):
        d = load("proposal-sample")["fields"]
        for k in ("budget", "payment_terms", "security"):
            self.assertIsNone(d[k], k)


if __name__ == "__main__":
    unittest.main()
