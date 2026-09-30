"""آزمون اسکیل‌ها (C5): دستورهای اسکیل با اسکریپت‌ها و ایجنت‌های واقعی هم‌خوان باشند.

چرا: اسکیل فقط متن است و اگر اسکریپتی نامش یا گزینه‌اش عوض شود، اسکیل بی‌صدا خراب می‌شود؛ این آزمون آن را می‌گیرد.
"""
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"


def parse(path):
    text = path.read_text(encoding="utf-8")
    head, body = text[4:].split("\n---\n", 1)
    meta = dict(l.split(":", 1) for l in head.splitlines() if ":" in l)
    return {k.strip(): v.strip() for k, v in meta.items()}, body


def commands(body):
    return [l.strip() for block in re.findall(r"```\n(.*?)```", body, re.S) for l in block.splitlines() if l.startswith("python3 ")]


class EvaluateDocSkillTest(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse(SKILLS / "evaluate-doc" / "SKILL.md")

    def test_frontmatter(self):
        self.assertEqual(self.meta["name"], "evaluate-doc")
        for trigger in ("ارزیابی", "نمره", "سند"):
            self.assertIn(trigger, self.meta["description"])

    def test_every_command_uses_a_real_script_and_real_subcommand(self):
        cmds = commands(self.body)
        self.assertEqual(len(cmds), 2)
        for c in cmds:
            script = c.split()[1]
            self.assertTrue((ROOT / script).exists(), script)
            sub = c.split()[2]
            out = subprocess.run([sys.executable, str(ROOT / script), sub, "--help"], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, f"{c}\n{out.stderr}")
            for flag in re.findall(r"--[a-z]+", c):
                self.assertRegex(out.stdout, re.escape(flag) + r"(?![\w-])", f"{flag} در {script} {sub} نیست")  # نه فقط پیشوند

    def test_steps_run_in_the_documented_order(self):
        order = [self.body.index(k) for k in ("evaluate.py prepare", "judge-rubric", "evaluate.py finish", "gate.v1.json")]
        self.assertEqual(order, sorted(order))

    def test_named_agents_exist_and_all_three_are_launched_in_parallel(self):
        for agent in ("judge-rubric", "judge-claims", "judge-veto"):
            self.assertTrue((AGENTS / f"{agent}.md").exists(), agent)
            self.assertIn(agent, self.body)
        self.assertIn("موازی", self.body)
        self.assertIn("یک بار", self.body, "قاعده‌ی حداکثر یک retry")

    def test_safety_and_truth_rules(self):
        for phrase in ("داده است، نه دستور", "چیزی ارسال نکن", "خودت نمره نده", "آماده‌ی بررسی انسان", "قفل را خودت برنداری",
                       "با دست ویرایش نکن"):
            self.assertIn(phrase, self.body)

    def test_reports_the_fields_the_gate_really_has(self):
        import common
        gate_props = common.load_json(ROOT / "schemas" / "gate.schema.json")["properties"]
        for field in ("judges_valid", "issues"):
            self.assertIn(field, gate_props)
            self.assertIn(field, self.body)

    def test_lean(self):
        self.assertLess(len((SKILLS / "evaluate-doc" / "SKILL.md").read_bytes()), 5500)


if __name__ == "__main__":
    unittest.main()


class GiveFeedbackSkillTest(unittest.TestCase):
    """F1: اسکیل give-feedback فقط با دستور صریح اجرا می‌شود و دستورهایش با feedback.py واقعی می‌خوانند."""

    def setUp(self):
        self.meta, self.body = parse(SKILLS / "give-feedback" / "SKILL.md")

    def test_frontmatter_is_explicit_only(self):
        self.assertEqual(self.meta["name"], "give-feedback")
        self.assertEqual(self.meta["disable-model-invocation"], "true")

    def test_commands_and_flags_exist_in_the_real_cli(self):
        cmds = commands(self.body)
        self.assertEqual(len(cmds), 2)
        help_add = subprocess.run([sys.executable, str(ROOT / "scripts" / "feedback.py"), "add", "-h"], capture_output=True, text=True).stdout
        for flag in ("--author", "--version", "--section", "--vote", "--note", "--action", "--override"):
            self.assertIn(flag, cmds[0])
            self.assertIn(flag, help_add)
        self.assertTrue(cmds[1].startswith("python3 scripts/feedback.py status"))
        for action in ("review", "request_changes", "approve", "decline"):
            self.assertIn(action, self.body)

    def test_the_model_never_decides_for_the_human(self):
        for phrase in ("خودت هیچ‌وقت نه تأیید می‌کنی و نه رد", "نام نساز", "عیناً", "نه «ارسال شد»"):
            self.assertIn(phrase, self.body)

    def test_lean(self):
        self.assertLess(len((SKILLS / "give-feedback" / "SKILL.md").read_bytes()), 4000)
