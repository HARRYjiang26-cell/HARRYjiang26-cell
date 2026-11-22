#!/usr/bin/env python3
"""Turn a square avatar into a terminal-style ASCII portrait.

Usage:
    python ascii_avatar.py avatar.png --cols 44 --out avatar.txt
    python ascii_avatar.py avatar.png --cols 44 --ansi   # coloured escape output

Rendering model: each character cell is sampled as an average of the source
pixels it covers, then mapped through a luminance ramp.  Because a terminal
cell is roughly twice as tall as it is wide, the row count is derived with a
0.5 aspect factor so the portrait does not come out stretched.
"""

from __future__ import annotations

import argparse
import sys

from PIL import Image

RAMP = " .:-=+*#%@"
# 256-colour cube -> truecolour escape gives the closest match without a palette.
ANSI_RESET = "\033[0m"


def load(path: str, size: int):
    img = Image.open(path).convert("RGBA")
    # Flatten onto white so transparency does not read as bright ink.
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")
    return img.resize((size, size), Image.LANCZOS)


def to_ascii(img, cols: int, rows: int, invert: bool, contrast: float):
    """Return (luminance, rgb) grids on a cols x rows grid."""
    cell_w = img.width / cols
    cell_h = img.height / rows
    lum, rgb = [], []
    for r in range(rows):
        lum_row, rgb_row = [], []
        for c in range(cols):
            box = (
                int(c * cell_w),
                int(r * cell_h),
                max(int((c + 1) * cell_w), int(c * cell_w) + 1),
                max(int((r + 1) * cell_h), int(r * cell_h) + 1),
            )
            patch = img.crop(box)
            # Average the block; resize to 1x1 is cheaper than a manual loop.
            px = patch.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
            rgb_row.append(px)
            y = (0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]) / 255.0
            if contrast != 1.0:
                y = min(1.0, max(0.0, (y - 0.5) * contrast + 0.5))
            lum_row.append(1.0 - y if invert else y)
        lum.append(lum_row)
        rgb.append(rgb_row)
    return lum, rgb


def render_text(lum) -> str:
    out = []
    for row in lum:
        line = []
        for y in row:
            idx = min(len(RAMP) - 1, max(0, int(y * (len(RAMP) - 1) + 0.5)))
            line.append(RAMP[idx])
        out.append("".join(line).rstrip())
    return "\n".join(out)


def render_ansi(lum, rgb) -> str:
    out = []
    for r, row in enumerate(lum):
        line = []
        for c, y in enumerate(row):
            idx = min(len(RAMP) - 1, max(0, int(y * (len(RAMP) - 1) + 0.5)))
            ch = RAMP[idx]
            pr, pg, pb = rgb[r][c]
            line.append(f"\033[38;2;{pr};{pg};{pb}m{ch}")
        out.append("".join(line) + ANSI_RESET)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--cols", type=int, default=44, help="character columns")
    ap.add_argument("--rows", type=int, default=0, help="rows; 0 = derive from aspect")
    ap.add_argument("--aspect", type=float, default=0.5, help="cell height / width factor")
    ap.add_argument("--invert", action="store_true", help="dark background portrait")
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--ansi", action="store_true", help="emit 24-bit colour escapes")
    ap.add_argument(
        "--json",
        metavar="FILE",
        help="write {cols, rows, cells:[{ch, rgb}]} for coloured_svg.py",
    )
    ap.add_argument("--out", help="write to file instead of stdout")
    args = ap.parse_args()

    rows = args.rows or max(1, int(round(args.cols * args.aspect)))
    img = load(args.image, max(args.cols, rows))
    lum, rgb = to_ascii(img, args.cols, rows, args.invert, args.contrast)
    text = render_ansi(lum, rgb) if args.ansi else render_text(lum)

    if args.json:
        import json

        cells = []
        for r in range(rows):
            line = []
            for c in range(args.cols):
                idx = min(len(RAMP) - 1, max(0, int(lum[r][c] * (len(RAMP) - 1) + 0.5)))
                line.append({"ch": RAMP[idx], "rgb": list(rgb[r][c])})
            cells.append(line)
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"cols": args.cols, "rows": rows, "cells": cells}, fh)
        print(f"wrote {args.json}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
