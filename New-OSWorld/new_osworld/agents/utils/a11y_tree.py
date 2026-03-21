"""Accessibility-tree linearisation and tagging utilities."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

import tiktoken

from new_osworld.logging_setup import get_logger

logger = get_logger("a11y")

# XML namespace URIs (kept generic -- no company-specific branding)
_NS = {
    "ubuntu": {
        "attributes": "https://accessibility.windows.example.org/ns/attributes",
        "state": "https://accessibility.ubuntu.example.org/ns/state",
        "component": "https://accessibility.ubuntu.example.org/ns/component",
        "value": "https://accessibility.ubuntu.example.org/ns/value",
    },
    "windows": {
        "attributes": "https://accessibility.windows.example.org/ns/attributes",
        "state": "https://accessibility.windows.example.org/ns/state",
        "component": "https://accessibility.windows.example.org/ns/component",
        "value": "https://accessibility.windows.example.org/ns/value",
        "class": "https://accessibility.windows.example.org/ns/class",
    },
}


def _ns(platform: str, key: str) -> str:
    """Build a ``{namespace}`` prefix for element attribute lookups."""
    return "{" + _NS[platform][key] + "}"


def linearize_accessibility_tree(
    accessibility_tree: str,
    platform: str = "ubuntu",
) -> str:
    """Convert an AT-SPI XML tree into a tab-separated text table.

    Args:
        accessibility_tree: Raw XML string from the VM server.
        platform: ``"ubuntu"`` or ``"windows"``.

    Returns:
        A multi-line string with one row per interactive element.
    """
    try:
        from new_osworld.agents.utils._heuristic_retrieve import filter_nodes
    except ImportError:
        logger.warning("heuristic_retrieve not available; returning raw tree header.")
        return "tag\tname\ttext\tclass\tdescription\tposition\tsize"

    root = ET.fromstring(accessibility_tree)
    filtered = filter_nodes(root, platform)
    attr_ns = _ns(platform, "attributes")
    comp_ns = _ns(platform, "component")
    val_ns = _ns(platform, "value")
    class_ns = _NS["windows"].get("class", "")

    header = "tag\tname\ttext\tclass\tdescription\tposition (top-left x&y)\tsize (w&h)"
    rows = [header]

    for node in filtered:
        if node.text:
            text = node.text if '"' not in node.text else f'"{node.text.replace(chr(34), chr(34)*2)}"'
        elif (
            platform == "windows"
            and node.get(f"{{{class_ns}}}class", "").endswith("EditWrapper")
            and node.get(f"{val_ns}value")
        ):
            raw = node.get(f"{val_ns}value", "")
            text = raw if '"' not in raw else f'"{raw.replace(chr(34), chr(34)*2)}"'
        else:
            text = '""'

        cls = (
            node.get(f"{attr_ns}class", "")
            if platform == "ubuntu"
            else node.get(f"{{{class_ns}}}class", "")
        )

        rows.append(
            f"{node.tag}\t{node.get('name', '')}\t{text}\t{cls}"
            f"\t{node.get(f'{attr_ns}description', '')}"
            f"\t{node.get(f'{comp_ns}screencoord', '')}"
            f"\t{node.get(f'{comp_ns}size', '')}"
        )

    return "\n".join(rows)


def trim_accessibility_tree(tree_text: str, max_tokens: int) -> str:
    """Truncate a linearised tree to fit within a token budget.

    Args:
        tree_text: The linearised text table.
        max_tokens: Maximum token count (using the GPT-4 tokeniser).

    Returns:
        The (possibly truncated) tree text with a ``[...]`` suffix.
    """
    enc = tiktoken.encoding_for_model("gpt-4")
    tokens = enc.encode(tree_text)
    if len(tokens) <= max_tokens:
        return tree_text
    return enc.decode(tokens[:max_tokens]) + "[...]\n"
