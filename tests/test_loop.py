"""آزمون C3: Loop اصلی.

چرا: تصمیم توقف و انتخاب بهترین نسخه باید برای هر سناریو قابل‌پیش‌بینی باشد. ورودی آزمون‌ها gate.v<n>.json ساختگی
ولی معتبر با schema است (از خروجی واقعی gate ساخته می‌شود)، پس رابطه‌ی loop و gate هم سنجیده می‌شود.
"""
import copy
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
sys.path.insert(0, str(ROOT / "tests"))
import common  # noqa: E402
import loop as loopmod  # noqa: E402
import test_gate as tg  # noqa: E402

GOOD = tg.go()


def fake_gate(total, passed=None, veto=(), scores=None, limited=(), version=1, text_issues=None):
    """gate معتبر با schema که فقط فیلدهای مورد استفاده‌ی loop را تنظیم می‌کند."""
    g = copy.deepcopy(GOOD)
    g["version"] = version
    g["total"] = float(total)
    g["guide"]["pass"] = (total >= 85 and not veto) if passed is None else passed
    g["target"].update(score10=total / 10, met=bool(g["guide"]["pass"] and total > 90))
    g["veto"] = [{"id": v, "source": "CHK-X", "detail": "d"} for v in veto]
    for c in g["criteria"]:
        c["final_score"] = (scores or {}).get(c["id"], 4)
        c["limited_by_input"] = c["id"] in limited
    g["issues"] = text_issues if text_issues is not None else [
        {"id": "I-01", "source": "R05", "severity": "below_target", "section": "S07", "text": f"ایراد نسخه‌ی {version}",
         "points_at_stake": 2.5}]
    assert common.schema_errors(g, "gate") == []
    return g


class DecisionTest(unittest.TestCase):
    def loop(self, rounds=()):
        cfg = {"max_rounds": 4, "total_gt": 90.0, "plateau_rounds": 2, "plateau_min_gain": 1.0}
        rs = []
        for i, (total, veto, passed) in enumerate(rounds, 1):
            rs.append({"round": i, "version": i, "total": total, "veto": veto, "guide_pass": passed})
        return {"config": cfg, "rounds": rs}

    def rnd(self, n, total, veto=(), passed=None, target=None, limited=False):
        passed = (total >= 85 and not veto) if passed is None else passed
        return {"round": n, "version": n, "total": float(total), "veto": list(veto), "guide_pass": passed,
                "target_met": passed and total > 90 if target is None else target, "limited_by_input": limited}

    def test_rule1_target_met_stops(self):
        d, reason, best = loopmod.decide(self.loop(), self.rnd(1, 91))
        self.assertEqual((d, best), ("stop_target_met", 1))
        self.assertIn("۹۱", reason)

    def test_exactly_90_does_not_stop(self):
        self.assertEqual(loopmod.decide(self.loop(), self.rnd(1, 90))[0], "continue")

    def test_rule2_input_limited_only_without_veto(self):
        self.assertEqual(loopmod.decide(self.loop(), self.rnd(1, 80, limited=True))[0], "stop_input_limited")
        self.assertEqual(loopmod.decide(self.loop(), self.rnd(1, 80, veto=["V03"], limited=True))[0], "continue")

    def test_rule3_max_rounds(self):
        lp = self.loop([(70, [], False), (75, [], False), (80, [], False)])
        d, reason, best = loopmod.decide(lp, self.rnd(4, 86))
        self.assertEqual((d, best), ("stop_max_rounds", 4))
        lp = self.loop([(70, [], False), (75, [], False)])
        self.assertEqual(loopmod.decide(lp, self.rnd(3, 80))[0], "continue")

    def test_rule4_plateau_needs_history_and_uses_best_not_last(self):
        # دور ۳: بهترین دور ۱ و ۳ فقط ۰٫۵ اختلاف دارد (< ۱٫۰) ← درجا زدن
        lp = self.loop([(80, [], False), (70, [], False)])
        self.assertEqual(loopmod.decide(lp, self.rnd(3, 80.5))[0], "stop_plateau")
        # با ۱٫۰ دقیق درجا زدن نیست (کمتر از ۱٫۰ می‌خواهد)
        self.assertEqual(loopmod.decide(lp, self.rnd(3, 81.0))[0], "continue")
        # تاریخچه‌ی کم: بعد از دور ۲ هنوز قضاوت نمی‌شود
        self.assertEqual(loopmod.decide(self.loop([(80, [], False)]), self.rnd(2, 80))[0], "continue")

    def test_plateau_measures_the_best_version_not_the_last_round(self):
        # دور ۳ بدتر از بهترین (۸۷) است ولی بهترین نسبت به دور ۱ هنوز ۷ امتیاز پیشرفت دارد ← ادامه
        lp = self.loop([(80, [], False), (87, [], True)])
        self.assertEqual(loopmod.decide(lp, self.rnd(3, 70))[0], "continue")

    def test_rule_order_target_beats_everything_and_input_limited_beats_max_rounds(self):
        lp = self.loop([(70, [], False), (70, [], False), (70, [], False)])
        self.assertEqual(loopmod.decide(lp, self.rnd(4, 95))[0], "stop_target_met")
        self.assertEqual(loopmod.decide(lp, self.rnd(4, 70, limited=True))[0], "stop_input_limited")

    def test_best_version_priority(self):
        R = lambda v, total, veto, passed: {"version": v, "total": total, "veto": veto, "guide_pass": passed}  # noqa: E731
        # بدون رد فوری همیشه بر total بالاتر با رد فوری می‌چربد
        self.assertEqual(loopmod.best_of([R(1, 95, ["V03"], False), R(2, 60, [], False)]), 2)
        # قبولی راهنما بر total بالاتر بدون قبولی
        self.assertEqual(loopmod.best_of([R(1, 84.9, [], False), R(2, 85.0, [], True)]), 2)
        # قبولی بر total: نسخه‌ی ۱ total بالاتر ولی ردیف حیاتی زیر حداقل (قبولی ندارد)
        self.assertEqual(loopmod.best_of([R(1, 95, [], False), R(2, 86, [], True)]), 2)
        # رد فوری بر قبولی: نسخه‌ای با رد فوری (قبولی هم ندارد) هیچ‌وقت بهترین نیست
        self.assertEqual(loopmod.best_of([R(1, 60, [], False), R(2, 99, ["V02"], False)]), 1)
        # بعد total؛ و در تساوی دور جدیدتر
        self.assertEqual(loopmod.best_of([R(1, 88, [], True), R(2, 86, [], True)]), 1)
        self.assertEqual(loopmod.best_of([R(1, 88, [], True), R(2, 88, [], True)]), 2)

    def test_summary_below_target_and_limited_flag(self):
        g = fake_gate(80, scores={"R02": 2, "R05": 3}, limited={"R02", "R05"})
        s = loopmod.summarize(g, 1, None)
        self.assertEqual((s["below_target"], s["limited_by_input"]), (["R02", "R05"], True))
        g = fake_gate(80, scores={"R02": 2, "R05": 3}, limited={"R02"})
        self.assertFalse(loopmod.summarize(g, 1, None)["limited_by_input"])
        g = fake_gate(100)
        self.assertFalse(loopmod.summarize(g, 1, None)["limited_by_input"], "بدون ردیف زیر ۴ شرط تهی است، نه محدود به ورودی")


class RunFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        os.environ["STUDIO_RUNS_DIR"] = self.env["STUDIO_RUNS_DIR"]
        common.RUNS = pathlib.Path(self.env["STUDIO_RUNS_DIR"])
        doc = self.tmp / "d.json"
        doc.write_text(json.dumps(tg.DOC, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), "new-eval", "proposal", str(doc)],
                           env=self.env, capture_output=True, text=True, check=True)
        self.run_dir = pathlib.Path(r.stdout.strip())
        # اجرای ارزیابی، حالت studio نیست؛ برای Loop حالت و مرحله را مثل اجرای ساخت می‌گذاریم
        run = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
        run["mode"], run["stage"] = "studio", "write"
        common.dump_json(run, self.run_dir / "run.json")
        loopmod.init_loop(self.run_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)
        os.environ.pop("STUDIO_RUNS_DIR", None)

    def put(self, n, **kw):
        common.dump_json(fake_gate(version=n, **kw), self.run_dir / f"gate.v{n}.json")

    def status(self):
        return json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))

    def test_init_matches_card_and_is_schema_valid(self):
        lp = common.load_json(self.run_dir / "loop.json")
        card = common.load_card("proposal")
        self.assertEqual(lp["config"], {k: card["loop_target"][k] for k in ("max_rounds", "total_gt", "plateau_rounds", "plateau_min_gain")})
        self.assertEqual((lp["state"], lp["rounds"], lp["best_version"]), ("running", [], None))
        self.assertIn("ارسال", lp["contract"]["authority_human"])

    def test_target_met_in_round_one_ends_ready_for_review(self):
        self.put(1, total=95)
        lp = loopmod.record(self.run_dir, 1)
        self.assertEqual((lp["state"], lp["best_version"], self.status()["status"]), ("stopped", 1, "ready_for_review"))
        self.assertFalse((self.run_dir / "issues.v1.json").exists(), "بعد از توقف ایراد تازه لازم نیست")

    def test_continue_writes_issues_of_best_version_for_next_round(self):
        self.put(1, total=80, scores={"R05": 2})
        lp = loopmod.record(self.run_dir, 1)
        self.assertEqual((lp["state"], self.status()["status"], self.status()["round"]), ("running", "running", 1))
        iss = common.load_json(self.run_dir / "issues.v1.json")
        self.assertEqual((iss["for_round"], iss["base_version"], iss["regressions"]), (2, 1, []))
        self.assertEqual(iss["issues"][0]["text"], "ایراد نسخه‌ی 1")
        self.assertEqual(common.schema_errors(iss, "issues"), [])

    def test_regression_rolls_back_to_best_and_reports_lost_rows(self):
        self.put(1, total=86, scores={"R05": 3})
        loopmod.record(self.run_dir, 1)
        self.put(2, total=70, scores={"R05": 3, "R06": 2, "R09": 3})  # دور ۲ بدتر شد
        lp = loopmod.record(self.run_dir, 2)
        self.assertEqual(lp["best_version"], 1)
        self.assertEqual(lp["rounds"][1]["base_version"], 1)
        iss = common.load_json(self.run_dir / "issues.v2.json")
        self.assertEqual(iss["base_version"], 1, "دور ۳ روی بهترین نسخه بازنویسی می‌شود، نه نسخه‌ی ۲")
        self.assertEqual(iss["issues"][0]["text"], "ایراد نسخه‌ی 1")
        self.assertEqual(len(iss["regressions"]), 2)
        self.assertIn("R06", iss["regressions"][0])
        self.assertIn("نسخه‌ی ۲", iss["regressions"][0])

    def test_base_version_of_round_comes_from_previous_issues_file(self):
        self.put(1, total=80, scores={"R05": 2})
        loopmod.record(self.run_dir, 1)
        self.put(2, total=82, scores={"R05": 2})
        lp = loopmod.record(self.run_dir, 2)
        self.assertEqual([r["base_version"] for r in lp["rounds"]], [None, 1])

    def test_full_run_to_max_rounds_with_improvement(self):
        for n, total in enumerate((70, 76, 82, 86), 1):
            self.put(n, total=total, scores={"R05": 2})
            lp = loopmod.record(self.run_dir, n)
        self.assertEqual((lp["state"], lp["rounds"][-1]["decision"], lp["best_version"]), ("stopped", "stop_max_rounds", 4))
        self.assertEqual(self.status()["status"], "needs_human")

    def test_plateau_stops_at_round_three(self):
        for n, total in enumerate((80, 80.4, 80.5), 1):
            self.put(n, total=total, scores={"R05": 2})
            lp = loopmod.record(self.run_dir, n)
        self.assertEqual((lp["rounds"][-1]["decision"], self.status()["status"]), ("stop_plateau", "needs_human"))

    def test_input_limited_stops_with_needs_human(self):
        self.put(1, total=78, scores={"R01": 2, "R02": 3}, limited={"R01", "R02"})
        lp = loopmod.record(self.run_dir, 1)
        self.assertEqual((lp["rounds"][0]["decision"], self.status()["status"]), ("stop_input_limited", "needs_human"))

    def test_refuses_out_of_order_duplicate_and_after_stop(self):
        self.put(2, total=80)
        with self.assertRaises(SystemExit):
            loopmod.record(self.run_dir, 2)
        self.put(1, total=95)
        loopmod.record(self.run_dir, 1)
        with self.assertRaises(SystemExit):
            loopmod.record(self.run_dir, 1)
        self.put(2, total=95)
        with self.assertRaises(SystemExit):
            loopmod.record(self.run_dir, 2)

    def test_missing_or_invalid_gate_is_refused(self):
        with self.assertRaises(SystemExit):
            loopmod.record(self.run_dir, 1)
        (self.run_dir / "gate.v1.json").write_text('{"x": 1}', encoding="utf-8")
        with self.assertRaises(SystemExit):
            loopmod.record(self.run_dir, 1)

    def test_log_is_regenerated_from_loop_and_revisions(self):
        self.put(1, total=80, scores={"R05": 2})
        loopmod.record(self.run_dir, 1)
        common.dump_json({"version": 2, "base_version": 1, "addressed": [{"issue": "I-01", "change": "زمان‌بندی اصلاح شد"}],
                          "not_addressed": [{"issue": "I-02", "reason": "ورودی لازم است"}], "summary": "دور دوم"},
                         self.run_dir / "revision.v2.json")
        self.put(2, total=95)
        loopmod.record(self.run_dir, 2)
        log = (self.run_dir / "loop-log.md").read_text(encoding="utf-8")
        self.assertIn("| ۱ | — | ۸۰ |", log)
        self.assertIn("| ۲ | ۱ | ۹۵ |", log)
        self.assertIn("رفع‌شده: I-01 — زمان‌بندی اصلاح شد", log)
        self.assertIn("رفع‌نشده: I-02 — ورودی لازم است", log)
        self.assertIn("`gate.v2.json`", log)

    def test_finalize_copies_best_version_and_writes_honest_report(self):
        self.put(1, total=86, scores={"R05": 3})
        (self.run_dir / "document.v1.json").write_text("{}", encoding="utf-8")
        (self.run_dir / "document.v1.md").write_text("متن", encoding="utf-8")
        loopmod.record(self.run_dir, 1)
        self.put(2, total=70, scores={"R05": 2, "R06": 2})
        (self.run_dir / "document.v2.md").write_text("بدتر", encoding="utf-8")
        loopmod.record(self.run_dir, 2)
        for n, t in ((3, 88), (4, 90)):  # ۳: پیشرفت ≥ ۱ نسبت به دور ۱ ← درجا زدن نیست
            self.put(n, total=t, scores={"R05": 3})
            loopmod.record(self.run_dir, n)
        (self.run_dir / "document.v4.md").write_text("بهترین", encoding="utf-8")
        out = loopmod.finalize(self.run_dir)
        self.assertEqual((out / "document.v4.md").read_text(encoding="utf-8"), "بهترین")
        self.assertFalse((out / "document.v1.md").exists() or (out / "document.v2.md").exists(), "فقط بهترین نسخه در final است")
        rep = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn("بهترین نسخه:** ۴", rep)
        self.assertIn("نیازمند تصمیم انسان", rep)
        self.assertIn("**فرضیه**", rep, "داور کالیبره‌نشده باید صریح گفته شود")
        self.assertIn("برآورده نشد", rep)
        self.assertIn("## ایرادهای باقی‌مانده", rep)
        self.assertIn("(زیر هدف)", rep)
        self.assertNotRegex(rep, r"\((veto|critical|below_min|below_target|warn|human)\)", "برچسب‌ها فارسی‌اند")
        self.assertEqual(set(loopmod.SEVERITY_FA), set(common.load_json(ROOT / "schemas" / "issues.schema.json")
                                                        ["properties"]["issues"]["items"]["properties"]["severity"]["enum"]))
        self.assertNotIn("ready_for_review", rep)

    def test_finalize_refused_while_running(self):
        self.put(1, total=80, scores={"R05": 2})
        loopmod.record(self.run_dir, 1)
        with self.assertRaises(SystemExit):
            loopmod.finalize(self.run_dir)

    def test_cli_record_and_finalize(self):
        self.put(1, total=95)
        env = self.env
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "loop.py"), "record", str(self.run_dir), "--version", "1"],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stop_target_met", r.stdout)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "loop.py"), "finalize", str(self.run_dir)],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.run_dir / "final" / "report.md").exists())


if __name__ == "__main__":
    unittest.main()
