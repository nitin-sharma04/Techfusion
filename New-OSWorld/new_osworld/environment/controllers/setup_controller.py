"""Setup controller -- delegates to the original OSWorld-SFT SetupController.

The original SetupController has ~800 lines of setup methods (_launch_setup,
_execute_setup, _download_setup, etc.) that call specific VM server endpoints
like /setup/launch, /setup/open_file, /setup/upload, etc.

We import it directly from the old repo when available, falling back to a
minimal implementation that handles basic cases.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import requests

from new_osworld.logging_setup import get_logger

logger = get_logger("setup_controller")

_OLD_REPO = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "OSWorld-SFT")
)


def _try_import_original():
    """Attempt to import the full SetupController from OSWorld-SFT."""
    if os.path.isdir(_OLD_REPO) and _OLD_REPO not in sys.path:
        sys.path.insert(0, _OLD_REPO)
    try:
        from desktop_env.controllers.setup import SetupController as _OriginalSetupController
        return _OriginalSetupController
    except ImportError:
        return None


_OriginalSetupController = _try_import_original()

if _OriginalSetupController is not None:
    SetupController = _OriginalSetupController
    logger.debug("Using original OSWorld-SFT SetupController.")
else:
    logger.debug("OSWorld-SFT not found; using minimal fallback SetupController.")

    class SetupController:
        """Minimal fallback when the original OSWorld-SFT repo isn't available.

        Handles the most common setup step types by calling the correct
        VM server endpoints (``/setup/launch``, ``/setup/open_file``, etc.).
        """

        MAX_RETRIES = 20

        def __init__(
            self,
            vm_ip: str,
            server_port: int = 5000,
            chromium_port: int = 9222,
            vlc_port: int = 8080,
            cache_dir: str = "cache",
            client_password: str = "password",
            screen_width: int = 1920,
            screen_height: int = 1080,
        ) -> None:
            self.vm_ip = vm_ip
            self.server_port = server_port
            self.chromium_port = chromium_port
            self.vlc_port = vlc_port
            self.http_server = f"http://{vm_ip}:{server_port}"
            self.cache_dir = cache_dir
            self.use_proxy = False
            self.client_password = client_password
            self.screen_width = screen_width
            self.screen_height = screen_height

        def reset_cache_dir(self, cache_dir: str) -> None:
            self.cache_dir = cache_dir
            os.makedirs(cache_dir, exist_ok=True)

        def setup(self, config_steps: List[Dict[str, Any]], use_proxy: bool = False) -> bool:
            """Execute setup steps by dispatching to ``_{type}_setup`` methods."""
            if not config_steps:
                return True

            self.use_proxy = use_proxy

            retry = 0
            while retry < self.MAX_RETRIES:
                try:
                    requests.get(self.http_server + "/terminal", timeout=10)
                    break
                except Exception:
                    time.sleep(5)
                    retry += 1
            if retry >= self.MAX_RETRIES:
                logger.error("Cannot connect to VM server after %d retries.", self.MAX_RETRIES)
                return False

            for i, cfg in enumerate(config_steps):
                config_type = cfg.get("type", "")
                parameters = cfg.get("parameters", {})
                setup_fn = f"_{config_type}_setup"

                if hasattr(self, setup_fn):
                    try:
                        logger.info("Setup step %d/%d: %s", i + 1, len(config_steps), setup_fn)
                        getattr(self, setup_fn)(**parameters)
                    except Exception as exc:
                        logger.error("Setup step %s failed: %s", setup_fn, exc)
                        return False
                else:
                    logger.warning("Unknown setup type '%s' -- skipping.", config_type)

            return True

        def _launch_setup(self, command, shell: bool = False, **kw) -> None:
            if isinstance(command, str) and not shell and len(command.split()) > 1:
                command = command.split()
            payload = json.dumps({"command": command, "shell": shell})
            resp = requests.post(
                self.http_server + "/setup/launch",
                headers={"Content-Type": "application/json"},
                data=payload, timeout=120,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"launch failed (HTTP {resp.status_code}): {resp.text}")

        def _execute_setup(self, command, shell: bool = True, **kw) -> None:
            if isinstance(command, list):
                command = " ".join(command)
            payload = json.dumps({"command": command if isinstance(command, list) else command.split(), "shell": shell})
            resp = requests.post(
                self.http_server + "/execute",
                headers={"Content-Type": "application/json"},
                data=payload, timeout=120,
            )
            if resp.status_code != 200:
                logger.warning("execute returned HTTP %d", resp.status_code)

        def _command_setup(self, command, shell: bool = True, **kw) -> None:
            self._execute_setup(command=command, shell=shell)

        def _open_setup(self, path: str, **kw) -> None:
            payload = json.dumps({"path": path})
            resp = requests.post(
                self.http_server + "/setup/open_file",
                headers={"Content-Type": "application/json"},
                data=payload, timeout=1810,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"open failed: {resp.text}")

        def _sleep_setup(self, seconds: float = 5, **kw) -> None:
            time.sleep(seconds)

        def _activate_window_setup(self, window_name: str = "", **kw) -> None:
            pass

        def _chrome_open_tabs_setup(self, urls: list = None, **kw) -> None:
            if urls:
                for url in urls:
                    cmd = f'DISPLAY=:1 google-chrome "{url}" &'
                    self._execute_setup(command=cmd, shell=True)
                    time.sleep(2)

        def _chrome_close_tabs_setup(self, **kw) -> None:
            pass

        def _download_setup(self, files: list = None, **kw) -> None:
            logger.warning("download_setup requires full SetupController from OSWorld-SFT.")

        def _proxy_setup(self, password: str = "", **kw) -> None:
            pass
