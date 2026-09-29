"""آزمون لایه‌ی برند (BR).

چرا: کارت برند نسخه‌ی ساخت‌یافته‌ی منابع برند است؛ اگر از منبع جدا شود، سیستم با قواعدی می‌نویسد که
برند تأییدشان نکرده.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import docx_to_md  # noqa: E402

SRC = ROOT / "brand" / "sources"


class BrandSourcesTest(unittest.TestCase):
    def test_extracted_markdown_matches_docx(self):
        """md همیشه خروجی دقیق docx است؛ کسی نباید md را دستی ویرایش کند."""
        expected = docx_to_md.convert(str(SRC / "brand-guide-v2.docx"))
        self.assertEqual((SRC / "brand-guide-v2.md").read_text(encoding="utf-8"), expected)

    def test_truth_skill_installed(self):
        skill = (ROOT / ".claude" / "skills" / "truth" / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: "))
        self.assertIn("The bottom line", skill)


class BrandCardTest(unittest.TestCase):
    def setUp(self):
        self.card = common.load_json(ROOT / "brand" / "mahdiyar.json")
        self.ds = (SRC / "design-system-v2.md").read_text(encoding="utf-8")
        self.bg = (SRC / "brand-guide-v2.md").read_text(encoding="utf-8")

    def ds_section(self, title):
        i = self.ds.index("\n# " + title)
        return self.ds[i: self.ds.find("\n# ", i + 1)]

    def test_schema_and_default(self):
        self.assertEqual(common.schema_errors(self.card, "brand"), [])
        self.assertEqual(common.DEFAULT_BRAND, self.card["id"])

    def test_words_verbatim(self):
        approved = self.ds_section("102. Approved Words")
        forbidden = self.ds_section("103. Forbidden Words")
        for w in self.card["approved_words"]:
            self.assertIn(f"- {w}\n", approved)
        for f in self.card["forbidden_words"]:
            self.assertIn(f"- {f['text']}\n", forbidden)
            self.assertEqual(f["pattern"].replace("\\", ""), common.normalize(f["text"]).rstrip("!").strip())
        self.assertEqual(len(self.card["forbidden_words"]), forbidden.count("\n- "))

    def test_cta_rules_colors_verbatim(self):
        cta = self.ds_section("106. CTA Language")
        for x in self.card["cta"]["preferred"] + self.card["cta"]["avoid"]:
            self.assertIn(f"- {x}\n", cta)
        for r in self.card["copy_rules"]:
            self.assertIn(f"- {r}\n", self.ds_section("104. Copywriting Rules"))
        for c in self.card["design"]["colors"]:
            self.assertIn(f"| `{c['token']}` | {c['name']} | `{c['hex']}` |", self.ds)
        for r in self.card["design"]["rules"]:
            self.assertIn(r.strip("*"), self.ds.replace("**", ""))

    def test_brand_guide_texts_verbatim(self):
        for key in ("positioning", "usp", "one_liner_fa"):
            self.assertIn(self.card[key], self.bg, key)
        for v in self.card["voice"]:
            self.assertIn(v["do"], self.bg)
            self.assertIn(v["dont"], self.bg)
        for p in self.card["proof"]:
            self.assertIn(p["source_quote"], self.bg, p["id"])
        for k in self.card["packages"]:
            self.assertIn(k["source_quote"], self.bg, k["id"])
            self.assertTrue(k["needs_confirmation"], "قیمت‌های تیر ۱۴۰۴ بدون تأیید تازه استفاده نمی‌شوند")

    def test_unverified_proof_is_marked(self):
        """هیچ ادعای برند «تأییدشده» نیست تا وقتی شاهد مستقل ثبت شود (قاعده‌ی حقیقت CLAUDE.md)."""
        for p in self.card["proof"]:
            self.assertEqual(p["status"], "self_reported", p["id"])
            if p["kind"] in ("client", "result"):
                self.assertEqual(p["publish_permission"], "unknown", p["id"])


if __name__ == "__main__":
    unittest.main()
