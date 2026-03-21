"""Replay SFT trajectories to verify annotator runs.

Rehydrates a recorded trajectory inside the desktop environment, captures
screenshots at each step, and runs the evaluator.  Produces a verification
summary JSON with the score.

Fixes over the old verify_trajectory.py:
  - No global mutable state for the fix function
  - Clean env lifecycle with context-manager-style finally
  - Proper ``step()`` call signatures (no ``pause=`` kwarg)
  - Progress reporting with rich
"""

from __future__ import annotations

import datetime
import io
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from new_osworld.logging_setup import get_logger

logger = get_logger("tech.replayer")
console = Console()

CONTROL_ACTIONS = frozenset({"DONE", "FAIL", "WAIT"})


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Read a JSONL file into a list of dicts."""
    steps: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Bad JSON on line {lineno} of {path}") from exc
            if isinstance(entry, dict):
                steps.append(entry)
    return steps


def _normalise_action(raw: Any) -> str:
    """Extract a usable action string from various trajectory formats."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        return raw.get("command", raw.get("action", json.dumps(raw)))
    return str(raw)


def _build_command(action_str: str) -> Tuple[str, bool]:
    """Convert a raw action string into a pyautogui command.

    Returns:
        ``(command, is_control)`` -- *is_control* is True for DONE/FAIL/WAIT.
    """
    trimmed = action_str.strip()
    if trimmed.upper() in CONTROL_ACTIONS:
        return trimmed.upper(), True

    command = trimmed.replace("pg.", "pyautogui.") if trimmed.startswith("pg.") else trimmed

    from new_osworld.environment.desktop_env import _fix_pyautogui_less_than
    command = _fix_pyautogui_less_than(command)

    prefixes = ("pyautogui.", "time.", "import ", "#", "from ")
    is_python = any(command.startswith(p) for p in prefixes) or "\n" in command
    if not is_python:
        escaped = json.dumps(command)
        command = f"pyautogui.typewrite({escaped})\npyautogui.press('enter')"

    imports = []
    if "pyautogui." in command and "import pyautogui" not in command:
        imports.append("import pyautogui")
    if "time." in command and "import time" not in command:
        imports.append("import time")
    if imports:
        command = "\n".join(imports + [command])

    return command, False


def _save_screenshot(obs: Dict[str, Any], dest: str) -> bool:
    raw = obs.get("screenshot")
    if not raw:
        return False
    try:
        Image.open(io.BytesIO(raw)).save(dest)
        return True
    except Exception as exc:
        logger.warning("Screenshot save failed: %s", exc)
        return False


def replay_and_evaluate(
    trajectory_path: str,
    task_config_path: str,
    *,
    provider: str = "vmware",
    path_to_vm: Optional[str] = None,
    headless: bool = False,
    client_password: str = "",
    screen_width: int = 1920,
    screen_height: int = 1080,
    sleep_after: float = 0.2,
    max_steps: int = 1000,
    post_replay_sleep: float = 5.0,
    result_dir: Optional[str] = None,
    stop_on_error: bool = False,
    env_retries: int = 3,
) -> Dict[str, Any]:
    """Replay a trajectory file and run the evaluator.

    Args:
        trajectory_path: Path to ``trajectory.jsonl``.
        task_config_path: Path to the task JSON.
        provider: VM provider name.
        path_to_vm: Path to VM image (auto-detected if *None*).
        headless: Run VM headlessly.
        client_password: VM sudo password.
        screen_width: VM screen width.
        screen_height: VM screen height.
        sleep_after: Pause after each action.
        max_steps: Maximum steps to replay.
        post_replay_sleep: Wait before evaluation.
        result_dir: Output directory (auto-generated if *None*).
        stop_on_error: Halt on first VM error.
        env_retries: Retries for env reset.

    Returns:
        Summary dict with ``executed_steps``, ``evaluation_score``, etc.
    """
    with open(task_config_path, "r", encoding="utf-8") as fh:
        task_config = json.load(fh)

    steps = _load_jsonl(trajectory_path)
    logger.info("Loaded %d steps from %s", len(steps), trajectory_path)

    if result_dir is None:
        stem = os.path.splitext(os.path.basename(trajectory_path))[0]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join("trajectory_verifications", f"{stem}_{ts}")
    os.makedirs(result_dir, exist_ok=True)

    summary: Dict[str, Any] = {
        "trajectory_file": os.path.abspath(trajectory_path),
        "task_config": os.path.abspath(task_config_path),
        "total_steps": len(steps),
        "executed_steps": 0,
        "done": False,
        "evaluation_score": None,
    }

    from new_osworld.environment.desktop_env import DesktopEnv

    env = None
    try:
        console.print("[bold]Initialising environment ...[/]")
        env = DesktopEnv(
            provider_name=provider,
            path_to_vm=path_to_vm,
            action_space="pyautogui",
            headless=headless,
            screen_size=(screen_width, screen_height),
            client_password=client_password,
            require_a11y_tree=False,
        )

        for attempt in range(1, env_retries + 1):
            try:
                env.reset(task_config=task_config)
                break
            except ValueError as exc:
                if attempt < env_retries:
                    logger.warning("Reset failed (attempt %d/%d): %s", attempt, env_retries, exc)
                    time.sleep(10)
                else:
                    raise

        time.sleep(10)
        _save_screenshot(env._get_obs(), os.path.join(result_dir, "step_initial.png"))

        # Focus VM window
        cx, cy = max(screen_width // 2, 1), max(screen_height // 2, 1)
        env.controller.execute_python_command(f"import pyautogui; pyautogui.click({cx}, {cy})")
        env.step(None, sleep_after)

        console.print(f"[bold]Replaying {len(steps)} steps ...[/]")
        executed = 0
        done = False

        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"),
            BarColumn(), MofNCompleteColumn(), console=console,
        ) as progress:
            bar = progress.add_task("Replaying", total=min(len(steps), max_steps))

            for idx, step in enumerate(steps):
                if idx >= max_steps:
                    logger.warning("Hit max_steps=%d limit.", max_steps)
                    break

                action_str = _normalise_action(step.get("action"))
                if not action_str:
                    progress.advance(bar)
                    continue

                command, is_control = _build_command(action_str)
                progress.update(bar, description=f"Step {idx}: {action_str[:50]}")

                if is_control:
                    obs, _, done, info = env.step(command, sleep_after)
                else:
                    result = env.controller.execute_python_command(command)
                    if isinstance(result, dict) and result.get("error"):
                        msg = f"VM error at step {idx}: {result['error']}"
                        if stop_on_error:
                            raise RuntimeError(msg)
                        logger.warning(msg)
                    obs, _, done, info = env.step(None, sleep_after)

                executed += 1
                _save_screenshot(obs, os.path.join(result_dir, f"step_{idx:04d}_after.png"))
                progress.advance(bar)

                if done:
                    logger.info("Environment signalled done at step %d.", idx)
                    break

        summary["executed_steps"] = executed
        summary["done"] = done

        if post_replay_sleep > 0:
            console.print(f"[dim]Waiting {post_replay_sleep}s for VM to settle ...[/]")
            time.sleep(post_replay_sleep)

        console.print("[bold]Running evaluator ...[/]")
        score = env.evaluate()
        summary["evaluation_score"] = score

        with open(os.path.join(result_dir, "evaluation_score.txt"), "w") as fh:
            fh.write(str(score))

        style = "green" if score >= 0.5 else "red"
        console.print(f"[bold {style}]Score: {score}[/]")

    finally:
        if env:
            env.close()
        with open(os.path.join(result_dir, "verification_summary.json"), "w") as fh:
            json.dump(summary, fh, indent=2)
        console.print(f"[dim]Summary saved to {result_dir}[/]")

    return summary
