"""آزمون D3: kappa.py با مقدارهای دست‌حساب و مرزهای صریح.

چرا: κ روی مرز ۰٫۶ تصمیم می‌گیرد نمره‌ها «فرضیه»اند یا نه؛ پس مقدارها باید با محاسبه‌ی دستیِ مستقل بخوانند، و بدون برچسب انسانی
هیچ فایل کالیبراسیونی ساخته نشود.
"""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import gate  # noqa: E402
import kappa  # noqa: E402


class KappaMathTest(unittest.TestCase):
    def test_cohen_textbook_example(self):
        # ۲۰ بله/بله، ۵ بله/خیر، ۱۰ خیر/بله، ۱۵ خیر/خیر ← po=0.7، pe=0.5، κ=0.4
        a = [1] * 20 + [1] * 5 + [0] * 10 + [0] * 15
        b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
        self.assertEqual(kappa.kappa(a, b, weighted=False), Fraction(2, 5))

    def test_weighted_hand_computed(self):
        # محاسبه‌ی دستی: مشاهده‌شده ۱/۸، مورد انتظار ۷/۱۶ ← κ = 1 − 2/7 = 5/7
        self.assertEqual(kappa.kappa([0, 2, 4, 4], [0, 3, 4, 3]), Fraction(5, 7))

    def test_perfect_and_perfectly_opposed(self):
        self.assertEqual(kappa.kappa([0, 1, 2, 3, 4], [0, 1, 2, 3, 4]), 1)
        self.assertEqual(kappa.kappa([0, 0, 4, 4], [4, 4, 0, 0]), -1)

    def test_weighting_matters(self):
        a, b = [0, 1, 2, 3, 4, 4], [1, 2, 3, 4, 4, 3]
        self.assertGreater(kappa.kappa(a, b, weighted=True), kappa.kappa(a, b, weighted=False))

    def test_result_is_exact_fraction(self):
        self.assertIsInstance(kappa.kappa([0, 2, 4, 4], [0, 3, 4, 3]), Fraction)

    def test_undefined_and_bad_inputs_raise(self):
        with self.assertRaisesRegex(ValueError, "تعریف‌شده نیست"):
            kappa.kappa([2, 2, 2], [2, 2, 2])            # هر دو همه‌جا ۲: توافق تصادفی کامل
        for a, b in (([], []), ([1], [1, 2]), ([5], [1]), ([1], [5]), ([-1], [1]), ([True], [1]), ([1.5], [1])):
            with self.assertRaisesRegex(ValueError, "هم‌طول|نمره‌ها باید", msg=str((a, b))):
                kappa.kappa(a, b)


class KappaCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.cal = self.tmp / "calibration.json"
        self._old = common.CALIBRATION
        common.CALIBRATION = self.cal          # فایل واقعی evals/calibration.json دست نمی‌خورد

    def tearDown(self):
        common.CALIBRATION = self._old
        import shutil
        shutil.rmtree(self.tmp)

    def setup_docs(self, human_scores, judge_scores):
        labels = {"docs": {}}
        for i, (h, j) in enumerate(zip(human_scores, judge_scores)):
            name = f"d{i}"
            labels["docs"][name] = {"human": {"rows": {f"R{k + 1:02d}": s for k, s in enumerate(h)}} if h else None}
            (self.tmp / name).mkdir()
            (self.tmp / name / "rubric.json").write_text(json.dumps(
                {"criteria": [{"id": f"R{k + 1:02d}", "score": s} for k, s in enumerate(j)]}), encoding="utf-8")
        (self.tmp / "labels.json").write_text(json.dumps(labels), encoding="utf-8")

    def run_cli(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = kappa.main(["--labels", str(self.tmp / "labels.json"), "--judged", str(self.tmp), *extra])
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_no_human_labels_means_no_kappa_and_no_calibration_file(self):
        self.setup_docs([None, None], [[3, 3], [2, 2]])
        code, _, err = self.run_cli("--write")
        self.assertEqual(code, 1)
        self.assertIn("برچسب انسانی نیست", err)
        self.assertFalse(self.cal.exists())

    def test_write_needs_enough_pairs(self):
        self.setup_docs([[0, 1, 2, 3, 4]], [[0, 1, 2, 3, 3]])
        code, out, err = self.run_cli("--write")
        self.assertEqual(code, 1)
        self.assertIn("کافی نیست", err)
        self.assertFalse(self.cal.exists())
        code, out, _ = self.run_cli()                    # بدون --write فقط گزارش
        self.assertEqual(code, 0)
        self.assertIn("κ وزنی", out)

    def test_writes_calibration_the_gate_can_read(self):
        h = [[0, 1, 2, 3, 4] * 2, [4, 3, 2, 1, 0] * 2]
        j = [[0, 1, 2, 3, 4] * 2, [4, 3, 2, 1, 1] * 2]
        self.setup_docs(h, j)
        code, out, err = self.run_cli("--write")
        self.assertEqual(code, 0, err)
        cal = json.loads(self.cal.read_text(encoding="utf-8"))
        self.assertGreater(cal["kappa"]["proposal"], 0.6)
        old, gate.common.CALIBRATION = gate.common.CALIBRATION, self.cal
        try:
            self.assertTrue(gate.judges_valid("proposal"))
            self.assertFalse(gate.judges_valid("pitch"))
        finally:
            gate.common.CALIBRATION = old

    def test_low_kappa_keeps_judges_a_hypothesis(self):
        h = [[0, 1, 2, 3, 4] * 4]
        j = [[4, 3, 2, 1, 0] * 4]
        self.setup_docs(h, j)
        code, _, _ = self.run_cli("--write")
        self.assertEqual(code, 0)
        self.assertFalse(gate.judges_valid("proposal"))

    def test_missing_judge_file_or_row_is_a_loud_error(self):
        self.setup_docs([[1, 2, 3]], [[1, 2]])
        code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("R03", err)
        (self.tmp / "d0" / "rubric.json").unlink()
        code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("rubric.json", err)


if __name__ == "__main__":
    unittest.main()
