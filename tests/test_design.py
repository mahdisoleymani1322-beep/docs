"""آزمون DESIGN.md (DS3).

چرا: DESIGN.md منبع توکن‌های خروجی طراحی‌شده است. اگر رنگ یا اندازه‌ای بی‌منبع وارد آن شود، یا جفت متن و
پس‌زمینه‌ای کنتراست کافی نداشته باشد، همه‌ی سندهای خروجی آن خطا را به ارث می‌برند.
بازه‌های زیر عیناً از منبع کپی شده‌اند (شماره‌ی بخش کنار هرکدام)، نه از خود DESIGN.md.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import design_tokens  # noqa: E402
from design_tokens import contrast  # noqa: E402

# (کمینه، بیشینه) هر نقش
SOURCE_SIZES = {
    # راهنمای پرپوزال فصل ۸: متن ۱۱ تا ۱۳ پوینت، تیتر ۱۸ تا ۲۴؛ V2 بخش ۱۵ (Presentation) برای caption و metadata
    "doc-title": (18, 24), "doc-h1": (18, 24), "doc-h2": (18, 24), "doc-number": (18, 24),
    "doc-body": (11, 13), "doc-body-strong": (11, 13), "doc-table": (11, 13),
    "doc-caption": (10, 13), "doc-metadata": (9, 12),
    # V2 بخش ۱۵، Presentation / Large Visual (pt)
    "slide-hero": (44, 72), "slide-number": (84, 160), "slide-h1": (34, 48), "slide-h2": (26, 34),
    "slide-body": (15, 18), "slide-caption": (10, 13), "slide-metadata": (9, 12),
    # V2 بخش ۱۵، Web / Digital (px)
    "web-h1": (44, 64), "web-h2": (32, 44), "web-h3": (24, 32), "web-body": (16, 18),
    "web-small": (14, 14), "web-metadata": (12, 12),
}
# V2 بخش ۱۶، Persian
LINE_HEIGHT = {"heading": (1.25, 1.45), "body": (1.7, 2.0), "caption": (1.6, 1.8)}
# V2 بخش ۱۹
SPACING = {"xs": 4, "s": 8, "m": 16, "l": 24, "xl": 32, "2xl": 48, "3xl": 64, "4xl": 96, "5xl": 128}
# V2 بخش ۲۳: 0 برای editorial، 4 برای UI فنی، 8 بیشینه
ROUNDED = {0, 4, 8}


def line_height_role(name: str) -> str:
    if name.endswith(("caption", "metadata")):
        return "caption"
    if name.endswith(("body", "body-strong", "table", "small")):
        return "body"
    return "heading"


def is_large(typo: dict) -> bool:
    """WCAG: متن درشت = ≥ ۱۸pt، یا ≥ ۱۴pt با وزن bold (۱pt = ۴/۳ px)."""
    m = re.fullmatch(r"([0-9.]+)(pt|px)", typo["fontSize"])
    pt = float(m.group(1)) * (0.75 if m.group(2) == "px" else 1)
    return pt >= 18 or (pt >= 14 and typo.get("fontWeight", 400) >= 700)


class DesignTokensTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = design_tokens.load()

    def test_structure(self):
        for key in ("version", "name", "description", "colors", "typography", "rounded", "spacing", "components"):
            self.assertIn(key, self.t)

    def test_colors_come_from_brand_card(self):
        card = {c["hex"].upper() for c in common.load_json(ROOT / "brand" / "mahdiyar.json")["design"]["colors"]}
        for name, hexv in self.t["colors"].items():
            self.assertRegex(hexv, r"^#[0-9A-F]{6}$", name)
            self.assertIn(hexv, card, f"رنگ {name} در کارت برند (V2) نیست")

    def test_type_sizes_within_source(self):
        self.assertTrue(set(SOURCE_SIZES) <= set(self.t["typography"]), "نقشی از مقیاس جا افتاده")
        for name, typo in self.t["typography"].items():
            if name.startswith("en-"):
                continue
            with self.subTest(name=name):
                self.assertIn(name, SOURCE_SIZES, "اندازه‌ای بدون بازه‌ی منبع")
                unit = "px" if name.startswith("web-") else "pt"
                m = re.fullmatch(r"([0-9]+)" + unit, typo["fontSize"])
                self.assertIsNotNone(m, typo["fontSize"])
                lo, hi = SOURCE_SIZES[name]
                self.assertTrue(lo <= int(m.group(1)) <= hi, f"{typo['fontSize']} بیرون از {lo}–{hi}")
                lo, hi = LINE_HEIGHT[line_height_role(name)]
                self.assertTrue(lo <= typo["lineHeight"] <= hi, f"lineHeight {typo['lineHeight']}")
                self.assertTrue(typo["fontFamily"].startswith("Vazirmatn"))

    def test_spacing_and_rounded(self):
        self.assertEqual(self.t["spacing"], SPACING)
        self.assertLessEqual(set(self.t["rounded"].values()), ROUNDED)

    def test_component_refs_resolve(self):
        for comp, props in self.t["components"].items():
            for prop, value in props.items():
                with self.subTest(component=comp, prop=prop):
                    design_tokens.resolve(self.t, value)  # ارجاع ناموجود KeyError می‌دهد

    def test_component_contrast(self):
        """هر جزء متنی ≥ ۴٫۵؛ جزء «فقط متن درشت» ≥ ۳ و تایپوگرافی‌اش واقعاً درشت."""
        for comp, props in self.t["components"].items():
            if "textColor" not in props:
                continue
            with self.subTest(component=comp):
                fg = design_tokens.resolve(self.t, props["textColor"])
                bg = design_tokens.resolve(self.t, props["backgroundColor"])
                ratio = contrast(fg, bg)
                if props.get("largeTextOnly"):
                    self.assertTrue(is_large(design_tokens.resolve(self.t, props["typography"])))
                    self.assertGreaterEqual(ratio, 3)
                else:
                    self.assertGreaterEqual(ratio, 4.5, f"{fg} روی {bg}: {ratio:.2f}")

    def test_css_variables(self):
        css = design_tokens.css_variables(self.t)
        self.assertIn("--mh-color-ink: #051939;", css)
        self.assertIn("--mh-space-2xl: 48px;", css)


class DesignProseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
        cls.t = design_tokens.parse_front_matter(cls.text)

    def test_contrast_table_matches_computation(self):
        """جدول کنتراست متن دستی است؛ هر عدد و هر ✗ آن باید با محاسبه یکی باشد."""
        section = self.text.split("### کنتراست", 1)[1].split("\n\n", 2)[1]
        rows = [r for r in section.splitlines() if r.startswith("|")]
        header = [c.strip() for c in rows[0].strip("|").split("|")][1:]
        checked = 0
        for row in rows[2:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            fg = self.t["colors"][cells[0].split()[0]]
            for bg_name, cell in zip(header, cells[1:]):
                if cell == "—":
                    continue
                value = float(re.search(r"[0-9]+\.[0-9]+", cell).group())
                ratio = contrast(fg, self.t["colors"][bg_name])
                with self.subTest(fg=cells[0], bg=bg_name):
                    self.assertAlmostEqual(value, ratio, delta=0.01)
                    self.assertEqual("✗" in cell, ratio < 4.5)
                checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_sections_follow_reference_format(self):
        for h in ("## Overview", "## Colors", "## Typography", "## Layout", "## Elevation", "## Shapes",
                  "## Components", "## Do's and Don'ts", "## Responsive", "## Iteration Guide", "## Known Gaps"):
            self.assertRegex(self.text, r"(?m)^" + re.escape(h), h)
        self.assertTrue((ROOT / "brand" / "sources" / "references" / "DESIGN-apple.md").exists())


class ParserTest(unittest.TestCase):
    def test_hash_inside_quotes_is_value(self):
        t = design_tokens.parse_front_matter('---\na:\n  b: "#FFFFFF"   # توضیح\n  c: 4 # x\n---\n')
        self.assertEqual(t, {"a": {"b": "#FFFFFF", "c": 4}})

    def test_list_rejected(self):
        with self.assertRaises(ValueError):
            design_tokens.parse_front_matter("---\na:\n  - 1\n---\n")

    def test_missing_ref_rejected(self):
        with self.assertRaises(KeyError):
            design_tokens.resolve({"colors": {}}, "{colors.gold}")


if __name__ == "__main__":
    unittest.main()
