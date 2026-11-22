#!/usr/bin/env python3
"""Render a grid of coloured glyphs into a self-contained SVG.

Each cell becomes its own <tspan> carrying the sampled RGB in a `fill`
attribute. GitHub strips <style> from raw SVG but keeps presentation
attributes, so this is the one way to get true per-character colour there.

Input is JSON produced by ascii_avatar.py --json:
    {"cols": N, "rows": M, "cells": [[{"ch": "x", "rgb": [r,g,b]}, ...], ...]}

    python colored_svg.py avatar.json --out avatar.svg
"""

from __future__ import annotations

import argparse
import json
import xml.sax.saxutils as sx

CELL_W = 9.0          # monospace advance at 15px inline font
LINE_H = 17.0
FONT_SIZE = 15
PAD_X = 20
PAD_Y = 18
MONO = (
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
    "'Liberation Mono', 'Courier New', monospace"
)
BG = "#0d1117"


def build(payload: dict, bg: str) -> str:
    cells = payload["cells"]
    rows = len(cells)
    cols = max((len(r) for r in cells), default=0)
    width = round(cols * CELL_W + PAD_X * 2)
    height = round(rows * LINE_H + PAD_Y * 2)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="coloured ASCII portrait">',
        f'<rect width="{width}" height="{height}" rx="10" fill="{bg}"/>',
        f'<g font-family="{MONO}" font-size="{FONT_SIZE}" xml:space="preserve" '
        'text-anchor="start">',
    ]

    for row_index, row in enumerate(cells):
        y = round(PAD_Y + (row_index + 1) * LINE_H - 4.5, 1)
        runs: list[str] = []
        # Group consecutive cells that share a colour into one tspan to keep
        # the file small without losing per-cell fidelity.
        prev_rgb = None
        chunk: list[str] = []

        def flush() -> None:
            nonlocal chunk, prev_rgb
            if chunk:
                r, g, b = prev_rgb
                runs.append(f'<tspan fill="#{r:02x}{g:02x}{b:02x}">{"".join(chunk)}</tspan>')
                chunk = []

        for cell in row:
            rgb = tuple(cell["rgb"])
            if prev_rgb is not None and rgb != prev_rgb:
                flush()
            prev_rgb = rgb
            chunk.append(sx.escape(cell["ch"]))
        flush()

        if runs:
            out.append(f'<text x="{PAD_X}" y="{y}">' + "".join(runs) + "</text>")

    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("json_file")
    ap.add_argument("--out", default="avatar.svg")
    ap.add_argument("--bg", default=BG)
    args = ap.parse_args()

    with open(args.json_file, encoding="utf-8") as fh:
        payload = json.load(fh)

    svg = build(payload, args.bg)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
