"""Response-parsing utilities -- extract actions from LLM output strings."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_actions_from_string(text: str) -> List[Dict[str, Any]]:
    """Parse JSON action dicts from an LLM response (``computer_13`` mode).

    Looks for JSON blocks inside triple-backtick fences, falling back to
    bare JSON parsing.

    Args:
        text: Raw LLM response text.

    Returns:
        A list of action dicts.

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    stripped = text.strip()
    if stripped in ("WAIT", "DONE", "FAIL"):
        return [stripped]

    actions: List[Dict[str, Any]] = []

    for pattern in (r"```json\s+(.*?)\s+```", r"```\s+(.*?)\s+```"):
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            for m in matches:
                try:
                    actions.append(json.loads(m))
                except json.JSONDecodeError:
                    continue
            if actions:
                return actions

    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse actions from: {text[:200]}")


def _split_semicolons_outside_quotes(s: str) -> List[str]:
    """Split a string on ``;`` but respect Python string literals and comments."""
    parts: List[str] = []
    buf: List[str] = []
    in_single = in_double = False
    in_triple_single = in_triple_double = False
    in_comment = False
    i, n = 0, len(s)

    def flush() -> None:
        chunk = "".join(buf).strip()
        if chunk:
            parts.append(chunk)
        buf.clear()

    while i < n:
        c = s[i]

        if in_comment:
            buf.append(c)
            if c == "\n":
                in_comment = False
            i += 1
            continue

        if in_triple_single:
            if s[i:i+3] == "'''":
                buf.append("'''"); i += 3; in_triple_single = False
            else:
                buf.append(c); i += 1
            continue
        if in_triple_double:
            if s[i:i+3] == '"""':
                buf.append('"""'); i += 3; in_triple_double = False
            else:
                buf.append(c); i += 1
            continue

        if in_single:
            buf.append(c)
            if c == "\\" and i + 1 < n:
                buf.append(s[i + 1]); i += 2
            elif c == "'":
                in_single = False; i += 1
            else:
                i += 1
            continue
        if in_double:
            buf.append(c)
            if c == "\\" and i + 1 < n:
                buf.append(s[i + 1]); i += 2
            elif c == '"':
                in_double = False; i += 1
            else:
                i += 1
            continue

        if s[i:i+3] == "'''":
            buf.append("'''"); i += 3; in_triple_single = True; continue
        if s[i:i+3] == '"""':
            buf.append('"""'); i += 3; in_triple_double = True; continue
        if c == "'":
            in_single = True; buf.append(c); i += 1; continue
        if c == '"':
            in_double = True; buf.append(c); i += 1; continue
        if c == "#":
            in_comment = True; buf.append(c); i += 1; continue
        if c == ";":
            flush(); i += 1; continue

        buf.append(c)
        i += 1

    flush()
    return parts


def parse_code_from_string(text: str) -> List[str]:
    """Extract executable code snippets from an LLM response (``pyautogui`` mode).

    Handles triple-backtick fenced code blocks (with optional language tag)
    and the special ``WAIT``/``DONE``/``FAIL`` tokens.

    Args:
        text: Raw LLM response text.

    Returns:
        A list of code strings and/or special tokens.
    """
    text = "\n".join(_split_semicolons_outside_quotes(text))
    stripped = text.strip()
    if stripped in ("WAIT", "DONE", "FAIL"):
        return [stripped]

    pattern = r"```(?:\w+\s+)?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    codes: List[str] = []
    specials = {"WAIT", "DONE", "FAIL"}

    for match in matches:
        match = match.strip()
        if match in specials:
            codes.append(match)
        elif match.split("\n")[-1] in specials:
            lines = match.split("\n")
            if len(lines) > 1:
                codes.append("\n".join(lines[:-1]))
            codes.append(lines[-1])
        else:
            codes.append(match)

    return codes


def parse_code_from_som_string(
    text: str,
    masks: List[Tuple[int, int, int, int]],
) -> List[str]:
    """Parse code from SOM (Set-of-Marks) tagged response.

    Prepends ``tag_N = (cx, cy)`` variable assignments so that the
    extracted code can reference elements by tag ID.

    Args:
        text: Raw LLM response.
        masks: List of ``(x, y, w, h)`` bounding boxes.

    Returns:
        A list of executable code strings.
    """
    tag_vars = ""
    for i, (x, y, w, h) in enumerate(masks):
        tag_vars += f"tag_{i + 1} = ({int(x + w // 2)}, {int(y + h // 2)})\n"

    actions = parse_code_from_string(text)
    result: List[str] = []
    for action in actions:
        if action.strip() in ("WAIT", "DONE", "FAIL"):
            result.append(action)
        else:
            result.append(tag_vars + action)
    return result
