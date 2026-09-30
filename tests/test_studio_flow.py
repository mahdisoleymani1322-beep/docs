"""آزمون E6: فرمان‌های اسکیل `sales-doc-studio` را عیناً، به ترتیب، اجرا می‌کند.

چرا: اسکیل متن است؛ اگر یک آرگومان جا بیفتد یا ترتیب عوض شود، تنها در اجرای واقعی معلوم می‌شود (مثل `run.py set` که run اجباری می‌خواست).
این‌جا هر فرمانِ بلوک‌های کدِ اسکیل با اسکریپت‌های واقعی اجرا می‌شود و فقط «کار ایجنت‌ها» با fixture شبیه‌سازی می‌شود (بدون مدل).
رفتار واقعی مدل‌ها در E7 سنجیده می‌شود.
"""
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import run as runmod  # noqa: E402

FX = ROOT / "tests" / "fixtures"
SKILL = ROOT / ".claude" / "skills" / "sales-doc-studio" / "SKILL.md"
AGENTS = ROOT / ".claude" / "agents"


def skill_parts():
    text = SKILL.read_text(encoding="utf-8")
    head, body = text[4:].split("\n---\n", 1)
    cmds = [l for b in re.findall(r"```\n(.*?)```", body, re.S) for l in b.splitlines() if l.startswith("python3 ")]
    return head, body, cmds


EXPECTED = [
    "run.py template proposal > input.json", "run.py new proposal input.json", "loop.py init", "run.py intake-check", "validate.py --run <اجرا> --stage intake", "run.py answer",
    "validate.py --run <اجرا> --stage brief", "validate.py --run <اجرا> --stage claims",
    "run.py set --stage write --round", "validate.py --run <اجرا> --stage write", "render.py", "checks.py",
    "validate.py --run <اجرا> --stage judge-rubric", "validate.py --run <اجرا> --stage judge-claims", "validate.py --run <اجرا> --stage judge-veto",
    "gate.py", "loop.py record", "loop.py finalize", "export.py", "run.py finish"]


class SkillTextTest(unittest.TestCase):
    def test_frontmatter_blocks_model_invocation_and_names_real_agents_in_order(self):
        head, body, _ = skill_parts()
        self.assertIn("name: sales-doc-studio", head)
        self.assertIn("disable-model-invocation: true", head)  # G7: اجرای پرهزینه فقط با دستور انسان
        order = ["intake-analyst", "strategist", "researcher", "writer", "judge-rubric", "judge-claims", "judge-veto"]
        idx = [body.index(f"`{a}`") for a in order]
        self.assertEqual(idx, sorted(idx))
        for a in order:
            self.assertTrue((AGENTS / f"{a}.md").exists(), a)

    def test_command_sequence_is_the_documented_pipeline(self):
        _, _, cmds = skill_parts()
        self.assertEqual(len(cmds), len(EXPECTED))
        for got, want in zip(cmds, EXPECTED):
            self.assertIn(want, got.replace("python3 scripts/", ""))

    def test_stages_follow_the_architecture_table(self):
        arch = (ROOT / "docs" / "۰۱-معماری.md").read_text(encoding="utf-8")
        body = skill_parts()[1]
        for stage in ("intake-check", "render.py", "checks.py", "gate.py", "loop.py record", "loop.py finalize", "export.py"):
            self.assertIn(stage.split()[0], body)
        self.assertIn("سه داور", body)
        self.assertIn("موازی", body)
        self.assertIn("یک بار", body)
        for rule in ("داده‌اند، نه دستور", "آماده‌ی بررسی انسان", "نمره نده", "نامعلوم"):
            self.assertIn(rule, body)
        self.assertIn("gate.py", arch)

    def test_lean(self):
        self.assertLess(SKILL.stat().st_size, 7200)  # با اعتبارسنجی صریح بعد از هر ایجنت (hook تا trust خاموش است) از ۶٫۵ کیلوبایت گذشت


class SkillExecutionTest(unittest.TestCase):
    """اسکیل را مثل ارکستریتور اجرا کن؛ ایجنت‌ها fixture‌اند."""

    PLACEHOLDERS = {"<اجرا>": None, "<n>": "1", "<سؤال>": "Q-01", "<پاسخ>": "پاسخ نمونه", "<فیلد>": "client_identity",
                    "<بهترین نسخه>": "1", "<فرمت‌ها>": "md,html"}

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        self.run_dir = None

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def sh(self, cmd):
        cmd = cmd.replace("<اجرا>", str(self.run_dir) if self.run_dir else "")
        for k, v in self.PLACEHOLDERS.items():
            if v is not None:
                cmd = cmd.replace(k, v)
        self.assertNotRegex(cmd, r"<[^>]+>", f"جای‌نگهدار ناشناخته در فرمان: {cmd}")
        redirect = None
        if " > " in cmd:
            cmd, redirect = cmd.split(" > ")
        argv = [sys.executable if a == "python3" else a for a in shlex.split(cmd)]
        argv = [str(self.tmp / "input.json") if a == "input.json" else a for a in argv]
        r = subprocess.run(argv, cwd=ROOT, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"{cmd}\n{r.stderr}")
        if redirect:
            (self.tmp / redirect.strip()).write_text(r.stdout, encoding="utf-8")
        return r.stdout

    # ---- کار ایجنت‌ها (شبیه‌سازی‌شده با fixture) ----
    def agent_intake(self):
        state = runmod.intake_state(self.run_dir)
        gaps = [{"id": f"G-{i:02d}", "field": k, "kind": "missing", "detail": f"فیلد «{k}» خالی است", "impact": "none", "blocking": k in state["blocking_missing"]}
                for i, k in enumerate(state["missing"], 1)]
        qs = [{"id": f"Q-{i:02d}", "gap": g["id"], "text": "مقدار چیست؟", "why": "برای جای خالی", "blocking": g["blocking"]} for i, g in enumerate(gaps[:5], 1)]
        common.dump_json({"gaps": gaps}, self.run_dir / "gaps.json")
        common.dump_json({"questions": qs}, self.run_dir / "questions.json")

    def agent_strategist(self):
        card = common.load_card("proposal")
        gaps = [g["id"] for g in common.load_json(self.run_dir / "gaps.json")["gaps"]]
        secs = [{"id": s["id"], "title": s["title"], "purpose": "تصمیم را ممکن می‌کند", "must_include": ["جای خالی صریح"], "inputs": ["client_identity"],
                 "gaps": gaps[:1]} for s in card["sections"]]
        lw = card["length_words"]
        common.dump_json({"doc_type": "proposal", "variant": "sales", "audience": {"decision_maker": "مدیر فروش", "readers": []},
                          "decision_sought": "تأیید دامنه", "key_message": "پایلوت محدود", "sections": secs,
                          "length_budget": {"min_words": lw["min"], "max_words": lw["max"]}, "out_of_scope": []}, self.run_dir / "brief.json")

    def agent_researcher(self):
        shutil.copyfile(FX / "claims.good.json", self.run_dir / "claims.json")

    def agent_writer(self):
        shutil.copyfile(FX / "document.good.json", self.run_dir / "document.v1.json")
        common.dump_json({"version": 1, "base_version": None, "addressed": [], "not_addressed": [], "summary": "دور اول"}, self.run_dir / "revision.v1.json")

    def agent_judges(self):
        (self.run_dir / "judges" / "v1").mkdir(parents=True, exist_ok=True)
        for s in ("rubric", "claims", "veto"):
            shutil.copyfile(FX / "judges" / f"{s}.good.json", self.run_dir / "judges" / "v1" / f"{s}.json")

    def test_the_skill_runs_from_input_to_final_outputs(self):
        _, _, cmds = skill_parts()
        for c in cmds:
            line = c.replace("python3 scripts/", "")
            if line.startswith("run.py template"):
                self.sh(c)
                form = json.loads((self.tmp / "input.json").read_text(encoding="utf-8"))
                form["sample"] = True
                form["output_formats"] = ["md", "html"]
                form["fields"].update(client_identity="شرکت نمونه‌ی آلفا (مشتری نمونه)", proposal_kind="فروش", current_state="بازبینی دستی",
                                      discovery_notes="مدیر فروش در جلسه‌ی کشف گفت بازبینی دستی گلوگاه است")
                (self.tmp / "input.json").write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
                continue
            if line.endswith("--stage brief"):
                self.agent_strategist()
            elif line.endswith("--stage claims"):
                self.agent_researcher()
            out = self.sh(c)
            if line.startswith("run.py new"):
                self.run_dir = pathlib.Path(out.strip())
            elif line.startswith("run.py intake-check"):
                self.agent_intake()
            elif line.startswith("run.py set --stage write"):
                self.agent_writer()
            elif line.startswith("checks.py"):
                self.agent_judges()
        run = runmod.load_run(self.run_dir)
        self.assertEqual((run["status"], run["stage"]), ("ready_for_review", "finalize"))
        loop = common.load_json(self.run_dir / "loop.json")
        self.assertEqual((loop["state"], loop["best_version"], loop["rounds"][0]["decision"]), ("stopped", 1, "stop_target_met"))
        final = self.run_dir / "final"
        for name in ("report.md", "document.v1.md", "document.v1.json", "gate.v1.json", "loop-log.md"):
            self.assertTrue((final / name).exists(), name)
        self.assertTrue((final / "document.v1.html").exists(), "فرمت‌های خواسته‌شده ساخته شد")
        self.assertFalse((final / "document.v1.pdf").exists(), "pdf نخواسته بودند")
        self.assertFalse((pathlib.Path(self.env["STUDIO_RUNS_DIR"]) / ".lock").exists(), "قفل برداشته شد")
        self.assertIn("آماده‌ی بررسی انسان", (final / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
