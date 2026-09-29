"""آزمون B3: کارت هر نوع سند عیناً با راهنمای خودش می‌خواند.

چرا: روبریک، آستانه و رد فوری «قانون» ارزیابی‌اند. اگر یک حرف با راهنما فرق کند، سیستم با معیاری
قضاوت می‌کند که هیچ‌کس تأییدش نکرده. این آزمون راهنما را مستقل از کارت می‌خواند و مقایسه می‌کند.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402

FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
TYPES = ("proposal", "pitch", "catalog")


def guide_text(card):
    return (ROOT / card["guide"]).read_text(encoding="utf-8").replace("\r", "")


def chapter(text, heading):
    i = text.index(heading + "\n")
    j = text.find("\n## ", i + 1)
    return text[i: j if j != -1 else len(text)]


class RubricCardTest(unittest.TestCase):
    def setUp(self):
        self.cards = {t: common.load_card(t) for t in TYPES}

    def test_schema_valid(self):
        for t, card in self.cards.items():
            with self.subTest(t=t):
                self.assertEqual(common.schema_errors(card, "rubric"), [])
                self.assertEqual(card["doc_type"], t)

    def test_weights_and_rows_match_guide_table(self):
        for t, card in self.cards.items():
            with self.subTest(t=t):
                text = guide_text(card)
                sec = chapter(text, card["slices"]["rubric_text"])
                rows = [(m.group(1), int(m.group(2).translate(FA)))
                        for m in re.finditer(r"^\| (.+?) \| ([۰-۹]+) \|$", sec, re.M)]
                self.assertEqual([(c["title"], c["weight"]) for c in card["criteria"]], rows)
                self.assertEqual(sum(c["weight"] for c in card["criteria"]), 100)
                total = re.search(r"^\| \*\*جمع\*\* \| \*\*([۰-۹]+)\*\* \|$", sec, re.M)
                self.assertEqual(int(total.group(1).translate(FA)), 100)

    def test_scale_verbatim(self):
        for t, card in self.cards.items():
            with self.subTest(t=t):
                self.assertIn(card["scale_source"], guide_text(card))
                parts = card["scale_source"].split("؛ ")
                self.assertEqual(len(parts), 5)
                for i, part in enumerate(parts):
                    digit, level = part.split(" ", 1)
                    self.assertEqual(int(digit.translate(FA)), i)
                    self.assertEqual(card["scale"][str(i)], level)
                    self.assertNotIn("\n", level, "سطح روبریک نباید تیتر را با خود آورده باشد (درس ۷)")

    def test_gate_verbatim_and_numbers(self):
        for t, card in self.cards.items():
            with self.subTest(t=t):
                src = card["gate_source"]
                self.assertIn(src, guide_text(card))
                nums = [int(n.translate(FA)) for n in re.findall(r"[۰-۹]+", src)]
                self.assertIn(int(card["gate"]["min_total"]), nums)
                self.assertIn(card["gate"]["min_row"], nums)
                if card["gate"]["critical"]:
                    self.assertIn(card["gate"]["critical"]["min"], nums)

    def test_only_proposal_has_critical_rows(self):
        """درس ۳: فقط راهنمای پرپوزال «حداقل ۳ در دامنه، پذیرش و قیمت» دارد."""
        self.assertIsNotNone(self.cards["proposal"]["gate"]["critical"])
        titles = {c["id"]: c["title"] for c in self.cards["proposal"]["criteria"]}
        crit = [titles[i] for i in self.cards["proposal"]["gate"]["critical"]["criteria"]]
        self.assertEqual(crit, ["دامنه و تحویل‌دادنی", "پذیرش و مدیریت تغییر", "قیمت و شرایط تجاری"])
        self.assertIsNone(self.cards["pitch"]["gate"]["critical"])
        self.assertIsNone(self.cards["catalog"]["gate"]["critical"])

    def test_veto_verbatim_and_complete(self):
        for t, card in self.cards.items():
            with self.subTest(t=t):
                src = card["veto_source"]
                self.assertIn(src, guide_text(card))
                rest = src.split(": ", 1)[1].rstrip(".")
                for v in card["veto"]:
                    self.assertIn(v["text"], rest)
                    rest = rest.replace(v["text"], "", 1)
                leftover = re.sub(r"[،\s]|(?<![^\s،])یا(?![^\s،])", "", rest)
                self.assertEqual(leftover, "", f"بخشی از فهرست رد فوری در کارت نیامده: {rest!r}")
                ids = [v["id"] for v in card["veto"]]
                self.assertEqual(ids, [f"V{i:02d}" for i in range(1, len(ids) + 1)])

    def test_intake_fields_match_form(self):
        for t, card in self.cards.items():
            with self.subTest(t=t):
                sec = chapter(guide_text(card), card["slices"]["intake_form"])
                block = sec.split("```text\n", 1)[1].split("```", 1)[0]
                labels = [ln[:-1] if ln.endswith(":") else ln for ln in block.strip("\n").splitlines()]
                self.assertEqual([f["label"] for f in card["intake_fields"]], labels)
                keys = [f["key"] for f in card["intake_fields"]]
                self.assertEqual(len(keys), len(set(keys)), "کلید تکراری")
                for f in card["intake_fields"]:
                    if f.get("required_if"):
                        self.assertIn(f["required_if"]["field"], keys)
                    if f["blocking"]:
                        self.assertTrue(f["required"], f"{f['key']}: مسدودکننده باید الزامی باشد")

    def test_sections_match_architecture(self):
        kinds = {"proposal": "بخش", "pitch": "اسلاید", "catalog": "صفحه"}
        for t, card in self.cards.items():
            with self.subTest(t=t):
                heads = [(int(m.group(1).translate(FA)), m.group(2)) for m in
                         re.finditer(r"^### " + kinds[t] + r" ([۰-۹]+): (.+)$", guide_text(card), re.M)]
                self.assertEqual([(int(s["id"][1:]), s["title"]) for s in card["sections"]], heads)

    def test_slices_exist(self):
        for t, card in self.cards.items():
            for name, heading in card["slices"].items():
                with self.subTest(t=t, slice=name):
                    self.assertRegex(guide_text(card), "(?m)^" + re.escape(heading) + "$")
            with self.subTest(t=t, need="stage slices"):
                needed = {"intake_form", "doc_types", "architecture", "operations", "writing_rules", "evidence_rules", "rubric_text"}
                self.assertEqual(needed - set(card["slices"]), set())

    def test_internal_references(self):
        banned_cats = {p["category"] for p in common.load_banned()["phrases"]}
        for t, card in self.cards.items():
            with self.subTest(t=t):
                crit_ids = {c["id"] for c in card["criteria"]}
                sec_ids = {s["id"] for s in card["sections"]}
                veto_ids = {v["id"] for v in card["veto"]}
                self.assertIn(card["claims_criterion"], crit_ids)
                if card["gate"]["critical"]:
                    self.assertTrue(set(card["gate"]["critical"]["criteria"]) <= crit_ids)
                for c in card["criteria"]:
                    self.assertTrue(set(c["sections"]) <= sec_ids, c["id"])
                # دسته‌های banned.json (از راهنما) + brand_voice (واژه‌های ممنوع کارت برند)
                self.assertEqual(set(card["banned_effects"]), banned_cats | {"brand_voice"})
                for eff in card["banned_effects"].values():
                    self.assertTrue(set(eff.get("veto", [])) <= veto_ids)
                    self.assertTrue({c["criterion"] for c in eff.get("caps", [])} <= crit_ids)
                self.assertGreater(card["loop_target"]["total_gt"], card["gate"]["min_total"])


class BannedTest(unittest.TestCase):
    def setUp(self):
        self.banned = common.load_banned()
        self.proposal_guide = (ROOT / "guides" / "پرپوزال.md").read_text(encoding="utf-8").replace("\r", "")

    def test_schema_and_patterns(self):
        self.assertEqual(common.schema_errors(self.banned, "banned"), [])
        for p in self.banned["phrases"]:
            re.compile(p["pattern"])

    def test_sources_quote_the_guide(self):
        for p in self.banned["phrases"]:
            for quoted in re.findall(r"«([^«»]+)»", p["source"]):
                for piece in quoted.split(" ... "):
                    with self.subTest(id=p["id"], piece=piece):
                        self.assertIn(piece.strip(), self.proposal_guide)

    def test_patterns_are_normalized_form(self):
        """الگو روی متن یکسان‌شده اجرا می‌شود، پس خودش هم باید یکسان‌شده باشد (بدون نیم‌فاصله و ي/ك عربی)."""
        for p in self.banned["phrases"]:
            self.assertNotRegex(p["pattern"], "[‌يك0-9%]", p["id"])

    def test_good_fixture_has_no_affirmative_hits(self):
        doc = common.load_json(ROOT / "tests" / "fixtures" / "document.good.json")
        text = common.normalize(" ".join(s for _, s in common.iter_text_fields(doc)))
        hits = [p["id"] for p in self.banned["phrases"] if re.search(p["pattern"], text)]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
