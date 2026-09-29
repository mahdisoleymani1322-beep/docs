<div dir="rtl">

# Handoff — استودیوی اسناد فروش

> این فایل پیش از **هر کامیت و پوش** به‌روز می‌شود (اجبار: `scripts/check_handoff.py` در hook گیت و hook Claude Code).
> هر کس کار را از اینجا برمی‌دارد، اول همین را بخواند. آخرین به‌روزرسانی: DS1، ۲۹ سپتامبر ۲۰۲۶.

## 1) Goal

سیستم مولتی‌ایجنت فارسی که از روی اطلاعات و خواسته‌ی کاربر، **پروپوزال، پیچ‌دک یا کاتالوگ** را از طرف
**مهدیار هوش‌افزا** می‌نویسد، با روبریک راهنماها و Loop مستند تا نمره‌ی بالای ۹ ارزیابی و بازنویسی می‌کند،
و در قالب طراحی‌شده‌ی برند (لوگو، DESIGN.md) و فرمتی که کاربر می‌گوید (PDF، HTML، Word، PowerPoint) تحویل می‌دهد.
هر سند باید **cost-to-benefit** برای مشتری داشته باشد. هیچ ادعای بی‌منبع و هیچ ارسال خودکاری نیست.

## 2) Current state

- **تمام:**
  - فاز A (داک‌ها)، فاز B (قرارداد داده: ۲۲ schema، کارت سه نوع سند، `validate.py`، `run.py`، `slice_guide.py`)
  - C0 (`render.py`)
  - لایه‌ی برند BR1 تا BR4 (منابع، کارت برند مهدیار، `brand.md` در کانتکست، حالت truth در داورها)
- **در حال انجام:** فاز DS، طبق پلن تأییدشده، این ترتیب:
  1. DS1: handoff.md و اجبارش (همین کار)
  2. DS2: لوگو و `brand/LOGO.md`
  3. DS3: `DESIGN.md` مهدیار
  4. DS4: cost-to-benefit اجباری
  5. DS5: خروجی طراحی‌شده (HTML، PDF، سپس DOCX و PPTX)
- **آزمون‌ها:** ۵۷ از ۵۷ پاس پیش از DS1.
- **شاخه:** `claude/epic-newton-vgg5h7`؛ آخرین پوش: BR4.

## 3) Active files

| فایل | نقش در کار جاری |
|---|---|
| `handoff.md` | همین فایل |
| `scripts/check_handoff.py` | چک ساختار و به‌روز بودن handoff |
| `.githooks/pre-commit`، `.githooks/pre-push` | لایه‌ی گیت اجبار |
| `.claude/settings.json` | لایه‌ی Claude Code اجبار (PreToolUse روی Bash) |
| `tests/test_handoff.py` | آزمون ساختار و رد کامیت بدون handoff |
| `ROADMAP.md` | فاز DS و وضعیت هر کار |
| `CLAUDE.md` | قاعده‌ی handoff برای همه‌ی جلسه‌ها |

## 4) Changes made

- DS1: `handoff.md` با شش بخش. `check_handoff.py` با سه حالت (`--structure`، `--staged`، `--push`) و حالت hook.
  hook گیت و hook Claude Code؛ آزمون؛ قاعده در CLAUDE.md.
- پیش از DS1 (خلاصه؛ جزئیات در `git log`):
  - BR4 داک‌ها با برند هم‌خوان شدند.
  - BR3 برند و truth به خط تولید وصل شد.
  - BR2 کارت برند ساخته شد؛ BR1 منابع برند اضافه شد.
  - C0 `render.py` ساخته شد.
  - B1 تا B4 قرارداد داده و ابزارهای P0 ساخته شدند؛ A1 تا A8 داک‌ها.

## 5) Failed attempts

- **استخراج سطح ۰ روبریک (B3):** regex روی «۰ » اول، داخل «۱۰۰ امتیازی» تیتر گیر کرد و سطح ۰ هر سه کارت خراب شد.
  با بازبینی چشمی پیدا شد؛ درمان: لنگر روی «۰ غایب» + آزمون. درس ۷.
- **validate روی داده‌ی بدشکل (BR3):** بعد از افزودن فیلدهای truth، چک متقاطع روی گزارش بدون فیلد KeyError داد.
  درمان: چک متقاطع فقط روی داده‌ی schema-معتبر. درس ۸.
- **حالت فایلِ validate (B4):** نام `document.good.json` به هیچ schema نگاشت نمی‌شد و آزمون شکست خورد.
  درمان: الگوی نام انعطاف‌پذیر + گزینه‌ی `--schema`.
- **لینک شکسته در README (A8):** README به پوشه‌ی هنوزساخته‌نشده‌ی `scripts/` لینک داشت. آزمون داک‌ها گرفت؛ لینک برداشته شد.
- **DS1، نسخه‌ی اول hook:** `git diff HEAD` فایل تازه (untracked) را نمی‌بیند؛ پس اولین کامیت handoff رد می‌شد.
  درمان: `git status --porcelain`.

## 6) Next steps

1. DS2: لوگو در `brand/assets/logo/`، قواعد در `brand/LOGO.md`، `assets.logo` در کارت برند (فعلاً فقط پس‌زمینه‌ی روشن).
2. DS3: `DESIGN.md` در قالب فایل مرجع Apple، با توکن‌های Design System V2 و آزمون کنتراست WCAG.
3. DS4: `data.cost_benefit` در schema، `required_elements` در کارت‌ها، رندر و مستندات.
4. DS5: `render_html.py` و `export.py` (PDF با متن قابل انتخاب از Chromium؛ سپس DOCX و PPTX).
5. بعد از DS: ادامه‌ی فاز C، از C1 (`checks.py`).
- **منتظر کاربر:** نسخه‌های دیگر لوگو (SVG، PNG شفاف، نسخه‌ی تیره یا افقی).

</div>
