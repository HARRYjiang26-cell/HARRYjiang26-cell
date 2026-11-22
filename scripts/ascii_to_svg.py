#!/usr/bin/env python3
"""Render the ASCII portrait into a self-contained SVG.

GitHub strips <style> on raw SVG, so the whole card is built from <text> runs
with an explicit fill per row. Using an SVG instead of a fenced code block means
the portrait keeps its terminal look on both light and dark themes.

    python ascii_to_svg.py avatar.txt --out avatar.svg
"""

from __future__ import annotations

import argparse
import sys
import xml.sax.saxutils as sx

CELL_W = 7.2          # monospace advance at 12px
LINE_H = 14.5
FONT_SIZE = 12
PAD = 18
MONO = (
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
    "'Liberation Mono', 'Courier New', monospace"
)
FG = "#6977cc"        # taken from the avatar's own accent colour
BG = "#0d1117"


def build(rows: list[str]) -> str:
    cols = max((len(r) for r in rows), default=0)
    width = round(cols * CELL_W + PAD * 2)
    height = round(len(rows) * LINE_H + PAD * 2)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="ASCII portrait">',
        f'<rect width="{width}" height="{height}" rx="10" fill="{BG}"/>',
        f'<g font-family="{MONO}" font-size="{FONT_SIZE}" fill="{FG}" '
        'xml:space="preserve" text-anchor="start">',
    ]
    for i, row in enumerate(rows):
        if not row.strip():
            continue
        y = round(PAD + (i + 1) * LINE_H - 3, 1)
        parts.append(f'<text x="{PAD}" y="{y}">{sx.escape(row)}</text>')
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ascii_file")
    ap.add_argument("--out", default="avatar.svg")
    args = ap.parse_args()

    with open(args.ascii_file, encoding="utf-8") as fh:
        rows = fh.read().replace("\r\n", "\n").rstrip("\n").split("\n")

    # Trim the empty margins the sampler leaves around the artwork.
    while rows and not rows[0].strip():
        rows.pop(0)
    while rows and not rows[-1].strip():
        rows.pop()

    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build(rows))
    print(f"wrote {args.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
