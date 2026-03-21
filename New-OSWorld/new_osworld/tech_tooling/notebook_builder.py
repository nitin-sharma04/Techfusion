"""Build Jupyter notebooks in the OSWorld SFT format from trajectories.

Fixes from the old notebook_generator.py:
  - Proper notebook cell source formatting (list of newline-terminated strings)
  - No double-JSON-escaping of commands
  - Clean separation between trajectory-based and live-run notebook generation
  - Generates reasoning that passes validation (no "Executing step" pattern)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


_NOTEBOOK_SKELETON = {
    "nbformat": 4,
    "nbformat_minor": 4,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": [],
}


def _md_cell(lines: List[str]) -> Dict[str, Any]:
    """Create a markdown cell with properly newline-terminated source lines."""
    source = [line if line.endswith("\n") else line + "\n" for line in lines]
    if source:
        source[-1] = source[-1].rstrip("\n")
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def _action_to_pyautogui(raw: str) -> str:
    """Normalise ``pg.`` shorthand to ``pyautogui.`` calls."""
    if raw.startswith("pg."):
        return raw.replace("pg.", "pyautogui.", 1)
    return raw


def _generate_reasoning(action: str, step: int) -> str:
    """Produce a short, natural-language reasoning line for an action.

    Avoids the "Executing step N" pattern that the validator rejects.
    """
    lower = action.lower()
    if "click(" in lower:
        return f"I need to click the target element to proceed with the task."
    if "doubleclick(" in lower or "double_click(" in lower:
        return f"Double-clicking the element to open or select it."
    if "rightclick(" in lower or "right_click(" in lower:
        return f"Right-clicking to open the context menu."
    if "typewrite(" in lower or "write(" in lower:
        return f"Typing the required text into the active field."
    if "press(" in lower:
        return f"Pressing a key to confirm or navigate."
    if "hotkey(" in lower:
        return f"Using a keyboard shortcut to perform the operation."
    if "scroll(" in lower:
        return f"Scrolling to bring the target element into view."
    if "sleep(" in lower:
        return f"Waiting briefly for the interface to update."
    if "drag" in lower:
        return f"Dragging the element to the target location."
    return f"Performing the next action to advance the task."


def build_sft_notebook(
    task_config: Dict[str, Any],
    instruction: str,
    trajectory: List[Dict[str, Any]],
    result_dir: str,
    task_id: Optional[str] = None,
) -> str:
    """Generate an SFT notebook from a completed manual trajectory.

    Args:
        task_config: The task JSON config dict.
        instruction: Human-readable task instruction.
        trajectory: List of step-log dicts (must have ``"action"`` key).
        result_dir: Directory to write the notebook into.
        task_id: Notebook filename stem.  Auto-generated if *None*.

    Returns:
        Absolute path to the generated ``.ipynb`` file.
    """
    task_id = task_id or f"osw.sft.{int(time.time())}"
    notebook = {**_NOTEBOOK_SKELETON, "cells": []}

    notebook["cells"].append(_md_cell([
        "**[metadata]**\n",
        "\n",
        "```json\n",
        json.dumps(task_config, indent=2) + "\n",
        "```",
    ]))

    notebook["cells"].append(_md_cell([
        "**[user]**\n",
        "\n",
        instruction,
    ]))

    step_num = 0
    for entry in trajectory:
        raw_action = entry.get("action", "")
        if not raw_action or raw_action.lower() in ("done", "exit", ""):
            continue

        step_num += 1
        command = _action_to_pyautogui(raw_action)
        full_command = f"import pyautogui, time\n{command}"
        reasoning = _generate_reasoning(command, step_num)

        notebook["cells"].append(_md_cell([
            "**[assistant]**\n",
            "\n",
            reasoning,
        ]))

        notebook["cells"].append(_md_cell([
            "**[tool_call]**\n",
            "\n",
            "```json\n",
            json.dumps({"tool_name": "pyautogui", "arguments": full_command}, indent=2) + "\n",
            "```",
        ]))

        step_idx = entry.get("step", step_num - 1)
        notebook["cells"].append(_md_cell([
            "**[tool_output]**\n",
            "\n",
            "**Attachments:**\n",
            "\n",
            "```json\n",
            json.dumps([
                {"type": "screenshot", "src": f"vm://screen/{step_idx + 1:04d}.png"},
                {"type": "a11y_tree", "src": f"vm://a11y/{step_idx + 1:04d}.xml"},
            ], indent=2) + "\n",
            "```",
        ]))

    notebook["cells"].append(_md_cell(["**[assistant]**\n", "\n", "DONE"]))

    os.makedirs(result_dir, exist_ok=True)
    out_path = os.path.join(result_dir, f"{task_id}.ipynb")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(notebook, fh, indent=2, ensure_ascii=False)

    return out_path


def notebook_from_trajectory_file(
    trajectory_path: str,
    task_config: Optional[Dict[str, Any]] = None,
    instruction: str = "Complete the given task",
    output_dir: Optional[str] = None,
) -> str:
    """Create an SFT notebook from an existing ``trajectory.jsonl`` file.

    Args:
        trajectory_path: Path to the JSONL trajectory.
        task_config: Task config dict.  A minimal one is generated if *None*.
        instruction: Task instruction text.
        output_dir: Output directory.  Defaults to the trajectory's parent dir.

    Returns:
        Path to the generated notebook.
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(trajectory_path))

    trajectory: List[Dict[str, Any]] = []
    with open(trajectory_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                trajectory.append(json.loads(stripped))

    stem = os.path.splitext(os.path.basename(trajectory_path))[0]
    task_id = f"osw.sft.{stem}"

    if task_config is None:
        task_config = {
            "task_id": task_id,
            "title": f"SFT task: {stem}",
            "instruction": instruction,
            "modality": ["screenshot", "a11y_tree"],
            "action_schema": "pyautogui_code_string",
            "tool_name": "pyautogui",
        }

    return build_sft_notebook(
        task_config=task_config,
        instruction=instruction,
        trajectory=trajectory,
        result_dir=output_dir,
        task_id=task_id,
    )
