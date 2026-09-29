"""آزمون DS5: HTML طراحی‌شده و خروجی PDF.

چرا: خروجی همان چیزی است که مشتری می‌بیند. آزمون‌ها سه چیز را می‌سنجند که با چشم دیر پیدا می‌شوند:
متن HTML با Markdown داورها یکی است، PDF متن قابل‌انتخاب فارسی دارد، و لوگو طبق قواعد LOGO.md جا گرفته.
آزمون‌های PDF بدون Chromium یا pypdf (requirements-dev.txt) رد نمی‌شوند؛ skip می‌شوند و در گزارش پیدا هستند.
"""
import copy
import pathlib
import re
import sys
import tempfile
import unicodedata
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import design_tokens  # noqa: E402
import export  # noqa: E402
import render  # noqa: E402
import render_html  # noqa: E402

DOC = common.load_json(ROOT / "tests" / "fixtures" / "document.good.json")
BRAND = common.load_brand("mahdiyar")


def text_of(html_doc: str) -> str:
    body = re.sub(r"<style>.*?</style>", "", html_doc, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


class InputFormatsTest(unittest.TestCase):
    def test_output_formats_validated(self):
        base = {"doc_type": "proposal", "fields": {}, "attachments": [], "answers": [], "sample": True}
        for ok in (["pdf"], ["md", "html", "pdf", "docx", "pptx"]):
            self.assertEqual(common.schema_errors({**base, "output_formats": ok}, "input"), [], ok)
        self.assertEqual(common.schema_errors(base, "input"), [], "اختیاری است")
        for bad in ([], ["pdf", "pdf"], ["doc"], "pdf"):
            self.assertNotEqual(common.schema_errors({**base, "output_formats": bad}, "input"), [], bad)


class HtmlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = render_html.build(DOC, None, BRAND)

    def test_deterministic(self):
        self.assertEqual(self.html, render_html.build(DOC, None, BRAND))

    def test_rtl_persian_and_self_contained(self):
        self.assertIn('<html lang="fa" dir="rtl">', self.html)
        self.assertNotRegex(self.html, r'(src|href)="https?://')
        self.assertEqual(self.html.count("@font-face"), 4)

    def test_text_matches_markdown_the_judges_saw(self):
        """هر سلول و هر پاراگراف Markdown باید در HTML باشد؛ رندر دوم نباید چیزی را جا بیندازد یا بسازد."""
        md = render.render(DOC)
        squash = lambda t: re.sub(r"\s+", "", t)  # noqa: E731  برچینش تگ‌ها فاصله می‌افزاید؛ محتوا مهم است
        html_text = squash(html_unescape(text_of(self.html)))
        for line in md.splitlines():
            if line.startswith("|") and not re.fullmatch(r"\|(-+\|)+", line):
                for cell in line.strip("|").split("|"):
                    cell = re.sub(r"\*\*|\\", "", cell).strip()
                    if cell:
                        self.assertTrue(squash(cell) in html_text, f"سلول در HTML نیست: {cell}")
            elif line and not line.startswith(("<", "#", "|")):
                plain = re.sub(r"^(- |> |[0-9]+\. )", "", re.sub(r"\*\*", "", line)).strip()
                self.assertTrue(squash(plain) in html_text, f"خط در HTML نیست: {plain}")

    def test_colors_come_only_from_design_md(self):
        allowed = {c.lower() for c in design_tokens.load()["colors"].values()}
        used = {m.lower() for m in re.findall(r"#[0-9A-Fa-f]{6}\b", re.sub(r"data:[^)\"]+", "", self.html))}
        self.assertLessEqual(used, allowed, used - allowed)

    def test_component_classes_are_defined(self):
        """هر کلاس c-* که در HTML به کار رفته باید جزء واقعی DESIGN.md باشد (نه نام ساختگی)."""
        comps = set(design_tokens.load()["components"])
        used = set(re.findall(r'class="c-([a-z-]+)', self.html))
        self.assertLessEqual(used, comps, used - comps)

    def test_logo_rules(self):
        """جلد و انتهای بدنه، هرکدام یک لوگو؛ هر دو ≥ حداقل ۳۶mm؛ هیچ‌جای دیگر (LOGO.md بخش ۶ و ۷)."""
        self.assertEqual(self.html.count("<img"), 2)
        self.assertLess(self.html.index('class="logo"'), self.html.index("</section>"))
        last_section = DOC["sections"][-1]["title"]
        closing = self.html.index('class="closing"')
        self.assertGreater(closing, self.html.index(last_section), "لوگوی پایانی بعد از آخرین بخش بدنه")
        self.assertLess(closing, self.html.index("پیوست: جدول"), "و پیش از پیوست‌ها")
        min_mm = BRAND["assets"]["logo"]["min_width_mm"]
        for mm in re.findall(r"\bwidth: ([0-9.]+)mm", self.html):
            self.assertGreaterEqual(float(mm), min_mm)
        self.assertNotIn("transform", self.html.split("</style>")[0].split("logo")[-1][:200])

    def test_special_components(self):
        self.assertIn('class="c-sample-banner box"', self.html)
        self.assertIn("c-cost-benefit-block", self.html)
        self.assertIn("c-cost-benefit-caveat", self.html)
        self.assertIn('class="c-claim-ref"', self.html)
        d = copy.deepcopy(DOC)
        d["data"]["pricing"]["items"][0]["amount"] = None
        d["data"]["pricing"]["totals"]["one_time"] = None
        self.assertIn('class="c-unknown-marker"', render_html.build(d, None, BRAND))

    def test_id_column_does_not_wrap_but_prose_column_may(self):
        rows = [["شناسه", "شرح"], ["K-01", "متن بلند"], ["K-02", "متن دیگر"]]
        self.assertIn("data-nowrap", render_html.table_html(rows, None))
        rows = [["کار", "مجری"], ["نوشتن گزارش", "تیم"]]
        self.assertNotIn("data-nowrap", render_html.table_html(rows, None))

    def test_only_nine_or_more_columns_go_landscape(self):
        def cols(n):
            return render_html.table_html([[f"c{i}" for i in range(n)], ["x"] * n], None)
        # عدد ثابت، نه ثابت ماژول: ۸ ستون (شاخص‌ها) در A4 عمودی دیده و خوانا بود؛ ۹ ستون (پذیرش) نه
        self.assertNotIn("tbl wide", cols(8))
        self.assertIn("tbl wide", cols(9))

    def test_html_is_escaped(self):
        d = copy.deepcopy(DOC)
        d["sections"][0]["blocks"][0]["text"] = "<script>alert(1)</script> & x"
        out = render_html.build(d, None, BRAND)
        self.assertNotIn("<script>alert", out)
        self.assertIn("&lt;script&gt;", out)


def html_unescape(t: str) -> str:
    import html
    return html.unescape(t)


def _pdf_tools():
    try:
        import pypdf  # noqa: F401
        export.find_chrome()
        return True
    except (ImportError, SystemExit):
        return False


@unittest.skipUnless(_pdf_tools(), "Chromium یا pypdf نیست (pip install -r requirements-dev.txt)")
class PdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pypdf
        cls.tmp = tempfile.TemporaryDirectory()
        files = export.export(DOC, None, BRAND, ["pdf"], pathlib.Path(cls.tmp.name), "doc")
        cls.pdf_path = files[0]
        cls.reader = pypdf.PdfReader(str(cls.pdf_path))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_requested_format_is_left(self):
        self.assertEqual([p.name for p in pathlib.Path(self.tmp.name).iterdir()], ["doc.pdf"])

    def test_page_sizes_a4(self):
        for p in self.reader.pages:
            w, h = sorted((round(float(p.mediabox.width) / 72 * 25.4), round(float(p.mediabox.height) / 72 * 25.4)))
            self.assertEqual((w, h), (210, 297))

    def test_persian_text_is_extractable(self):
        """کروم حروف را به شکل نمایشی (ﻣﺸﺨﺼﺎت) ذخیره می‌کند؛ NFKC آن را به متن قابل‌جست‌وجو برمی‌گرداند."""
        text = "".join(p.extract_text() for p in self.reader.pages)
        norm = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
        for word in ("خلاصهاجرایی", "قیمتوشرایطتجاری", "ظرفیتآزادشده", "پیشنهادپایلوت"):
            self.assertIn(word, norm, word)

    def test_logo_on_cover_and_at_end_only(self):
        pages_with_logo = [i for i, p in enumerate(self.reader.pages) if len(p.images) > 0]
        self.assertEqual(pages_with_logo[0], 0)
        self.assertEqual(len(pages_with_logo), 2, "فقط جلد و انتهای بدنه")
        self.assertLess(pages_with_logo[-1], len(self.reader.pages), "لوگو نباید تنها صفحه‌ی آخر باشد")
        last = self.reader.pages[pages_with_logo[-1]].extract_text()
        self.assertGreater(len(last.strip()), 100, "صفحه‌ی لوگو باید متن هم داشته باشد")

    def test_fonts_embedded(self):
        fonts = set()
        for p in self.reader.pages:
            for f in (p["/Resources"].get("/Font") or {}).values():
                fonts.add(str(f.get_object().get("/BaseFont")))
        self.assertTrue(fonts and all("Vazirmatn" in f for f in fonts), fonts)


class ExportRefusalTest(unittest.TestCase):
    def test_unbuilt_and_unknown_formats_fail_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            for fmt in ("docx", "pptx", "xls"):
                with self.subTest(fmt=fmt), self.assertRaises(SystemExit):
                    export.export(DOC, None, BRAND, ["md", fmt], pathlib.Path(d), "x")
            self.assertEqual(list(pathlib.Path(d).iterdir()), [], "قبل از رد شدن چیزی ساخته نشود")

    def test_md_and_html_without_chrome(self):
        with tempfile.TemporaryDirectory() as d:
            files = export.export(DOC, None, BRAND, ["md", "html"], pathlib.Path(d), "x")
            self.assertEqual(sorted(f.suffix for f in files), [".html", ".md"])


if __name__ == "__main__":
    unittest.main()
