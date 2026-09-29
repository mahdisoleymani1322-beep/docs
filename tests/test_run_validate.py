"""آزمون B4: slice_guide.py، run.py و validate.py.

چرا: این سه ابزار P0 پایه‌ی همه‌ی مراحل‌اند. اگر برش اشتباه باشد ایجنت دانش غلط می‌گیرد؛ اگر run.py
وضعیت را غلط منتقل کند Loop قابل‌اعتماد نیست؛ اگر validate.py نقل‌قول ساختگی را بپذیرد، نمره‌ی داور بی‌پشتوانه است.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
import slice_guide  # noqa: E402
import validate  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def sh(args, env, stdin=None, check=True):
    r = subprocess.run([sys.executable, *args], cwd=SCRIPTS, env=env, input=stdin,
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"{args} ← {r.returncode}\n{r.stderr}")
    return r


class SliceTest(unittest.TestCase):
    def test_rubric_slice_is_exact_table(self):
        card = common.load_card("proposal")
        text = slice_guide.slice_chapter("proposal", "rubric_text")
        rows = re.findall(r"^\| (.+?) \| [۰-۹]+ \|$", text, re.M)
        self.assertEqual(rows, [c["title"] for c in card["criteria"]])

    def test_slices_are_single_chapters(self):
        for t in common.DOC_TYPES:
            card = common.load_card(t)
            for name, heading in card["slices"].items():
                with self.subTest(t=t, slice=name):
                    text = slice_guide.slice_chapter(t, name)
                    self.assertTrue(text.startswith(heading + "\n"))
                    self.assertEqual(len(re.findall(r"(?m)^## ", text)), 1, "برش نباید فصل بعدی را بیاورد")
                    self.assertNotIn("\r", text)

    def test_context_is_smaller_than_guide(self):
        """سیاست کانتکست: ورودی راهنمایی نویسنده کمتر از نصف کل راهنما است."""
        guide = len((ROOT / "guides" / "پرپوزال.md").read_text(encoding="utf-8"))
        writer = sum(len(slice_guide.slice_chapter("proposal", s)) for s in ("architecture", "operations", "writing_rules"))
        self.assertLess(writer, guide / 2)


class RunCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        form = json.loads(sh(["run.py", "template", "proposal"], self.env).stdout)
        form["fields"]["client_identity"] = "شرکت نمونه‌ی آلفا"
        form["fields"]["proposal_kind"] = "فروش"
        form["sample"] = True
        self.form = self.tmp / "input.json"
        self.form.write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_template_matches_card(self):
        for t in common.DOC_TYPES:
            form = json.loads(sh(["run.py", "template", t], self.env).stdout)
            self.assertEqual(common.schema_errors(form, "input"), [])
            self.assertEqual(list(form["fields"]), [f["key"] for f in common.load_card(t)["intake_fields"]])

    def test_new_run_layout_lock_and_finish(self):
        run_dir = pathlib.Path(sh(["run.py", "new", "proposal", str(self.form)], self.env).stdout.strip())
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(common.schema_errors(run, "run"), [])
        self.assertEqual((run["status"], run["lifecycle"], run["revision"]), ("running", "draft", 1))
        for f in ("intake_form.md", "architecture.md", "rubric.md", "veto.md", "brand.md", "lessons.writer.md"):
            self.assertTrue((run_dir / "context" / f).exists(), f)
        runs = self.tmp / "runs"
        self.assertEqual((runs / ".current").read_text(), run_dir.name)
        self.assertTrue((runs / ".lock").exists())
        second = sh(["run.py", "new", "proposal", str(self.form)], self.env, check=False)
        self.assertNotEqual(second.returncode, 0, "اجرای دوم با قفل باز نباید ساخته شود")
        sh(["run.py", "finish"], self.env)
        self.assertFalse((runs / ".lock").exists())

    def test_intake_blocking_then_answer(self):
        run_dir = pathlib.Path(sh(["run.py", "new", "proposal", str(self.form)], self.env).stdout.strip())
        state = json.loads(sh(["run.py", "intake-check"], self.env).stdout)
        self.assertEqual(state["blocking_missing"], ["current_state"])
        self.assertEqual(state["status"], "blocked_on_input")
        sh(["run.py", "answer", "current", "Q-01", "پیش‌نویس‌ها دستی بازبینی می‌شوند", "--field", "current_state"], self.env)
        state = json.loads(sh(["run.py", "intake-check"], self.env).stdout)
        self.assertEqual(state["blocking_missing"], [])
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["status"], "running")
        self.assertEqual(run["intake_rounds"], 2)

    def test_status_transitions(self):
        sh(["run.py", "new", "proposal", str(self.form)], self.env)
        sh(["run.py", "set", "current", "--status", "ready_for_review"], self.env)
        back = sh(["run.py", "set", "current", "--status", "running"], self.env, check=False)
        self.assertNotEqual(back.returncode, 0, "وضعیت پایانی نباید برگردد")

    def test_unknown_field_rejected(self):
        form = json.loads(self.form.read_text(encoding="utf-8"))
        form["fields"]["guess"] = "x"
        self.form.write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
        r = sh(["run.py", "new", "proposal", str(self.form)], self.env, check=False)
        self.assertNotEqual(r.returncode, 0)


    def test_unknown_brand_rejected(self):
        form = json.loads(self.form.read_text(encoding="utf-8"))
        form["brand"] = "nobrand"
        self.form.write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
        r = sh(["run.py", "new", "proposal", str(self.form)], self.env, check=False)
        self.assertNotEqual(r.returncode, 0)


class ValidateStageTest(unittest.TestCase):
    """چک‌های متقاطع روی یک پوشه‌ی اجرای دست‌ساز."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        form = json.loads(sh(["run.py", "template", "proposal"], self.env).stdout)
        form["fields"].update(client_identity="شرکت نمونه", proposal_kind="فروش",
                              current_state="بازبینی دستی", discovery_notes="جلسه‌ی ۱۴۰۵/۰۶/۳۰")
        form["sample"] = True
        p = self.tmp / "input.json"
        p.write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
        self.run_dir = pathlib.Path(sh(["run.py", "new", "proposal", str(p)], self.env).stdout.strip())
        self.missing = json.loads(sh(["run.py", "intake-check"], self.env).stdout)["missing"]
        sh(["run.py", "set", "current", "--round", "1"], self.env)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, data):
        path = self.run_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def gaps_for(self, fields):
        return {"gaps": [{"id": f"G-{i:02d}", "field": f, "kind": "missing", "detail": "خالی", "impact": "none",
                          "blocking": False} for i, f in enumerate(fields, 1)]}

    def test_intake_hidden_gap_is_caught(self):
        self.write("questions.json", {"questions": []})
        self.write("gaps.json", self.gaps_for(self.missing[1:]))
        errors = validate.validate_stage(self.run_dir, "intake")
        self.assertTrue(any(self.missing[0] in e for e in errors), errors)
        self.write("gaps.json", self.gaps_for(self.missing))
        self.assertEqual(validate.validate_stage(self.run_dir, "intake"), [])

    def test_claims_sources(self):
        base = {"id": "C-01", "text": "بازبینی دستی است", "type": "fact", "used_in": ["S03"], "limits": "", "impact": "none"}
        cases = {
            "فیلد خالی": {"kind": "input", "ref": "budget"},
            "فیلد ناموجود": {"kind": "input", "ref": "nope"},
            "URL جست‌وجونشده": {"kind": "url", "ref": "https://example.com/x"},
        }
        for label, src in cases.items():
            with self.subTest(case=label):
                self.write("claims.json", {"claims": [dict(base, source=dict(src, date=None, quote=None))], "searches": []})
                self.assertNotEqual(validate.validate_stage(self.run_dir, "claims"), [], label)
        self.write("claims.json", {"claims": [dict(base, source={"kind": "input", "ref": "current_state", "date": None, "quote": None})],
                                   "searches": []})
        self.assertEqual(validate.validate_stage(self.run_dir, "claims"), [])

    def _doc_md(self):
        self.write("document.v1.md", "## بخش ۳\n\nطبق **صورت‌جلسه‌ی کشف نیاز** در ۱۴۰۵/۰۶/۳۰، هر پیش‌نویس بازبینی می‌شود.\n")

    def _rubric(self, quote):
        crit = []
        for c in common.load_card("proposal")["criteria"]:
            crit.append({"id": c["id"], "score": 2, "evidence": [{"section": "S03", "quote": quote}],
                         "reason": "نمونه", "fix": "", "limited_by_input": False, "gap_refs": []})
        return {"judge": "rubric", "version": 1, "criteria": crit, "bottom_line": "همه‌ی ردیف‌ها ناقص‌اند.",
                "biggest_weakness": {"criterion": "R06", "what": "قیمت ناقص", "why": "تصمیم خرید ممکن نیست", "fix": "اقلام قیمت را کامل کن"},
                "would_change": "جدول قیمت کامل"}

    def test_fabricated_quote_is_rejected(self):
        self._doc_md()
        self.write("gaps.json", {"gaps": []})
        self.write("judges/v1/rubric.json", self._rubric("زمان بازبینی ۴۰ درصد کم شد"))
        errors = validate.validate_stage(self.run_dir, "judge-rubric")
        self.assertTrue(any("پیدا نشد" in e for e in errors), errors)
        # نقل‌قول واقعی با نیم‌فاصله‌ی متفاوت و ارقام لاتین هم باید پیدا شود (یکسان‌سازی)
        self.write("judges/v1/rubric.json", self._rubric("طبق صورت جلسه ی کشف نیاز در 1405/06/30"))
        self.assertEqual(validate.validate_stage(self.run_dir, "judge-rubric"), [])

    def test_rubric_must_score_every_row(self):
        self._doc_md()
        self.write("gaps.json", {"gaps": []})
        rep = self._rubric("طبق صورت‌جلسه‌ی کشف نیاز")
        rep["criteria"].pop()
        self.write("judges/v1/rubric.json", rep)
        self.assertTrue(any("نمره نگرفته" in e for e in validate.validate_stage(self.run_dir, "judge-rubric")))

    def test_veto_coverage_and_applicability(self):
        self._doc_md()
        card = common.load_card("proposal")
        responsible = [v["id"] for v in card["veto"] if v["detector"] != "code"]
        self.write("judges/v1/veto.json", {"judge": "veto", "version": 1, "checked": responsible[:-1], "hits": [], "bottom_line": "آزمون پوشش رد فوری."})
        self.assertTrue(any("بررسی نشده" in e for e in validate.validate_stage(self.run_dir, "judge-veto")))
        self.write("judges/v1/veto.json", {"judge": "veto", "version": 1, "checked": responsible, "hits": [], "bottom_line": "آزمون پوشش رد فوری.",
                                           "not_applicable": [{"veto_id": "V01", "reason": "بی‌ربط"}]})
        self.assertTrue(any("شرط ندارد" in e for e in validate.validate_stage(self.run_dir, "judge-veto")))
        self.write("judges/v1/veto.json", {"judge": "veto", "version": 1, "checked": responsible[:-1], "hits": [], "bottom_line": "آزمون پوشش رد فوری.",
                                           "not_applicable": [{"veto_id": "V08", "reason": "پیشنهاد RFP نیست"}]})
        self.assertEqual(validate.validate_stage(self.run_dir, "judge-veto"), [])

    def test_truth_fields_are_enforced(self):
        """حالت truth: «بدون ضعف» فقط وقتی همه ۴ است؛ مهم‌ترین ضعف باید ردیفی باشد که امتیاز از دست داده."""
        self._doc_md()
        self.write("gaps.json", {"gaps": []})
        rep = self._rubric("طبق صورت‌جلسه‌ی کشف نیاز")
        rep["biggest_weakness"] = None
        self.write("judges/v1/rubric.json", rep)
        self.assertTrue(any("biggest_weakness خالی" in e for e in validate.validate_stage(self.run_dir, "judge-rubric")))
        rep = self._rubric("طبق صورت‌جلسه‌ی کشف نیاز")
        rep["criteria"][5]["score"] = 4
        self.write("judges/v1/rubric.json", rep)
        self.assertTrue(any("نمره‌ی کامل" in e for e in validate.validate_stage(self.run_dir, "judge-rubric")))

    def test_brand_proof_source(self):
        base = {"id": "C-01", "text": "۲۵+ سال تجربه‌ی نرم‌افزاری", "type": "fact", "used_in": ["S14"], "limits": "ادعای تهیه‌کننده", "impact": "none"}
        self.write("claims.json", {"claims": [dict(base, source={"kind": "brand", "ref": "BP-99", "date": None, "quote": None})], "searches": []})
        self.assertTrue(any("شاهد برند ناموجود" in e for e in validate.validate_stage(self.run_dir, "claims")))
        self.write("claims.json", {"claims": [dict(base, source={"kind": "brand", "ref": "BP-01", "date": None, "quote": None})], "searches": []})
        self.assertEqual(validate.validate_stage(self.run_dir, "claims"), [])

    def test_brand_context_marks_unverified_proof(self):
        md = (self.run_dir / "context" / "brand.md").read_text(encoding="utf-8")
        self.assertIn("مهدیار هوش‌افزا", md)
        self.assertIn("نامعلوم — پیش از نام‌بردن تأیید لازم است", md)
        self.assertIn("| PK-01 | پکیج رشد دیجیتال | ۱۵٬۰۰۰٬۰۰۰ |", md)
        run = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["brand"], "mahdiyar")

    def test_hook_blocks_once_then_releases(self):
        self.write("questions.json", {"questions": []})
        self.write("gaps.json", {"gaps": []})
        first = sh(["validate.py", "--hook", "--stage", "intake"], self.env, stdin="{}")
        decision = json.loads(first.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("فقط یک فرصت", decision["reason"])
        second = sh(["validate.py", "--hook", "--stage", "intake"], self.env, stdin="{}")
        self.assertEqual(second.stdout.strip(), "", "بار دوم نباید دوباره block کند")
        self.assertTrue((self.run_dir / ".retries" / "intake.v1.errors.txt").exists())
        explicit = sh(["validate.py", "--run", "current", "--stage", "intake"], self.env, check=False)
        self.assertEqual(explicit.returncode, 1, "ارکستریتور باید خطا را ببیند")

    def test_cost_benefit_cross_refs(self):
        doc = common.load_json(FIX / "document.good.json")
        self.assertEqual(validate.cost_benefit_errors(doc["data"]), [])
        cb = doc["data"]["cost_benefit"]
        cb["costs"][0]["amount"] = 1
        cb["costs"][1]["price_ref"] = "P-09"
        cb["benefits"][0]["metric"] = "M-09"
        cb["scenarios"] = [{"name": "base", "assumptions": "x", "net_value": None}] * 3
        errors = " ".join(validate.cost_benefit_errors(doc["data"]))
        for needle in ("CC-01", "P-09", "M-09", "low"):
            self.assertIn(needle, errors)

    def test_file_mode(self):
        r = sh(["validate.py", str(FIX / "document.good.json")], self.env, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
