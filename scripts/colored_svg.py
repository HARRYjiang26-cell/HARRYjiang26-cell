#!/usr/bin/env python3
r"""Render a plain ASCII art file into a self-contained, colour-graded SVG.

Two input modes:
    coloured_svg.py avatar.json            # cells already carry RGB (from ascii_avatar.py)
    coloured_svg.py avatar.txt --text-mode # grade colours from glyph density

In text mode every glyph is ranked by its ink coverage so the portrait keeps
its shading after colour is applied: sparse strokes go dim green, dense blocks
climb to bright cyan, occasional outline glyphs (`/ \ | -`) get a warmer tint.
GitHub strips <style> from raw SVG but keeps presentation attributes, so
colour has to live in per-run `fill` attributes.
"""

from __future__ import annotations

import argparse
import json
import xml.sax.saxutils as sx

CELL_W = 6.6
LINE_H = 12.6
FONT_SIZE = 11
PAD_X = 20
PAD_Y = 16
MONO = (
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
    "'Liberation Mono', 'Courier New', monospace"
)
BG = "#0d1117"

# Ink density per glyph, ordered from light to heavy. Values are 0..1.
DENSITY: dict[str, float] = {
    " ": 0.0, ".": 0.06, "'": 0.08, "`": 0.08, ",": 0.10, '"': 0.12,
    "^": 0.14, ":": 0.16, ";": 0.18, "-": 0.22, "_": 0.24, "~": 0.26,
    "+": 0.32, "=": 0.34, "<": 0.30, ">": 0.30, "(": 0.30, ")": 0.30,
    "{": 0.34, "}": 0.34, "[": 0.36, "]": 0.36, "!": 0.30, "?": 0.32,
    "l": 0.30, "I": 0.32, "i": 0.28, "1": 0.34, "|": 0.34, "/": 0.30,
    "\\": 0.30, "t": 0.36, "f": 0.38, "j": 0.38, "r": 0.40, "x": 0.46,
    "n": 0.48, "u": 0.50, "v": 0.52, "c": 0.56, "z": 0.56, "s": 0.54,
    "a": 0.52, "e": 0.52, "o": 0.54, "y": 0.52, "X": 0.70, "Y": 0.68,
    "U": 0.66, "Z": 0.68, "C": 0.66, "S": 0.64, "O": 0.68, "Q": 0.68,
    "G": 0.66, "0": 0.68, "8": 0.72, "B": 0.68, "R": 0.66, "P": 0.66,
    "D": 0.68, "N": 0.68, "M": 0.72, "W": 0.72, "&": 0.70, "@": 0.84,
    "#": 0.78, "%": 0.72, "$": 0.72, "*": 0.44, "k": 0.52, "h": 0.50,
    "b": 0.52, "d": 0.52, "p": 0.52, "q": 0.52, "g": 0.52,
}

# Low density -> dim teal; mid -> green; high -> blue; outline -> slate.
STOPS = [
    (0.00, (28, 58, 54)),
    (0.18, (60, 120, 96)),
    (0.34, (86, 168, 120)),
    (0.50, (96, 196, 168)),
    (0.66, (92, 176, 232)),
    (0.82, (122, 150, 242)),
    (1.00, (176, 200, 255)),
]


def density(ch: str) -> float:
    if ch in DENSITY:
        return DENSITY[ch]
    if ch.isupper():
        return 0.62
    if ch.isalnum():
        return 0.5
    return 0.3


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def grade(value: float) -> tuple[int, int, int]:
    for (p0, c0), (p1, c1) in zip(STOPS, STOPS[1:]):
        if value <= p1:
            t = 0.0 if p1 == p0 else (value - p0) / (p1 - p0)
            return lerp(c0, c1, max(0.0, min(1.0, t)))
    return STOPS[-1][1]


def rows_from_text(path: str) -> list[list[dict]]:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().replace("\r\n", "\n").split("\n")
    while raw and not raw[0].strip():
        raw.pop(0)
    while raw and not raw[-1].strip():
        raw.pop()
    width = max(len(line) for line in raw)
    cells = []
    for line in raw:
        row = []
        for ch in line.ljust(width):
            d = density(ch)
            row.append({"ch": ch, "rgb": list(grade(d)) if ch != " " else None})
        cells.append(row)
    return cells


def rows_from_json(path: str) -> list[list[dict]]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["cells"]


def build(cells: list[list[dict]], bg: str) -> str:
    rows = len(cells)
    cols = max((len(r) for r in cells), default=0)
    width = round(cols * CELL_W + PAD_X * 2)
    height = round(rows * LINE_H + PAD_Y * 2)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="ASCII portrait">',
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
        f'<g font-family="{MONO}" font-size="{FONT_SIZE}" xml:space="preserve">',
    ]

    for index, row in enumerate(cells):
        y = round(PAD_Y + (index + 1) * LINE_H - 3.5, 1)
        runs: list[str] = []
        prev = "sentinel"
        chunk: list[str] = []

        def flush() -> None:
            nonlocal chunk, prev
            if not chunk:
                return
            if prev is None:
                runs.append(sx.escape("".join(chunk)))
            else:
                r, g, b = prev
                # The run is wrapped in <tspan>, so lone '<' and '&' must be
                # escaped or the document is not well-formed XML.
                body = sx.escape("".join(chunk))
                runs.append(f'<tspan fill="#{r:02x}{g:02x}{b:02x}">{body}</tspan>')
            chunk = []

        for cell in row:
            rgb = tuple(cell["rgb"]) if cell["rgb"] else None
            if rgb != prev:
                flush()
                prev = rgb
            chunk.append(cell["ch"])
        flush()

        line = "".join(runs)
        if line:
            # xml:space must sit on the <text> element itself: Chrome does not
            # inherit it from an ancestor <g>, and without it every leading
            # space collapses, which shifts the whole portrait to the left.
            out.append(
                f'<text x="{PAD_X}" y="{y}" xml:space="preserve">{line}</text>'
            )

    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source")
    ap.add_argument("--out", default="avatar.svg")
    ap.add_argument("--bg", default=BG)
    ap.add_argument(
        "--text-mode",
        action="store_true",
        help="treat the source as plain ASCII and grade colours from glyph density",
    )
    args = ap.parse_args()

    cells = rows_from_text(args.source) if args.text_mode else rows_from_json(args.source)
    svg = build(cells, args.bg)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print(f"wrote {args.out} ({len(cells)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
