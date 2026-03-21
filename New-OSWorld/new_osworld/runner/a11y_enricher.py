"""Accessibility tree enrichment -- ensure every interactive element has coordinates.

The VM's AT-SPI server only attaches ``screencoord`` / ``size`` to elements
that are both ``visible`` and ``showing``.  For SFT data collection we need
coordinates for as many elements as possible.

This module:
  1. Parses the raw XML
  2. Identifies elements with names/text but missing coordinates
  3. Builds a human-readable coordinates table (TSV) for quick lookup
  4. Optionally writes a "clean" XML with only coordinate-bearing elements
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

_NS_CP = "https://accessibility.ubuntu.example.org/ns/component"
_NS_ATTR = "https://accessibility.ubuntu.example.org/ns/attributes"
_NS_ST = "https://accessibility.ubuntu.example.org/ns/state"
_NS_VAL = "https://accessibility.ubuntu.example.org/ns/value"
_NS_CLASS_WIN = "https://accessibility.windows.example.org/ns/class"

_CP_COORD = f"{{{_NS_CP}}}screencoord"
_CP_SIZE = f"{{{_NS_CP}}}size"


def _parse_coord(s: str) -> Optional[Tuple[int, int]]:
    """Parse ``'(123, 456)'`` into ``(123, 456)``."""
    try:
        s = s.strip().strip("()")
        parts = s.split(",")
        return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, IndexError):
        return None


def parse_elements_with_coords(xml_string: str) -> List[Dict[str, Any]]:
    """Extract all elements that have screen coordinates from the XML.

    Returns a list of dicts with keys:
        tag, name, text, x, y, width, height, center_x, center_y
    """
    root = ET.fromstring(xml_string)
    results: List[Dict[str, Any]] = []

    for elem in root.iter():
        coord_str = elem.get(_CP_COORD)
        size_str = elem.get(_CP_SIZE)
        if not coord_str or not size_str:
            continue

        coord = _parse_coord(coord_str)
        size = _parse_coord(size_str)
        if not coord or not size:
            continue

        x, y = coord
        w, h = size

        if w <= 0 or h <= 0:
            continue

        name = elem.get("name", "")
        text = (elem.text or "").strip()
        tag = elem.tag

        results.append({
            "tag": tag,
            "name": name,
            "text": text,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "center_x": x + w // 2,
            "center_y": y + h // 2,
        })

    return results


def build_coordinates_table(xml_string: str) -> str:
    """Build a human-readable TSV table of all elements with coordinates.

    This is the file operators use to find click targets during SFT.

    Format:
        tag  name  text  x  y  width  height  center_x  center_y
    """
    elements = parse_elements_with_coords(xml_string)
    lines = ["tag\tname\ttext\tx\ty\twidth\theight\tcenter_x\tcenter_y"]

    for e in elements:
        name = e["name"].replace("\t", " ").replace("\n", " ")
        text = e["text"].replace("\t", " ").replace("\n", " ")
        if len(text) > 80:
            text = text[:77] + "..."
        lines.append(
            f"{e['tag']}\t{name}\t{text}\t{e['x']}\t{e['y']}"
            f"\t{e['width']}\t{e['height']}\t{e['center_x']}\t{e['center_y']}"
        )

    return "\n".join(lines)


def build_interactive_elements_table(xml_string: str) -> str:
    """Build a focused table of only interactive/clickable elements.

    Filters to buttons, links, text fields, menu items, etc.
    This is the most useful file for SFT operators.
    """
    interactive_tags = {
        "push-button", "toggle-button", "radio-button", "check-box",
        "combo-box", "menu-item", "check-menu-item", "radio-menu-item",
        "link", "text", "entry", "password-text", "spin-button",
        "slider", "scroll-bar", "tab", "page-tab", "tool-bar-button",
        "tree-item", "table-cell", "list-item",
    }

    elements = parse_elements_with_coords(xml_string)
    lines = [
        "# Interactive elements with click coordinates",
        "# Use center_x, center_y for pg.click(center_x, center_y)",
        "",
        "tag\tname\ttext\tcenter_x\tcenter_y\twidth\theight",
    ]

    for e in elements:
        if e["tag"].lower() not in interactive_tags and not e["name"] and not e["text"]:
            continue

        name = e["name"].replace("\t", " ").replace("\n", " ")
        text = e["text"].replace("\t", " ").replace("\n", " ")
        if len(text) > 60:
            text = text[:57] + "..."
        if not name and not text:
            continue

        lines.append(
            f"{e['tag']}\t{name}\t{text}"
            f"\t{e['center_x']}\t{e['center_y']}\t{e['width']}\t{e['height']}"
        )

    return "\n".join(lines)


def save_enriched_a11y(
    xml_string: str,
    result_dir: str,
    step: int,
) -> Dict[str, str]:
    """Save the full XML plus enriched coordinate tables.

    Creates:
      - ``step_N_before.xml``       -- raw accessibility tree XML
      - ``step_N_coords.tsv``       -- all elements with coordinates (TSV)
      - ``step_N_interactive.tsv``   -- interactive elements only (TSV)

    Args:
        xml_string: Raw XML from the VM.
        result_dir: Output directory.
        step: Step number.

    Returns:
        Dict of saved file paths.
    """
    saved = {}

    xml_path = os.path.join(result_dir, f"step_{step}_before.xml")
    with open(xml_path, "w", encoding="utf-8") as fh:
        fh.write(xml_string)
    saved["xml"] = xml_path

    try:
        coords_table = build_coordinates_table(xml_string)
        coords_path = os.path.join(result_dir, f"step_{step}_coords.tsv")
        with open(coords_path, "w", encoding="utf-8") as fh:
            fh.write(coords_table)
        saved["coords"] = coords_path

        elements = parse_elements_with_coords(xml_string)
        saved["element_count"] = len(elements)
    except Exception:
        pass

    try:
        interactive_table = build_interactive_elements_table(xml_string)
        interactive_path = os.path.join(result_dir, f"step_{step}_interactive.tsv")
        with open(interactive_path, "w", encoding="utf-8") as fh:
            fh.write(interactive_table)
        saved["interactive"] = interactive_path
    except Exception:
        pass

    return saved
