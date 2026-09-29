<div dir="rtl">

# brand/ — لایه‌ی برند

سندها از طرف یک برند نوشته می‌شوند. این پوشه هویت آن برند را نگه می‌دارد: صدا، واژه‌های مجاز و ممنوع،
فراخوان عمل، شواهد (proof) با وضعیت اعتبار، پکیج‌ها و قواعد بصری.

| مسیر | چیست |
|---|---|
| `sources/brand-guide-v2.docx` | برند گاید جامع مهدیار هوش‌افزا، نسخه ۲.۰، تیر ۱۴۰۴ (منبع اصلی) |
| `sources/brand-guide-v2.md` | متن همان docx برای خواندن ایجنت‌ها؛ با `scripts/docx_to_md.py` ساخته می‌شود و دستی ویرایش نمی‌شود |
| `sources/design-system-v2.md` | Mahdiyar Refined Minimal AI Design System، نسخه ۲.۰ |
| `<brand_id>.json` | کارت برند: نسخه‌ی ساخت‌یافته و قابل‌چک همین منابع (فعلاً `mahdiyar.json`، پیش‌فرض) |

**تقدم منابع** (تصمیم کاربر، ۲۹ سپتامبر ۲۰۲۶): برای قواعد بصری Design System V2 مقدم است. برند گاید «نور تیره» و
«اجتناب از فضاهای بسیار روشن» می‌گوید، اما V2 عمداً Light-first است. در قواعد کلامی، فهرست واژه‌های ممنوع V2
شامل کل فهرست برند گاید است و سه مورد بیشتر دارد.

**برند تازه:** یک فایل `<brand_id>.json` مطابق `schemas/brand.schema.json` و منابعش در `sources/`؛ در فرم ورودی
فیلد `brand` را تنظیم کنید.

**به‌روزرسانی برند گاید:** docx تازه را جایگزین کنید و بعد
`python3 scripts/docx_to_md.py brand/sources/brand-guide-v2.docx > brand/sources/brand-guide-v2.md`.
آزمون `tests/test_brand.py` هم‌خوانی این دو را چک می‌کند.

</div>
