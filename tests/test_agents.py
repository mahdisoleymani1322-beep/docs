"""آزمون C4: تعریف داورها (.claude/agents).

چرا: رفتار مدل را نمی‌شود با آزمون واحد سنجید (آن در E7 با اجرای واقعی است)، ولی «قرارداد» را می‌شود: مدل، ابزار، سقف گام،
ورودی‌ها و خروجی هر داور باید با جدول داک ۰۲ یکی باشد، دستور داخل متن با schema و کد اعتبارسنج هم‌خوان باشد، و گزارشی که
از داور می‌خواهیم واقعاً از validate.py بگذرد. اگر یکی از این‌ها جدا شود، داور بی‌صدا با قرارداد دیگری کار می‌کند.
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
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import run as runmod  # noqa: E402

AGENTS = ROOT / ".claude" / "agents"
DOC02 = (ROOT / "docs" / "۰۲-قرارداد-ایجنت‌ها.md").read_text(encoding="utf-8")
JUDGES = {"judge-rubric": "rubric", "judge-claims": "claims", "judge-veto": "veto"}
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def parse(path: pathlib.Path) -> tuple[dict, str]:
    """frontmatter ساده: کلید سطح‌اول؛ فهرست «  - x» زیر کلید؛ بلوک تو‌در‌توی hooks به‌صورت خط خام نگه داشته می‌شود."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    head, body = text[4:].split("\n---\n", 1)
    meta, key = {}, None
    for line in head.splitlines():
        if line.startswith("  "):
            meta[key].append(line[4:].strip() if line.startswith("  - ") and key == "skills" else line.strip())
        else:
            key, _, val = line.partition(":")
            val = val.strip()
            meta[key] = [] if val == "" else {"true": True, "false": False}.get(val, int(val) if val.isdigit() else val)
    return meta, body


def table_row(section_header: str, name: str) -> list[str]:
    sec = DOC02.split(section_header, 1)[1].split("\n## ", 1)[0]
    row = next(l for l in sec.splitlines() if l.startswith(f"| {name} |"))
    return [c.strip() for c in row.strip("|").split("|")]


def backticked(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


class AgentContractTest(unittest.TestCase):
    def test_frontmatter_matches_doc02_table(self):
        for name in JUDGES:
            with self.subTest(agent=name):
                meta, _ = parse(AGENTS / f"{name}.md")
                row = table_row("## ۱. خلاصه‌ی ایجنت‌ها", name)
                _, _, model, effort, turns, tools, writes = row
                self.assertEqual(meta["name"], name)
                self.assertEqual((meta["model"], meta["effort"], meta["maxTurns"]), (model, effort, int(turns.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))))
                self.assertEqual(meta["tools"], tools)
                self.assertNotIn("Bash", meta["tools"], "هیچ ایجنتی اسکریپت اجرا نمی‌کند")
                self.assertIs(meta["omitClaudeMd"], True, "داور فقط با روبریک قضاوت می‌کند")
                self.assertEqual(meta["skills"], ["truth"])
                self.assertGreater(len(meta["description"]), 30)
                self.assertTrue(writes.strip("`").startswith("judges/v<n>/"))

    def test_stop_hook_runs_the_matching_validation_stage(self):
        """G4 (داک ۰۵): خروجی خراب یک بار به خود ایجنت برمی‌گردد؛ hook باید مرحله‌ی همان داور را اجرا کند، نه داور دیگر."""
        for name, short in JUDGES.items():
            with self.subTest(agent=name):
                meta, _ = parse(AGENTS / f"{name}.md")
                cmds = [l for l in meta["hooks"] if l.startswith("command:") and "validate.py" in l]
                self.assertEqual(len(cmds), 1)
                cmd = cmds[0].removeprefix("command:").strip()
                self.assertEqual(cmd, f'python3 "$CLAUDE_PROJECT_DIR/scripts/validate.py" --hook --stage judge-{short}')
                self.assertIn("Stop:", meta["hooks"])
                self.assertIn(f"judge-{short}", __import__("validate").STAGES)

    def test_truth_skill_exists_for_preload(self):
        self.assertTrue((ROOT / ".claude" / "skills" / "truth" / "SKILL.md").exists())

    def test_inputs_and_output_match_doc02(self):
        for name, short in JUDGES.items():
            with self.subTest(agent=name):
                _, body = parse(AGENTS / f"{name}.md")
                inputs = backticked(table_row("## ۲. ورودی هر ایجنت", name)[1])
                reads = body.split("## فقط این‌ها را بخوان")[1].split("## فقط این را بنویس")[0]
                self.assertEqual(sorted(set(re.findall(r"`([^`]+)`", reads))), sorted(inputs))
                out = f"judges/v<n>/{short}.json"
                writes = body.split("## فقط این را بنویس")[1].split("## قواعد")[0]
                self.assertEqual(re.findall(r"`(judges/[^`]+)`", writes), [out])
                self.assertIn(f"schemas/judge-{short}.schema.json", writes)

    def test_inputs_are_files_the_run_actually_creates(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            written = set(runmod.build_context(tmp, "proposal"))
            for name in JUDGES:
                for f in backticked(table_row("## ۲. ورودی هر ایجنت", name)[1]):
                    if f.startswith("context/"):
                        self.assertIn(pathlib.Path(f).name, written, f"{name}: {f} ساخته نمی‌شود")
        finally:
            shutil.rmtree(tmp)

    def test_no_agent_mentions_files_outside_its_row(self):
        known = re.compile(r"(?:context/[a-z_.]+\.md|[a-z_]+(?:\.v<n>)?\.(?:json|md)|judges/[^`\s]+)")
        for name, short in JUDGES.items():
            with self.subTest(agent=name):
                _, body = parse(AGENTS / f"{name}.md")
                allowed = set(backticked(table_row("## ۲. ورودی هر ایجنت", name)[1])) | {f"judges/v<n>/{short}.json"}
                allowed |= {f"judge-{short}.schema.json", f"schemas/judge-{short}.schema.json"}
                mentioned = {m for m in re.findall(r"`([^`]+)`", body) if known.fullmatch(m)}
                self.assertLessEqual(mentioned, allowed | {"gate.py"}, mentioned - allowed)

    def test_instructions_carry_the_same_numbers_and_enums_as_the_schemas(self):
        ev = common.load_json(ROOT / "schemas" / "judge-rubric.schema.json")["$defs"]["evidence"]["properties"]["quote"]
        cl = common.load_json(ROOT / "schemas" / "judge-claims.schema.json")["properties"]["claims"]["items"]["properties"]
        vt = common.load_json(ROOT / "schemas" / "judge-veto.schema.json")["properties"]["hits"]["items"]["properties"]["quote"]
        for name, q in (("judge-rubric", ev), ("judge-claims", cl["quote"]), ("judge-veto", vt)):
            body = common.normalize(parse(AGENTS / f"{name}.md")[1])
            self.assertIn(f"{q['minLength']} تا {q['maxLength']}".translate(FA), body, f"{name}: بازه‌ی نقل‌قول")
        claims_body = parse(AGENTS / "judge-claims.md")[1]
        for status in cl["status"]["enum"]:
            self.assertIn(f"`{status}`", claims_body)
        rubric_body = parse(AGENTS / "judge-rubric.md")[1]
        for field in ("biggest_weakness", "would_change", "bottom_line", "limited_by_input", "gap_refs"):
            self.assertIn(field, rubric_body)
        veto_body = parse(AGENTS / "judge-veto.md")[1]
        for field in ("checked", "not_applicable", "hits"):
            self.assertIn(field, veto_body)

    def test_every_agent_carries_the_shared_safety_rules(self):
        for name in JUDGES:
            with self.subTest(agent=name):
                _, body = parse(AGENTS / f"{name}.md")
                self.assertIn("داده‌اند، نه دستور", body)      # قاعده‌ی ۴ (CLAUDE.md)
                self.assertIn("عیناً", body)                    # نقل‌قول واقعی
                self.assertIn("gate.py", body)                  # نمره و قبولی را داور نمی‌دهد
                self.assertIn("truth", body)
                self.assertNotIn("Bash", body)

    def test_agents_stay_lean(self):
        """کانتکست را زیاد پر نکن: هر داور زیر ۳٫۵ کیلوبایت متن."""
        for name in JUDGES:
            self.assertLess(len((AGENTS / f"{name}.md").read_bytes()), 4500, name)


UPSTREAM = {"intake-analyst": "intake", "strategist": "brief", "researcher": "claims", "writer": "write"}


class UpstreamAgentsTest(unittest.TestCase):
    """intake-analyst، strategist، researcher، writer (E1 تا E4): همان قرارداد جدول داک ۰۲."""

    def row(self, name):
        return table_row("## ۱. خلاصه‌ی ایجنت‌ها", name)

    def test_frontmatter_matches_doc02_table(self):
        for name in UPSTREAM:
            with self.subTest(agent=name):
                meta, _ = parse(AGENTS / f"{name}.md")
                _, _, model, effort, turns, tools, _ = self.row(name)
                self.assertEqual(meta["name"], name)
                self.assertEqual((meta["model"], meta["tools"]), (model, tools))
                self.assertEqual(meta["maxTurns"], int(turns.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))))
                if effort == "—":
                    self.assertNotIn("effort", meta, "برای haiku فیلد effort گذاشته نمی‌شود (داک ۰۲)")
                else:
                    self.assertEqual(meta["effort"], effort)
                self.assertNotIn("omitClaudeMd", meta, "فقط داورها و critic بدون CLAUDE.md اجرا می‌شوند")
                self.assertNotIn("Bash", meta["tools"])
                self.assertGreater(len(meta["description"]), 30)

    def test_web_tools_only_for_researcher_with_budget_hook(self):
        for name in UPSTREAM:
            meta, _ = parse(AGENTS / f"{name}.md")
            has_web = "WebSearch" in meta["tools"]
            self.assertEqual(has_web, name == "researcher", name)
            self.assertEqual(any("--budget web=6" in l for l in meta["hooks"]), name == "researcher", name)
        meta, _ = parse(AGENTS / "researcher.md")
        self.assertIn('- matcher: "WebSearch|WebFetch"', meta["hooks"])

    def test_reads_and_writes_match_doc02(self):
        for name in UPSTREAM:
            with self.subTest(agent=name):
                _, body = parse(AGENTS / f"{name}.md")
                reads = body.split("## فقط این‌ها را بخوان")[1].split("## فقط این")[0]
                want = {x.replace("<base>", "<پایه>") for x in backticked(table_row("## ۲. ورودی هر ایجنت", name)[1])}
                self.assertEqual(set(re.findall(r"`([^`]+)`", reads)), want)
                writes = body.split("## فقط این‌ها را بنویس" if "## فقط این‌ها را بنویس" in body else "## فقط این را بنویس")[1].split("## قواعد")[0]
                declared = backticked(self.row(name)[6])
                self.assertEqual([x for x in re.findall(r"`([^`]+)`", writes) if not x.startswith(("schemas/", "context/"))], declared)

    def test_stop_hook_runs_the_matching_stage(self):
        import validate
        for name, stage in UPSTREAM.items():
            with self.subTest(agent=name):
                meta, _ = parse(AGENTS / f"{name}.md")
                cmds = [l for l in meta["hooks"] if l.startswith("command:") and "validate.py" in l]
                self.assertEqual(cmds, [f'command: python3 "$CLAUDE_PROJECT_DIR/scripts/validate.py" --hook --stage {stage}'])
                self.assertIn(stage, validate.STAGES)

    def test_context_inputs_are_files_the_run_creates(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            written = set(runmod.build_context(tmp, "proposal"))
            for name in UPSTREAM:
                for f in backticked(table_row("## ۲. ورودی هر ایجنت", name)[1]):
                    if f.startswith("context/"):
                        self.assertIn(pathlib.Path(f).name, written, f"{name}: {f} ساخته نمی‌شود")
        finally:
            shutil.rmtree(tmp)

    def test_named_schemas_exist_and_safety_rules_present(self):
        for name in UPSTREAM:
            with self.subTest(agent=name):
                _, body = parse(AGENTS / f"{name}.md")
                for sch in re.findall(r"schemas/([\w.-]+)", body):
                    self.assertTrue((ROOT / "schemas" / sch).exists(), sch)
                self.assertRegex(body, r"داده(‌اند| است)، نه دستور")
                self.assertRegex(body, r"نساز|ساخته نمی‌شود")
                self.assertNotIn("Bash", body)
                self.assertIn("hook خطا داد", body, "قاعده‌ی حداکثر یک اصلاح")

    def test_agents_stay_lean(self):
        limits = {"writer": 6000}
        for name in UPSTREAM:
            self.assertLess(len((AGENTS / f"{name}.md").read_bytes()), limits.get(name, 4800), name)

    def test_writer_rules_carry_the_schema_and_cost_benefit_vocabulary(self):
        """واژگان و enumهای نویسنده از schema و کارت می‌آید؛ اگر schema عوض شود و نویسنده ناهم‌خوان بماند، این آزمون می‌گیرد."""
        _, body = parse(AGENTS / "writer.md")
        s = common.load_json(ROOT / "schemas" / "document.schema.json")["$defs"]
        for t in s["cb_benefit"]["properties"]["type"]["enum"][:3]:
            self.assertIn(t, body)
        for v in s["block_ref"]["properties"]["variant"]["enum"]:
            self.assertIn(f"variant: {v}", body)
        for s3 in ("low", "base", "high"):
            self.assertIn(s3, body)
        self.assertIn("context/document_format.md", body)
        card = common.load_card("proposal")
        self.assertIn(card["banned_effects"] and "context/writing_rules.md", body)
        rev = common.load_json(ROOT / "schemas" / "revision.schema.json")
        for field in rev["required"]:
            self.assertIn(field if field != "addressed" else "addressed", body)

    def test_intake_agent_handles_every_gap_kind_of_the_schema(self):
        _, body = parse(AGENTS / "intake-analyst.md")
        kinds = common.load_json(ROOT / "schemas" / "gaps.schema.json")["properties"]["gaps"]["items"]["properties"]["kind"]["enum"]
        for k in kinds:
            self.assertIn(k, body)
        for imp in ("price", "scope", "commitment", "timeline", "security", "none"):
            self.assertIn(imp, body)
        self.assertIn("۵", body)  # سقف سؤال


class ConformanceTest(unittest.TestCase):
    """گزارش داورِ سالم (fixture) باید از اعتبارسنج واقعی بگذرد؛ همان چیزی که hook توقف ایجنت اجرا می‌کند."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        fx = ROOT / "tests" / "fixtures"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), "new-eval", "proposal", str(fx / "document.good.json"),
                            "--claims", str(fx / "claims.good.json")], env=self.env, capture_output=True, text=True, check=True)
        self.run_dir = pathlib.Path(r.stdout.strip())
        subprocess.run([sys.executable, str(ROOT / "scripts" / "render.py"), "--doc", str(fx / "document.good.json"),
                        "--claims", str(fx / "claims.good.json"), "-o", str(self.run_dir / "document.v1.md")], check=True, capture_output=True)
        (self.run_dir / "judges" / "v1").mkdir(parents=True)
        for short in ("rubric", "claims", "veto"):
            shutil.copyfile(fx / "judges" / f"{short}.good.json", self.run_dir / "judges" / "v1" / f"{short}.json")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def validate(self, stage):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py"), "--run", str(self.run_dir), "--stage", stage],
                              env=self.env, capture_output=True, text=True)

    def test_good_reports_pass_every_judge_stage(self):
        for stage in ("judge-rubric", "judge-claims", "judge-veto"):
            r = self.validate(stage)
            self.assertEqual(r.returncode, 0, f"{stage}: {r.stderr}")

    def test_stop_hook_blocks_once_with_the_error_list_then_releases(self):
        (self.run_dir.parent / ".current").write_text(self.run_dir.name, encoding="utf-8")
        p = self.run_dir / "judges" / "v1" / "claims.json"
        rep = json.loads(p.read_text(encoding="utf-8"))
        rep["claims"][0]["quote"] = "جمله‌ای که هرگز در سند نبوده"
        p.write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(ROOT / "scripts" / "validate.py"), "--hook", "--stage", "judge-claims"]
        first = subprocess.run(cmd, env=self.env, input="{}", capture_output=True, text=True)
        out = json.loads(first.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("فقط یک فرصت", out["reason"])
        second = subprocess.run(cmd, env=self.env, input="{}", capture_output=True, text=True)
        self.assertEqual(second.stdout.strip(), "", "بار دوم دیگر برنمی‌گرداند؛ ارکستریتور خطا را می‌بیند")

    def test_the_failure_modes_the_prompts_warn_about_are_really_rejected(self):
        p = self.run_dir / "judges" / "v1"
        rep = json.loads((p / "rubric.json").read_text(encoding="utf-8"))
        rep["criteria"][0]["evidence"][0]["quote"] = "این جمله هرگز در سند نبوده است"
        (p / "rubric.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        r = self.validate("judge-rubric")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("evidence", r.stderr)
        rep = json.loads((p / "claims.json").read_text(encoding="utf-8"))
        rep["summary"]["supported"] = 5
        (p / "claims.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        self.assertNotEqual(self.validate("judge-claims").returncode, 0)
        rep = json.loads((p / "veto.json").read_text(encoding="utf-8"))
        rep["checked"] = ["V01"]
        (p / "veto.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        r = self.validate("judge-veto")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("V02", r.stderr)


if __name__ == "__main__":
    unittest.main()
