"""ابزارهای مشترک اسکریپت‌ها.

چرا یک ماژول مشترک: یکسان‌سازی متن فارسی، یافتن schema و مسیرهای ریپو باید در همه‌ی
اسکریپت‌ها دقیقاً یکی باشد؛ وگرنه validate.py یک نقل‌قول را پیدا می‌کند و checks.py پیدا نمی‌کند.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import re
import sys
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
RUBRICS = ROOT / "rubrics"
GUIDES = ROOT / "guides"
# مسیرهای خروجی با متغیر محیطی قابل‌جابه‌جایی‌اند تا آزمون‌ها در پوشه‌ی موقت اجرا شوند، نه در ریپو
RUNS = pathlib.Path(os.environ.get("STUDIO_RUNS_DIR", ROOT / "runs"))
LESSONS = pathlib.Path(os.environ.get("STUDIO_LESSONS_DIR", ROOT / "lessons"))
FEEDBACK = pathlib.Path(os.environ.get("STUDIO_FEEDBACK_DIR", ROOT / "feedback"))
GOLDEN = ROOT / "evals" / "golden"
CALIBRATION = ROOT / "evals" / "calibration.json"
DOC_TYPES = ("proposal", "pitch", "catalog")
BRANDS = ROOT / "brand"
DEFAULT_BRAND = "mahdiyar"  # تصمیم کاربر: کارت برند قابل‌تعویض، مهدیار پیش‌فرض


# ---------------------------------------------------------------- JSON

def load_json(path: pathlib.Path | str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(data: Any, path: pathlib.Path | str) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # نوشتن در فایل موقت و جابه‌جایی: فایل نیمه‌نوشته هرگز خوانده نمی‌شود
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------- schema

_REGISTRY = None


def _registry():
    """همه‌ی schemaها با $id خودشان ثبت می‌شوند تا $ref بین فایل‌ها (مثل gate → issues) حل شود."""
    global _REGISTRY
    if _REGISTRY is None:
        from referencing import Registry, Resource
        resources = []
        for p in sorted(SCHEMAS.glob("*.schema.json")):
            schema = load_json(p)
            resources.append((schema["$id"], Resource.from_contents(schema)))
        _REGISTRY = Registry().with_resources(resources)
    return _REGISTRY


def schema_errors(data: Any, schema_name: str) -> list[str]:
    """فهرست خطاهای schema به‌صورت «مسیر: پیام»؛ فهرست خالی یعنی معتبر."""
    import jsonschema
    schema = load_json(SCHEMAS / f"{schema_name}.schema.json")
    validator = jsonschema.Draft202012Validator(schema, registry=_registry())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{e.json_path}: {e.message}" for e in errors]


def schema_for_path(path: pathlib.Path) -> str | None:
    """نام schema از روی نام فایل؛ قرارداد نام‌گذاری در docs/۰۱-معماری.md بخش ۳."""
    name = path.name
    parent = path.parent.name
    if parent.startswith("v") and path.parent.parent.name == "judges":
        return {"rubric.json": "judge-rubric", "claims.json": "judge-claims", "veto.json": "judge-veto"}.get(name)
    if path.parent.name == "rubrics" or (path.parent.parent.name == "rubrics"):
        return "banned" if name == "banned.json" else "rubric"
    table = [
        (r"^input\.json$", "input"), (r"^gaps\.json$", "gaps"), (r"^questions\.json$", "questions"),
        (r"^brief\.json$", "brief"), (r"^(.+\.)?claims\.json$", "claims"),
        (r"^(.+\.)?document(\..+)?\.json$", "document"), (r"^revision\.v[0-9]+\.json$", "revision"),
        (r"^checks\.v[0-9]+\.json$", "checks"), (r"^gate\.v[0-9]+\.json$", "gate"),
        (r"^issues\.v[0-9]+\.json$", "issues"), (r"^loop\.json$", "loop"), (r"^run\.json$", "run"),
        (r"^lessons\.proposed\.json$", "lessons-proposed"), (r"^lessons\.json$", "lessons"),
        (r"^labels\.json$", "labels"),
    ]
    for pattern, schema in table:
        if re.match(pattern, name):
            return schema
    return None


# ---------------------------------------------------------------- متن فارسی

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه"})
_LATIN_TO_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ARABIC_TO_PERSIAN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")
_ZW = re.compile("[‌‍‎‏⁦-⁩﻿]")
_TATWEEL = "ـ"


def normalize(text: str) -> str:
    """یکسان‌سازی برای مقایسه، نه برای نمایش.

    نیم‌فاصله و نویسه‌های جهت‌دار ← فاصله، ي/ك عربی ← ی/ک، ارقام ← فارسی، علامت درصد یکسان،
    فاصله‌های پشت‌سرهم ← یکی. هر مقایسه‌ی متن (نقل‌قول داور، عبارت ممنوع) از همین تابع می‌گذرد.
    """
    text = text.translate(_ARABIC_TO_PERSIAN).replace(_TATWEEL, "")
    text = text.translate(_LATIN_TO_PERSIAN_DIGITS).translate(_ARABIC_TO_PERSIAN_DIGITS)
    text = text.replace("%", "٪")
    text = _ZW.sub(" ", text)
    text = re.sub(r"[ \t\r\n]+", " ", text)
    return text.strip()


def strip_markdown(text: str) -> str:
    """نشانه‌های Markdown که داور ممکن است در نقل‌قول نیاورد (ستاره، تیتر، خط جدول) حذف می‌شوند."""
    text = re.sub(r"[*_`#>]+", " ", text)
    text = text.replace("|", " ")
    return text


def quote_in_text(quote: str, text_norm: str) -> bool:
    """آیا نقل‌قول (پس از یکسان‌سازی) در متن یکسان‌شده هست؟"""
    q = normalize(strip_markdown(quote))
    q = q.strip(" .،؛:«»\"'…")
    return bool(q) and q in text_norm


def to_fa_digits(value: Any) -> str:
    return str(value).translate(_LATIN_TO_PERSIAN_DIGITS)


def fa_number(value: float | int | None) -> str:
    """۱۵۰۰۰۰۰۰۰ ← «۱۵۰٬۰۰۰٬۰۰۰»؛ None ← «[نامعلوم]»."""
    if value is None:
        return "[نامعلوم]"
    if float(value).is_integer():
        s = f"{int(value):,}"
    else:
        s = f"{value:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "٬").replace(".", "٫").translate(_LATIN_TO_PERSIAN_DIGITS)


# ---------------------------------------------------------------- کارت نوع سند

def load_card(doc_type: str) -> dict:
    if doc_type not in DOC_TYPES:
        raise SystemExit(f"نوع سند ناشناخته: {doc_type} (مجاز: {', '.join(DOC_TYPES)})")
    return load_json(RUBRICS / f"{doc_type}.json")


def load_brand(brand_id: str | None = None) -> dict:
    brand_id = brand_id or DEFAULT_BRAND
    path = BRANDS / f"{brand_id}.json"
    if not path.exists():
        raise SystemExit(f"کارت برند پیدا نشد: {path}")
    return load_json(path)


def load_banned() -> dict:
    return load_json(RUBRICS / "banned.json")


# ---------------------------------------------------------------- اجرا

def current_run() -> pathlib.Path | None:
    marker = RUNS / ".current"
    if not marker.exists():
        return None
    run_dir = RUNS / marker.read_text(encoding="utf-8").strip()
    return run_dir if run_dir.is_dir() else None


def resolve_run(arg: str | None) -> pathlib.Path:
    """«current» یا نبودِ آرگومان ← اجرای جاری؛ وگرنه مسیر یا شناسه‌ی اجرا."""
    if not arg or arg == "current":
        run = current_run()
        if run is None:
            raise SystemExit("اجرای جاری وجود ندارد (runs/.current).")
        return run
    p = pathlib.Path(arg)
    if not p.is_absolute():
        p = (ROOT / arg) if (ROOT / arg).exists() else (RUNS / arg)
    if not p.is_dir():
        raise SystemExit(f"پوشه‌ی اجرا پیدا نشد: {arg}")
    return p


def fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def iter_text_fields(obj: Any, path: str = "") -> Iterable[tuple[str, str]]:
    """همه‌ی رشته‌های یک ساختار JSON با مسیرشان؛ برای چک‌هایی که کل متن سند را می‌گردند."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_text_fields(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_text_fields(v, f"{path}[{i}]")
