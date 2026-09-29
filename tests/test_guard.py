"""آزمون C6: guard.py (G2 فقط فایل مجاز، G3 مسیرهای قفل، G5 بودجه) و اتصال hookها.

چرا: هر گاردریل باید هم مورد رد و هم مورد عبورش را نشان بدهد؛ گاردی که همه چیز را رد کند یا همه چیز را بگذراند بی‌فایده است.
همه‌ی آزمون‌ها guard.py را مثل Claude Code اجرا می‌کنند: subprocess با JSON hook روی stdin.
"""
import fcntl
import itertools
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import common  # noqa: E402
from test_agents import JUDGES, parse, table_row, backticked  # noqa: E402

GUARD = str(ROOT / "scripts" / "guard.py")


class GuardBase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.runs = self.tmp / "runs"
        self.runs.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k != "STUDIO_ALLOW_LOCKED"}
        self.env["STUDIO_RUNS_DIR"] = str(self.runs)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def make_run(self, name="run-a", round_=1, current=True):
        d = self.runs / name
        d.mkdir()
        (d / "run.json").write_text(json.dumps({"round": round_}), encoding="utf-8")
        if current:
            (self.runs / ".current").write_text(name, encoding="utf-8")
        return d

    def call(self, args, tool="Write", path=None, agent=False, cwd=None, env=None, raw=None):
        payload = raw if raw is not None else json.dumps({
            "tool_name": tool, "tool_input": {"file_path": str(path)} if path is not None else {}, "cwd": str(cwd or ROOT),
            **({"agent_id": "agent-1", "agent_type": "judge-rubric"} if agent else {})})
        r = subprocess.run([sys.executable, GUARD, *args], input=payload, capture_output=True, text=True, env=env or self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None

    def denied(self, *a, **k):
        out = self.call(*a, **k)
        self.assertIsNotNone(out, "باید رد می‌شد")
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        return out["permissionDecisionReason"]

    def allowed(self, *a, **k):
        self.assertIsNone(self.call(*a, **k), "باید عبور می‌کرد")


class LockedTest(GuardBase):
    LOCKED = ["guides/x.md", "rubrics/proposal.json", "schemas/run.schema.json", "evals/golden/proposal/a.json"]
    FREE = ["docs/x.md", "scripts/x.py", "evals/calibration.json", "rubrics2/x.json", "schemas_old/x", "brand/x.json", "tests/x.py"]

    def test_full_matrix(self):
        """فقط «پوشه‌ی قفل و (قفل هست یا از داخل ایجنت)» رد می‌شود."""
        for lock, agent, (rel, is_locked) in itertools.product(
                (False, True), (False, True), [(p, True) for p in self.LOCKED] + [(p, False) for p in self.FREE]):
            with self.subTest(lock=lock, agent=agent, path=rel):
                lock_file = self.runs / ".lock"
                lock_file.unlink(missing_ok=True)
                if lock:
                    lock_file.write_text("run-a", encoding="utf-8")
                out = self.call(["--locked"], path=ROOT / rel, agent=agent)
                self.assertEqual(out is not None, is_locked and (lock or agent))

    def test_human_override_env(self):
        (self.runs / ".lock").write_text("run-a", encoding="utf-8")
        self.denied(["--locked"], path=ROOT / "rubrics/proposal.json")
        self.allowed(["--locked"], path=ROOT / "rubrics/proposal.json", env=dict(self.env, STUDIO_ALLOW_LOCKED="1"))
        self.denied(["--locked"], path=ROOT / "rubrics/proposal.json", env=dict(self.env, STUDIO_ALLOW_LOCKED="0"))

    def test_edit_and_notebook_like_write_but_read_is_ignored(self):
        for tool in ("Edit", "MultiEdit"):
            self.denied(["--locked"], tool=tool, path=ROOT / "rubrics/proposal.json", agent=True)
        for tool in ("Read", "Grep", "Bash"):
            self.allowed(["--locked"], tool=tool, path=ROOT / "rubrics/proposal.json", agent=True)

    def test_relative_traversal_and_symlink_do_not_bypass(self):
        self.denied(["--locked"], path="rubrics/x.json", agent=True)  # نسبی به cwd = ریشه
        self.denied(["--locked"], path=ROOT / "docs" / ".." / "rubrics" / "x.json", agent=True)
        self.denied(["--locked"], path="../rubrics/x.json", cwd=ROOT / "docs", agent=True)
        link = self.tmp / "innocent"
        link.symlink_to(ROOT / "rubrics")
        self.denied(["--locked"], path=link / "x.json", agent=True)
        self.allowed(["--locked"], path=self.tmp / "elsewhere.json", agent=True)

    def test_reason_is_actionable_and_names_the_way_out(self):
        reason = self.denied(["--locked"], path=ROOT / "rubrics/x.json", agent=True)
        for needle in ("منجمد", "STUDIO_ALLOW_LOCKED=1", "ایجنت", "گزارش کن"):
            self.assertIn(needle, reason)
        (self.runs / ".lock").write_text("r", encoding="utf-8")
        self.assertIn("اجرای جاری", self.denied(["--locked"], path=ROOT / "guides/x.md"))

    def test_bad_input_passes_through_and_missing_path_is_ignored(self):
        self.allowed(["--locked"], raw="not json")
        self.allowed(["--locked"], raw="{}")
        self.allowed(["--locked"], raw=json.dumps({"tool_name": "Write", "tool_input": {}, "agent_id": "a"}))


class AllowTest(GuardBase):
    def setUp(self):
        super().setUp()
        self.run_dir = self.make_run(round_=1)
        (self.run_dir / "judges" / "v1").mkdir(parents=True)
        self.args = ["--allow", "judges/v{n}/rubric.json"]

    def test_only_its_own_file(self):
        self.allowed(self.args, path=self.run_dir / "judges/v1/rubric.json", agent=True)
        for bad in ("judges/v1/claims.json", "judges/v1/veto.json", "judges/v2/rubric.json", "judges/rubric.json",
                    "document.v1.json", "run.json", "judges/v1/rubric.json.bak", "judges/v1/sub/rubric.json"):
            with self.subTest(bad=bad):
                self.denied(self.args, path=self.run_dir / bad, agent=True)

    def test_round_number_follows_run_json(self):
        d = self.make_run("run-b", round_=3)
        self.allowed(self.args, path=d / "judges/v3/rubric.json", agent=True)
        self.denied(self.args, path=d / "judges/v1/rubric.json", agent=True)

    def test_outside_the_run_dir_and_traversal_and_symlink(self):
        self.denied(self.args, path=ROOT / "judges/v1/rubric.json", agent=True)
        self.denied(self.args, path=self.tmp / "judges/v1/rubric.json", agent=True)
        self.denied(self.args, path=self.run_dir / "judges/v1/../../../rubrics/x.json", agent=True)
        other = self.make_run("run-other", current=False)
        self.denied(self.args, path=other / "judges/v1/rubric.json", agent=True)
        outside = self.tmp / "outside"
        outside.mkdir()
        (self.run_dir / "judges" / "v1" / "rubric.json").symlink_to(outside / "steal.json")
        self.denied(self.args, path=self.run_dir / "judges/v1/rubric.json", agent=True)

    def test_no_active_run_means_no_writes(self):
        (self.runs / ".current").unlink()
        reason = self.denied(self.args, path=self.run_dir / "judges/v1/rubric.json", agent=True)
        self.assertIn("هیچ اجرای فعالی", reason)

    def test_multiple_patterns_and_wildcards_stay_within_one_segment(self):
        args = ["--allow", "judges/v{n}/rubric.json", "brief.json"]
        self.allowed(args, path=self.run_dir / "brief.json", agent=True)
        args = ["--allow", "judges/v{n}/*.json"]
        self.allowed(args, path=self.run_dir / "judges/v1/veto.json", agent=True)
        self.denied(args, path=self.run_dir / "judges/v1/deep/veto.json", agent=True)

    def test_path_depth_must_match_the_pattern_exactly(self):
        args = ["--allow", "judges/v{n}/*"]
        self.allowed(args, path=self.run_dir / "judges/v1/x.json", agent=True)
        self.denied(args, path=self.run_dir / "judges/v1/x/y.json", agent=True)  # عمیق‌تر
        self.denied(args, path=self.run_dir / "judges/v1", agent=True)  # کوتاه‌تر: خود پوشه

    def test_reason_lists_the_allowed_files(self):
        reason = self.denied(self.args, path=self.run_dir / "run.json", agent=True)
        self.assertIn("judges/v1/rubric.json", reason)
        self.assertIn("run.json", reason)

    def test_read_is_never_blocked(self):
        self.allowed(self.args, tool="Read", path=self.run_dir / "document.v1.md", agent=True)


class BudgetTest(GuardBase):
    def test_sixth_passes_seventh_denied_and_denied_calls_do_not_count(self):
        d = self.make_run()
        for i in range(6):
            self.allowed(["--budget", "web=6"], tool="WebSearch")
        reason = self.denied(["--budget", "web=6"], tool="WebSearch")
        self.assertIn("6 از 6", reason)
        for _ in range(3):
            self.denied(["--budget", "web=6"], tool="WebFetch")
        self.assertEqual((d / ".budget" / "web").read_text(encoding="utf-8"), "6")

    def test_counters_are_per_run_and_per_name(self):
        a = self.make_run("run-a")
        for _ in range(2):
            self.allowed(["--budget", "web=2"], tool="WebSearch")
        self.denied(["--budget", "web=2"], tool="WebSearch")
        self.allowed(["--budget", "other=2"], tool="WebSearch")
        self.make_run("run-b", current=False)
        (self.runs / ".current").write_text("run-b", encoding="utf-8")
        self.allowed(["--budget", "web=2"], tool="WebSearch")
        self.assertEqual((a / ".budget" / "web").read_text(encoding="utf-8"), "2")

    def test_zero_budget_denies_immediately_and_no_run_denies(self):
        self.denied(["--budget", "web=0"], tool="WebSearch")  # اجرا نیست ← رد
        self.make_run()
        self.denied(["--budget", "web=0"], tool="WebSearch")

    def test_bad_argument_is_a_loud_error(self):
        for spec in ("web", "web=", "web=x", "=6", "web=-1"):
            with self.subTest(spec=spec):
                r = subprocess.run([sys.executable, GUARD, "--budget", spec], input="{}", capture_output=True, text=True, env=self.env)
                self.assertEqual(r.returncode, 2, spec)
                self.assertIn("نام=عدد", r.stderr)

    def test_counter_is_updated_under_a_file_lock(self):
        """قطعی، نه وابسته به زمان‌بندی: قفل را نگه می‌داریم؛ گارد باید منتظر بماند و بعد از آزادی بی‌خطا تمام شود."""
        d = self.make_run()
        (d / ".budget").mkdir()
        with open(d / ".budget" / "web", "a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            p = subprocess.Popen([sys.executable, GUARD, "--budget", "web=3"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=self.env)
            p.stdin.write("{}")
            p.stdin.close()
            time.sleep(0.7)
            self.assertIsNone(p.poll(), "گارد باید پشت قفل منتظر بماند")
            fcntl.flock(held, fcntl.LOCK_UN)
        self.assertEqual(p.wait(timeout=10), 0)
        self.assertEqual((d / ".budget" / "web").read_text(encoding="utf-8"), "1")

    def test_parallel_calls_never_exceed_the_limit(self):
        d = self.make_run()
        procs = [subprocess.Popen([sys.executable, GUARD, "--budget", "web=3"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                  env=self.env) for _ in range(10)]
        outs = [p.communicate("{}")[0] for p in procs]
        self.assertEqual(sum(1 for o in outs if not o.strip()), 3)
        self.assertEqual((d / ".budget" / "web").read_text(encoding="utf-8"), "3")


class ModesTest(GuardBase):
    def test_no_mode_is_an_error(self):
        r = subprocess.run([sys.executable, GUARD], input="{}", capture_output=True, text=True, env=self.env)
        self.assertNotEqual(r.returncode, 0)

    def test_locked_and_allow_combine_and_first_denial_wins(self):
        d = self.make_run()
        args = ["--locked", "--allow", "judges/v{n}/rubric.json"]
        self.allowed(args, path=d / "judges/v1/rubric.json", agent=True)
        self.assertIn("منجمد", self.denied(args, path=ROOT / "rubrics/x.json", agent=True))
        self.assertIn("اجازه‌ی نوشتن", self.denied(args, path=d / "run.json", agent=True))


class WiringTest(unittest.TestCase):
    def test_settings_have_the_locked_hook_and_spawn_depth(self):
        cfg = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        pre = cfg["hooks"]["PreToolUse"]
        write = [g for g in pre if g["matcher"] == "Write|Edit"]
        self.assertEqual(len(write), 1)
        cmd = write[0]["hooks"][0]
        self.assertEqual(cmd["command"], 'python3 "$CLAUDE_PROJECT_DIR/scripts/guard.py" --locked')
        self.assertIn("Bash", [g["matcher"] for g in pre], "hook handoff سر جایش می‌ماند")
        self.assertEqual(cfg["env"]["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"], "1")  # G6

    def test_every_agent_has_a_write_guard_matching_its_declared_output(self):
        """ایجنتِ بی‌گارد نباید بماند؛ الگوی مجاز هر ایجنت عیناً ستون «می‌نویسد» جدول داک ۰۲ است."""
        files = sorted(p for p in (ROOT / ".claude" / "agents").glob("*.md"))
        self.assertGreaterEqual(len(files), 3)
        for f in files:
            with self.subTest(agent=f.stem):
                meta, _ = parse(f)
                lines = meta["hooks"]
                self.assertIn("PreToolUse:", lines)
                self.assertIn('- matcher: "Write|Edit"', lines)
                cmd = next(l for l in lines if l.startswith("command:") and "guard.py" in l).removeprefix("command:").strip()
                m = re.fullmatch(r'python3 "\$CLAUDE_PROJECT_DIR/scripts/guard\.py" --allow "([^"]+)"', cmd)
                self.assertIsNotNone(m, cmd)
                declared = [x.strip("`") for x in table_row("## ۱. خلاصه‌ی ایجنت‌ها", f.stem)[6].split("،")]
                self.assertEqual([m.group(1).replace("{n}", "<n>")], declared)

    def test_environment_assumptions_are_stated_in_readme(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in ("فرض محیط", "fcntl.flock", "ویندوز", "۲٫۱٫۲۷۱", "Chromium", "CLAUDE_PROJECT_DIR", "اعتماد پوشه"):
            self.assertIn(needle, readme)
        self.assertIn("workspace trust", (ROOT / "docs" / "۰۵-ابزارها-و-گاردریل‌ها.md").read_text(encoding="utf-8"))

    def test_guard_docs_match_the_code(self):
        doc = (ROOT / "docs" / "۰۵-ابزارها-و-گاردریل‌ها.md").read_text(encoding="utf-8")
        for needle in ("guard.py --allow", "guard.py --locked", "guard.py --budget web=6", "STUDIO_ALLOW_LOCKED=1", "{n}"):
            self.assertIn(needle, doc)
        self.assertNotIn(".retries.json", doc, "کد از پوشه‌ی .retries استفاده می‌کند")


class EndToEndTest(GuardBase):
    def test_the_exact_frontmatter_commands_work(self):
        d = self.make_run(round_=1)
        for name, short in JUDGES.items():
            meta, _ = parse(ROOT / ".claude" / "agents" / f"{name}.md")
            cmd = next(l for l in meta["hooks"] if "guard.py" in l).removeprefix("command:").strip()
            argv = cmd.replace('python3 "$CLAUDE_PROJECT_DIR/scripts/guard.py"', "").split(" ", 2)
            args = ["--allow", f"judges/v{{n}}/{short}.json"]
            self.assertEqual(args, [argv[1], argv[2].strip('"')])
            mine, other = d / f"judges/v1/{short}.json", d / "judges/v1/other.json"
            self.allowed(args, path=mine, agent=True)
            self.denied(args, path=other, agent=True)


if __name__ == "__main__":
    unittest.main()
