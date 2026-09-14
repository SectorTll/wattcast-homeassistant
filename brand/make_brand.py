#!/usr/bin/env python
"""Generate the Home Assistant brand assets for the wattcast integration.

Mark: a rounded dark tile with five rounded price bars (mint), the peak bar in rose — the Wattcast price-forecast
motif from the site (ground #120f16, accent #7ff0c8, rose #f28bb4). Everything is drawn at 4x and downscaled with
LANCZOS for clean anti-aliasing.

Outputs (home-assistant/brands layout, custom_integrations/wattcast/):
  icon.png       256x256   tile + bars
  icon@2x.png    512x512
  logo.png       <=256 wide   mark + "Wattcast" wordmark, trimmed
  logo@2x.png    <=512 wide
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# HA 2026.3+: custom integrations bundle brand images in custom_components/<domain>/brand/ and they take priority
# over the brands CDN (https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api). No brands-repo PR needed.
OUT = Path(__file__).resolve().parent.parent / "custom_components" / "wattcast" / "brand"
SS = 4  # supersample

GROUND_TOP = (32, 24, 38)     # #201826
GROUND_BOT = (16, 13, 21)     # #100d15
MINT = (127, 240, 200)        # #7ff0c8
ROSE = (242, 139, 180)        # #f28bb4
TEXT = (241, 236, 244)        # #f1ecf4
WORDMARK = (36, 156, 122)     # #249c7a — mid teal, legible on both light and dark backgrounds

# bar heights as a fraction of the usable height, left→right; index 2 is the peak (rose)
BARS = [0.34, 0.60, 1.00, 0.72, 0.46]
PEAK = 2
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def _tile(px: int) -> Image.Image:
    """Rounded square tile with a vertical gradient ground."""
    grad = Image.new("RGB", (1, px))
    for y in range(px):
        t = y / (px - 1)
        grad.putpixel((0, y), tuple(round(GROUND_TOP[i] + (GROUND_BOT[i] - GROUND_TOP[i]) * t) for i in range(3)))
    grad = grad.resize((px, px))
    tile = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    tile.paste(grad, (0, 0), _rounded_mask((px, px), radius=round(px * 0.22)))
    return tile


def _bars(px: int, pad: float = 0.16, gap_frac: float = 0.34, baseline: bool = True) -> Image.Image:
    """Transparent layer of five rounded price bars sized to a px×px area."""
    layer = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    left = px * pad
    right = px * (1 - pad)
    top = px * pad
    bottom = px * (1 - pad)
    n = len(BARS)
    span = right - left
    bw = span / (n + (n - 1) * gap_frac)
    gap = bw * gap_frac
    usable = bottom - top
    r = bw * 0.42
    for i, h in enumerate(BARS):
        x0 = left + i * (bw + gap)
        bh = max(usable * h, bw)   # never shorter than its width
        y0 = bottom - bh
        color = ROSE if i == PEAK else MINT
        d.rounded_rectangle([x0, y0, x0 + bw, bottom], radius=r, fill=color + (255,))
    if baseline:
        by = bottom + bw * 0.5
        d.rounded_rectangle([left, by, right, by + bw * 0.22], radius=bw * 0.11, fill=MINT + (90,))
    return layer


def make_icon(px: int) -> Image.Image:
    s = px * SS
    tile = _tile(s)
    tile.alpha_composite(_bars(s))
    return tile.resize((px, px), Image.LANCZOS)


def make_logo(long_side: int) -> Image.Image:
    """Mark (a tile) + 'Wattcast' wordmark, trimmed, scaled so the longest side == long_side (brands cap)."""
    s = 256 * SS
    img = Image.new("RGBA", (s * 6, s), (0, 0, 0, 0))
    img.alpha_composite(make_icon_hi(s), (0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_BOLD, round(s * 0.52))
    bbox = d.textbbox((0, 0), "Wattcast", font=font)
    ty = round((s - (bbox[3] - bbox[1])) / 2 - bbox[1])
    d.text((round(s * 1.18), ty), "Wattcast", font=font, fill=WORDMARK + (255,))
    img = img.crop(img.getbbox())
    scale = long_side / max(img.size)
    return img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)


def make_icon_hi(s: int) -> Image.Image:
    tile = _tile(s)
    tile.alpha_composite(_bars(s))
    return tile


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_icon(256).save(OUT / "icon.png")
    make_icon(512).save(OUT / "icon@2x.png")
    make_logo(512).save(OUT / "logo@2x.png")   # longest side 512 (brands cap for @2x)
    make_logo(256).save(OUT / "logo.png")       # longest side 256 (brands cap)
    for f in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        im = Image.open(OUT / f)
        print(f, im.size, im.mode)


if __name__ == "__main__":
    main()
