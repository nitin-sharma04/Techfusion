"""Validate task deliverables against the OSWorld schema and directory conventions.

Redesigned from the old validation_script.py:
  - Uses dataclasses for structured results instead of print()
  - Returns a ValidationReport object instead of printing inline
  - Rich-formatted output
  - Modular check functions that can be composed
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

console = Console()

VALID_SNAPSHOTS = {
    "chrome", "gimp", "libreoffice_calc", "libreoffice_impress",
    "libreoffice_writer", "multi_apps", "os", "thunderbird", "vlc", "vs_code",
}

VALID_RELATED_APPS = {
    "browser", "calc", "chrome", "excel", "gimp", "image", "libreoffice",
    "libreoffice calc", "libreoffice_calc", "libreoffice_impress",
    "libreoffice_writer", "os", "pdf", "picard", "powerpoint", "ppt",
    "terminal", "thunderbird", "ubuntu_media_player", "vlc", "vs_code",
    "vscode", "word", "writer",
}

VALID_CONFIG_TYPES = {
    "launch", "chrome_open_tabs", "chrome_close_tabs", "activate_window",
    "execute", "update_browse_history", "download", "open", "sleep",
    "command", "googledrive", "login",
}

REQUIRED_FIELDS = [
    "id", "snapshot", "instruction", "source", "trajectory", "config",
    "related_apps", "evaluator", "proxy", "fixed_ip",
    "possibility_of_env_change", "model_pass_rate",
    "annotator_hints", "knowledge_points", "coverage",
]


@dataclass
class CheckResult:
    """Result of a single validation check."""
    name: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Aggregate validation report for a delivery."""
    delivery_path: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def total_errors(self) -> int:
        return sum(len(c.errors) for c in self.checks)

    def display(self) -> None:
        """Print a rich-formatted summary table."""
        table = Table(title=f"Validation: {self.delivery_path}")
        table.add_column("Check", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details")

        for check in self.checks:
            status = "[green]PASS[/]" if check.passed else "[red]FAIL[/]"
            details_parts = []
            for e in check.errors:
                details_parts.append(f"[red]{e}[/]")
            for w in check.warnings:
                details_parts.append(f"[yellow]{w}[/]")
            details = "\n".join(details_parts) if details_parts else "[dim]OK[/]"
            table.add_row(check.name, status, details)

        table.add_section()
        overall = "[bold green]ALL PASSED[/]" if self.passed else f"[bold red]{self.total_errors} ERROR(S)[/]"
        table.add_row("[bold]Overall[/]", overall, "")
        console.print(table)


def check_json_schema(task_json_path: str) -> CheckResult:
    """Validate the task JSON against the OSWorld schema rules.

    Args:
        task_json_path: Path to the task JSON file.

    Returns:
        A :class:`CheckResult` with any schema violations.
    """
    result = CheckResult(name="JSON Schema", passed=True)

    try:
        with open(task_json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        result.passed = False
        result.errors.append(f"Invalid JSON: {exc}")
        return result
    except OSError as exc:
        result.passed = False
        result.errors.append(f"Cannot read file: {exc}")
        return result

    for f in REQUIRED_FIELDS:
        if f not in data:
            result.errors.append(f"Missing required field: {f}")

    if result.errors:
        result.passed = False
        return result

    if data.get("snapshot") not in VALID_SNAPSHOTS:
        result.errors.append(f"Invalid snapshot: {data.get('snapshot')}")

    for i, app in enumerate(data.get("related_apps", [])):
        if app not in VALID_RELATED_APPS:
            result.errors.append(f"related_apps[{i}] invalid: {app}")

    for i, cfg in enumerate(data.get("config", [])):
        if not isinstance(cfg, dict) or "type" not in cfg:
            result.errors.append(f"config[{i}] missing 'type'")
        elif cfg["type"] not in VALID_CONFIG_TYPES:
            result.errors.append(f"config[{i}] invalid type: {cfg['type']}")

    ev = data.get("evaluator", {})
    if not isinstance(ev, dict):
        result.errors.append("evaluator must be a dict")
    elif "func" not in ev:
        result.errors.append("evaluator missing 'func'")

    if data.get("possibility_of_env_change") not in ("low", "medium", "high"):
        result.errors.append("possibility_of_env_change must be low/medium/high")

    for bf in ("proxy", "fixed_ip"):
        if not isinstance(data.get(bf), bool):
            result.errors.append(f"{bf} must be boolean")

    has_browser = any(a in data.get("related_apps", []) for a in ("browser", "chrome"))
    proxy_val = data.get("proxy", False)
    if has_browser and not proxy_val:
        result.warnings.append("proxy should be true when related_apps includes browser/chrome")
    if not has_browser and proxy_val:
        result.warnings.append("proxy should be false when no browser/chrome in related_apps")

    result.passed = len(result.errors) == 0
    return result


def check_directory_structure(delivery_dir: str) -> CheckResult:
    """Verify that the delivery folder has the expected layout.

    Expected:
        <delivery_dir>/
            <task_id>.json
            Annotator_trajectory/
                <annotator>/
                    trajectory.jsonl
                    step_*.png
    """
    result = CheckResult(name="Directory Structure", passed=True)
    root = Path(delivery_dir)

    if not root.is_dir():
        result.passed = False
        result.errors.append(f"Directory does not exist: {delivery_dir}")
        return result

    json_files = list(root.glob("*.json"))
    if not json_files:
        result.errors.append("No task JSON file found in delivery root")

    traj_dirs = list(root.glob("**/trajectory.jsonl"))
    if not traj_dirs:
        result.errors.append("No trajectory.jsonl found anywhere under delivery")
    else:
        for traj in traj_dirs:
            parent = traj.parent
            pngs = list(parent.glob("step_*.png"))
            if not pngs:
                result.warnings.append(f"No step screenshots in {parent}")

    forbidden = list(root.glob("**/args.json"))
    for f in forbidden:
        result.errors.append(f"Forbidden file found: {f}")

    result.passed = len(result.errors) == 0
    return result


def check_notebook_cells(notebook_path: str) -> CheckResult:
    """Validate an SFT notebook has proper cell structure.

    Checks:
      - Contains [metadata], [user], [assistant], [tool_call], [tool_output] cells
      - Assistant cells don't contain forbidden patterns
    """
    result = CheckResult(name="Notebook Cells", passed=True)

    try:
        with open(notebook_path, "r", encoding="utf-8") as fh:
            nb = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        result.passed = False
        result.errors.append(f"Cannot read notebook: {exc}")
        return result

    cells = nb.get("cells", [])
    if not cells:
        result.errors.append("Notebook has no cells")
        result.passed = False
        return result

    found_tags = set()
    for i, cell in enumerate(cells):
        source = "".join(cell.get("source", []))
        for tag in ("[metadata]", "[user]", "[assistant]", "[tool_call]", "[tool_output]"):
            if tag in source:
                found_tags.add(tag)

        if "[assistant]" in source:
            content = source.replace("**[assistant]**", "").strip()
            if "Executing step" in content:
                result.errors.append(
                    f"Cell {i}: assistant contains forbidden 'Executing step' pattern"
                )

    for required in ("[metadata]", "[user]", "[assistant]"):
        if required not in found_tags:
            result.errors.append(f"Missing required cell type: {required}")

    result.passed = len(result.errors) == 0
    return result


def check_evaluation_score(score_path: str, min_score: float = 1.0) -> CheckResult:
    """Verify the evaluation score meets the minimum threshold."""
    result = CheckResult(name="Evaluation Score", passed=True)

    if not os.path.isfile(score_path):
        result.passed = False
        result.errors.append(f"Score file not found: {score_path}")
        return result

    try:
        with open(score_path, "r") as fh:
            score = float(fh.read().strip())
    except (ValueError, OSError) as exc:
        result.passed = False
        result.errors.append(f"Cannot parse score: {exc}")
        return result

    if score < min_score:
        result.passed = False
        result.errors.append(f"Score {score} < required {min_score}")
    return result


def validate_delivery(delivery_dir: str, task_json: Optional[str] = None) -> ValidationReport:
    """Run all validation checks on a delivery directory.

    Args:
        delivery_dir: Root of the delivery folder.
        task_json: Explicit path to the task JSON.  Auto-detected if *None*.

    Returns:
        A :class:`ValidationReport` that can be displayed or inspected.
    """
    report = ValidationReport(delivery_path=delivery_dir)
    root = Path(delivery_dir)

    report.checks.append(check_directory_structure(delivery_dir))

    if task_json is None:
        candidates = list(root.glob("*.json"))
        task_json = str(candidates[0]) if candidates else None

    if task_json and os.path.isfile(task_json):
        report.checks.append(check_json_schema(task_json))

    for nb_path in root.rglob("*.ipynb"):
        report.checks.append(check_notebook_cells(str(nb_path)))

    for score_path in root.rglob("result.txt"):
        report.checks.append(check_evaluation_score(str(score_path)))

    return report
