"""آزمون C5: ارزیابی سند موجود (evaluate.py).

چرا: مسیر «سندم را ارزیابی کن» باید از سند تا گزارش، بدون ایجنت نویسنده و بدون Loop، قطعی و با قفل درست کار کند.
داورها در این آزمون گزارش‌های سالم آماده (fixture) هستند؛ رفتار واقعی مدل در E7 سنجیده می‌شود.
"""
import contextlib
import copy
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import evaluate  # noqa: E402
import render  # noqa: E402
import run as runmod  # noqa: E402

FX = ROOT / "tests" / "fixtures"
DOC = common.load_json(FX / "document.good.json")
LEDGER = common.load_json(FX / "claims.good.json")


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        os.environ["STUDIO_RUNS_DIR"] = self.env["STUDIO_RUNS_DIR"]
        common.RUNS = pathlib.Path(self.env["STUDIO_RUNS_DIR"])

    def tearDown(self):
        shutil.rmtree(self.tmp)
        os.environ.pop("STUDIO_RUNS_DIR", None)

    def doc(self, mutate=None, name="doc.json"):
        d = copy.deepcopy(DOC)
        if mutate:
            mutate(d)
        p = self.tmp / name
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return p

    def put_judges(self, run_dir, **replace):
        (run_dir / "judges" / "v1").mkdir(parents=True, exist_ok=True)
        for short in ("rubric", "claims", "veto"):
            shutil.copyfile(FX / "judges" / f"{short}.good.json", run_dir / "judges" / "v1" / f"{short}.json")
        for short, rep in replace.items():
            (run_dir / "judges" / "v1" / f"{short}.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")

    def status(self, run_dir):
        return runmod.load_run(run_dir)

    def test_prepare_builds_run_render_and_checks(self):
        rd = evaluate.prepare("proposal", str(self.doc()), str(FX / "claims.good.json"))
        self.assertTrue((rd / "document.v1.md").exists())
        checks = common.load_json(rd / "checks.v1.json")
        self.assertEqual(checks["mode"], "structured")
        self.assertEqual([r["id"] for r in checks["results"] if r["status"] != "pass"], [])
        run = self.status(rd)
        self.assertEqual((run["mode"], run["status"], run["stage"], run["round"]), ("evaluate", "running", "checks", 1))
        self.assertTrue((common.RUNS / ".lock").exists(), "در طول ارزیابی مشخصات قفل‌اند")
        self.assertFalse((rd / "loop.json").exists(), "ارزیابی بدون Loop")

    def test_finish_writes_gate_report_releases_lock(self):
        rd = evaluate.prepare("proposal", str(self.doc()), str(FX / "claims.good.json"))
        self.put_judges(rd)
        report = evaluate.finish(rd)
        gate = common.load_json(rd / "gate.v1.json")
        self.assertEqual((gate["total"], gate["guide"]["pass"], gate["target"]["met"]), (97.5, True, True))
        run = self.status(rd)
        self.assertEqual((run["status"], run["stage"]), ("ready_for_review", "done"))
        self.assertFalse((common.RUNS / ".lock").exists())
        text = report.read_text(encoding="utf-8")
        for needle in ("گزارش ارزیابی سند", "۹۷٫۵", "ساخت‌یافته (JSON)", "**فرضیه**", "## نمره‌ی هر ردیف", "| R05 |", "آماده‌ی بررسی انسان",
                       "بزرگ‌ترین ضعف (R05)"):
            self.assertIn(needle, text)
        self.assertNotIn("چک‌های قطعی که پاس نشدند", text, "همه‌ی چک‌ها پاس‌اند")
        self.assertNotIn("Loop", text, "ارزیابی Loop ندارد؛ واژه‌اش نباید در گزارش بیاید")
        self.assertIn("هدف کیفیت (> ۹۰)", text)

    def test_report_shows_veto_failed_checks_and_caps_for_a_broken_document(self):
        rd = evaluate.prepare("proposal", str(self.doc(lambda d: d["data"]["pricing"]["totals"].update(one_time=1))),
                              str(FX / "claims.good.json"))
        self.put_judges(rd)
        text = evaluate.finish(rd).read_text(encoding="utf-8")
        gate = common.load_json(rd / "gate.v1.json")
        self.assertEqual([v["id"] for v in gate["veto"]], ["V03"])
        self.assertFalse(gate["guide"]["pass"])
        for needle in ("رد فوری V03", "چک‌های قطعی که پاس نشدند", "CHK-PRICE-SUM | رد", "CHK-PRICE-SUM ≤ ۱", "قبولی راهنما:** خیر"):
            self.assertIn(needle, text)

    def test_bad_judge_report_is_refused_without_gate_and_lock_stays(self):
        rd = evaluate.prepare("proposal", str(self.doc()), str(FX / "claims.good.json"))
        fake = json.loads((FX / "judges" / "claims.good.json").read_text(encoding="utf-8"))
        fake["claims"][0]["quote"] = "این جمله هرگز در سند نبوده است"
        self.put_judges(rd, claims=fake)
        with self.assertRaises(SystemExit):
            evaluate.finish(rd)
        self.assertFalse((rd / "gate.v1.json").exists())
        self.assertFalse((rd / "report.md").exists())
        self.assertTrue((common.RUNS / ".lock").exists())
        self.assertEqual(self.status(rd)["status"], "running")
        self.put_judges(rd)  # داور یک بار اصلاح می‌کند
        evaluate.finish(rd)
        self.assertTrue((rd / "report.md").exists())

    def test_missing_judge_file_is_refused(self):
        rd = evaluate.prepare("proposal", str(self.doc()), str(FX / "claims.good.json"))
        self.put_judges(rd)
        (rd / "judges" / "v1" / "veto.json").unlink()
        err = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(err):
            evaluate.finish(rd)
        self.assertIn("گزارش داور نیست: judges/v1/veto.json", err.getvalue(), "پیام صریح، نه خطای عمومی اعتبارسنج")

    def test_finish_never_removes_a_lock_that_belongs_to_another_run(self):
        rd = evaluate.prepare("proposal", str(self.doc()), str(FX / "claims.good.json"))
        self.put_judges(rd)
        (common.RUNS / ".lock").write_text("run-دیگری", encoding="utf-8")
        evaluate.finish(rd)
        self.assertEqual((common.RUNS / ".lock").read_text(encoding="utf-8"), "run-دیگری")

    def test_markdown_document_is_scored_but_never_passes(self):
        md = self.tmp / "doc.md"
        md.write_text(render.render(DOC, LEDGER), encoding="utf-8")
        rd = evaluate.prepare("proposal", str(md), str(FX / "claims.good.json"))
        checks = common.load_json(rd / "checks.v1.json")
        self.assertEqual(checks["mode"], "text")
        self.assertEqual(next(r for r in checks["results"] if r["id"] == "CHK-PRICE-SUM")["status"], "skip")
        self.put_judges(rd)
        text = evaluate.finish(rd).read_text(encoding="utf-8")
        gate = common.load_json(rd / "gate.v1.json")
        self.assertEqual(gate["total"], 97.5)
        self.assertEqual((gate["guide"]["pass"], gate["target"]["met"]), (False, False))
        for needle in ("متنی (Markdown)", "سند ساخت‌یافته نیست", "CHK-PRICE-SUM | اجرا نشد"):
            self.assertIn(needle, text)

    def test_schema_invalid_json_fails_and_releases_the_lock(self):
        with self.assertRaises(SystemExit) as cm:
            evaluate.prepare("proposal", str(self.doc(lambda d: d["meta"].pop("title"))))
        self.assertEqual(cm.exception.code, 2)
        self.assertFalse((common.RUNS / ".lock").exists(), "اجرای شکست‌خورده قفل نگه نمی‌دارد")
        run = self.status(next(p for p in common.RUNS.iterdir() if p.is_dir()))
        self.assertEqual(run["status"], "failed")
        evaluate.prepare("proposal", str(self.doc()))  # اجرای بعدی آزاد است

    def test_second_evaluation_is_refused_while_first_holds_the_lock(self):
        evaluate.prepare("proposal", str(self.doc()))
        with self.assertRaises(SystemExit):
            evaluate.prepare("proposal", str(self.doc()))

    def test_cli_end_to_end(self):
        script = str(ROOT / "scripts" / "evaluate.py")
        r = subprocess.run([sys.executable, script, "prepare", "proposal", str(self.doc()), "--claims", str(FX / "claims.good.json")],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("سه داور", r.stdout)
        rd = pathlib.Path(r.stdout.splitlines()[0].split(": ", 1)[1])
        self.put_judges(rd)
        r = subprocess.run([sys.executable, script, "finish"], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().endswith("report.md"))
        self.assertIn("pass=True", r.stderr)


if __name__ == "__main__":
    unittest.main()
