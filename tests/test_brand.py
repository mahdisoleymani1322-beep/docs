"""آزمون لایه‌ی برند (BR).

چرا: کارت برند نسخه‌ی ساخت‌یافته‌ی منابع برند است؛ اگر از منبع جدا شود، سیستم با قواعدی می‌نویسد که
برند تأییدشان نکرده.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
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


if __name__ == "__main__":
    unittest.main()
