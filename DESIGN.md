---
version: 1.0
name: Mahdiyar-document-design
description: "طراحی سندهای فروش مهدیار هوش‌افزا (پروپوزال، پیچ‌دک، کاتالوگ): آرام، معماری‌وار، اجرایی و داده‌محور. Light-first روی Soft White، متن Deep Navy، تأکید محدود Mahdiyar Teal، بدون سایه و گرادیان، گوشه‌ی تیز، فارسی راست‌به‌چپ با Vazirmatn. قدرت بصری از نظم، فضای خالی و عددِ بزرگِ مستند می‌آید، نه از تزئین."

colors:
  # منبع: brand/sources/design-system-v2.md بخش ۶ و ۷ (همه‌ی hexها عیناً)
  canvas: "#FDFDFD"            # Soft White — پس‌زمینه‌ی اصلی
  canvas-cream: "#F0EBE5"      # Warm Cream — پس‌زمینه‌ی ثانویه، کارت، ردیف یک‌درمیان
  border-sand: "#D9D1C9"       # Soft Sand — خط جداکننده و حاشیه
  surface-teal-light: "#9AD9D5" # Light Teal — سطح تأکید نرم؛ متن روی آن فقط Deep Navy
  ink: "#051939"               # Deep Navy — تیتر و متن اصلی
  body: "#585A5D"              # Charcoal Gray — متن بدنه
  muted: "#8A8988"             # Soft Gray — فقط متن درشت یا غیرضروری (کنتراست ۳٫۴۳)
  primary: "#059B9A"           # Mahdiyar Teal — عنصر فعال، خط، گره، عدد درشت؛ نه متن ریز
  positive: "#147B72"          # Deep Teal — وضعیت مثبت و تأیید
  accent-mid: "#37A09A"        # Medium Teal — نمودار و یک ردیف کلیدی
  dark-surface: "#051939"      # Deep Navy به‌عنوان سطح تیره (حداکثر ۳ تا ۶٪ صفحه)
  on-dark: "#FDFDFD"           # متن روی سطح تیره

typography:
  # فارسی (V2 بخش ۱۴): Vazirmatn، YekanBakh، IRANYekan؛ تیتر 700/600، متن 400/500/600
  # ارتفاع خط فارسی (V2 بخش ۱۶): تیتر ۱٫۲۵ تا ۱٫۴۵، متن ۱٫۷ تا ۲٫۰، کپشن ۱٫۶ تا ۱٫۸
  # سند A4 چاپی: متن ۱۱ تا ۱۳pt و تیتر ۱۸ تا ۲۴pt (guides/پرپوزال.md فصل ۸)
  doc-title:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 24pt
    fontWeight: 700
    lineHeight: 1.35
  doc-h1:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 20pt
    fontWeight: 700
    lineHeight: 1.35
  doc-h2:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 18pt
    fontWeight: 600
    lineHeight: 1.4
  doc-number:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 24pt
    fontWeight: 700
    lineHeight: 1.25
  doc-body:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 12pt
    fontWeight: 400
    lineHeight: 1.8
  doc-body-strong:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 12pt
    fontWeight: 600
    lineHeight: 1.8
  doc-table:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 11pt
    fontWeight: 400
    lineHeight: 1.7
  doc-caption:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 10pt
    fontWeight: 400
    lineHeight: 1.7
  doc-metadata:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 9pt
    fontWeight: 500
    lineHeight: 1.6
  # اسلاید پیچ‌دک (V2 بخش ۱۵، Presentation، pt)
  slide-hero:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 56pt
    fontWeight: 700
    lineHeight: 1.25
  slide-number:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 96pt
    fontWeight: 700
    lineHeight: 1.25
  slide-h1:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 40pt
    fontWeight: 700
    lineHeight: 1.3
  slide-h2:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 28pt
    fontWeight: 600
    lineHeight: 1.35
  slide-body:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 18pt
    fontWeight: 400
    lineHeight: 1.7
  slide-caption:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 12pt
    fontWeight: 400
    lineHeight: 1.6
  slide-metadata:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 10pt
    fontWeight: 500
    lineHeight: 1.6
  # وب و HTML (V2 بخش ۱۵، Web، px)
  web-h1:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.35
  web-h2:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 36px
    fontWeight: 700
    lineHeight: 1.35
  web-h3:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.4
  web-body:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.8
  web-small:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.7
  web-metadata:
    fontFamily: "Vazirmatn, YekanBakh, IRANYekan, sans-serif"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.6
  # انگلیسی داخل متن فارسی (V2 بخش ۱۲ و ۱۳): LTR می‌ماند
  en-heading:
    fontFamily: "Space Grotesk, Helvetica Now, Inter, Arial, sans-serif"
    fontWeight: 700
  en-body:
    fontFamily: "Inter, Helvetica, Arial, sans-serif"
    fontWeight: 400

rounded:
  # V2 بخش ۲۳: ۰ برای ادیتوریال و اسلاید، ۴ برای UI فنی، حداکثر ۸ برای کارت وب
  editorial: 0
  technical: 4
  card: 8

spacing:
  # V2 بخش ۱۹: پایه‌ی ۸؛ «فاصله‌ی بین مفهوم‌ها بیشتر از فاصله‌ی داخل مفهوم»
  xs: 4
  s: 8
  m: 16
  l: 24
  xl: 32
  2xl: 48
  3xl: 64
  4xl: 96
  5xl: 128

layout:
  # V2 بخش ۲۰: شبکه‌ی ۱۲ ستونی؛ حاشیه‌ی امن ۵ تا ۷٪؛ کانتینر وب ۱۲۰۰ تا ۱۴۴۰px
  grid-columns: 12
  safe-area-min: 5
  safe-area-max: 7
  web-container-max: 1440
  border-width: 1

components:
  cover:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-title}"
    rounded: "{rounded.editorial}"
  page-header:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-metadata}"
    borderColor: "{colors.border-sand}"
  section-heading:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-h1}"
  body-text:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.doc-body}"
  table-header:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.on-dark}"
    typography: "{typography.doc-table}"
  table-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.doc-table}"
    borderColor: "{colors.border-sand}"
  table-row-alt:
    backgroundColor: "{colors.canvas-cream}"
    textColor: "{colors.body}"
    typography: "{typography.doc-table}"
  table-row-highlight:
    backgroundColor: "{colors.surface-teal-light}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-table}"
  metric-card:
    backgroundColor: "{colors.canvas-cream}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-number}"
    rounded: "{rounded.editorial}"
  metric-label:
    backgroundColor: "{colors.canvas-cream}"
    textColor: "{colors.body}"
    typography: "{typography.doc-caption}"
  callout:
    backgroundColor: "{colors.canvas-cream}"
    textColor: "{colors.body}"
    typography: "{typography.doc-body}"
    borderColor: "{colors.border-sand}"
    rounded: "{rounded.editorial}"
  cost-benefit-block:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.doc-table}"
    borderColor: "{colors.border-sand}"
  cost-benefit-positive:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.positive}"
    typography: "{typography.doc-body-strong}"
  cost-benefit-caveat:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.doc-caption}"
  claim-ref:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.doc-metadata}"
  unknown-marker:
    backgroundColor: "{colors.surface-teal-light}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-body-strong}"
  sample-banner:
    backgroundColor: "{colors.canvas-cream}"
    textColor: "{colors.ink}"
    typography: "{typography.doc-caption}"
    borderColor: "{colors.border-sand}"
  cta-block:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.on-dark}"
    typography: "{typography.doc-h2}"
    rounded: "{rounded.editorial}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-dark}"
    typography: "{typography.web-body}"
    rounded: "{rounded.technical}"
    height: 44
  text-muted-large:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.muted}"
    typography: "{typography.doc-h2}"
    largeTextOnly: true
---

<div dir="rtl">

## Overview

این فایل زبان طراحی **سندهای خروجی مهدیار هوش‌افزا** است: پروپوزال A4، پیچ‌دک و کاتالوگ، در PDF، HTML، Word و
PowerPoint. ساختار آن از قالب مرجع `brand/sources/references/DESIGN-apple.md` گرفته شده، اما **هیچ مقدار آن از Apple
نیست**. همه‌ی مقادیر از Design System V2 مهدیار (`brand/sources/design-system-v2.md`) یا راهنمای نوع سند آمده است.

شخصیت (V2 بخش ۳ تا ۵):
- Strategic Calm: طراحی فریاد نمی‌زند.
- Intelligent Minimalism: هر عنصر دلیل دارد.
- Execution Over Decoration: جدول، شاخص، برنامه و فرایند، نه تزئین انتزاعی.
- Premium Through Restraint.

سند فروش مهدیار باید مثل گزارش یک شریک اجرایی خوانده شود، نه بروشور تبلیغاتی.

**ویژگی‌های کلیدی:**
- Light-first: حدود ۷۰ تا ۸۲٪ Soft White، ۸ تا ۱۵٪ Warm Cream، Deep Navy فقط ۳ تا ۶٪ و Mahdiyar Teal ۲ تا ۵٪ (V2 بخش ۸).
- بدون سایه، گرادیان و glow (V2 بخش ۲۵). عمق از تغییر سطح (سفید ← کرم ← سرمه‌ای) می‌آید.
- گوشه‌ی تیز: `{rounded.editorial}` = ۰ برای همه‌ی اجزای سند.
- عدد بزرگ ابزار اصلی بصری است (V2 بخش ۱۸)، **فقط وقتی عدد منبع دارد** (CLAUDE.md، قواعد حقیقت).
- فارسی راست‌به‌چپ با Vazirmatn؛ واژه‌ی انگلیسی داخل متن فارسی LTR می‌ماند.
- لوگو فقط در جلد و صفحه‌ی آخر، طبق [`brand/LOGO.md`](brand/LOGO.md).

## Colors

| توکن | hex | نقش | متن روی آن |
|---|---|---|---|
| `{colors.canvas}` | `#FDFDFD` | پس‌زمینه‌ی اصلی | ink، body |
| `{colors.canvas-cream}` | `#F0EBE5` | کارت، callout، ردیف یک‌درمیان | ink، body |
| `{colors.border-sand}` | `#D9D1C9` | خط و حاشیه‌ی ۱px | — |
| `{colors.surface-teal-light}` | `#9AD9D5` | ردیف کلیدی جدول، نشانگر نامعلوم | **فقط ink** |
| `{colors.ink}` | `#051939` | تیتر، متن اصلی، سرستون جدول، CTA | — |
| `{colors.body}` | `#585A5D` | متن بدنه | — |
| `{colors.muted}` | `#8A8988` | فقط متن درشت یا غیرضروری | — |
| `{colors.primary}` | `#059B9A` | گره، خط، عدد درشت، حلقه‌ی focus | — |
| `{colors.positive}` | `#147B72` | منفعت و وضعیت مثبت | — |
| `{colors.accent-mid}` | `#37A09A` | نمودار؛ یک ردیف کلیدی | — |

**نارنجی، طلایی و زرد گرم جزو پالت نیستند** (V2 بخش ۸). قرمز فقط برای خطای واقعی؛ وضعیت مثبت Deep Teal است،
نه سبز (V2 بخش ۵۴).

### کنتراست (WCAG، محاسبه‌شده؛ آزمون `tests/test_design.py` دوباره حساب می‌کند)

| متن \ پس‌زمینه | canvas | canvas-cream | surface-teal-light | dark-surface |
|---|---:|---:|---:|---:|
| ink `#051939` | 17.14 | 14.71 | 11.01 | — |
| body `#585A5D` | 6.80 | 5.84 | **4.37 ✗** | 2.52 ✗ |
| muted `#8A8988` | **3.43 ✗** | 2.95 ✗ | 2.20 ✗ | 4.99 |
| primary `#059B9A` | **3.35 ✗** | 2.88 ✗ | 2.15 ✗ | 5.12 |
| positive `#147B72` | 5.03 | **4.32 ✗** | 3.23 ✗ | 3.41 ✗ |
| on-dark `#FDFDFD` | — | — | — | 17.14 |

✗ یعنی کمتر از ۴٫۵، حداقل WCAG برای متن معمولی (راهنمای پرپوزال فصل ۸). نتیجه‌ها:
- **Soft Gray (`muted`) برای متادیتای ریز مجاز نیست**، با اینکه V2 آن را «Secondary text / metadata» نامیده؛ متادیتا
  `body` است. `muted` فقط برای متن درشت (`{component.text-muted-large}`) یا تزئین غیرضروری.
- **Mahdiyar Teal متن ریز نمی‌شود.** برای عدد درشت، خط، گره و آیکون (کنتراست ≥ ۳ برای عنصر غیرمتنی و متن درشت) مجاز است.
- **روی Light Teal فقط Deep Navy.** Charcoal با ۴٫۳۷ رد است.
- **Deep Teal (مثبت) فقط روی سفید.** روی کرم ۴٫۳۲ است.

## Typography

- **فارسی:** Vazirmatn (جایگزین‌ها YekanBakh، IRANYekan). تیتر 700 و 600، متن 400، تأکید 600؛ بدون فونت تزئینی (V2 بخش ۱۴).
- **انگلیسی:** Space Grotesk برای تیتر، Inter برای متن (V2 بخش ۱۲ و ۱۳). در یک خروجی بیش از دو خانواده‌ی فونت نه (V2 بخش ۱۷).
- **ارتفاع خط فارسی:** تیتر ۱٫۳۵، متن ۱٫۸، کپشن ۱٫۷ (بازه‌های V2 بخش ۱۶). «Persian body text must never feel compressed.»

| مقیاس | توکن‌ها | منبع بازه |
|---|---|---|
| سند A4 (pt) | title 24 · h1 20 · h2 18 · body 12 · table 11 · caption 10 · metadata 9 · number 24 | راهنمای پرپوزال فصل ۸ (متن ۱۱ تا ۱۳، تیتر ۱۸ تا ۲۴)؛ V2 بخش ۱۵ (caption و metadata) |
| اسلاید (pt) | hero 56 · number 96 · h1 40 · h2 28 · body 18 · caption 12 · metadata 10 | V2 بخش ۱۵، Presentation |
| وب (px) | h1 48 · h2 36 · h3 28 · body 17 · small 14 · metadata 12 | V2 بخش ۱۵، Web |

قواعد (V2 بخش ۱۷):
- تیتر کوتاه و قاطع.
- پاراگراف فارسی بلند وسط‌چین نمی‌شود.
- bold فقط برای سلسله‌مراتب.

## Layout

- **شبکه:** ۱۲ ستون؛ فارسی راست‌چین؛ اجزا به لبه‌ی شبکه تراز (V2 بخش ۲۰ و ۲۱).
- **حاشیه‌ی امن:** ۵ تا ۷٪ هر طرف، در A4 و اسلاید.
- **فاصله‌ها:** فقط از `{spacing.*}` (۴ تا ۱۲۸). فاصله‌ی بین مفهوم‌ها بزرگ‌تر از فاصله‌ی داخل مفهوم.
- **فضای خالی ابزار برند است** (V2 بخش ۲۲)؛ جای خالی فقط چون خالی است پر نمی‌شود.
- **سند A4:** جلد (عنوان، مشتری، شناسه، تاریخ، اعتبار، لوگو بالا-راست) ← صفحه‌های داخلی با سربرگ متنی
  «مهدیار / رشد هوشمند» ← صفحه‌ی آخر (گام بعد، تماس، لوگو پایین-راست).
- **اسلاید:** هر اسلاید یک ایده‌ی غالب؛ حداکثر ۱ تیتر، ۱ جمله، ۱ سیستم بصری و ۱ تا ۳ جزئیات (V2 بخش ۹۲).
  چگالی تحلیلی (Level C) برای همه‌ی اسلایدها نه (V2 بخش ۹۳).

## Elevation & Depth

| سطح | رفتار | کاربرد |
|---|---|---|
| تخت | بدون سایه، بدون حاشیه | متن، جلد، بخش‌ها |
| خط ۱px | `{colors.border-sand}` | جدول، callout، بلوک cost-benefit |
| تغییر سطح | canvas ← canvas-cream ← dark-surface | جدا کردن بخش بدون خط |

**سایه: هیچ**. V2 سایه را فقط برای UI شناور وب و پیش‌نمایش داشبورد مجاز می‌داند، و سند فروش هیچ‌کدام نیست.

## Shapes

- `{rounded.editorial}` (۰): همه‌ی اجزای سند و اسلاید.
- `{rounded.technical}` (۴): دکمه و ورودی HTML.
- `{rounded.card}` (۸): حداکثر، فقط کارت وب.
- دایره فقط برای گره داده و timeline (V2 بخش ۲۳). بدون pill همه‌جایی، بدون شکل ارگانیک.

## Components

**سند**
- **`cover`:** Soft White، عنوان `{typography.doc-title}` به رنگ ink، لوگو بالا-راست ۴۵ تا ۵۵mm.
  متادیتا در `{typography.doc-metadata}` به رنگ body: شناسه، ویرایش، تاریخ با تقویم، اعتبار.
- **`page-header`:** نشانگر «مهدیار / رشد هوشمند» و نام سند، خط ۱px Soft Sand زیرش؛ نه لوگو (LOGO.md بخش ۳).
- **`section-heading`:** `{typography.doc-h1}` به رنگ ink. شماره‌ی بخش می‌تواند primary باشد، چون درشت است.
- **`table-*`:** سرستون Deep Navy با متن سفید؛ بدنه سفید با ردیف یک‌درمیان Warm Cream و خط Soft Sand؛
  ردیف کلیدی Light Teal با متن ink، **فقط یک ردیف** (V2 بخش ۵۶). خط شبکه‌ی سنگین ممنوع.
- **`metric-card`:** عدد `{typography.doc-number}` ink، برچسب `{component.metric-label}` body؛ بدون آیکون تزئینی.
  **عدد فقط با ارجاع دفتر ادعا** (V2 بخش ۵۸: «Never invent metrics»).
- **`callout`:** Warm Cream با خط Soft Sand؛ برای فرض، محدودیت و نکته‌ی تصمیم.
- **`cost-benefit-block`:** جدول هزینه در برابر منفعت برای مشتری (الزام کاربر).
  - منفعت در `{component.cost-benefit-positive}` (Deep Teal روی سفید).
  - نوع هر منفعت صریح است: ظرفیت آزادشده، صرفه‌جویی نقدی، درآمد بالقوه، کاهش ریسک، کیفی.
  - سناریوها کم، پایه و زیاد.
  - جمله‌ی «سناریوی مالی، تضمین درآمد نیست» در `{component.cost-benefit-caveat}`.
- **`claim-ref`:** ارجاع `[C-01]` در `{typography.doc-metadata}` به رنگ body. پیوست دفتر ادعا در انتهای سند.
- **`unknown-marker`:** `[نامعلوم: …]` روی Light Teal با متن ink؛ عمداً دیده می‌شود تا مجهول پنهان نماند.
- **`sample-banner`:** برای داده‌ی نمایشی، بالای جلد.
- **`cta-block`:** Deep Navy با متن سفید؛ تیتر کوتاه + یک جمله + اقدام. CTA از فهرست مجاز کارت برند
  (مثل «گفت‌وگو درباره پروژه»). نارنجی یا طلایی هرگز.

**وب و HTML**
- **`button-primary`:** Deep Navy، متن سفید، `{rounded.technical}`، ارتفاع ۴۴ (V2 بخش ۴۴: ۴۴ تا ۵۲).
  focus: حلقه‌ی ۲px `{colors.primary}`.

## RTL / LTR

- فارسی: راست‌چین؛ تیتر روی لبه‌ی راست؛ متادیتا راست یا بالا-راست؛ جریان فرایند راست‌به‌چپ؛
  جهت فلش با منطق خواندن (V2 بخش ۲۹).
- محور نمودار از نظر ریاضی درست می‌ماند و بی‌دلیل آینه نمی‌شود.
- واژه‌ی انگلیسی داخل متن فارسی LTR است (`<bdi>` یا `dir="ltr"`)؛ حرف‌به‌حرف آینه نمی‌شود.
- اعداد فارسی در متن؛ شناسه، کد و نشانی لاتین می‌مانند (راهنمای پرپوزال فصل ۷).

## Do's and Don'ts

**انجام بده**
- ink روی canvas برای هر متن مهم.
- body برای متن بدنه و متادیتا.
- عدد بزرگ + برچسب کوچک، فقط برای عدد مستند.
- یک ایده‌ی غالب در هر صفحه و اسلاید.
- جدول برای دامنه، زمان، قیمت، نقش، پذیرش و cost-benefit (راهنمای پرپوزال فصل ۸).
- هر جزء از `{component.*}`؛ هیچ hex مستقیم.

**انجام نده**
- نارنجی، طلایی، گرادیان سایبری، glow، سایه‌ی کارت.
- teal برای پاراگراف یا متن ریز؛ چند سایه‌ی teal با وزن برابر (V2 بخش ۹).
- `muted` برای متن ریز ضروری (کنتراست ۳٫۴۳).
- قرمز و سبز پیش‌فرض برای وضعیت.
- وضعیت را فقط با رنگ نشان دادن (V2 بخش ۱۰۷).
- لوگو روی Deep Navy، وسط صفحه، بزرگ یا تکراری (LOGO.md).
- واژه‌های ممنوع برند (کارت برند) و عدد ساختگی.

## Responsive & Print

- **PDF:** A4 عمودی (راهنمای پرپوزال فصل ۸). متن باید قابل انتخاب باشد، نه تصویر؛ زبان سند `fa` با ترتیب خواندن درست
  (راهنما فصل ۸، W3C PDF3). ردیف کلیدی جدول بین دو صفحه نمی‌شکند.
- **HTML:** کانتینر حداکثر ۱۴۴۰px؛ حاشیه‌ی موبایل ۲۴ تا ۴۰px (V2 بخش ۲۰)؛ زیر ۷۶۸px جدول‌ها افقی اسکرول می‌خورند،
  نه فشرده.
- **اسلاید:** ۱۶:۹؛ حاشیه‌ی امن ۵ تا ۷٪.

## Iteration Guide

1. هر تغییر روی یک جزء؛ به کلید YAML آن ارجاع بده (مثل `{component.cost-benefit-block}`).
2. hex مستقیم در خروجی‌ساز ممنوع؛ همه از `{colors.*}` از راه `scripts/design_tokens.py`.
3. هر جفت متن و پس‌زمینه‌ی تازه باید آزمون کنتراست را پاس کند (≥ ۴٫۵، یا `largeTextOnly` با ≥ ۳).
4. عدد تازه در مقیاس‌ها فقط داخل بازه‌ی منبع (V2 بخش ۱۵ یا راهنمای نوع سند).
5. در شک: اول فضای خالی و تغییر سطح، بعد خط، و هرگز تزئین.

## Known Gaps

- **لوگو:** فقط lockup مربع رستری؛ SVG، نسخه‌ی معکوس برای سرمه‌ای و نسخه‌ی افقی در راه است (LOGO.md بخش ۸).
  تا آن وقت، سربرگ متنی است و هیچ سطح سرمه‌ای‌ای لوگو ندارد.
- **فونت:** Vazirmatn (چهار وزن ۴۰۰، ۵۰۰، ۶۰۰، ۷۰۰؛ مجوز OFL، از بسته‌ی npm نسخه‌ی ۳۳٫۰٫۳) در `brand/assets/fonts/` است و داخل
  HTML جاسازی می‌شود. Space Grotesk و Inter فایل ندارند؛ متن انگلیسی به Arial برمی‌گردد. فقط وقتی متن انگلیسی نمایشی
  در سند باشد لازم می‌شوند.
- **جابه‌جایی صفحه:** جدول با ۹ ستون یا بیشتر (پذیرش) صفحه‌ی افقی می‌گیرد؛ با ۸ ستون هنوز عمودی خوانا بود (بازبینی چشمی DS5).
  لوگوی پایانی در انتهای بدنه، پیش از پیوست‌ها؛ وگرنه پیوستِ پرِ صفحه آن را تنها به یک صفحه‌ی خالی می‌راند.
- **تناقض داخلی V2:** Soft Gray «metadata» نامیده شده اما برای متن ریز کنتراست کافی ندارد؛ این فایل body را جایگزین کرد.
- **اندازه‌ی عدد در سند A4:** V2 فقط «very large» می‌گوید و مقیاس A4 ندارد؛ ۲۴pt، سقف بازه‌ی تیتر راهنما، انتخاب شد.
- **نمودار:** قواعد V2 بخش ۳۸ تا ۴۲ (برچسب، رنگ معنادار) هنوز جزء نمودار ندارد؛ با اولین نیاز واقعی اضافه می‌شود.

</div>
