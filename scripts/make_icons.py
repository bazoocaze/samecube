#!/usr/bin/env python3
"""Render the PWA icons from the game's own palette.

    uv run python scripts/make_icons.py        # needs Pillow

Deterministic (fixed seed + fixed pattern), so re-running produces the same files.
Writes icons/icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png.

The drawing is a 3x3x3 block of mini-cubes in isometric projection, using the same
palette and face shading as the game (top 1.00, left 0.86, right 0.72).
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "icons"

PALETTE = ["#e8434f", "#45c86a", "#3f7ee6", "#f2b8d0", "#eef2f6", "#f7a13b"]
SHADE = {"top": 1.00, "left": 0.86, "right": 0.72}
BG = "#0b1220"

N = 3            # 3x3x3 mini-cubes
GAP = 0.16       # fraction of each cell left as a seam
SEED = 20260101

# Fixed colour pattern (readable at 192 px): one value per mini-cube, keyed by (i,j,k).
def color_for(i, j, k):
    h = (SEED + i * 7 + j * 13 + k * 29 + (i * j + j * k + i * k) * 5) % len(PALETTE)
    return PALETTE[h]

COS30, SIN30 = math.cos(math.radians(30)), math.sin(math.radians(30))

def proj(i, j, k):
    """Isometric screen point for a grid corner (x right, y down in image space)."""
    return ((i - j) * COS30, (i + j) * SIN30 - k)

def faces_for(i, j, k):
    """The three faces of a mini-cube that point towards the viewer, outer shell only
    (drawing the inner ones would show them through the seams)."""
    out = {}
    if k == N - 1:
        out["top"] = [(i, j, k + 1), (i + 1, j, k + 1), (i + 1, j + 1, k + 1), (i, j + 1, k + 1)]
    if j == N - 1:
        out["left"] = [(i, j + 1, k), (i + 1, j + 1, k), (i + 1, j + 1, k + 1), (i, j + 1, k + 1)]
    if i == N - 1:
        out["right"] = [(i + 1, j, k), (i + 1, j + 1, k), (i + 1, j + 1, k + 1), (i + 1, j, k + 1)]
    return out

def tint(hexcolor, shade):
    r, g, b = (int(hexcolor[s:s + 2], 16) for s in (1, 3, 5))
    return tuple(min(255, int(v * shade)) for v in (r, g, b))

def render(size, maskable=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable:
        d.rectangle([0, 0, size - 1, size - 1], fill=BG)          # full bleed
        safe = size * 0.80                                        # content inside the safe zone
    else:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.18), fill=BG)
        safe = size * 0.70

    pts = [proj(i, j, k) for i in range(N + 1) for j in range(N + 1) for k in range(N + 1)]
    minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
    scale = safe / max(maxx - minx, maxy - miny)
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2

    def screen(p):
        return (size / 2 + (p[0] - cx) * scale, size / 2 + (p[1] - cy) * scale)

    for depth in range(3 * N):                       # far mini-cubes first
        for i in range(N):
            for j in range(N):
                for k in range(N):
                    if i + j + k != depth:
                        continue
                    c = color_for(i, j, k)
                    for name, quad0 in faces_for(i, j, k).items():
                        quad = [screen(proj(*p)) for p in quad0]
                        gx = sum(p[0] for p in quad) / 4
                        gy = sum(p[1] for p in quad) / 4
                        f = 1 - GAP
                        quad = [(gx + (p[0] - gx) * f, gy + (p[1] - gy) * f) for p in quad]
                        d.polygon(quad, fill=tint(c, SHADE[name]))
    return img

def main():
    OUT.mkdir(exist_ok=True)
    big = render(512)
    big.save(OUT / "icon-512.png")
    big.resize((192, 192), Image.LANCZOS).save(OUT / "icon-192.png")
    big.resize((180, 180), Image.LANCZOS).save(OUT / "apple-touch-icon.png")
    render(512, maskable=True).save(OUT / "icon-maskable-512.png")
    print(f"wrote {OUT}")

if __name__ == "__main__":
    main()
