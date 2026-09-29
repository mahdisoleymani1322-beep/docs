"""توصیف فشرده‌ی schema سند برای نویسنده (context/document_format.md) و فهرست بخش‌های کارت (context/sections.md).

چرا تولیدشده از schema و کارت: نویسنده schema را نمی‌خواند (docs/۰۲ بخش ۲) ولی باید JSON معتبر بنویسد. متنِ دستیِ «شکل سند» دیر یا زود با schema
ناهم‌خوان می‌شود؛ این‌جا هر فیلد، الزام، الگو و مقدار مجاز عیناً از خود schema می‌آید و آزمون هم‌خوانی را می‌سنجد.
"""
from __future__ import annotations

import common

MAIN = ("meta", "section", "block_para", "block_list", "block_table", "block_callout", "block_ref", "proposal_data")


def type_of(prop: dict, defs: dict) -> str:
    if "$ref" in prop:
        name = prop["$ref"].rsplit("/", 1)[-1]
        return {"text": "متن غیرخالی", "text_or_null": "متن یا null"}.get(name, f"شیء «{name}»")
    if "enum" in prop:
        return "یکی از " + " | ".join(f"`{v}`" for v in prop["enum"])
    if "const" in prop:
        return f"ثابت `{prop['const']}`"
    t = prop.get("type")
    if t == "object" and prop.get("properties"):
        inner = "، ".join(f"`{k}`" + ("" if k in prop.get("required", []) else "؟") + f": {type_of(v, defs)}" for k, v in prop["properties"].items())
        return f"شیء با {inner}"
    if t == "array":
        return "فهرست از " + type_of(prop.get("items", {}), defs)
    if isinstance(t, list):
        t = " یا ".join("null" if x == "null" else x for x in t)
    extra = f"، الگو `{prop['pattern']}`" if "pattern" in prop else ""
    if "minimum" in prop:
        extra += f"، حداقل {prop['minimum']}"
    return f"{t or 'هر مقدار'}{extra}"


def describe(name: str, schema: dict, defs: dict) -> list[str]:
    req = set(schema.get("required", []))
    L = [f"### {name}", ""]
    if schema.get("description"):
        L += [schema["description"], ""]
    for key, prop in schema.get("properties", {}).items():
        note = f" — {prop['description']}" if isinstance(prop, dict) and prop.get("description") else ""
        L.append(f"- `{key}`{' (الزامی)' if key in req else ''}: {type_of(prop, defs)}{note}")
    return L + [""]


def referenced(schema: dict, defs: dict, seen: list[str]) -> None:
    for prop in schema.get("properties", {}).values():
        for node in (prop, prop.get("items", {}) if isinstance(prop, dict) else {}):
            ref = node.get("$ref", "") if isinstance(node, dict) else ""
            name = ref.rsplit("/", 1)[-1]
            if name in defs and name not in seen and name not in ("text", "text_or_null") and name not in MAIN:
                seen.append(name)
                referenced(defs[name], defs, seen)


def document_format_md() -> str:
    s = common.load_json(common.SCHEMAS / "document.schema.json")
    defs = s["$defs"]
    L = ["# شکل `document.v<n>.json` (تولیدشده از `schemas/document.schema.json`)", "",
         "همه‌ی فیلدهای «الزامی» باید باشند و هیچ فیلد دیگری مجاز نیست. مقدارِ نامعلوم `null` است، نه صفر و نه متن ساختگی.", "",
         "## سطح بالا", ""]
    top = describe("سند", {k: v for k, v in s.items() if k in ("properties", "required")}, defs)
    L += top[2:]
    for name in MAIN:
        L += describe(name, defs[name], defs)
    seen: list[str] = []
    referenced(defs["proposal_data"], defs, seen)
    L += ["## جدول‌های `data`", ""]
    for name in seen:
        L += describe(name, defs[name], defs)
    return "\n".join(L)


def sections_md(card: dict) -> str:
    L = [f"# بخش‌های «{card['title']}» (از `rubrics/{card['doc_type']}.json`)", "",
         "شناسه و عنوان هر بخش را **عیناً** همین‌ها بنویس؛ کد هر انحرافی را رد می‌کند.", "",
         "| شناسه | عنوان | الزامی | ردیف‌های روبریک که آن را می‌سنجند |", "|---|---|---|---|"]
    for sec in card["sections"]:
        rows = "، ".join(c["id"] for c in card["criteria"] if sec["id"] in c["sections"]) or "—"
        L.append(f"| {sec['id']} | {sec['title']} | {'بله' if sec['required'] else 'خیر'} | {rows} |")
    lw = card["length_words"]
    return "\n".join(L + ["", f"بودجه‌ی طول پیشنهادی راهنما: {common.to_fa_digits(lw['min'])} تا {common.to_fa_digits(lw['max'])} کلمه (فقط هشدار).", ""])
