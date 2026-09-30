"""آزمون F1: feedback.py — انتقال‌های مجاز lifecycle، رد بدون اثر، و اجرای تازه برای درخواست تغییر.

چرا: تنها چیزی که «انسان تأیید کرد» را ثبت می‌کند همین است؛ انتقال غیرمجاز که خاموش بپذیرد یا نیمه‌کاره بنویسد، تاریخچه را دروغ می‌کند.
CLI مثل کاربر اجرا می‌شود (subprocess) روی پوشه‌های موقت.
"""
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
import feedback  # noqa: E402

INPUT = ROOT / "examples" / "inputs" / "proposal-sample.json"


def snapshot(d: pathlib.Path):
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


class FeedbackBase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.runs, self.fb = self.tmp / "runs", self.tmp / "feedback"
        self.env = {**os.environ, "STUDIO_RUNS_DIR": str(self.runs), "STUDIO_FEEDBACK_DIR": str(self.fb),
                    "STUDIO_LESSONS_DIR": str(self.tmp / "lessons")}
        self.run_dir = self.new_run()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def sh(self, script, *args):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args], capture_output=True, text=True, env=self.env)
        return r.returncode, r.stdout, r.stderr

    def new_run(self, parent=None):
        args = ["new", "proposal", str(INPUT)] + (["--parent", str(parent)] if parent else [])
        code, out, err = self.sh("run.py", *args)
        self.assertEqual(code, 0, err)
        return pathlib.Path(out.strip().splitlines()[-1])

    def release(self):
        self.assertEqual(self.sh("run.py", "finish")[0], 0)

    def add(self, *args, run=None):
        return self.sh("feedback.py", "add", str(run or self.run_dir), "--author", "مدیر فروش", *args)

    def lifecycle(self, run=None):
        return json.loads((run or self.run_dir).joinpath("run.json").read_text(encoding="utf-8"))["lifecycle"]

    def records(self, run=None):
        f = self.fb / f"{(run or self.run_dir).name}.jsonl"
        return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []

    def make_ready(self):
        self.assertEqual(self.sh("run.py", "set", str(self.run_dir), "--status", "needs_human")[0], 0)


class TransitionsTest(FeedbackBase):
    def test_first_vote_or_note_moves_draft_to_in_review(self):
        for args in (["--vote", "up"], ["--note", "قیمت مبهم است"], ["--action", "review"]):
            self.tearDown()
            self.setUp()
            code, out, err = self.add(*args)
            self.assertEqual(code, 0, err)
            self.assertEqual(self.lifecycle(), "in_review", args)

    def test_repeat_votes_stay_in_review_and_are_all_recorded(self):
        self.add("--vote", "down", "--note", "بخش قیمت")
        code, out, _ = self.add("--vote", "up")
        self.assertEqual(code, 0)
        self.assertIn("بدون تغییر", out)
        self.assertEqual(len(self.records()), 2)
        hist = json.loads(self.run_dir.joinpath("run.json").read_text(encoding="utf-8"))["history"]
        self.assertEqual([h["event"] for h in hist].count("lifecycle"), 1, "فقط انتقال واقعی در تاریخچه می‌آید")
        self.assertIn("draft ← in_review (مدیر فروش)", [h["detail"] for h in hist])

    def test_decline_and_terminal_states_reject_everything(self):
        self.assertEqual(self.add("--action", "decline")[0], 0)
        self.assertEqual(self.lifecycle(), "declined")
        before = snapshot(self.tmp)
        for args in (["--vote", "up"], ["--action", "approve", "--override", "x"], ["--action", "review"], ["--note", "هنوز"]):
            code, _, err = self.add(*args)
            self.assertEqual(code, 1, args)
            self.assertIn("پایانی", err)
        self.assertEqual(snapshot(self.tmp), before, "رد نباید فایلی را تغییر دهد")

    def test_approve_needs_ready_or_override(self):
        before = snapshot(self.tmp)
        code, _, err = self.add("--action", "approve")
        self.assertEqual(code, 1)
        self.assertIn("--override", err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(self.add("--action", "approve", "--override", "   ")[0], 1, "دلیل فقط فاصله پذیرفته نیست")
        code, out, err = self.add("--action", "approve", "--override", "مدیر عامل شفاهی تأیید کرد")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.lifecycle(), "approved")
        self.assertEqual(self.records()[-1]["override_reason"], "مدیر عامل شفاهی تأیید کرد")

    def test_approve_of_a_ready_run_needs_no_override(self):
        run = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
        run["status"] = "ready_for_review"
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        self.assertEqual(self.add("--action", "approve")[0], 0)
        self.assertEqual(self.lifecycle(), "approved")

    def test_request_changes_needs_a_note_somewhere(self):
        before = snapshot(self.tmp)
        code, _, err = self.add("--action", "request_changes")
        self.assertEqual(code, 1)
        self.assertIn("یادداشت", err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(self.add("--note", "قیمت را روشن کنید")[0], 0)      # یادداشتِ قبلی کافی است
        self.assertEqual(self.add("--action", "request_changes")[0], 1)       # قفل اجرا هنوز دست همین اجراست
        self.release()
        self.assertEqual(self.add("--action", "request_changes")[0], 0)
        self.assertEqual(self.lifecycle(), "changes_requested")

    def test_empty_record_and_bad_fields_are_rejected_without_writing(self):
        before = snapshot(self.tmp)
        for args in ([], ["--section", "S6", "--vote", "up"], ["--vote", "maybe"]):
            self.assertNotEqual(self.add(*args)[0], 0, args)
        self.assertNotEqual(self.sh("feedback.py", "add", str(self.run_dir), "--vote", "up")[0], 0)   # بدون author
        self.assertEqual(snapshot(self.tmp), before)

    def test_version_and_section_must_exist(self):
        before = snapshot(self.tmp)
        self.assertEqual(self.add("--version", "3", "--vote", "up")[0], 1)
        self.assertEqual(snapshot(self.tmp), before)
        shutil.copy(ROOT / "tests" / "fixtures" / "document.good.json", self.run_dir / "document.v1.json")
        self.assertEqual(self.add("--version", "1", "--section", "S99", "--vote", "down", "--note", "؟")[0], 1)
        code, _, err = self.add("--version", "1", "--section", "S09", "--vote", "down", "--note", "قیمت مبهم")
        self.assertEqual(code, 0, err)
        self.assertEqual((self.records()[-1]["version"], self.records()[-1]["section"]), (1, "S09"))


class RequestChangesTest(FeedbackBase):
    def test_creates_child_run_with_human_issues(self):
        shutil.copy(ROOT / "tests" / "fixtures" / "document.good.json", self.run_dir / "document.v1.json")
        self.add("--version", "1", "--section", "S09", "--vote", "down", "--note", "مبلغ کل با اقلام نمی‌خواند")
        self.add("--vote", "up", "--note", "ولی خلاصه خوب است")                      # رأی مثبت ← ایراد نمی‌شود
        self.add("--note", "لحن رسمی‌تر")
        self.release()
        code, out, err = self.add("--action", "request_changes", "--note", "نسخه‌ی تازه لازم است")
        self.assertEqual(code, 0, err)
        child = self.runs / sorted(p.name for p in self.runs.iterdir() if p.is_dir() and p.name != self.run_dir.name)[-1]
        crun = json.loads((child / "run.json").read_text(encoding="utf-8"))
        self.assertEqual((crun["revision"], crun["parent_run"], crun["lifecycle"]), (2, self.run_dir.name, "draft"))
        issues = json.loads((child / "issues.v0.json").read_text(encoding="utf-8"))
        self.assertEqual([(i["id"], i["source"], i["severity"], i["section"]) for i in issues["issues"]],
                         [("I-01", "human", "human", "S09"), ("I-02", "human", "human", None), ("I-03", "human", "human", None)])
        self.assertEqual([i["text"] for i in issues["issues"]],
                         ["مبلغ کل با اقلام نمی‌خواند", "لحن رسمی‌تر", "نسخه‌ی تازه لازم است"])
        self.assertEqual(self.sh("validate.py", "--schema", "issues", str(child / "issues.v0.json"))[0], 0)
        self.assertEqual(self.lifecycle(), "changes_requested")
        self.assertTrue((self.run_dir / "input.json").exists())               # اجرای قبلی دست‌نخورده
        self.assertEqual(json.loads((self.run_dir / "run.json").read_text())["revision"], 1)

    def test_missing_input_stops_before_any_write(self):
        self.add("--note", "یادداشت")
        self.release()
        (self.run_dir / "input.json").unlink()
        before = snapshot(self.tmp)
        code, _, err = self.add("--action", "request_changes")
        self.assertEqual(code, 1)
        self.assertIn("input.json", err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(self.lifecycle(), "in_review")

    def test_status_command(self):
        self.add("--vote", "up")
        self.add("--vote", "down", "--note", "n")
        code, out, _ = self.sh("feedback.py", "status", str(self.run_dir))
        s = json.loads(out)
        self.assertEqual((code, s["lifecycle"], s["feedback"], s["votes"]), (0, "in_review", 2, {"up": 1, "down": 1}))


class PureLogicTest(unittest.TestCase):
    def rec(self, **kw):
        return {"vote": None, "note": None, "action": None, **kw}

    def test_plan_matrix(self):
        run = {"lifecycle": "in_review", "status": "ready_for_review"}
        self.assertEqual(feedback.plan(run, self.rec(action="approve"), []), "approved")
        self.assertEqual(feedback.plan(run, self.rec(action="decline"), []), "declined")
        self.assertEqual(feedback.plan(run, self.rec(action="request_changes", note="x"), []), "changes_requested")
        self.assertEqual(feedback.plan(run, self.rec(action="request_changes"), [{"note": "قبلی"}]), "changes_requested")
        for cur in ("approved", "declined", "changes_requested"):
            with self.assertRaises(SystemExit):
                feedback.plan({"lifecycle": cur, "status": "ready_for_review"}, self.rec(vote="up"), [])

    def test_build_issues_skips_positive_and_empty(self):
        issues = feedback.build_issues([
            {"note": "الف", "vote": "down", "section": "S02"}, {"note": "ب", "vote": "up", "section": None},
            {"note": None, "vote": "down", "section": None}, {"note": "پ", "vote": None, "section": None}])["issues"]
        self.assertEqual([(i["id"], i["text"], i["section"]) for i in issues], [("I-01", "الف", "S02"), ("I-02", "پ", None)])


if __name__ == "__main__":
    unittest.main()
