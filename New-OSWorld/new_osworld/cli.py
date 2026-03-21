"""Unified CLI entry point -- ``osworld`` or ``python -m new_osworld``.

All commands share a common set of flags loaded from config.yaml with
CLI overrides applied on top.
"""

from __future__ import annotations

import json
import os
import sys

import click
from rich.console import Console

from new_osworld import __version__

console = Console()


def _common_options(fn):
    """Decorator that adds shared CLI options to every command."""
    opts = [
        click.option("--config", "config_path", default=None, help="Path to config.yaml"),
        click.option("--provider", default=None, help="VM provider (docker, aws, vmware, ...)"),
        click.option("--region", default=None, help="Cloud region"),
        click.option("--path-to-vm", default=None, help="Path to VM image"),
        click.option("--model", default=None, help="LLM model name"),
        click.option("--action-space", default=None, help="pyautogui | computer_13"),
        click.option("--observation-type", default=None, help="screenshot | a11y_tree | screenshot_a11y_tree | som"),
        click.option("--max-steps", default=None, type=int, help="Max steps per task"),
        click.option("--result-dir", default=None, help="Results output directory"),
        click.option("--domain", default=None, help="Filter to a specific domain"),
        click.option("--num-workers", default=None, type=int, help="Parallel worker count"),
        click.option("--headless", is_flag=True, default=None, help="Run VMs headlessly"),
        click.option("--log-level", default=None, help="DEBUG | INFO | WARNING | ERROR"),
        click.option("--screen-width", default=None, type=int),
        click.option("--screen-height", default=None, type=int),
        click.option("--temperature", default=None, type=float),
        click.option("--top-p", default=None, type=float),
        click.option("--max-tokens", default=None, type=int),
        click.option("--client-password", default=None),
        click.option("--test-meta-path", default=None),
    ]
    for opt in reversed(opts):
        fn = opt(fn)
    return fn


def _load_cfg(ctx):
    """Load config and merge CLI overrides."""
    from new_osworld.config import load_config, merge_cli_overrides

    params = ctx.params
    cfg = load_config(params.pop("config_path", None))
    cfg = merge_cli_overrides(cfg, **params)
    return cfg


@click.group()
@click.version_option(__version__, prog_name="osworld")
def main():
    """New-OSWorld -- Desktop environment benchmark for multimodal AI agents."""


@main.command()
@_common_options
@click.pass_context
def evaluate(ctx, **kwargs):
    """Run the full evaluation benchmark."""
    cfg = _load_cfg(ctx)

    from new_osworld.logging_setup import setup_logging
    setup_logging(cfg.logging)

    from new_osworld.logging_setup import get_logger
    logger = get_logger("cli")

    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.makedirs("logs", exist_ok=True)

    args_path = os.path.join(
        cfg.evaluation.result_dir,
        cfg.environment.action_space,
        cfg.environment.observation_type,
        cfg.agent.model,
        "args.json",
    )
    os.makedirs(os.path.dirname(args_path), exist_ok=True)
    with open(args_path, "w", encoding="utf-8") as fh:
        json.dump(cfg.model_dump(), fh, indent=2)

    with open(cfg.evaluation.test_meta_path, "r", encoding="utf-8") as fh:
        test_meta = json.load(fh)

    if cfg.evaluation.domain != "all":
        test_meta = {cfg.evaluation.domain: test_meta[cfg.evaluation.domain]}

    from new_osworld.runner.batch import get_unfinished_tasks
    test_meta = get_unfinished_tasks(
        test_meta,
        cfg.evaluation.result_dir,
        cfg.environment.action_space,
        cfg.environment.observation_type,
        cfg.agent.model,
    )

    total = sum(len(v) for v in test_meta.values())
    console.print(f"[bold]Tasks remaining:[/] {total}")
    for domain, ids in test_meta.items():
        console.print(f"  {domain}: {len(ids)}")

    if total == 0:
        console.print("[green]All tasks already completed![/]")
        return

    if cfg.execution.num_workers > 1:
        from new_osworld.runner.parallel import run_parallel
        run_parallel(cfg, test_meta)
    else:
        from new_osworld.agents.prompt_agent import PromptAgent
        from new_osworld.environment.desktop_env import DesktopEnv
        from new_osworld.runner.batch import run_batch

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

        try:
            run_batch(cfg, agent, env, test_meta)
        finally:
            env.close()


@main.command()
@_common_options
@click.pass_context
def results(ctx, **kwargs):
    """Show evaluation results for a given configuration."""
    cfg = _load_cfg(ctx)

    from new_osworld.results.analyzer import show_results
    show_results(
        cfg.evaluation.result_dir,
        cfg.environment.action_space,
        cfg.environment.observation_type,
        cfg.agent.model,
    )


@main.command()
@_common_options
@click.argument("example_path")
@click.pass_context
def human(ctx, example_path, **kwargs):
    """Run a task with human-in-the-loop interaction."""
    import time as _time

    cfg = _load_cfg(ctx)

    from new_osworld.logging_setup import setup_logging
    setup_logging(cfg.logging)

    from new_osworld.environment.desktop_env import DesktopEnv

    with open(example_path, "r", encoding="utf-8") as fh:
        example = json.load(fh)

    env = DesktopEnv(
        provider_name=cfg.environment.provider,
        path_to_vm=cfg.environment.path_to_vm,
        action_space=cfg.environment.action_space,
        snapshot_name=cfg.environment.snapshot_name,
        region=cfg.environment.region,
    )

    try:
        env.reset(task_config=example)
        console.print(f"[bold green]Task:[/] {example['instruction']}")
        input("Press Enter to start human operation...")
        start = _time.time()
        input("Press Enter when finished...")
        elapsed = _time.time() - start
        console.print(f"[dim]Time elapsed: {elapsed:.2f}s[/]")

        score = env.evaluate()
        console.print(f"[bold]Score:[/] {score:.2f}")
    finally:
        env.close()


@main.command()
@_common_options
@click.option("--task-file", default=None, help="Path to a task meta JSON (domain -> [ids])")
@click.option("--sft-output", "sft_result_dir", default=None, help="SFT output directory (default: --result-dir or ./SFT)")
@click.option("--sleep-after", default=1.0, type=float, help="Sleep after each action")
@click.pass_context
def sft(ctx, task_file, sft_result_dir, sleep_after, **kwargs):
    """Interactive manual SFT data collection -- step through tasks and record actions."""
    import time as _time
    from pathlib import Path

    cfg = _load_cfg(ctx)

    if sft_result_dir is None:
        sft_result_dir = cfg.evaluation.result_dir if cfg.evaluation.result_dir != "./results" else "./SFT"

    from new_osworld.logging_setup import setup_logging
    setup_logging(cfg.logging)
    os.makedirs("logs", exist_ok=True)

    from new_osworld.environment.desktop_env import DesktopEnv
    from new_osworld.runner.manual import run_manual_example

    env = DesktopEnv(
        provider_name=cfg.environment.provider,
        path_to_vm=cfg.environment.path_to_vm,
        action_space=cfg.environment.action_space,
        headless=cfg.environment.headless,
        screen_size=(cfg.environment.screen_width, cfg.environment.screen_height),
        client_password=cfg.environment.client_password,
        require_a11y_tree=True,
    )

    if not task_file:
        default_manual = os.path.join(os.getcwd(), "manual_task.json")
        if os.path.isfile(default_manual):
            task_file = default_manual
            console.print(f"[dim]Using default task file:[/] {default_manual}")

    if task_file:
        with open(task_file, "r", encoding="utf-8") as fh:
            task_meta = json.load(fh)
    else:
        meta_path = cfg.evaluation.test_meta_path
        with open(meta_path, "r", encoding="utf-8") as fh:
            task_meta = json.load(fh)

    if cfg.evaluation.domain != "all":
        task_meta = {cfg.evaluation.domain: task_meta.get(cfg.evaluation.domain, [])}

    try:
        for domain, examples in task_meta.items():
            for example_id in examples:
                eid = example_id.replace(".json", "")
                config_path = Path(cfg.evaluation.test_config_base_dir) / "examples" / domain / f"{eid}.json"
                if not config_path.exists():
                    console.print(f"[red]Config not found:[/] {config_path}")
                    continue

                with open(config_path, "r", encoding="utf-8") as fh:
                    example = json.load(fh)

                example_dir = os.path.join(sft_result_dir, domain, eid)
                console.print(f"\n[bold cyan]Task:[/] {domain}/{eid}")

                run_manual_example(
                    env=env,
                    task_config=example,
                    max_steps=cfg.evaluation.max_steps,
                    instruction=example["instruction"],
                    result_dir=example_dir,
                    sleep_after=sleep_after,
                )
    finally:
        env.close()
        console.print("[bold green]Environment closed.[/]")


@main.command("start-vm")
@_common_options
@click.pass_context
def start_vm(ctx, **kwargs):
    """Download the VM image (if needed) and start it.

    This is the equivalent of the old ``python Turing_tooling/run_manual.py --provider_name vmware``
    command.  It downloads ~12 GB, extracts the VM, boots it, waits for the
    server to be ready, and keeps it running until you press Ctrl+C.
    """
    cfg = _load_cfg(ctx)

    from new_osworld.logging_setup import setup_logging
    setup_logging(cfg.logging)
    os.makedirs("logs", exist_ok=True)

    from new_osworld.logging_setup import get_logger
    logger = get_logger("cli")

    from new_osworld.environment.desktop_env import DesktopEnv

    console.print(f"[bold]Provider:[/] {cfg.environment.provider}")
    console.print(f"[bold]OS type:[/]  {cfg.environment.os_type}")
    console.print("")
    console.print("[dim]This will download the VM image (~12 GB) if not already cached.[/]")
    console.print("[dim]The VM will start locally.  Press Ctrl+C to shut down.[/]\n")

    env = DesktopEnv(
        provider_name=cfg.environment.provider,
        path_to_vm=cfg.environment.path_to_vm,
        action_space=cfg.environment.action_space,
        headless=cfg.environment.headless,
        screen_size=(cfg.environment.screen_width, cfg.environment.screen_height),
        client_password=cfg.environment.client_password,
        os_type=cfg.environment.os_type,
        require_a11y_tree=False,
    )

    console.print("[bold green]VM is running![/]")
    console.print(f"  VM IP:       [cyan]{env.vm_ip}[/]")
    console.print(f"  Server port: [cyan]{env.server_port}[/]")
    console.print(f"  VM path:     [cyan]{env.path_to_vm}[/]")
    console.print("")
    console.print("[dim]You can now proceed with task creation.[/]")
    console.print("[dim]Press Ctrl+C to shut down the VM.[/]")

    try:
        import time as _time
        while True:
            _time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down VM ...[/]")
        env.close()
        console.print("[bold green]VM stopped.[/]")


# =====================================================================
# Tech Tooling commands
# =====================================================================

@main.command("convert-trajectory")
@click.argument("trajectory_path")
@click.option("--task-config", default=None, help="Path to task config JSON")
@click.option("--instruction", default="Complete the given task", help="Task instruction")
@click.option("--output-dir", default=None, help="Output directory for the notebook")
def convert_trajectory(trajectory_path, task_config, instruction, output_dir):
    """Convert a trajectory.jsonl file into an SFT notebook."""
    from new_osworld.tech_tooling.trajectory_converter import convert
    convert(trajectory_path, task_config, instruction, output_dir)


@main.command("validate")
@click.argument("delivery_dir")
@click.option("--task-json", default=None, help="Explicit path to the task JSON file")
def validate_delivery(delivery_dir, task_json):
    """Validate a task delivery against the OSWorld schema and conventions."""
    from new_osworld.tech_tooling.delivery_validator import validate_delivery as _validate
    report = _validate(delivery_dir, task_json)
    report.display()
    if not report.passed:
        raise SystemExit(1)


@main.command("replay")
@_common_options
@click.argument("trajectory_path")
@click.option("--task-config", "replay_task_config", required=True, help="Path to task config JSON")
@click.option("--stop-on-error", is_flag=True, help="Stop on first VM error")
@click.option("--post-replay-sleep", default=5.0, type=float, help="Wait before evaluation")
@click.option("--env-retries", default=3, type=int, help="Environment reset retries")
@click.pass_context
def replay_trajectory(ctx, trajectory_path, replay_task_config, stop_on_error, post_replay_sleep, env_retries, **kwargs):
    """Replay a trajectory.jsonl in the VM and run the evaluator."""
    cfg = _load_cfg(ctx)

    from new_osworld.logging_setup import setup_logging
    setup_logging(cfg.logging)
    os.makedirs("logs", exist_ok=True)

    from new_osworld.tech_tooling.trajectory_replayer import replay_and_evaluate
    summary = replay_and_evaluate(
        trajectory_path=trajectory_path,
        task_config_path=replay_task_config,
        provider=cfg.environment.provider,
        path_to_vm=cfg.environment.path_to_vm,
        headless=cfg.environment.headless,
        client_password=cfg.environment.client_password,
        screen_width=cfg.environment.screen_width,
        screen_height=cfg.environment.screen_height,
        sleep_after=cfg.evaluation.sleep_after_execution or 0.2,
        max_steps=cfg.evaluation.max_steps,
        post_replay_sleep=post_replay_sleep,
        stop_on_error=stop_on_error,
        env_retries=env_retries,
    )
    score = summary.get("evaluation_score")
    if score is not None and score < 1.0:
        console.print(f"[yellow]Warning: score {score} < 1.0[/]")


@main.command()
def info():
    """Show version and configuration info."""
    console.print(f"[bold]New-OSWorld[/] v{__version__}")
    console.print(f"Python: {sys.version}")

    from new_osworld.config import load_config
    cfg = load_config()
    console.print(f"Provider: {cfg.environment.provider}")
    console.print(f"Model: {cfg.agent.model}")
    console.print(f"Action space: {cfg.environment.action_space}")
    console.print(f"Observation: {cfg.environment.observation_type}")


if __name__ == "__main__":
    main()
