#!/usr/bin/env python3
"""ساخت نسخه‌های مشتق لوگو از فایل اصلی (ابزار توسعه؛ نیازمند pillow و numpy، نه وابستگی زمان اجرا).

چرا در ریپو: نسخه‌های مشتق باید قابل‌بازتولید باشند؛ اگر لوگوی اصلی عوض شد، همین اسکریپت همه را دوباره می‌سازد.
نسخه‌ها از روی رستر ساخته می‌شوند، پس «بازسازی» اند، نه فایل طراحِ اصلی؛ SVG ساخته نمی‌شود چون ردیابی خودکار حروف را خراب کرد (brand/LOGO.md بخش ۸).
"""
from __future__ import annotations

import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "brand" / "assets" / "logo"
SRC = D / "mahdiyar-logo-square.png"
NAVY = np.array([5, 25, 57], float)
WHITE = np.array([253, 253, 253], float)
# ردیف‌های بلوک‌ها روی بوم ۱۲۵۴ (اندازه‌گیری‌شده؛ tests/test_brand.py دوباره می‌سنجد)
ICON_ROWS, WORD_ROWS = (65, 925), (959, 1178)


def bbox(a: np.ndarray, r0: int, r1: int) -> tuple[int, int, int, int]:
    m = a[r0:r1, :, 3] > 20
    ys, xs = np.where(m)
    return xs.min(), r0 + ys.min(), xs.max() + 1, r0 + ys.max() + 1


def reversed_colors(im: Image.Image) -> Image.Image:
    """سرمه‌ای و سفید جایشان را عوض می‌کنند، teal ثابت می‌ماند. برای نشستن روی Deep Navy.

    فاصله‌ی هر پیکسل تا خط سرمه‌ای←سفید تعیین می‌کند «خنثی» است یا teal؛ لبه‌های نرم هم وزن پیوسته می‌گیرند.
    """
    a = np.array(im).astype(float)
    rgb = a[..., :3]
    d = WHITE - NAVY
    t = ((rgb - NAVY) @ d / (d @ d))[..., None]
    dist = np.linalg.norm(rgb - (NAVY + t * d), axis=-1)
    w = np.clip(1 - dist / 60, 0, 1)[..., None]
    flipped = NAVY + (1 - np.clip(t, 0, 1)) * d
    a[..., :3] = np.clip(w * flipped + (1 - w) * rgb, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def crop(im: Image.Image, box) -> Image.Image:
    return im.crop(box)


def horizontal(im: Image.Image, a: np.ndarray) -> Image.Image:
    ix0, iy0, ix1, iy1 = bbox(a, *ICON_ROWS)
    wx0, wy0, wx1, wy1 = bbox(a, *WORD_ROWS)
    icon, word = im.crop((ix0, iy0, ix1, iy1)), im.crop((wx0, wy0, wx1, wy1))
    h = icon.height
    ww = int(word.width * (h * 0.62 / word.height))  # متن کنار نماد؛ ارتفاع ~۶۲٪ نماد تا خوانا بماند
    word = word.resize((ww, int(h * 0.62)), Image.LANCZOS)
    gap = int(h * 0.12)
    out = Image.new("RGBA", (icon.width + gap + word.width, h), (0, 0, 0, 0))
    out.alpha_composite(icon, (0, 0))
    out.alpha_composite(word, (icon.width + gap, (h - word.height) // 2))
    return out


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    a = np.array(im)
    ix = bbox(a, *ICON_ROWS)
    icon = im.crop(ix)
    icon.save(D / "mahdiyar-logo-icon.png")
    horizontal(im, a).save(D / "mahdiyar-logo-horizontal.png")
    rev = reversed_colors(im)
    rev.save(D / "mahdiyar-logo-square-reversed.png")
    horizontal(rev, np.array(rev)).save(D / "mahdiyar-logo-horizontal-reversed.png")
    reversed_colors(icon).save(D / "mahdiyar-logo-icon-reversed.png")
    print(*sorted(p.name for p in D.iterdir()), sep="\n")


if __name__ == "__main__":
    main()
