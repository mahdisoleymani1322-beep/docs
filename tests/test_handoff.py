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


if __name__ == "__main__":
    unittest.main()
