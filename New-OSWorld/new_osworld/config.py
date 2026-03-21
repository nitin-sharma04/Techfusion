"""Unified configuration management via Pydantic models and YAML loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class EnvironmentConfig(BaseModel):
    """Configuration for the desktop VM environment."""

    provider: str = "docker"
    region: str = "us-east-1"
    path_to_vm: Optional[str] = None
    snapshot_name: str = "init_state"
    action_space: str = "pyautogui"
    observation_type: str = "screenshot"
    screen_width: int = 1920
    screen_height: int = 1080
    headless: bool = False
    require_a11y_tree: bool = True
    require_terminal: bool = False
    os_type: str = "Ubuntu"
    enable_proxy: bool = False
    client_password: str = ""
    cache_dir: str = "cache"


class AgentConfig(BaseModel):
    """Configuration for the LLM agent."""

    model: str = "gpt-4o"
    temperature: float = 1.0
    top_p: float = 0.9
    max_tokens: int = 1500
    max_trajectory_length: int = 3
    a11y_tree_max_tokens: int = 10000
    platform: str = "ubuntu"


class EvaluationConfig(BaseModel):
    """Configuration for evaluation / benchmark runs."""

    test_config_base_dir: str = "evaluation_examples"
    test_meta_path: str = "evaluation_examples/test_all.json"
    domain: str = "all"
    max_steps: int = 15
    sleep_after_execution: float = 0.0
    result_dir: str = "./results"


class ExecutionConfig(BaseModel):
    """Configuration for parallel execution."""

    num_workers: int = 1
    retry_limit: int = 5
    retry_interval: int = 5


class LoggingConfig(BaseModel):
    """Configuration for the logging subsystem."""

    level: str = "INFO"
    log_dir: str = "logs"
    colored_output: bool = True


class AppConfig(BaseModel):
    """Top-level application configuration."""

    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


_CONFIG_SEARCH_PATHS = [
    Path("config.yaml"),
    Path("config.yml"),
    Path.home() / ".osworld" / "config.yaml",
]


def _find_config_file() -> Optional[Path]:
    """Walk the search paths and return the first config file that exists."""
    env_path = os.environ.get("OSWORLD_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
    for p in _CONFIG_SEARCH_PATHS:
        if p.is_file():
            return p
    return None


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load configuration from a YAML file, falling back to defaults.

    Args:
        path: Explicit path to a YAML config file.  When *None* the usual
              search locations are tried (``$OSWORLD_CONFIG``, ``./config.yaml``,
              ``~/.osworld/config.yaml``).

    Returns:
        A fully-validated :class:`AppConfig` instance.
    """
    config_path = Path(path) if path else _find_config_file()
    if config_path and config_path.is_file():
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return AppConfig(**raw)
    return AppConfig()


def merge_cli_overrides(cfg: AppConfig, **overrides) -> AppConfig:
    """Apply CLI flag overrides on top of the loaded config.

    Only non-``None`` values in *overrides* take effect.  Keys use dotted
    notation mapped to flat CLI names (e.g. ``model`` -> ``agent.model``).
    """
    flat_map = {
        "provider": ("environment", "provider"),
        "provider_name": ("environment", "provider"),
        "region": ("environment", "region"),
        "path_to_vm": ("environment", "path_to_vm"),
        "snapshot_name": ("environment", "snapshot_name"),
        "action_space": ("environment", "action_space"),
        "observation_type": ("environment", "observation_type"),
        "screen_width": ("environment", "screen_width"),
        "screen_height": ("environment", "screen_height"),
        "headless": ("environment", "headless"),
        "os_type": ("environment", "os_type"),
        "enable_proxy": ("environment", "enable_proxy"),
        "client_password": ("environment", "client_password"),
        "cache_dir": ("environment", "cache_dir"),
        "model": ("agent", "model"),
        "temperature": ("agent", "temperature"),
        "top_p": ("agent", "top_p"),
        "max_tokens": ("agent", "max_tokens"),
        "max_trajectory_length": ("agent", "max_trajectory_length"),
        "platform": ("agent", "platform"),
        "test_config_base_dir": ("evaluation", "test_config_base_dir"),
        "test_meta_path": ("evaluation", "test_meta_path"),
        "domain": ("evaluation", "domain"),
        "max_steps": ("evaluation", "max_steps"),
        "sleep_after_execution": ("evaluation", "sleep_after_execution"),
        "result_dir": ("evaluation", "result_dir"),
        "num_workers": ("execution", "num_workers"),
        "log_level": ("logging", "level"),
    }

    data = cfg.model_dump()
    for key, value in overrides.items():
        if value is None:
            continue
        if key in flat_map:
            section, field = flat_map[key]
            data[section][field] = value

    return AppConfig(**data)
