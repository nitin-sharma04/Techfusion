"""Interactive manual SFT data collection runner.

The operator steps through a task one action at a time, typing pyautogui
commands.  Every step is logged with before/after screenshots and
accessibility tree XML files (with screen coordinates for every element).

Improvements over old Turing_tooling/lib_run_manual.py:
  - Always captures accessibility tree XML (coordinates for every element)
  - Saves both before-action and after-action screenshots
  - Runs the evaluator at the end and saves the score
  - Rich formatted output with colour and tables
  - Generates SFT notebook automatically after completion
"""

from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from new_osworld.environment.desktop_env import DesktopEnv, _fix_pyautogui_less_than
from new_osworld.logging_setup import get_logger
from new_osworld.runner.a11y_enricher import save_enriched_a11y, parse_elements_with_coords

logger = get_logger("runner.manual")
console = Console()


def _save_screenshot(obs: Dict[str, Any], path: str) -> bool:
    """Save the screenshot from an observation dict to a PNG file."""
    raw = obs.get("screenshot")
    if not isinstance(raw, bytes):
        return False
    try:
        Image.open(io.BytesIO(raw)).save(path)
        return True
    except Exception as exc:
        logger.error("Failed to save screenshot: %s", exc)
        return False


def _save_a11y_tree(obs: Dict[str, Any], path: str) -> bool:
    """Save the accessibility tree XML from an observation dict."""
    tree = obs.get("accessibility_tree")
    if not tree:
        return False
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(tree)
        return True
    except Exception as exc:
        logger.error("Failed to save a11y tree: %s", exc)
        return False


def _wait_for_observation(env: DesktopEnv, timeout: float = 60.0, poll: float = 5.0) -> Dict[str, Any]:
    """Poll until the VM returns a valid screenshot and accessibility tree."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        obs = env._get_obs()
        if obs.get("screenshot") and obs.get("accessibility_tree"):
            return obs
        time.sleep(poll)
    return env._get_obs()


def run_manual_example(
    env: DesktopEnv,
    task_config: Dict[str, Any],
    max_steps: int,
    instruction: str,
    result_dir: str,
    sleep_after: float = 1.0,
) -> None:
    """Run a single task in interactive manual mode.

    For each step, saves:
      - ``step_N_before.png``  -- screenshot before the action
      - ``step_N_before.xml``  -- accessibility tree XML with screen coordinates
      - ``step_N_after.png``   -- screenshot after action execution

    At the end, runs the evaluator and saves ``result.txt``.

    Args:
        env: The desktop environment (must have ``require_a11y_tree=True``).
        task_config: Task JSON dict.
        max_steps: Maximum allowed steps.
        instruction: Task instruction text.
        result_dir: Output directory for trajectory data.
        sleep_after: Pause after each executed action.
    """
    os.makedirs(result_dir, exist_ok=True)

    obs = env.reset(task_config=task_config)
    env.controller.start_recording()

    console.print("\n[dim]Initialising VM and services ...[/]")
    time.sleep(10)

    obs = _wait_for_observation(env)

    tree = obs.get("accessibility_tree")
    if tree:
        console.print(f"[green]Accessibility tree OK[/] ({len(tree)} chars)")
    else:
        console.print("[yellow]Warning: accessibility tree not available.[/]")
        console.print("[dim]Trying to start AT-SPI service ...[/]")
        env.controller.execute_python_command(
            "import subprocess; subprocess.run(['systemctl', '--user', 'start', 'at-spi-dbus-bus.service'])"
        )
        time.sleep(3)
        obs = env._get_obs()
        tree = obs.get("accessibility_tree")
        if tree:
            console.print(f"[green]Accessibility tree recovered[/] ({len(tree)} chars)")
        else:
            console.print("[red]Accessibility tree unavailable -- XML files will not be saved.[/]")

    _save_screenshot(obs, os.path.join(result_dir, "initial_state.png"))
    tree_xml = obs.get("accessibility_tree")
    if tree_xml:
        save_enriched_a11y(tree_xml, result_dir, step=-1)
        os.rename(
            os.path.join(result_dir, "step_-1_before.xml"),
            os.path.join(result_dir, "initial_state.xml"),
        )
        if os.path.exists(os.path.join(result_dir, "step_-1_coords.tsv")):
            os.rename(
                os.path.join(result_dir, "step_-1_coords.tsv"),
                os.path.join(result_dir, "initial_coords.tsv"),
            )
        if os.path.exists(os.path.join(result_dir, "step_-1_interactive.tsv")):
            os.rename(
                os.path.join(result_dir, "step_-1_interactive.tsv"),
                os.path.join(result_dir, "initial_interactive.tsv"),
            )

    trajectory: List[Dict[str, Any]] = []

    console.print(Panel(instruction, title="Task Instruction", border_style="bright_blue"))

    help_table = Table(title="Quick Reference", show_header=True, header_style="bold")
    help_table.add_column("Input", style="cyan")
    help_table.add_column("Meaning")
    help_table.add_row("pg.click(x, y)", "Left-click at coordinates")
    help_table.add_row("pg.doubleClick(x, y)", "Double-click")
    help_table.add_row("pg.rightClick(x, y)", "Right-click")
    help_table.add_row("pg.typewrite('text')", "Type text")
    help_table.add_row("pg.press('enter')", "Press a key")
    help_table.add_row("pg.hotkey('ctrl', 'c')", "Key combination")
    help_table.add_row("pg.scroll(-3)", "Scroll down")
    help_table.add_row("time.sleep(2)", "Wait 2 seconds")
    help_table.add_row("[bold]done[/]", "Finish task")
    help_table.add_row("[bold]exit[/]", "Abort task")
    console.print(help_table)

    done = False
    for step in range(max_steps):
        obs_log: Dict[str, str] = {}

        _save_screenshot(obs, os.path.join(result_dir, f"step_{step}_before.png"))
        obs_log["screenshot_before"] = f"step_{step}_before.png"

        tree_xml = obs.get("accessibility_tree")
        if tree_xml:
            a11y_files = save_enriched_a11y(tree_xml, result_dir, step)
            obs_log.update(a11y_files)
            elem_count = a11y_files.get("element_count", 0)
            console.print(f"  [dim]Saved: XML + coords.tsv + interactive.tsv ({elem_count} elements with coordinates)[/]")
        else:
            console.print(f"  [yellow]No accessibility tree for step {step}[/]")

        step_log: Dict[str, Any] = {
            "step": step,
            "observation": obs_log,
            "instruction": instruction,
        }

        try:
            action_input = input(f"\nStep {step + 1}/{max_steps} | Enter action (e.g., pg.click(100, 200)): ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[red]Aborted.[/]")
            break

        stripped = action_input.strip().lower()
        if not stripped or stripped == "exit":
            console.print("[yellow]Task aborted.[/]")
            break
        if stripped == "done":
            console.print("[green]Task marked as done.[/]")
            step_log["action"] = "DONE"
            trajectory.append(step_log)
            done = True
            break

        if action_input.startswith("pg."):
            command = action_input.replace("pg.", "pyautogui.")
        elif action_input.startswith("time.") or action_input.startswith("pyautogui."):
            command = action_input
        else:
            command = f'pyautogui.typewrite("{action_input}"); pyautogui.press("enter")'

        command = _fix_pyautogui_less_than(command)

        try:
            result = env.controller.execute_python_command(command)
            if result and result.get("error"):
                console.print(f"  [red]VM error:[/] {result['error']}")

            obs, reward, done, info = env.step(None, sleep_after)

            _save_screenshot(obs, os.path.join(result_dir, f"step_{step}_after.png"))
            obs_log["screenshot_after"] = f"step_{step}_after.png"

            step_log["action"] = action_input
            step_log["command"] = command
            step_log["info"] = info
            console.print(f"  [green]Executed:[/] {action_input}")
        except Exception as exc:
            console.print(f"  [red]Error:[/] {exc}")
            step_log["action"] = action_input
            step_log["error"] = str(exc)

        trajectory.append(step_log)

        if done:
            console.print("[green]Environment signalled task complete.[/]")
            break

    rec_path = os.path.join(result_dir, "recording.mp4")
    env.controller.end_recording(rec_path)

    traj_path = os.path.join(result_dir, "trajectory.jsonl")
    with open(traj_path, "w", encoding="utf-8") as fh:
        for entry in trajectory:
            fh.write(json.dumps(entry, default=str) + "\n")

    try:
        score = env.evaluate()
        console.print(f"\n[bold]Evaluation score:[/] {score:.2f}")
        with open(os.path.join(result_dir, "result.txt"), "w") as fh:
            fh.write(f"{score}\n")
    except Exception as exc:
        console.print(f"[yellow]Evaluation failed:[/] {exc}")

    try:
        from new_osworld.tech_tooling.notebook_builder import build_sft_notebook
        nb_path = build_sft_notebook(
            task_config=task_config,
            instruction=instruction,
            trajectory=trajectory,
            result_dir=result_dir,
        )
        console.print(f"[bold green]Notebook saved:[/]    {nb_path}")
    except Exception as exc:
        console.print(f"[yellow]Notebook generation failed:[/] {exc}")

    console.print(f"[bold green]Trajectory saved:[/] {traj_path}")
    console.print(f"[bold green]Recording saved:[/]  {rec_path}")
