"""آزمون E1 تا E4: خروجیِ «ایده‌آل» هر ایجنت بالادستی باید از اعتبارسنج واقعی همان مرحله بگذرد.

چرا: دستور هر ایجنت (`.claude/agents/`) و چک‌های کد (`validate.py`) دو نسخه از یک قرارداد هستند. اگر یکی عوض شود و دیگری نه، ایجنتِ واقعی
همیشه یک بار رد می‌شود. این‌جا ایجنت را با کدِ «آنچه دستور می‌گوید» شبیه‌سازی می‌کنیم (بدون مدل) و با validate.py می‌سنجیم؛
رفتار واقعی مدل در E7 سنجیده می‌شود. درس ۱۳: داده‌ی نمونه‌ای که ایجنت باید تولید کند باید از همان اعتبارسنج ایجنت واقعی بگذرد.
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
import common  # noqa: E402
import docformat  # noqa: E402
import run as runmod  # noqa: E402
import validate  # noqa: E402

FX = ROOT / "tests" / "fixtures"


class UpstreamPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.env = dict(os.environ, STUDIO_RUNS_DIR=str(self.tmp / "runs"))
        os.environ["STUDIO_RUNS_DIR"] = self.env["STUDIO_RUNS_DIR"]
        common.RUNS = pathlib.Path(self.env["STUDIO_RUNS_DIR"])
        form = json.loads(subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), "template", "proposal"], env=self.env,
                                         capture_output=True, text=True, check=True).stdout)
        form["sample"] = True
        form["fields"].update(client_identity="شرکت نمونه‌ی آلفا (مشتری نمونه)", proposal_kind="فروش", current_state="بازبینی دستی پیش‌نویس‌ها",
                              discovery_notes="مدیر فروش در جلسه‌ی کشف گفت بازبینی دستی گلوگاه است")
        (self.tmp / "input.json").write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), "new", "proposal", str(self.tmp / "input.json")],
                           env=self.env, capture_output=True, text=True, check=True)
        self.run_dir = pathlib.Path(r.stdout.strip())
        self.card = common.load_card("proposal")

    def tearDown(self):
        shutil.rmtree(self.tmp)
        os.environ.pop("STUDIO_RUNS_DIR", None)

    def stage(self, name):
        return validate.validate_stage(self.run_dir, name)

    def ideal_intake(self):
        """آنچه دستور intake-analyst می‌گوید: برای هر کلید missing یک gap؛ blocking فقط برای مسدودکننده‌ها؛ حداکثر ۵ سؤال."""
        state = runmod.intake_state(self.run_dir)
        gaps = [{"id": f"G-{i:02d}", "field": k, "kind": "missing", "detail": f"فیلد «{k}» خالی است", "impact": "none",
                 "blocking": k in state["blocking_missing"]} for i, k in enumerate(state["missing"], 1)]
        questions = [{"id": f"Q-{i:02d}", "gap": g["id"], "text": f"مقدار «{g['field']}» چیست؟", "why": "برای پر کردن جای خالی سند", "blocking": g["blocking"]}
                     for i, g in enumerate(gaps[:5], 1)]
        common.dump_json({"gaps": gaps}, self.run_dir / "gaps.json")
        common.dump_json({"questions": questions}, self.run_dir / "questions.json")
        return state

    def ideal_brief(self):
        gaps = [g["id"] for g in common.load_json(self.run_dir / "gaps.json")["gaps"]]
        secs = [{"id": s["id"], "title": s["title"], "purpose": "این بخش تصمیم را ممکن می‌کند", "must_include": ["جای خالی صریح با [نامعلوم]"],
                 "inputs": ["client_identity"], "gaps": gaps[:1]} for s in self.card["sections"]]
        lw = self.card["length_words"]
        brief = {"doc_type": "proposal", "variant": "sales", "audience": {"decision_maker": "مدیر فروش", "readers": []},
                 "decision_sought": "تأیید دامنه‌ی پایلوت", "key_message": "پایلوت محدود با معیار پذیرش روشن",
                 "sections": secs, "length_budget": {"min_words": lw["min"], "max_words": lw["max"]}, "out_of_scope": ["اتصال CRM"]}
        common.dump_json(brief, self.run_dir / "brief.json")

    def test_ideal_outputs_pass_every_upstream_stage(self):
        state = self.ideal_intake()
        self.assertEqual(state["blocking_missing"], [], "فیلدهای مسدودکننده در فرم پر شده‌اند")
        self.assertEqual(self.stage("intake"), [])
        self.ideal_brief()
        self.assertEqual(self.stage("brief"), [])
        shutil.copyfile(FX / "claims.good.json", self.run_dir / "claims.json")
        self.assertEqual(self.stage("claims"), [])
        runmod.set_run(self.run_dir, stage="write", round_=1)
        shutil.copyfile(FX / "document.good.json", self.run_dir / "document.v1.json")
        common.dump_json({"version": 1, "base_version": None, "addressed": [], "not_addressed": [], "summary": "دور اول"}, self.run_dir / "revision.v1.json")
        self.assertEqual(self.stage("write"), [])

    def test_fixture_document_follows_the_card_sections_exactly(self):
        doc = common.load_json(FX / "document.good.json")
        self.assertEqual([(s["id"], s["title"]) for s in doc["sections"]], [(s["id"], s["title"]) for s in self.card["sections"]])

    def test_hidden_gap_and_wrong_titles_are_rejected(self):
        self.ideal_intake()
        gaps = common.load_json(self.run_dir / "gaps.json")
        gaps["gaps"] = gaps["gaps"][1:]
        common.dump_json(gaps, self.run_dir / "gaps.json")
        self.assertTrue(any("پنهان" in e for e in self.stage("intake")))
        self.ideal_intake()
        self.ideal_brief()
        brief = common.load_json(self.run_dir / "brief.json")
        brief["sections"][0]["title"] = "عنوان دلخواه"
        common.dump_json(brief, self.run_dir / "brief.json")
        self.assertTrue(any("باید «مشخصات و کنترل نسخه» باشد" in e for e in self.stage("brief")))


class ContextFilesTest(unittest.TestCase):
    """context/document_format.md و sections.md تولیدشده‌اند؛ باید با schema و کارت هم‌خوان بمانند."""

    def test_document_format_mentions_every_field_and_enum_of_the_schema(self):
        md = docformat.document_format_md()
        s = common.load_json(ROOT / "schemas" / "document.schema.json")
        defs = s["$defs"]
        for name in docformat.MAIN + ("cost_benefit", "cb_cost", "cb_benefit", "cb_scenario", "deliverable", "acceptance", "pricing", "price_item",
                                     "payment", "timeline_step", "metric", "risk", "role", "unknown"):
            self.assertIn(f"### {name}", md, name)
            for key, prop in defs[name].get("properties", {}).items():
                self.assertIn(f"`{key}`", md, f"{name}.{key}")
                for v in prop.get("enum", []):
                    self.assertIn(f"`{v}`", md, f"{name}.{key}={v}")
                if "pattern" in prop:
                    self.assertIn(prop["pattern"], md)
        for key in s["required"]:
            self.assertIn(f"`{key}` (الزامی)", md)

    def test_required_marks_match_the_schema(self):
        md = docformat.document_format_md()
        defs = common.load_json(ROOT / "schemas" / "document.schema.json")["$defs"]
        for key in defs["pricing"]["required"]:
            self.assertIn(f"- `{key}` (الزامی)", md)
        optional = set(defs["pricing"]["properties"]) - set(defs["pricing"]["required"])
        for key in optional:
            self.assertIn(f"- `{key}`:", md)
            self.assertNotIn(f"- `{key}` (الزامی)", md.split("### pricing")[1].split("### price_item")[0])

    def test_sections_md_lists_exact_card_titles_and_rows(self):
        card = common.load_card("proposal")
        md = docformat.sections_md(card)
        for s in card["sections"]:
            self.assertIn(f"| {s['id']} | {s['title']} |", md)
        self.assertIn("R06", md.split("| S09 |")[1].split("\n")[0])

    def test_context_is_created_for_every_run_and_is_lean(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            written = runmod.build_context(tmp, "proposal")
            for f in ("sections.md", "document_format.md"):
                self.assertIn(f, written)
            self.assertLess((tmp / "context" / "document_format.md").stat().st_size, 11000)
            self.assertLess((tmp / "context" / "sections.md").stat().st_size, 2500)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
