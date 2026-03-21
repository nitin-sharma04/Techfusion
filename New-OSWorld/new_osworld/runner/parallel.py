"""Parallel evaluation runner -- distribute tasks across multiple VM workers."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from multiprocessing import Manager, Process, current_process
from typing import Any, Dict, List

from new_osworld.agents.prompt_agent import PromptAgent
from new_osworld.config import AppConfig
from new_osworld.environment.desktop_env import DesktopEnv
from new_osworld.logging_setup import get_logger
from new_osworld.runner.single import run_single_example

logger = get_logger("runner.parallel")


def _worker(
    task_queue: Any,
    cfg: AppConfig,
) -> None:
    """Worker process: pull tasks from the queue and execute them.

    Each worker creates its own ``DesktopEnv`` and ``PromptAgent``.

    Args:
        task_queue: A multiprocessing :class:`Queue` of ``(domain, example_id)`` pairs.
        cfg: Application configuration.
    """
    env = None
    scores: List[float] = []
    proc_name = current_process().name

    try:
        env = DesktopEnv(
            provider_name=cfg.environment.provider,
            region=cfg.environment.region,
            path_to_vm=cfg.environment.path_to_vm,
            snapshot_name=cfg.environment.snapshot_name,
            action_space=cfg.environment.action_space,
            screen_size=(cfg.environment.screen_width, cfg.environment.screen_height),
            headless=cfg.environment.headless,
            os_type=cfg.environment.os_type,
            require_a11y_tree=cfg.environment.observation_type in (
                "a11y_tree", "screenshot_a11y_tree", "som"
            ),
            enable_proxy=cfg.environment.enable_proxy,
            client_password=cfg.environment.client_password,
        )
        agent = PromptAgent(
            platform=cfg.agent.platform,
            model=cfg.agent.model,
            max_tokens=cfg.agent.max_tokens,
            top_p=cfg.agent.top_p,
            temperature=cfg.agent.temperature,
            action_space=cfg.environment.action_space,
            observation_type=cfg.environment.observation_type,
            max_trajectory_length=cfg.agent.max_trajectory_length,
            client_password=cfg.environment.client_password,
        )

        logger.info("[%s] Worker started.", proc_name)

        while True:
            try:
                domain, example_id = task_queue.get(timeout=5)
            except Exception:
                break

            config_path = os.path.join(
                cfg.evaluation.test_config_base_dir,
                f"examples/{domain}/{example_id}.json",
            )
            try:
                with open(config_path, "r", encoding="utf-8") as fh:
                    example = json.load(fh)
            except FileNotFoundError:
                logger.error("[%s] Config not found: %s", proc_name, config_path)
                continue

            result_dir = os.path.join(
                cfg.evaluation.result_dir,
                cfg.environment.action_space,
                cfg.environment.observation_type,
                cfg.agent.model,
                domain,
                example_id,
            )
            os.makedirs(result_dir, exist_ok=True)

            logger.info("[%s] Running %s/%s", proc_name, domain, example_id)
            try:
                run_single_example(
                    agent=agent,
                    env=env,
                    example=example,
                    max_steps=cfg.evaluation.max_steps,
                    instruction=example["instruction"],
                    result_dir=result_dir,
                    scores=scores,
                    sleep_after_execution=cfg.evaluation.sleep_after_execution,
                )
            except Exception as exc:
                logger.error("[%s] Error in %s/%s: %s", proc_name, domain, example_id, exc)
                logger.debug(traceback.format_exc())
                try:
                    env.controller.end_recording(os.path.join(result_dir, "recording.mp4"))
                except Exception:
                    pass
                with open(os.path.join(result_dir, "traj.jsonl"), "a") as fh:
                    fh.write(json.dumps({"Error": f"{domain}/{example_id}: {exc}"}) + "\n")

    except Exception as exc:
        logger.error("[%s] Fatal error: %s", proc_name, exc)
        logger.debug(traceback.format_exc())
    finally:
        if env:
            try:
                env.close()
                logger.info("[%s] Environment closed.", proc_name)
            except Exception as exc:
                logger.error("[%s] Error closing env: %s", proc_name, exc)


def run_parallel(
    cfg: AppConfig,
    test_meta: Dict[str, List[str]],
) -> None:
    """Distribute tasks across *num_workers* parallel VM processes.

    Args:
        cfg: Application configuration (``execution.num_workers`` sets parallelism).
        test_meta: ``{domain: [example_id, ...]}`` task metadata.
    """
    all_tasks = [
        (domain, eid)
        for domain, ids in test_meta.items()
        for eid in ids
    ]
    num_workers = cfg.execution.num_workers
    logger.info("Launching %d workers for %d tasks.", num_workers, len(all_tasks))

    with Manager() as manager:
        task_queue = manager.Queue()
        for item in all_tasks:
            task_queue.put(item)

        processes: List[Process] = []
        for i in range(num_workers):
            p = Process(
                target=_worker,
                args=(task_queue, cfg),
                name=f"Worker-{i + 1}",
                daemon=True,
            )
            p.start()
            processes.append(p)
            logger.info("Started %s (PID %d).", p.name, p.pid)

        try:
            while not task_queue.empty():
                for idx, p in enumerate(processes):
                    if not p.is_alive():
                        logger.warning("%s died -- restarting.", p.name)
                        new_p = Process(
                            target=_worker,
                            args=(task_queue, cfg),
                            name=f"Worker-Restart-{idx + 1}",
                            daemon=True,
                        )
                        new_p.start()
                        processes[idx] = new_p
                time.sleep(5)

            for p in processes:
                p.join(timeout=60)

        except KeyboardInterrupt:
            logger.info("Ctrl+C received -- terminating workers.")
            for p in processes:
                if p.is_alive():
                    p.terminate()
            time.sleep(2)
            for p in processes:
                if p.is_alive():
                    os.kill(p.pid, signal.SIGKILL)
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()

    logger.info("Parallel evaluation complete.")
