"""Run a single evaluation example end-to-end."""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from new_osworld.agents.base import BaseAgent
from new_osworld.environment.desktop_env import DesktopEnv
from new_osworld.logging_setup import get_logger

logger = get_logger("runner.single")


def _wait_for_observation(
    env: DesktopEnv,
    timeout: float = 60.0,
    poll_interval: float = 5.0,
) -> Dict[str, Any]:
    """Poll until the VM returns a valid screenshot (and optional a11y tree).

    Args:
        env: The desktop environment instance.
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between polls.

    Returns:
        The observation dict (may have ``None`` values if the deadline passed).
    """
    deadline = time.time() + timeout
    obs: Optional[Dict[str, Any]] = None
    while time.time() < deadline:
        obs = env._get_obs()
        has_screenshot = obs.get("screenshot") is not None
        needs_tree = getattr(env, "require_a11y_tree", False)
        has_tree = not needs_tree or bool(obs.get("accessibility_tree"))
        if has_screenshot and has_tree:
            return obs
        time.sleep(poll_interval)
    return obs or {}


def _create_example_logger(
    example: Dict[str, Any],
    result_dir: str,
) -> logging.Logger:
    """Create a file-backed logger for a single example run."""
    example_logger = logging.getLogger(f"osworld.example.{example['id']}")
    example_logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(os.path.join(result_dir, "runtime.log"))
    handler.setFormatter(logging.Formatter("[%(asctime)s %(levelname)s] %(message)s"))
    example_logger.addHandler(handler)
    return example_logger


def run_single_example(
    agent: BaseAgent,
    env: DesktopEnv,
    example: Dict[str, Any],
    max_steps: int,
    instruction: str,
    result_dir: str,
    scores: List[float],
    sleep_after_execution: float = 0.0,
) -> None:
    """Run one evaluation example: reset env, loop agent predict/step, evaluate.

    Results (trajectory, screenshots, score) are written to *result_dir*.

    Args:
        agent: The agent to use for action prediction.
        env: The desktop environment.
        example: Task config dict.
        max_steps: Maximum interaction steps.
        instruction: Task instruction text.
        result_dir: Directory to write outputs.
        scores: Shared list to append the final score.
        sleep_after_execution: Extra pause between steps.
    """
    os.makedirs(result_dir, exist_ok=True)
    example_logger = _create_example_logger(example, result_dir)

    try:
        agent.reset(example_logger)
    except TypeError:
        agent.reset()

    env.reset(task_config=example)
    obs = _wait_for_observation(env)

    done = False
    step_idx = 0

    env.controller.start_recording()

    while not done and step_idx < max_steps:
        response, actions = agent.predict(instruction, obs)

        if not actions:
            logger.warning("No actions returned at step %d.", step_idx + 1)
            step_idx += 1
            continue

        for action in actions:
            ts = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
            logger.info("Step %d: %s", step_idx + 1, action)

            obs, reward, done, info = env.step(action, sleep_after_execution)

            screenshot = obs.get("screenshot")
            if screenshot:
                with open(os.path.join(result_dir, f"step_{step_idx + 1}_{ts}.png"), "wb") as fh:
                    fh.write(screenshot)
            else:
                logger.warning("Missing screenshot at step %d.", step_idx + 1)

            a11y = obs.get("accessibility_tree")
            if a11y:
                with open(
                    os.path.join(result_dir, f"step_{step_idx + 1}_{ts}_a11y.xml"),
                    "w", encoding="utf-8",
                ) as fh:
                    fh.write(a11y)

            with open(os.path.join(result_dir, "traj.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_timestamp": ts,
                    "action": action if isinstance(action, (str, dict)) else str(action),
                    "response": response,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_{ts}.png",
                }))
                fh.write("\n")

            if done:
                logger.info("Episode done at step %d.", step_idx + 1)
                break

        step_idx += 1

    score = env.evaluate()
    logger.info("Evaluation score: %.2f", score)
    scores.append(score)

    with open(os.path.join(result_dir, "result.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"{score}\n")

    env.controller.end_recording(os.path.join(result_dir, "recording.mp4"))
