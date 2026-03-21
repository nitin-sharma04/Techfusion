"""Action space definitions for desktop automation.

Centralises keyboard keys and the structured action-space description used by
the ``computer_13`` action mode.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

KEYBOARD_KEYS: List[str] = [
    "\t", "\n", "\r", " ", "!", '"', "#", "$", "%", "&", "'", "(", ")", "*",
    "+", ",", "-", ".", "/",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    ":", ";", "<", "=", ">", "?", "@",
    "[", "\\", "]", "^", "_", "`",
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "{", "|", "}", "~",
    "accept", "add", "alt", "altleft", "altright", "apps", "backspace",
    "browserback", "browserfavorites", "browserforward", "browserhome",
    "browserrefresh", "browsersearch", "browserstop",
    "capslock", "clear", "convert", "ctrl", "ctrlleft", "ctrlright",
    "decimal", "del", "delete", "divide", "down",
    "end", "enter", "esc", "escape", "execute",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10",
    "f11", "f12", "f13", "f14", "f15", "f16", "f17", "f18", "f19",
    "f20", "f21", "f22", "f23", "f24",
    "final", "fn", "hanguel", "hangul", "hanja", "help", "home", "insert",
    "junja", "kana", "kanji",
    "launchapp1", "launchapp2", "launchmail", "launchmediaselect",
    "left", "modechange", "multiply",
    "nexttrack", "nonconvert",
    "num0", "num1", "num2", "num3", "num4", "num5", "num6", "num7",
    "num8", "num9", "numlock",
    "pagedown", "pageup", "pause", "pgdn", "pgup", "playpause",
    "prevtrack", "print", "printscreen", "prntscrn", "prtsc", "prtscr",
    "return", "right",
    "scrolllock", "select", "separator", "shift", "shiftleft", "shiftright",
    "sleep", "stop", "subtract", "tab", "up",
    "volumedown", "volumemute", "volumeup",
    "win", "winleft", "winright", "yen",
    "command", "option", "optionleft", "optionright",
]

SPECIAL_ACTIONS = ("WAIT", "FAIL", "DONE")


def build_action_space(x_max: int = 1920, y_max: int = 1080) -> List[Dict[str, Any]]:
    """Return the structured action-space list for ``computer_13`` mode.

    Args:
        x_max: Screen width in pixels.
        y_max: Screen height in pixels.
    """
    return [
        {
            "action_type": "MOVE_TO",
            "note": "move the cursor to the specified position",
            "parameters": {
                "x": {"type": "float", "range": [0, x_max], "optional": False},
                "y": {"type": "float", "range": [0, y_max], "optional": False},
            },
        },
        {
            "action_type": "CLICK",
            "note": "click at the current or specified position",
            "parameters": {
                "button": {"type": "str", "range": ["left", "right", "middle"], "optional": True},
                "x": {"type": "float", "range": [0, x_max], "optional": True},
                "y": {"type": "float", "range": [0, y_max], "optional": True},
                "num_clicks": {"type": "int", "range": [1, 2, 3], "optional": True},
            },
        },
        {
            "action_type": "MOUSE_DOWN",
            "note": "press mouse button",
            "parameters": {
                "button": {"type": "str", "range": ["left", "right", "middle"], "optional": True},
            },
        },
        {
            "action_type": "MOUSE_UP",
            "note": "release mouse button",
            "parameters": {
                "button": {"type": "str", "range": ["left", "right", "middle"], "optional": True},
            },
        },
        {
            "action_type": "RIGHT_CLICK",
            "note": "right click at current or specified position",
            "parameters": {
                "x": {"type": "float", "range": [0, x_max], "optional": True},
                "y": {"type": "float", "range": [0, y_max], "optional": True},
            },
        },
        {
            "action_type": "DOUBLE_CLICK",
            "note": "double click at current or specified position",
            "parameters": {
                "x": {"type": "float", "range": [0, x_max], "optional": True},
                "y": {"type": "float", "range": [0, y_max], "optional": True},
            },
        },
        {
            "action_type": "DRAG_TO",
            "note": "drag cursor to position with left button pressed",
            "parameters": {
                "x": {"type": "float", "range": [0, x_max], "optional": False},
                "y": {"type": "float", "range": [0, y_max], "optional": False},
            },
        },
        {
            "action_type": "SCROLL",
            "note": "scroll the mouse wheel",
            "parameters": {
                "dx": {"type": "int", "range": None, "optional": False},
                "dy": {"type": "int", "range": None, "optional": False},
            },
        },
        {
            "action_type": "TYPING",
            "note": "type the specified text",
            "parameters": {
                "text": {"type": "str", "range": None, "optional": False},
            },
        },
        {
            "action_type": "PRESS",
            "note": "press and release a key",
            "parameters": {
                "key": {"type": "str", "range": "KEYBOARD_KEYS", "optional": False},
            },
        },
        {
            "action_type": "KEY_DOWN",
            "note": "press a key",
            "parameters": {
                "key": {"type": "str", "range": "KEYBOARD_KEYS", "optional": False},
            },
        },
        {
            "action_type": "KEY_UP",
            "note": "release a key",
            "parameters": {
                "key": {"type": "str", "range": "KEYBOARD_KEYS", "optional": False},
            },
        },
        {
            "action_type": "HOTKEY",
            "note": "press a key combination",
            "parameters": {
                "keys": {"type": "list", "range": "KEYBOARD_KEYS", "optional": False},
            },
        },
        {"action_type": "WAIT", "note": "wait until the next action"},
        {"action_type": "FAIL", "note": "task cannot be performed"},
        {"action_type": "DONE", "note": "task is completed"},
    ]


def is_special_action(action: Any) -> bool:
    """Return *True* when *action* is a terminal/meta action (WAIT/FAIL/DONE)."""
    if isinstance(action, str):
        return action.strip() in SPECIAL_ACTIONS
    if isinstance(action, dict):
        return action.get("action_type", "") in SPECIAL_ACTIONS
    return False
