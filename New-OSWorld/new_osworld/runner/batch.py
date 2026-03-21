"""Batch evaluation runner -- sequentially process all examples in a benchmark."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from tqdm import tqdm

from new_osworld.agents.base import BaseAgent
from new_osworld.config import AppConfig
from new_osworld.environment.desktop_env import DesktopEnv
from new_osworld.logging_setup import get_logger
from new_osworld.runner.single import run_single_example

logger = get_logger("runner.batch")
console = Console()


def flatten_tasks(meta: Dict[str, List[str]]) -> List[tuple]:
    """Convert ``{domain: [id, ...]}`` into a flat ``[(domain, id), ...]`` list."""
    tasks = []
    for domain, ids in meta.items():
        for eid in ids:
            tasks.append((domain, eid))
    return tasks


def get_unfinished_tasks(
    meta: Dict[str, List[str]],
    result_dir: str,
    action_space: str,
    observation_type: str,
    model: str,
) -> Dict[str, List[str]]:
    """Filter out already-completed examples based on existing result files.

    Incomplete runs (missing ``result.txt``) are cleaned up so they can
    be re-run.

    Args:
        meta: Full test metadata ``{domain: [example_id, ...]}``.
        result_dir: Base results directory.
        action_space: Action space name (used in path).
        observation_type: Observation type (used in path).
        model: Model name (used in path).

    Returns:
        A filtered copy of *meta* with only unfinished examples.
    """
    target = os.path.join(result_dir, action_space, observation_type, model)
    if not os.path.exists(target):
        return meta

    finished: Dict[str, List[str]] = {}
    for domain in os.listdir(target):
        domain_path = os.path.join(target, domain)
        if not os.path.isdir(domain_path):
            continue
        finished[domain] = []
        for eid in os.listdir(domain_path):
            if eid == "onboard":
                continue
            eid_path = os.path.join(domain_path, eid)
            if not os.path.isdir(eid_path):
                continue
            if "result.txt" in os.listdir(eid_path):
                finished[domain].append(eid)
            else:
                for f in os.listdir(eid_path):
                    os.remove(os.path.join(eid_path, f))

    result = {}
    for domain, ids in meta.items():
        done_ids = set(finished.get(domain, []))
        remaining = [i for i in ids if i not in done_ids]
        if remaining:
            result[domain] = remaining
    return result


def run_batch(
    cfg: AppConfig,
    agent: BaseAgent,
    env: DesktopEnv,
    test_meta: Dict[str, List[str]],
) -> List[float]:
    """Run all tasks sequentially, showing a rich progress bar.

    Args:
        cfg: Application configuration.
        agent: The LLM agent.
        env: The desktop environment.
        test_meta: ``{domain: [example_id, ...]}`` metadata.

    Returns:
        List of evaluation scores.
    """
    scores: List[float] = []
    all_tasks = flatten_tasks(test_meta)
    total = len(all_tasks)

    logger.info("Starting batch evaluation: %d tasks.", total)
    console.print(f"[bold green]Starting evaluation:[/] {total} tasks across {len(test_meta)} domains")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task_bar = progress.add_task("Evaluating ...", total=total)

        for domain, example_id in all_tasks:
            config_file = os.path.join(
                cfg.evaluation.test_config_base_dir,
                f"examples/{domain}/{example_id}.json",
            )
            try:
                with open(config_file, "r", encoding="utf-8") as fh:
                    example = json.load(fh)
            except FileNotFoundError:
                logger.error("Config not found: %s", config_file)
                progress.advance(task_bar)
                continue

            progress.update(task_bar, description=f"[cyan]{domain}[/]/{example_id[:8]}")

            example_result_dir = os.path.join(
                cfg.evaluation.result_dir,
                cfg.environment.action_space,
                cfg.environment.observation_type,
                cfg.agent.model,
                domain,
                example_id,
            )

            try:
                run_single_example(
                    agent=agent,
                    env=env,
                    example=example,
                    max_steps=cfg.evaluation.max_steps,
                    instruction=example["instruction"],
                    result_dir=example_result_dir,
                    scores=scores,
                    sleep_after_execution=cfg.evaluation.sleep_after_execution,
                )
            except Exception as exc:
                logger.exception("Error in %s/%s: %s", domain, example_id, exc)
                try:
                    env.controller.end_recording(os.path.join(example_result_dir, "recording.mp4"))
                except Exception:
                    pass
                os.makedirs(example_result_dir, exist_ok=True)
                with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as fh:
                    fh.write(json.dumps({"Error": f"{domain}/{example_id}: {exc}"}) + "\n")

            progress.advance(task_bar)

    if scores:
        avg = sum(scores) / len(scores)
        console.print(f"\n[bold green]Evaluation complete.[/]  Average score: [bold]{avg:.4f}[/]  ({len(scores)} tasks)")
    else:
        console.print("[yellow]No scores recorded.[/]")

    return scores
