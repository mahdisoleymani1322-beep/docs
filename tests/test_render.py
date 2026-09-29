"""آزمون C0: رندر قطعی و کامل.

چرا: داورها روی Markdown قضاوت می‌کنند؛ اگر رندر چیزی را جا بیندازد یا دو بار متفاوت بسازد،
نمره‌ها قابل تکرار نیستند.
"""
import copy
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import render  # noqa: E402

DOC = common.load_json(ROOT / "tests" / "fixtures" / "document.good.json")


class RenderTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(render.render(copy.deepcopy(DOC)), render.render(copy.deepcopy(DOC)))

    def test_every_section_and_id_present(self):
        md = render.render(DOC)
        for sec in DOC["sections"]:
            self.assertIn(sec["title"], md)
            self.assertIn(f"<!-- section: {sec['id']} -->", md)
        data = DOC["data"]
        ids = [x["id"] for k in ("deliverables", "acceptance", "timeline", "metrics", "risks", "unknowns") for x in data[k]]
        ids += [x["id"] for x in data["pricing"]["items"]] + [x["id"] for x in data["pricing"]["payments"]]
        for i in ids:
            self.assertIn(i, md, i)

    def test_numbers_are_persian_and_no_python_none(self):
        md = render.render(DOC)
        self.assertIn("۱۵۰٬۰۰۰٬۰۰۰", md)
        self.assertNotIn("None", md)
        self.assertIn("۴۰٪", md)

    def test_null_amount_is_unknown_not_zero(self):
        d = copy.deepcopy(DOC)
        d["data"]["pricing"]["items"][0]["amount"] = None
        d["data"]["pricing"]["totals"]["one_time"] = None
        md = render.render(d)
        self.assertIn("[نامعلوم]", md)

    def test_unreferenced_data_goes_to_appendix(self):
        md = render.render(DOC)  # unknowns در هیچ بلوک ref نیامده
        self.assertIn("## پیوست: جدول‌های تکمیلی", md)
        self.assertIn("U-01", md)

    def test_sample_banner(self):
        self.assertIn("**نمونه:**", render.render(DOC))
        d = copy.deepcopy(DOC)
        d["meta"]["sample"] = False
        self.assertNotIn("**نمونه:**", render.render(d))

    def test_pipe_in_cell_is_escaped(self):
        d = copy.deepcopy(DOC)
        d["data"]["risks"][0]["effect"] = "الف | ب"
        md = render.render(d)
        row = next(l for l in md.splitlines() if l.startswith("| K-01"))
        self.assertIn("الف \\| ب", row)

    def test_claims_appendix(self):
        claims = {"claims": [{"id": "C-01", "text": "بازبینی دستی است", "type": "fact",
                              "source": {"kind": "input", "ref": "discovery_notes", "date": "۱۴۰۵/۰۶/۳۰", "quote": None},
                              "used_in": ["S02"], "limits": "", "impact": "none"}], "searches": []}
        md = render.render(DOC, claims)
        self.assertIn("## پیوست: دفتر ادعا", md)
        self.assertRegex(md, r"\| C-01 \| بازبینی دستی است \| واقعی \| input: discovery_notes")


if __name__ == "__main__":
    unittest.main()
