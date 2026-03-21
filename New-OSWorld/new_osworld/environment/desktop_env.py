"""Core desktop environment -- OpenAI Gym-compatible wrapper around virtualised desktops."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import gymnasium as gym

from new_osworld.environment.actions import is_special_action
from new_osworld.environment.controllers.python_controller import PythonController
from new_osworld.environment.providers import create_provider
from new_osworld.logging_setup import get_logger

logger = get_logger("env")

MAX_SETUP_RETRIES = 5

Metric = Callable[..., float]
Getter = Callable[..., Any]


def _fix_pyautogui_less_than(command: str) -> str:
    """Work around the PyAutoGUI bug where ``<`` types ``>`` instead.

    Converts ``press('<')`` to ``hotkey("shift", ",")`` and splits
    ``typewrite()`` calls containing ``<``.

    See:
        - https://github.com/asweigart/pyautogui/issues/198
        - https://github.com/xlang-ai/OSWorld/issues/257
    """
    press_pat = r'pyautogui\.press\(["\'](?:<|\\u003c)["\']\)'
    command = re.sub(press_pat, 'pyautogui.hotkey("shift", ",")', command)

    typewrite_pat = r'pyautogui\.typewrite\((["\'])(.*?)\1\)'

    def _process_typewrite(match: re.Match) -> str:
        q = match.group(1)
        content = match.group(2)
        try:
            content = content.encode("utf-8").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        if "<" not in content:
            return match.group(0)
        parts = content.split("<")
        result: list[str] = []
        for i, part in enumerate(parts):
            if i > 0:
                result.append('pyautogui.hotkey("shift", ",")')
            if part:
                result.append(f"pyautogui.typewrite({q}{part}{q})")
        return "; ".join(result)

    return re.sub(typewrite_pat, _process_typewrite, command)


class DesktopEnv(gym.Env):
    """Gymnasium-compatible desktop environment.

    Manages a virtual machine through one of the supported providers,
    exposes screenshots / a11y trees as observations, and executes
    actions via pyautogui or a structured action dictionary.
    """

    VALID_ACTION_SPACES = ("computer_13", "pyautogui", "claude_computer_use")
    CLOUD_PROVIDERS = frozenset({"docker", "aws", "gcp", "azure", "aliyun", "volcengine"})
    LOCAL_PROVIDERS = frozenset({"vmware", "virtualbox"})

    def __init__(
        self,
        provider_name: str = "docker",
        region: Optional[str] = None,
        path_to_vm: Optional[str] = None,
        snapshot_name: str = "init_state",
        action_space: str = "pyautogui",
        cache_dir: str = "cache",
        screen_size: Tuple[int, int] = (1920, 1080),
        headless: bool = False,
        require_a11y_tree: bool = True,
        require_terminal: bool = False,
        os_type: str = "Ubuntu",
        enable_proxy: bool = False,
        client_password: str = "",
    ) -> None:
        if action_space not in self.VALID_ACTION_SPACES:
            raise ValueError(
                f"action_space must be one of {self.VALID_ACTION_SPACES}, got '{action_space}'"
            )

        self.provider_name = provider_name.lower().strip()
        self.region = region
        self.enable_proxy = enable_proxy
        self.current_use_proxy = False
        self.os_type = os_type

        if not client_password:
            self.client_password = (
                "osworld-public-evaluation" if self.provider_name == "aws" else "password"
            )
        else:
            self.client_password = client_password

        self.screen_width, self.screen_height = screen_size
        self.server_port = 5000
        self.chromium_port = 9222
        self.vnc_port = 8006
        self.vlc_port = 8080

        self.manager, self.provider = create_provider(self.provider_name, region)

        if self.provider_name in self.CLOUD_PROVIDERS:
            self._environment_dirty = False
        elif self.provider_name in self.LOCAL_PROVIDERS:
            self._environment_dirty = True
        else:
            raise ValueError(f"Unknown provider: {self.provider_name}")

        if path_to_vm:
            self.path_to_vm = (
                os.path.abspath(os.path.expandvars(os.path.expanduser(path_to_vm)))
                if self.provider_name in self.LOCAL_PROVIDERS
                else path_to_vm
            )
        else:
            raw_path = self.manager.get_vm_path(
                os_type=self.os_type,
                region=region,
                screen_size=(self.screen_width, self.screen_height),
            )
            self.path_to_vm = (
                os.path.abspath(raw_path)
                if self.provider_name in self.LOCAL_PROVIDERS
                else raw_path
            )

        self.snapshot_name = snapshot_name
        self.cache_dir_base = cache_dir
        self.headless = headless
        self.require_a11y_tree = require_a11y_tree
        self.require_terminal = require_terminal
        self.action_space_name = action_space

        self.instruction: Optional[str] = None
        self._traj_no: int = -1
        self._step_no: int = 0
        self.action_history: List[Dict[str, Any]] = []

        try:
            logger.info("Initialising desktop environment (%s) ...", self.provider_name)
            self._start_emulator()
        except Exception:
            logger.exception("Failed to initialise DesktopEnv -- cleaning up.")
            try:
                self.close()
                self.manager.delete_vm(self.path_to_vm, self.region)
            except Exception:
                logger.exception("Cleanup after failed init also failed.")
            raise

    # ------------------------------------------------------------------
    # Emulator lifecycle
    # ------------------------------------------------------------------

    def _start_emulator(self) -> None:
        """Boot the VM and create controller objects."""
        self.provider.start_emulator(self.path_to_vm, self.headless, self.os_type)

        ip_parts = self.provider.get_ip_address(self.path_to_vm).split(":")
        self.vm_ip = ip_parts[0]
        if len(ip_parts) > 1:
            self.server_port = int(ip_parts[1])
            self.chromium_port = int(ip_parts[2])
            self.vnc_port = int(ip_parts[3])
            self.vlc_port = int(ip_parts[4])

        self.controller = PythonController(vm_ip=self.vm_ip, server_port=self.server_port)
        # SetupController is imported lazily -- it depends on heavy optional deps
        from new_osworld.environment.controllers.setup_controller import SetupController

        self.setup_controller = SetupController(
            vm_ip=self.vm_ip,
            server_port=self.server_port,
            chromium_port=self.chromium_port,
            vlc_port=self.vlc_port,
            cache_dir=self.cache_dir_base,
            client_password=self.client_password,
            screen_width=self.screen_width,
            screen_height=self.screen_height,
        )

    def _revert_to_snapshot(self) -> None:
        snapshot = self.snapshot_name or "init_state"
        logger.info("Reverting to snapshot: %s", snapshot)
        new_path = self.provider.revert_to_snapshot(self.path_to_vm, snapshot)
        if new_path:
            self.path_to_vm = new_path

    def close(self) -> None:
        """Shut down the virtual machine."""
        self.provider.stop_emulator(self.path_to_vm)

    # ------------------------------------------------------------------
    # Gym interface
    # ------------------------------------------------------------------

    def reset(
        self,
        task_config: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Reset the environment, optionally loading a new task.

        Args:
            task_config: A task JSON dict.  When provided the VM is set up
                according to its ``config`` key, and the evaluator is prepared.
            seed: Unused (kept for Gym compatibility).
            options: Unused.

        Returns:
            The initial observation dict.
        """
        logger.info("Resetting environment ...")
        self._traj_no += 1
        self._step_no = 0
        self.action_history.clear()

        for attempt in range(1, MAX_SETUP_RETRIES + 1):
            if task_config is not None:
                task_wants_proxy = task_config.get("proxy", False) and self.enable_proxy
                if not self.enable_proxy and task_config.get("proxy", False):
                    logger.info("Task wants proxy but proxy is disabled system-wide; ignoring.")
                self.current_use_proxy = task_wants_proxy

            if self._environment_dirty:
                logger.info("Environment is dirty -- reverting to snapshot.")
                self._revert_to_snapshot()
                self._start_emulator()
                self._environment_dirty = False
            else:
                logger.info("Environment is clean (provider=%s), skipping revert.", self.provider_name)

            if task_config is not None:
                if task_config.get("proxy", False) and self.enable_proxy:
                    self.setup_controller._proxy_setup(self.client_password)
                self._load_task(task_config)
                self.setup_controller.reset_cache_dir(self.cache_dir)
                logger.info("Running task setup (attempt %d/%d) ...", attempt, MAX_SETUP_RETRIES)
                success = self.setup_controller.setup(
                    self.config,
                    task_config.get("proxy", False) and self.enable_proxy,
                )
                if success:
                    if self.config:
                        self._environment_dirty = True
                    break
                logger.error("Setup failed (attempt %d/%d).", attempt, MAX_SETUP_RETRIES)
                time.sleep(5)
            else:
                break

        logger.info("Environment reset complete.")
        return self._get_obs()

    def step(self, action: Any, pause: float = 2.0) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Execute an action and return ``(observation, reward, done, info)``.

        Args:
            action: A pyautogui command string, structured action dict, or
                one of ``"WAIT"``/``"FAIL"``/``"DONE"``.
            pause: Seconds to sleep after execution.
        """
        self._step_no += 1
        self.action_history.append(action)
        self._environment_dirty = True

        reward = 0.0
        done = False
        info: Dict[str, Any] = {}

        logger.info("Step %d (traj %d): %s", self._step_no, self._traj_no, action)

        if is_special_action(action):
            act_name = action if isinstance(action, str) else action.get("action_type", "")
            if act_name == "WAIT":
                time.sleep(pause)
            elif act_name == "FAIL":
                done = True
                info["fail"] = True
            elif act_name == "DONE":
                done = True
                info["done"] = True
        elif self.action_space_name == "computer_13":
            self.controller.execute_action(action)
        elif self.action_space_name in ("pyautogui", "claude_computer_use"):
            if action is None:
                pass
            elif isinstance(action, str):
                fixed = _fix_pyautogui_less_than(action)
                self.controller.execute_python_command(fixed)
            elif isinstance(action, dict):
                cmd = action.get("command", "")
                fixed = _fix_pyautogui_less_than(cmd)
                self.controller.execute_python_command(fixed)

        time.sleep(pause)
        return self._get_obs(), reward, done, info

    def evaluate(self) -> float:
        """Run the task evaluator and return a score in ``[0, 1]``."""
        postconfig = self.evaluator.get("postconfig", [])
        self.setup_controller.setup(postconfig)
        if postconfig:
            self._environment_dirty = True

        if self.evaluator["func"] == "infeasible":
            return 1.0 if self.action_history and self.action_history[-1] == "FAIL" else 0.0

        if self.action_history and self.action_history[-1] == "FAIL":
            return 0.0

        if isinstance(self.metric, list):
            return self._evaluate_multi()
        return self._evaluate_single()

    def render(self, mode: str = "rgb_array") -> bytes:
        """Capture a screenshot for rendering."""
        if mode == "rgb_array":
            return self.controller.get_screenshot()
        raise ValueError(f"Unsupported render mode: {mode}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_obs(self) -> Dict[str, Any]:
        return {
            "screenshot": self.controller.get_screenshot(),
            "accessibility_tree": (
                self.controller.get_accessibility_tree() if self.require_a11y_tree else None
            ),
            "terminal": (
                self.controller.get_terminal_output() if self.require_terminal else None
            ),
            "instruction": self.instruction,
        }

    @property
    def vm_platform(self) -> str:
        return self.controller.get_vm_platform()

    @property
    def vm_screen_size(self) -> Optional[Dict[str, Any]]:
        return self.controller.get_vm_screen_size()

    def _load_task(self, task_config: Dict[str, Any]) -> None:
        """Parse a task JSON and store evaluator state."""
        self.task_id = task_config["id"]
        self.cache_dir = os.path.join(self.cache_dir_base, self.task_id)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.instruction = task_config["instruction"]
        self.config = task_config.get("config", [])
        self._load_evaluator(task_config)

    def _load_evaluator(self, task_config: Dict[str, Any]) -> None:
        """Prepare metric / getter callables from the evaluator section."""
        from new_osworld.environment.evaluators import metrics, getters

        ev = task_config["evaluator"]
        self.evaluator = ev

        func_spec = ev["func"]
        if isinstance(func_spec, list):
            self.metric = [getattr(metrics, f) for f in func_spec]
        else:
            self.metric = getattr(metrics, func_spec)

        self.metric_conj = ev.get("conj", "and")

        def _make_getters(key: str) -> Any:
            if key not in ev or not ev[key]:
                return [None] * len(self.metric) if isinstance(self.metric, list) else None
            spec = ev[key]
            if isinstance(spec, list):
                return [
                    getattr(getters, f"get_{s['type']}") if s else None for s in spec
                ]
            return getattr(getters, f"get_{spec['type']}")

        self.result_getter = _make_getters("result")
        self.expected_getter = _make_getters("expected")

        opt_spec = ev.get("options", {})
        if isinstance(opt_spec, list):
            self.metric_options = [o if o else {} for o in opt_spec]
        elif isinstance(opt_spec, dict):
            self.metric_options = opt_spec
        else:
            self.metric_options = [{}] * len(self.metric) if isinstance(self.metric, list) else {}

    def _evaluate_single(self) -> float:
        try:
            result_state = self.result_getter(self, self.evaluator["result"])
        except FileNotFoundError:
            logger.error("Evaluator result file not found.")
            return 0.0

        if (
            "expected" in self.evaluator
            and self.expected_getter
            and self.evaluator["expected"]
        ):
            expected_state = self.expected_getter(self, self.evaluator["expected"])
            return float(self.metric(result_state, expected_state, **self.metric_options))
        return float(self.metric(result_state, **self.metric_options))

    def _evaluate_multi(self) -> float:
        results: List[float] = []
        for idx, metric_fn in enumerate(self.metric):
            try:
                result_state = self.result_getter[idx](self, self.evaluator["result"][idx])
            except FileNotFoundError:
                logger.error("Evaluator result file not found for metric %d.", idx)
                if self.metric_conj == "and":
                    return 0.0
                continue

            if (
                "expected" in self.evaluator
                and self.expected_getter
                and self.evaluator["expected"]
            ):
                expected = self.expected_getter[idx]
                if expected:
                    exp_state = expected(self, self.evaluator["expected"][idx])
                    score = float(metric_fn(result_state, exp_state, **self.metric_options[idx]))
                else:
                    score = float(metric_fn(result_state, **self.metric_options[idx]))
            else:
                score = float(metric_fn(result_state, **self.metric_options[idx]))

            if self.metric_conj == "and" and score == 0.0:
                return 0.0
            if self.metric_conj == "or" and score == 1.0:
                return 1.0
            results.append(score)

        if not results:
            return 0.0
        return sum(results) / len(results) if self.metric_conj == "and" else max(results)
