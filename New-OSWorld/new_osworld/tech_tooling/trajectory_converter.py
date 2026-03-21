"""Convert trajectory.jsonl files into SFT notebooks.

Standalone module that can be called from the CLI or imported as a library.
Replaces the old convert_trajectory_to_notebook.py with cleaner error handling.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from rich.console import Console

from new_osworld.tech_tooling.notebook_builder import notebook_from_trajectory_file

console = Console()


def convert(
    trajectory_path: str,
    task_config_path: Optional[str] = None,
    instruction: str = "Complete the given task",
    output_dir: Optional[str] = None,
) -> str:
    """Convert a trajectory file to an SFT notebook.

    Args:
        trajectory_path: Path to ``trajectory.jsonl``.
        task_config_path: Path to task JSON config (optional).
        instruction: Task instruction text.
        output_dir: Where to write the notebook. Defaults to trajectory's dir.

    Returns:
        Path to the generated notebook.

    Raises:
        FileNotFoundError: If the trajectory file doesn't exist.
        ValueError: If the trajectory cannot be parsed.
    """
    if not os.path.isfile(trajectory_path):
        raise FileNotFoundError(f"Trajectory file not found: {trajectory_path}")

    task_config: Optional[Dict[str, Any]] = None
    if task_config_path and os.path.isfile(task_config_path):
        with open(task_config_path, "r", encoding="utf-8") as fh:
            task_config = json.load(fh)

    notebook_path = notebook_from_trajectory_file(
        trajectory_path=trajectory_path,
        task_config=task_config,
        instruction=instruction,
        output_dir=output_dir,
    )

    console.print(f"[bold green]Notebook created:[/] {notebook_path}")
    return notebook_path
