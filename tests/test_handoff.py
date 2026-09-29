"""آزمون DS1: ساختار handoff.md و رد کامیت یا پوشی که آن را به‌روز نکرده.

چرا: کاربر خواسته handoff پیش از هر کامیت و پوش به‌روز شود؛ این آزمون نشان می‌دهد اجبار واقعاً کار می‌کند.
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
SCRIPT = ROOT / "scripts" / "check_handoff.py"
sys.path.insert(0, str(ROOT / "scripts"))
import check_handoff  # noqa: E402

GOOD = "\n\n".join(f"{h}\n\nمتن" for h in check_handoff.HEADINGS) + "\n"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


class HandoffStructureTest(unittest.TestCase):
    def test_repo_handoff_is_valid(self):
        self.assertEqual(check_handoff.structure_errors((ROOT / "handoff.md").read_text(encoding="utf-8")), [])

    def test_missing_empty_and_reordered(self):
        self.assertTrue(check_handoff.structure_errors(GOOD.replace("## 5) Failed attempts", "## 5) Failures")))
        self.assertTrue(check_handoff.structure_errors(GOOD.replace("## 3) Active files\n\nمتن", "## 3) Active files\n")))
        parts = GOOD.split("\n\n")
        swapped = "\n\n".join(parts[2:4] + parts[0:2] + parts[4:])
        self.assertTrue(check_handoff.structure_errors(swapped))


class HandoffEnforcementTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "handoff.md").write_text(GOOD, encoding="utf-8")
        (self.repo / "a.txt").write_text("1")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.repo)

    def run_check(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, input=stdin,
                              capture_output=True, text=True)

    def test_staged_requires_handoff_change(self):
        (self.repo / "a.txt").write_text("2")
        git(self.repo, "add", "a.txt")
        self.assertEqual(self.run_check("--staged").returncode, 1)
        (self.repo / "handoff.md").write_text(GOOD + "\nبه‌روز\n", encoding="utf-8")
        git(self.repo, "add", "handoff.md")
        self.assertEqual(self.run_check("--staged").returncode, 0)

    def test_push_requires_last_commit_to_touch_handoff(self):
        (self.repo / "a.txt").write_text("2")
        git(self.repo, "commit", "-qam", "بدون handoff")
        self.assertEqual(self.run_check("--push").returncode, 1)
        (self.repo / "handoff.md").write_text(GOOD + "\nبه‌روز\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "با handoff")
        self.assertEqual(self.run_check("--push").returncode, 0)

    def test_git_hook_blocks_commit(self):
        hooks = self.repo / ".githooks"
        hooks.mkdir()
        shutil.copy(ROOT / ".githooks" / "pre-commit", hooks / "pre-commit")
        (self.repo / "scripts").mkdir()
        shutil.copy(SCRIPT, self.repo / "scripts" / "check_handoff.py")
        git(self.repo, "config", "core.hooksPath", ".githooks")
        (self.repo / "a.txt").write_text("3")
        git(self.repo, "add", "a.txt")
        r = subprocess.run(["git", "commit", "-qm", "x"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "hook گیت باید کامیت بدون handoff را رد کند")

    def test_claude_hook_denies_and_ignores_other_commands(self):
        deny = self.run_check("--hook", stdin=json.dumps({"tool_input": {"command": "git add -A && git commit -m x"},
                                                          "cwd": str(self.repo)}))
        self.assertEqual(json.loads(deny.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        other = self.run_check("--hook", stdin=json.dumps({"tool_input": {"command": "ls -la"}, "cwd": str(self.repo)}))
        self.assertEqual(other.stdout.strip(), "")
        (self.repo / "handoff.md").write_text(GOOD + "\nبه‌روز\n", encoding="utf-8")
        allow = self.run_check("--hook", stdin=json.dumps({"tool_input": {"command": "git commit -am x"}, "cwd": str(self.repo)}))
        self.assertEqual(allow.stdout.strip(), "")


class GitActionParsingTest(unittest.TestCase):
    """hook فقط فرمان git واقعی را بگیرد، نه متنی که «git commit» را فقط می‌نویسد (باگ واقعی: ویرایش CLAUDE.md رد شد)."""

    def test_real_commands_are_detected(self):
        real = {
            "git commit -m x": "commit", "git add -A && git commit -q -F -": "commit", "cd /r && git commit": "commit",
            "git -C /repo commit -m x": "commit", "git -c user.name=a commit": "commit", "FOO=1 git commit": "commit",
            "true;git commit": "commit", "(git commit)": "commit", "echo a\ngit commit -m x": "commit",
            "git push": "push", "git push -u origin b": "push", "git add . && git push origin HEAD": "push",
            "git commit -F - <<'EOF'\nپیام\nEOF\ngit push": "commit",
        }
        for cmd, want in real.items():
            with self.subTest(cmd=cmd):
                self.assertEqual(check_handoff.git_action(cmd.replace("\\n", "\n")), want)

    def test_mentions_are_not_commands(self):
        text = {
            "heredoc": "python3 - <<'EOF'\nprint('بعد git commit بزن و git push')\nEOF",
            "double quote": 'echo "run git commit later"',
            "single quote": "echo 'git push'",
            "python string": "python3 -c \"open('CLAUDE.md').write('بعد git commit')\"",
            "grep": "grep -n 'git commit' CLAUDE.md",
            "path": "cat docs/git-commit-notes.md",
            "other git": "git status && git log -1 && git diff",
            "commit as word": "echo commit push",
            # اشاره‌ی سرِ مرز فرمان: بدون حذف رشته و heredoc، این‌ها فرمان واقعی به نظر می‌رسند
            "quoted after separator": 'echo "done; git commit"',
            "quoted multi-line": 'echo "line1\ngit push\nline3"',
            "heredoc line starts with git": "cat > notes.md <<'EOF'\ngit commit -m x\nEOF",
            "unquoted heredoc delimiter": "cat <<EOF\ngit push\nEOF",
        }
        for label, cmd in text.items():
            with self.subTest(label=label):
                self.assertIsNone(check_handoff.git_action(cmd), cmd)

    def test_heredoc_body_is_skipped_but_command_after_it_is_still_seen(self):
        cmd = "cat > f <<'EOF'\ngit push\nEOF\ngit commit -m x"
        self.assertEqual(check_handoff.git_action(cmd), "commit")

    def test_denial_message_tells_the_right_order(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        try:
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "a@b.c")
            git(repo, "config", "user.name", "t")
            (repo / "handoff.md").write_text(GOOD, encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "x")
            (repo / "f.txt").write_text("x", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPT), "--hook"], input=json.dumps({"tool_input": {"command": "git commit -m y"}, "cwd": str(repo)}),
                               capture_output=True, text=True)
            reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("فرمان جدا", reason)
            self.assertIn("پیش از اجرا", reason)
            mention = subprocess.run([sys.executable, str(SCRIPT), "--hook"], input=json.dumps({"tool_input": {"command": "echo 'git commit'"}, "cwd": str(repo)}),
                                     capture_output=True, text=True)
            self.assertEqual(mention.stdout.strip(), "", "فقط اشاره‌ی متنی است؛ رد نمی‌شود")
        finally:
            shutil.rmtree(repo)

    def test_rule_is_written_in_claude_md(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("در یک فرمان جدا", text)


if __name__ == "__main__":
    unittest.main()
