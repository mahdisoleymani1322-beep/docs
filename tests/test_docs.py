"""آزمون سلامت مستندات: لینک‌های نسبی و جدول‌های Markdown.

چرا: README و داک‌ها به فایل‌ها ارجاع می‌دهند؛ لینک شکسته یعنی ادعایی که پشتوانه ندارد.
جدول‌هایی که `|` بی‌گریز داخل کد دارند در GitHub می‌شکنند (درس ۶ در docs/درس‌های-مهندسی.md).
"""
import pathlib
import re
import unittest
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
MD_FILES = sorted(
    p for p in ROOT.rglob("*.md")
    if ".git" not in p.parts and "runs" not in p.parts
)
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
CODE_RE = re.compile(r"`[^`]*`")
# مسیرهایی که عمداً در داک‌ها «هنوز ساخته نشده» علامت خورده‌اند، لینک نمی‌شوند؛
# پس هر لینک نسبی باید واقعاً وجود داشته باشد.


class DocsTest(unittest.TestCase):
    def test_relative_links_exist(self):
        broken = []
        for md in MD_FILES:
            text = md.read_text(encoding="utf-8")
            for target in LINK_RE.findall(text):
                if re.match(r"^[a-z]+://", target) or target.startswith("#") or target.startswith("mailto:"):
                    continue
                path = unquote(target.split("#", 1)[0])
                if not path:
                    continue
                if not (md.parent / path).exists():
                    broken.append(f"{md.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [], "لینک‌های شکسته:\n" + "\n".join(broken))

    def test_no_unescaped_pipe_in_table_code(self):
        bad = []
        for md in MD_FILES:
            for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                if not line.lstrip().startswith("|"):
                    continue
                for span in CODE_RE.findall(line):
                    if re.search(r"(?<!\\)\|", span):
                        bad.append(f"{md.relative_to(ROOT)}:{i} {span}")
        self.assertEqual(bad, [], "| بی‌گریز داخل کد در جدول:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
