#!/usr/bin/env python3
"""Static sanity checks for the generated portrait SVG.

These assertions exist because a silent rendering bug shipped once: the
generator set `xml:space="preserve"` only on the ancestor <g>, Chrome does not
inherit it there, every leading space collapsed and the portrait was shifted
into a smear. A renderer that does inherit it (resvg) hid the bug, so the check
has to be structural rather than a diff against a rasterised preview.

    python check_svg.py avatar.svg
"""

from __future__ import annotations

import sys

from lxml import etree

SVG_NS = "http://www.w3.org/2000/svg"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def fail(message: str) -> None:
    print(f"FAIL: {message}")


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else "avatar.svg"
    problems: list[str] = []

    try:
        tree = etree.parse(path)
    except etree.XMLSyntaxError as exc:
        print(f"FAIL: {path} is not well-formed XML: {exc}")
        print("RESULT FAIL")
        return 1

    root = tree.getroot()
    viewbox = root.get("viewBox", "")
    parts = viewbox.split()
    width = float(parts[2]) if len(parts) == 4 else 0.0

    texts = root.findall(f".//{{{SVG_NS}}}text")
    if not texts:
        problems.append("no <text> elements found")

    # 1. every line carries its own xml:space, otherwise leading spaces collapse
    missing = [i for i, t in enumerate(texts) if t.get(f"{{{XML_NS}}}space") != "preserve"]
    if missing:
        problems.append(
            f"{len(missing)} <text> element(s) lack xml:space=\"preserve\" "
            f"(rows {missing[:5]}{'...' if len(missing) > 5 else ''})"
        )

    # 2. no line may be positioned outside the canvas
    for index, node in enumerate(texts):
        x = float(node.get("x", "0"))
        if x < 0:
            problems.append(f"row {index} has negative x={x}")

    # 3. character counts must agree with the declared canvas width
    counts = [len("".join(node.itertext())) for node in texts]
    widest = max(counts) if counts else 0
    if width and widest:
        # Cheapest useful upper bound: a monospace glyph is close to 0.6em, and
        # the canvas is padded, so a canvas narrower than 0.5 * count is a sign
        # the viewBox was computed from the wrong column count.
        if width < widest * 0.5:
            problems.append(
                f"viewBox width {width:.0f} looks too small for {widest} columns"
            )

    # 4. stray markup that would break the XML on a future edit
    raw = open(path, encoding="utf-8").read()
    if "<text" in raw and "xml:space" not in raw:
        problems.append("no xml:space attribute anywhere in the document")

    if problems:
        for problem in problems:
            fail(problem)
        print("RESULT FAIL")
        return 1

    print(f"rows={len(texts)} widest={widest} cols viewBoxWidth={width:.0f}")
    print("RESULT PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
