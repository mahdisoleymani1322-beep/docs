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
from design_tokens import contrast  # noqa: E402

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


class LogoTest(unittest.TestCase):
    def setUp(self):
        self.logo = common.load_json(ROOT / "brand" / "mahdiyar.json")["assets"]["logo"]
        self.files = self.logo["files"]

    def test_files_exist_and_match_card(self):
        for f in self.files:
            info = image_info(ROOT / f["path"])
            self.assertEqual((info["w"], info["h"]), (f["width_px"], f["height_px"]), f["path"])
            self.assertTrue(info["alpha"], f"{f['path']}: پس‌زمینه‌ی لوگو شفاف است")
        self.assertTrue((ROOT / self.logo["rules_doc"]).exists())
        on_disk = {p.name for p in (ROOT / "brand" / "assets" / "logo").iterdir()}
        self.assertEqual(on_disk, {pathlib.Path(f["path"]).name for f in self.files}, "فایل بی‌ثبت یا ثبت بی‌فایل")

    def test_every_variant_exists_in_both_polarities(self):
        for variant in ("square", "horizontal", "icon"):
            self.assertEqual({f["on"] for f in self.files if f["variant"] == variant}, {"light", "dark"}, variant)

    def test_backgrounds_match_polarity_and_contrast(self):
        """نسخه‌ی اصلی فقط روی روشن، معکوس فقط روی Deep Navy؛ و مؤلفه‌ی اصلی هر نسخه روی پس‌زمینه‌اش ≥ ۴٫۵ باشد."""
        navy, white = "#051939", "#FDFDFD"
        for f in self.files:
            with self.subTest(f=f["path"]):
                if f["on"] == "light":
                    self.assertNotIn(navy, f["allowed_backgrounds"])
                    for bg in f["allowed_backgrounds"]:
                        self.assertGreaterEqual(contrast(navy, bg), 4.5, bg)
                else:
                    self.assertEqual(f["allowed_backgrounds"], [navy])
                    self.assertGreaterEqual(contrast(white, navy), 4.5)
        self.assertEqual(self.logo["allowed_backgrounds"], [f for f in self.files if f["format"] == "webp"][0]["allowed_backgrounds"])

    def test_reversed_files_are_really_reversed(self):
        """معکوس یعنی جابه‌جایی سرمه‌ای و سفید: بدنه‌ی اصلی سفید شود و سرمه‌ای فقط جزئیات بماند (اندازه‌گیری: سهم سرمه‌ای
        نسخه‌ی معکوس ≈ سهم سفید نسخه‌ی اصلی)؛ وگرنه روی Deep Navy ناپدید می‌شود."""
        from PIL import Image
        import numpy as np
        navy, white = np.array([5, 25, 57]), np.array([253, 253, 253])

        def shares(path):
            a = np.array(Image.open(ROOT / path).convert("RGBA"))
            solid = a[a[..., 3] > 200][:, :3].astype(int)
            return (np.abs(solid - navy).sum(axis=1) < 60).mean(), (np.abs(solid - white).sum(axis=1) < 60).mean()

        by_key = {(f["variant"], f["on"]): f["path"] for f in self.files if f["format"] == "png"}
        for variant in ("square", "horizontal", "icon"):
            with self.subTest(variant=variant):
                n_light, w_light = shares(by_key[(variant, "light")])
                n_dark, w_dark = shares(by_key[(variant, "dark")])
                self.assertGreater(n_light, 0.5, "نسخه‌ی اصلی بدنه‌ی سرمه‌ای دارد")
                self.assertLess(n_dark, 0.1, "نسخه‌ی معکوس بدنه‌ی سرمه‌ای ندارد")
                self.assertGreater(w_dark, 0.3, "نسخه‌ی معکوس بدنه‌ی سفید دارد")
                self.assertAlmostEqual(n_dark, w_light, delta=0.03, msg="جابه‌جایی متقارن")

    def test_min_size_keeps_smallest_details_legible(self):
        """حداقل هر نسخه از اندازه‌گیری خود فایل: «HOOSH AFZA» ≥ ۱٫۵mm و ≥ ۸px؛ باریک‌ترین خط نماد ≥ ۰٫۱۵mm."""
        # ارتفاع «HOOSH AFZA» به‌عنوان سهم از عرض فایل؛ اندازه‌گیری‌شده (scripts/make_logo_variants.py): مربع ۵۲/۱۲۵۴،
        # افقی ۱۳۰/۳۳۹۹ (شامل خط‌های دو طرفش، پس محافظه‌کارانه)
        text_ratio = {"square": 52 / 1254, "horizontal": 130 / 3399}
        icon_stroke_ratio = 12 / 755  # باریک‌ترین خط نماد (باز کردن ریخت‌شناختی با هسته‌ی ۱۳px هنوز ۹۸٪ را نگه می‌دارد)
        for f in self.files:
            with self.subTest(f=f["path"]):
                if f["variant"] in text_ratio:
                    r = text_ratio[f["variant"]]
                    self.assertGreaterEqual(f["min_width_mm"] * r, 1.49)
                    self.assertGreaterEqual(f["min_width_px"] * r, 8)
                else:
                    self.assertGreaterEqual(f["min_width_mm"] * icon_stroke_ratio, 0.15)
                    self.assertGreaterEqual(f["min_width_px"] * icon_stroke_ratio, 1)
        self.assertEqual((self.logo["min_width_mm"], self.logo["min_width_px"]), (36, 200))

    def test_no_unverified_svg(self):
        """ردیابی خودکار SVG حروف را خراب کرد؛ SVG بی‌تأیید نباید وارد ریپو شود."""
        self.assertEqual(list((ROOT / "brand" / "assets" / "logo").glob("*.svg")), [])
        self.assertTrue(any("SVG" in v for v in self.logo["missing_versions"]))


if __name__ == "__main__":
    unittest.main()
