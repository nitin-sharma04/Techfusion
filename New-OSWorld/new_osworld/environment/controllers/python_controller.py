"""HTTP-based controller that drives pyautogui / shell commands inside the VM."""

from __future__ import annotations

import json
import time
import random
import traceback
from typing import Any, Dict, List, Optional

import requests

from new_osworld.environment.actions import KEYBOARD_KEYS
from new_osworld.logging_setup import get_logger

logger = get_logger("controller")


class PythonController:
    """Communicates with the osworld HTTP server running inside the VM.

    Every public method retries up to *retry_times* on transient failures.

    Args:
        vm_ip: IP address of the guest VM.
        server_port: Port the HTTP server listens on.
        retry_times: Maximum number of retry attempts per request.
        retry_interval: Seconds to wait between retries.
    """

    _PYAUTOGUI_PREFIX = (
        "import pyautogui; import time; pyautogui.FAILSAFE = False; {command}"
    )

    def __init__(
        self,
        vm_ip: str,
        server_port: int = 5000,
        retry_times: int = 5,
        retry_interval: float = 5.0,
    ) -> None:
        self.vm_ip = vm_ip
        self.base_url = f"http://{vm_ip}:{server_port}"
        self.retry_times = retry_times
        self.retry_interval = retry_interval
        self._recording_active = False

    # ------------------------------------------------------------------
    # Observation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_image(content_type: str, data: Optional[bytes]) -> bool:
        """Verify the payload looks like a real PNG or JPEG."""
        if not isinstance(data, (bytes, bytearray)) or not data:
            return False
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return True
        if content_type and any(
            t in content_type for t in ("image/png", "image/jpeg", "image/jpg")
        ):
            return True
        return False

    def _retry_request(
        self,
        method: str,
        endpoint: str,
        *,
        description: str = "request",
        timeout: Any = 20,
        **kwargs: Any,
    ) -> Optional[requests.Response]:
        """Issue an HTTP request with automatic retries.

        Returns the :class:`requests.Response` on success or *None* after
        exhausting all retries.
        """
        url = self.base_url + endpoint
        for attempt in range(1, self.retry_times + 1):
            try:
                resp = requests.request(method, url, timeout=timeout, **kwargs)
                if resp.status_code == 200:
                    return resp
                logger.error(
                    "%s failed (HTTP %d, attempt %d/%d).",
                    description, resp.status_code, attempt, self.retry_times,
                )
            except requests.exceptions.ReadTimeout:
                logger.error(
                    "%s timed out (attempt %d/%d).",
                    description, attempt, self.retry_times,
                )
                if method.upper() == "POST":
                    return None
            except requests.RequestException as exc:
                logger.error(
                    "%s error (attempt %d/%d): %s",
                    description, attempt, self.retry_times, exc,
                )
            time.sleep(self.retry_interval)

        logger.error("%s failed after %d attempts.", description, self.retry_times)
        return None

    def get_screenshot(self) -> Optional[bytes]:
        """Capture a screenshot (with cursor) from the VM.

        Returns:
            Raw PNG bytes, or *None* on failure.
        """
        for attempt in range(1, self.retry_times + 1):
            try:
                resp = requests.get(self.base_url + "/screenshot", timeout=20)
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if self._is_valid_image(ct, resp.content):
                        logger.info("Screenshot captured successfully.")
                        return resp.content
                    logger.error(
                        "Invalid screenshot payload (attempt %d/%d).",
                        attempt, self.retry_times,
                    )
                else:
                    logger.error(
                        "Screenshot HTTP %d (attempt %d/%d).",
                        resp.status_code, attempt, self.retry_times,
                    )
            except requests.RequestException as exc:
                logger.error("Screenshot error (attempt %d/%d): %s", attempt, self.retry_times, exc)
            time.sleep(self.retry_interval)
        return None

    def get_accessibility_tree(self, timeout: int = 120) -> Optional[str]:
        """Fetch the accessibility tree XML from the VM.

        Uses a longer timeout than other requests because large pages
        (Chrome with many tabs, LibreOffice documents) can produce trees
        with thousands of elements that take time to serialize.

        Args:
            timeout: Read timeout in seconds (default 120s for large trees).

        Returns:
            The AT-SPI XML string, or *None* on failure.
        """
        for attempt in range(1, self.retry_times + 1):
            try:
                resp = requests.get(
                    self.base_url + "/accessibility",
                    timeout=(10, timeout),
                )
                if resp.status_code == 200:
                    tree = resp.json().get("AT", "")
                    if tree and len(tree) > 100:
                        logger.info(
                            "Accessibility tree captured (%d chars, attempt %d).",
                            len(tree), attempt,
                        )
                        return tree
                    logger.warning(
                        "Accessibility tree too small (%d chars, attempt %d/%d) -- retrying.",
                        len(tree), attempt, self.retry_times,
                    )
                else:
                    logger.error(
                        "Accessibility tree HTTP %d (attempt %d/%d).",
                        resp.status_code, attempt, self.retry_times,
                    )
            except requests.exceptions.ReadTimeout:
                logger.error(
                    "Accessibility tree timed out after %ds (attempt %d/%d).",
                    timeout, attempt, self.retry_times,
                )
            except requests.RequestException as exc:
                logger.error(
                    "Accessibility tree error (attempt %d/%d): %s",
                    attempt, self.retry_times, exc,
                )
            time.sleep(self.retry_interval)

        logger.error("Failed to get accessibility tree after %d attempts.", self.retry_times)
        return None

    def get_terminal_output(self) -> Optional[str]:
        """Retrieve terminal output from the VM."""
        resp = self._retry_request("GET", "/terminal", description="Terminal output")
        if resp is not None:
            return resp.json().get("output")
        return None

    def get_file(self, file_path: str) -> Optional[bytes]:
        """Download a file from the VM."""
        resp = self._retry_request(
            "POST", "/file",
            description=f"File download ({file_path})",
            data={"file_path": file_path},
        )
        return resp.content if resp is not None else None

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def execute_python_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Run a one-liner Python command on the VM (typically pyautogui)."""
        full_cmd = self._PYAUTOGUI_PREFIX.format(command=command)
        payload = json.dumps({"command": ["python", "-c", full_cmd], "shell": False})
        resp = self._retry_request(
            "POST", "/execute",
            description="Python command",
            headers={"Content-Type": "application/json"},
            data=payload,
            timeout=90,
        )
        if resp is not None:
            return resp.json()
        return None

    def run_python_script(self, script: str) -> Dict[str, Any]:
        """Execute an arbitrary Python script on the VM."""
        payload = json.dumps({"code": script})
        resp = self._retry_request(
            "POST", "/run_python",
            description="Python script",
            headers={"Content-Type": "application/json"},
            data=payload,
            timeout=90,
        )
        if resp is not None:
            return resp.json()
        return {"status": "error", "output": "", "error": "Retry limit reached."}

    def run_bash_script(
        self,
        script: str,
        timeout: int = 30,
        working_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a bash script on the VM.

        Args:
            script: Shell script content.
            timeout: Execution timeout in seconds.
            working_dir: Working directory inside the VM.
        """
        payload = json.dumps(
            {"script": script, "timeout": timeout, "working_dir": working_dir}
        )
        resp = self._retry_request(
            "POST", "/run_bash_script",
            description="Bash script",
            headers={"Content-Type": "application/json"},
            data=payload,
            timeout=timeout + 100,
        )
        if resp is not None:
            result = resp.json()
            logger.info("Bash script returned code %d.", result.get("returncode", -1))
            return result
        return {
            "status": "error",
            "output": "",
            "error": f"Failed after {self.retry_times} retries",
            "returncode": -1,
        }

    # ------------------------------------------------------------------
    # Structured action execution (computer_13 action space)
    # ------------------------------------------------------------------

    def execute_action(self, action: Any) -> None:
        """Dispatch a structured ``computer_13`` action dict to the VM.

        Accepts string shortcuts ``"WAIT"``, ``"FAIL"``, ``"DONE"`` as no-ops.
        """
        if isinstance(action, str) and action in ("WAIT", "FAIL", "DONE"):
            return

        action_type = action["action_type"]
        params = action.get("parameters") or {
            k: v for k, v in action.items() if k != "action_type"
        }
        move_mode = random.choice([
            "pyautogui.easeInQuad", "pyautogui.easeOutQuad",
            "pyautogui.easeInOutQuad", "pyautogui.easeInBounce",
            "pyautogui.easeInElastic",
        ])
        duration = random.uniform(0.5, 1)

        dispatch = {
            "MOVE_TO": self._act_move_to,
            "CLICK": self._act_click,
            "MOUSE_DOWN": self._act_mouse_btn,
            "MOUSE_UP": self._act_mouse_btn,
            "RIGHT_CLICK": self._act_positional_click,
            "DOUBLE_CLICK": self._act_positional_click,
            "DRAG_TO": self._act_drag,
            "SCROLL": self._act_scroll,
            "TYPING": self._act_typing,
            "PRESS": self._act_key,
            "KEY_DOWN": self._act_key,
            "KEY_UP": self._act_key,
            "HOTKEY": self._act_hotkey,
        }

        handler = dispatch.get(action_type)
        if handler is None:
            if action_type in ("WAIT", "FAIL", "DONE"):
                return
            raise ValueError(f"Unknown action type: {action_type}")

        handler(action_type, params, move_mode=move_mode, duration=duration)

    def _act_move_to(self, _at: str, p: Dict, **kw: Any) -> None:
        if "x" in p and "y" in p:
            self.execute_python_command(
                f"pyautogui.moveTo({p['x']}, {p['y']}, {kw['duration']}, {kw['move_mode']})"
            )
        else:
            self.execute_python_command("pyautogui.moveTo()")

    def _act_click(self, _at: str, p: Dict, **_kw: Any) -> None:
        parts = []
        if "button" in p:
            parts.append(f"button='{p['button']}'")
        if "x" in p and "y" in p:
            parts.append(f"x={p['x']}, y={p['y']}")
        if "num_clicks" in p:
            parts.append(f"clicks={p['num_clicks']}")
        self.execute_python_command(f"pyautogui.click({', '.join(parts)})")

    def _act_mouse_btn(self, at: str, p: Dict, **_kw: Any) -> None:
        fn = "mouseDown" if at == "MOUSE_DOWN" else "mouseUp"
        btn = f"button='{p['button']}'" if "button" in p else ""
        self.execute_python_command(f"pyautogui.{fn}({btn})")

    def _act_positional_click(self, at: str, p: Dict, **_kw: Any) -> None:
        fn = "rightClick" if at == "RIGHT_CLICK" else "doubleClick"
        if "x" in p and "y" in p:
            self.execute_python_command(f"pyautogui.{fn}(x={p['x']}, y={p['y']})")
        else:
            self.execute_python_command(f"pyautogui.{fn}()")

    def _act_drag(self, _at: str, p: Dict, **_kw: Any) -> None:
        self.execute_python_command(
            f"pyautogui.dragTo({p['x']}, {p['y']}, duration=1.0, button='left', mouseDownUp=True)"
        )

    def _act_scroll(self, _at: str, p: Dict, **_kw: Any) -> None:
        if "dx" in p:
            self.execute_python_command(f"pyautogui.hscroll({p['dx']})")
        if "dy" in p:
            self.execute_python_command(f"pyautogui.vscroll({p['dy']})")

    def _act_typing(self, _at: str, p: Dict, **_kw: Any) -> None:
        if "text" not in p:
            raise ValueError("TYPING action requires 'text' parameter")
        self.execute_python_command(f"pyautogui.typewrite({repr(p['text'])})")

    def _act_key(self, at: str, p: Dict, **_kw: Any) -> None:
        key = p.get("key", "")
        if key.lower() not in KEYBOARD_KEYS:
            raise ValueError(f"Key '{key}' is not in KEYBOARD_KEYS")
        fn_map = {"PRESS": "press", "KEY_DOWN": "keyDown", "KEY_UP": "keyUp"}
        self.execute_python_command(f"pyautogui.{fn_map[at]}('{key}')")

    def _act_hotkey(self, _at: str, p: Dict, **_kw: Any) -> None:
        keys = p.get("keys", [])
        if not isinstance(keys, list):
            raise ValueError("HOTKEY 'keys' parameter must be a list")
        for k in keys:
            if k.lower() not in KEYBOARD_KEYS:
                raise ValueError(f"Key '{k}' is not in KEYBOARD_KEYS")
        joined = "', '".join(keys)
        self.execute_python_command(f"pyautogui.hotkey('{joined}')")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_recording(self) -> None:
        """Start screen recording on the VM."""
        self._recording_active = False
        resp = self._retry_request("POST", "/start_recording", description="Start recording")
        if resp is not None:
            self._recording_active = True
            logger.info("Recording started.")
        else:
            logger.error("Failed to start recording.")

    def end_recording(self, dest: str) -> Optional[str]:
        """Stop recording and download the video to *dest*.

        Returns:
            The destination path on success, or *None*.
        """
        if not self._recording_active:
            logger.info("No active recording session; checking for finalized video.")
            if self._download_finalized_recording(dest):
                return dest

        for _ in range(self.retry_times):
            try:
                resp = requests.post(self.base_url + "/end_recording", timeout=60)
                if resp.status_code == 200:
                    with open(dest, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                fh.write(chunk)
                    self._recording_active = False
                    logger.info("Recording saved to %s.", dest)
                    return dest

                msg = ""
                try:
                    payload = resp.json()
                    msg = payload.get("message", "") or payload.get("error", "")
                except ValueError:
                    msg = resp.text or ""

                if resp.status_code == 400 and msg == "No recording in progress to stop.":
                    if self._download_finalized_recording(dest):
                        self._recording_active = False
                        return dest

                logger.error("Stop recording HTTP %d: %s", resp.status_code, msg)
            except requests.RequestException as exc:
                logger.error("Stop recording error: %s", exc)
            time.sleep(self.retry_interval)

        if self._download_finalized_recording(dest):
            self._recording_active = False
            return dest
        self._recording_active = False
        return None

    def _download_finalized_recording(self, dest: str) -> bool:
        """Attempt to download an already-finalized recording."""
        try:
            status = requests.get(self.base_url + "/recording_status", timeout=10)
            if status.status_code != 200:
                return False
            if not status.json().get("file_exists"):
                return False
            dl = requests.get(self.base_url + "/download_recording", stream=True, timeout=60)
            if dl.status_code != 200:
                return False
            with open(dest, "wb") as fh:
                for chunk in dl.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
            logger.info("Finalized recording downloaded to %s.", dest)
            return True
        except requests.RequestException as exc:
            logger.error("Finalized recording download failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # VM info helpers
    # ------------------------------------------------------------------

    def get_vm_platform(self) -> str:
        """Return the OS name reported by the VM (e.g. ``'Linux'``)."""
        result = self.execute_python_command(
            "import platform; print(platform.system())"
        )
        return (result or {}).get("output", "").strip()

    def get_vm_screen_size(self) -> Optional[Dict[str, Any]]:
        """Query the VM's screen dimensions."""
        resp = self._retry_request("POST", "/screen_size", description="Screen size")
        return resp.json() if resp else None

    def get_vm_window_size(self, app_class_name: str) -> Optional[Dict[str, Any]]:
        """Query a specific window's size by app class name."""
        resp = self._retry_request(
            "POST", "/window_size",
            description=f"Window size ({app_class_name})",
            data={"app_class_name": app_class_name},
        )
        return resp.json() if resp else None

    def get_vm_wallpaper(self) -> Optional[bytes]:
        """Download the VM's desktop wallpaper image."""
        resp = self._retry_request("POST", "/wallpaper", description="Wallpaper")
        return resp.content if resp else None

    def get_vm_desktop_path(self) -> Optional[str]:
        """Return the Desktop directory path inside the VM."""
        resp = self._retry_request("POST", "/desktop_path", description="Desktop path")
        return resp.json().get("desktop_path") if resp else None

    def get_vm_directory_tree(self, path: str) -> Optional[Dict[str, Any]]:
        """List the directory tree at *path* inside the VM."""
        resp = self._retry_request(
            "POST", "/list_directory",
            description=f"Directory tree ({path})",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"path": path}),
        )
        return resp.json().get("directory_tree") if resp else None
