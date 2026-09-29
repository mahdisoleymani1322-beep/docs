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


def image_info(path: pathlib.Path) -> dict:
    """ابعاد و آلفا از هدر فایل، بدون Pillow (آزمون نباید وابستگی تازه بیاورد)."""
    data = path.read_bytes()
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and data[12:16] == b"VP8X":
        flags = data[20]
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
        return {"w": w, "h": h, "alpha": bool(flags & 0x10)}
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return {"w": w, "h": h, "alpha": data[25] in (4, 6)}
    raise ValueError(f"قالب ناشناخته: {path}")


def luminance(hex_color: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class LogoTest(unittest.TestCase):
    def setUp(self):
        self.logo = common.load_json(ROOT / "brand" / "mahdiyar.json")["assets"]["logo"]

    def test_files_exist_and_match_card(self):
        for f in self.logo["files"]:
            info = image_info(ROOT / f["path"])
            self.assertEqual((info["w"], info["h"]), (self.logo["canvas_px"],) * 2, f["path"])
            self.assertTrue(info["alpha"], f"{f['path']}: کارت می‌گوید پس‌زمینه شفاف است")
        self.assertTrue((ROOT / self.logo["rules_doc"]).exists())

    def test_backgrounds_only_light_until_reversed_version(self):
        """بخش‌های سرمه‌ای لوگو روی Deep Navy ناپدید می‌شوند؛ تا نسخه‌ی معکوس نیامده، فقط پس‌زمینه‌ی روشن."""
        navy = "#051939"
        for bg in self.logo["allowed_backgrounds"]:
            self.assertGreaterEqual(contrast(navy, bg), 4.5, bg)
        self.assertNotIn(navy, self.logo["allowed_backgrounds"])
        self.assertTrue(any("معکوس" in v for v in self.logo["missing_versions"]))

    def test_min_size_keeps_smallest_text_legible(self):
        """«HOOSH AFZA» ۵۲px از ۱۲۵۴px است؛ در حداقل عرض، ارتفاع حرف ≥ ۱٫۵mm و ≥ ۸px بماند."""
        ratio = 52 / 1254
        self.assertGreaterEqual(self.logo["min_width_mm"] * ratio, 1.49)
        self.assertGreaterEqual(self.logo["min_width_px"] * ratio, 8)


if __name__ == "__main__":
    unittest.main()
