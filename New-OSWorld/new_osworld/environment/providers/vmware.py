"""VMware Workstation / Fusion provider."""

from __future__ import annotations

import os
import platform
import random
import re
import subprocess
import threading
import uuid
import zipfile
from pathlib import Path
from time import sleep
from typing import Any, List, Optional

import psutil
import requests
from filelock import FileLock
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

from new_osworld.environment.providers.base import Provider, VMManager
from new_osworld.logging_setup import get_logger

logger = get_logger("provider.vmware")

WAIT_TIME = 3
MAX_RETRY = 10
RETRY_INTERVAL = 5

UBUNTU_ARM_URL = "https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu-arm.zip"
UBUNTU_X86_URL = "https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu-x86.zip"
WINDOWS_X86_URL = "https://huggingface.co/datasets/xlangai/windows_osworld/resolve/main/Windows-x86.zip"

REGISTRY_PATH = ".vmware_vms"
LOCK_FILE = ".vmware_lck"
VMS_DIR = "./vmware_vm_data"

_update_lock = threading.Lock()


def _vmrun_type(as_list: bool = False) -> Any:
    """Return the ``-T`` flag for vmrun depending on the host OS."""
    sys_name = platform.system()
    if sys_name in ("Windows", "Linux"):
        return ["-T", "ws"] if as_list else "-T ws"
    if sys_name == "Darwin":
        return ["-T", "fusion"] if as_list else "-T fusion"
    raise RuntimeError(f"Unsupported OS for VMware: {sys_name}")


def _find_vmrun() -> str:
    """Locate the vmrun executable, returning an absolute path on Windows."""
    if platform.system() == "Windows":
        for candidate in (
            r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
        ):
            if os.path.isfile(candidate):
                return candidate
    import shutil
    found = shutil.which("vmrun")
    if found:
        return found
    return "vmrun"


VMRUN = _find_vmrun()

if platform.system() == "Windows":
    _vmware_path = os.path.dirname(VMRUN)
    if _vmware_path and _vmware_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] += os.pathsep + _vmware_path


# ---------------------------------------------------------------------------
# VMware Provider
# ---------------------------------------------------------------------------

class VMwareProvider(Provider):
    """Drives a VMware Workstation / Fusion VM via ``vmrun``."""

    @staticmethod
    def _run(command: list, capture: bool = False, timeout: int = 300) -> Optional[str]:
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            out, err = proc.communicate(timeout=timeout)
            return out.strip() if capture else None
        except subprocess.TimeoutExpired:
            logger.warning("vmrun command timed out after %ds -- assuming it completed.", timeout)
            proc.kill()
            proc.communicate()
            return None

    def _is_vm_running(self, path_to_vm: str) -> bool:
        """Check if the VM is already listed as running by vmrun."""
        try:
            out = subprocess.check_output(
                [VMRUN] + _vmrun_type(True) + ["list"],
                stderr=subprocess.STDOUT, encoding="utf-8", timeout=30,
            )
            norm = os.path.abspath(os.path.normpath(path_to_vm))
            for line in out.splitlines():
                line = line.strip()
                if not line or line.startswith("Total"):
                    continue
                if os.path.abspath(os.path.normpath(line)) == norm:
                    return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        return False

    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str = "Ubuntu") -> None:
        abs_path = os.path.abspath(os.path.normpath(path_to_vm))
        logger.info("Starting VMware VM: %s", abs_path)

        for attempt in range(MAX_RETRY):
            if self._is_vm_running(abs_path):
                logger.info("VM is running.")
                return

            if attempt == 0:
                logger.info("Launching VM (this may take 1-2 minutes on cold boot) ...")

            cmd = [VMRUN] + _vmrun_type(True) + ["start", abs_path]
            if headless:
                cmd.append("nogui")

            # Fire-and-forget: launch vmrun start in background, don't wait
            subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # Wait and then check if it's up
            sleep(WAIT_TIME * 3)

        logger.warning("VM did not appear in vmrun list after %d checks.", MAX_RETRY)

    def get_ip_address(self, path_to_vm: str) -> str:
        abs_path = os.path.abspath(os.path.normpath(path_to_vm))
        logger.info("Retrieving VMware VM IP ...")
        for attempt in range(MAX_RETRY):
            try:
                ip = self._run(
                    [VMRUN] + _vmrun_type(True) + ["getGuestIPAddress", abs_path, "-wait"],
                    capture=True, timeout=120,
                )
                if ip:
                    logger.info("VM IP: %s", ip)
                    return ip
            except Exception as exc:
                logger.error("IP retrieval failed (attempt %d/%d): %s", attempt + 1, MAX_RETRY, exc)
            sleep(WAIT_TIME)
        raise RuntimeError(f"Failed to get VM IP after {MAX_RETRY} attempts.")

    def save_state(self, path_to_vm: str, snapshot_name: str) -> None:
        abs_path = os.path.abspath(os.path.normpath(path_to_vm))
        logger.info("Saving snapshot '%s' ...", snapshot_name)
        self._run([VMRUN] + _vmrun_type(True) + ["snapshot", abs_path, snapshot_name], timeout=120)
        sleep(WAIT_TIME)

    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str) -> Optional[str]:
        abs_path = os.path.abspath(os.path.normpath(path_to_vm))
        logger.info("Reverting to snapshot '%s' ...", snapshot_name)
        self._run([VMRUN] + _vmrun_type(True) + ["revertToSnapshot", abs_path, snapshot_name], timeout=120)
        sleep(WAIT_TIME)
        return path_to_vm

    def stop_emulator(self, path_to_vm: str) -> None:
        abs_path = os.path.abspath(os.path.normpath(path_to_vm))
        logger.info("Stopping VMware VM ...")
        self._run([VMRUN] + _vmrun_type(True) + ["stop", abs_path], timeout=60)
        sleep(WAIT_TIME)


# ---------------------------------------------------------------------------
# VM image download & setup
# ---------------------------------------------------------------------------

def _generate_vm_name(vms_dir: str, os_type: str) -> str:
    idx = 0
    while True:
        name = f"{os_type}{idx}"
        if not os.path.exists(os.path.join(vms_dir, name, f"{name}.vmx")):
            return name
        idx += 1


def _update_vmx(vmx_path: str, target_name: str) -> None:
    """Rewrite UUIDs and MAC so cloned VMs don't collide."""
    with _update_lock:
        dir_path, vmx_file = os.path.split(vmx_path)
        with open(vmx_path, "r") as fh:
            content = fh.read()

        new_mac = ":".join(f"{b:02x}" for b in [0x00, 0x0C, 0x29, random.randint(0, 127), random.randint(0, 255), random.randint(0, 255)])
        content = re.sub(r'displayName = ".*?"', f'displayName = "{target_name}"', content)
        content = re.sub(r'uuid\.bios = ".*?"', f'uuid.bios = "{uuid.uuid4()}"', content)
        content = re.sub(r'uuid\.location = ".*?"', f'uuid.location = "{uuid.uuid4()}"', content)
        content = re.sub(r'ethernet0\.generatedAddress = ".*?"', f'ethernet0.generatedAddress = "{new_mac}"', content)
        content = re.sub(r'vmci0\.id = ".*?"', f'vmci0.id = "{random.randint(-2**31, 2**31-1)}"', content)

        with open(vmx_path, "w") as fh:
            fh.write(content)

        base = os.path.splitext(vmx_file)[0]
        for ext in ("vmx", "nvram", "vmsd", "vmxf"):
            src = os.path.join(dir_path, f"{base}.{ext}")
            dst = os.path.join(dir_path, f"{target_name}.{ext}")
            if os.path.exists(src):
                os.rename(src, dst)

        parts = dir_path.rstrip(os.sep).split(os.sep)
        parts[-1] = target_name
        os.rename(dir_path, os.sep.join(parts))
        logger.info("VMX updated for '%s'.", target_name)


def _validate_zip(path: str) -> bool:
    """Return True if *path* is a valid zip file."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            return bad is None
    except (zipfile.BadZipFile, OSError):
        return False


def _download_file(url: str, dest: str) -> None:
    """Download *url* to *dest* with resume support and corruption detection.

    If the server ignores the Range header (returns 200 instead of 206),
    the partial file is discarded and the download restarts from scratch.
    A corrupted zip is also deleted automatically.
    """
    downloaded = os.path.getsize(dest) if os.path.exists(dest) else 0

    while True:
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=(15, 30))

            if resp.status_code == 416:
                logger.info("Server says file is fully downloaded (HTTP 416).")
                break

            resp.raise_for_status()

            if downloaded > 0 and resp.status_code == 200:
                # Server ignored Range header -- sending the full file.
                # Discard partial data and start fresh.
                logger.warning(
                    "Server returned 200 instead of 206 -- restarting download from scratch."
                )
                downloaded = 0

            content_length = int(resp.headers.get("content-length", 0))
            total_size = downloaded + content_length
            file_mode = "ab" if (downloaded > 0 and resp.status_code == 206) else "wb"

            with open(dest, file_mode) as fh, Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(
                    "Downloading VM",
                    total=total_size,
                    completed=downloaded,
                )
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
                    progress.advance(task, len(chunk))

            logger.info("Download complete.")
            break

        except (requests.RequestException, IOError) as exc:
            logger.error("Download error: %s -- retrying in %ds", exc, RETRY_INTERVAL)
            sleep(RETRY_INTERVAL)
            downloaded = os.path.getsize(dest) if os.path.exists(dest) else 0


def _download_and_install_vm(vm_name: str, vms_dir: str, os_type: str) -> str:
    """Download the VM image from HuggingFace, unzip, and start it."""
    os.makedirs(vms_dir, exist_ok=True)

    if os_type == "Ubuntu":
        url = UBUNTU_ARM_URL if platform.system() == "Darwin" else UBUNTU_X86_URL
        original_name = "Ubuntu"
    elif os_type == "Windows":
        url = WINDOWS_X86_URL
        original_name = "Windows 10 x64"
    else:
        raise ValueError(f"Unsupported os_type: {os_type}")

    hf_mirror = os.environ.get("HF_ENDPOINT", "")
    if "hf-mirror.com" in hf_mirror:
        url = url.replace("huggingface.co", "hf-mirror.com")

    zip_name = url.split("/")[-1]
    vmx_path = os.path.join(vms_dir, vm_name, f"{vm_name}.vmx")

    if not os.path.exists(vmx_path):
        zip_path = os.path.join(vms_dir, zip_name)

        # Download if the zip doesn't exist or is corrupted
        if os.path.exists(zip_path) and _validate_zip(zip_path):
            logger.info("Valid zip already cached at %s", zip_path)
        else:
            if os.path.exists(zip_path):
                logger.warning("Existing zip is corrupted -- deleting and re-downloading.")
                os.remove(zip_path)
            logger.info("Downloading VM image (~12 GB) ...")
            _download_file(url, zip_path)

        # Validate before extracting
        if not _validate_zip(zip_path):
            file_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
            logger.error(
                "Downloaded file is not a valid zip (size: %.2f GB). Deleting it.",
                file_size / (1024 ** 3),
            )
            os.remove(zip_path)
            raise RuntimeError(
                "Downloaded VM image is corrupted. Please re-run the command to try again. "
                "If this keeps happening, check your network connection."
            )

        logger.info("Extracting VM image (this takes a few minutes) ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(os.path.join(vms_dir, vm_name))
        _update_vmx(os.path.join(vms_dir, vm_name, f"{original_name}.vmx"), vm_name)

    # Start VM
    for attempt in range(MAX_RETRY):
        result = subprocess.run(
            f'"{VMRUN}" {_vmrun_type()} start "{vmx_path}" nogui',
            shell=True, text=True, capture_output=True, encoding="utf-8",
        )
        if result.returncode == 0:
            logger.info("VM started.")
            break
        logger.error("Start attempt %d failed: %s", attempt + 1, result.stderr.strip())
    else:
        raise RuntimeError("Failed to start VM after max retries.")

    # Wait for IP
    ip = None
    for attempt in range(MAX_RETRY):
        result = subprocess.run(
            f'"{VMRUN}" {_vmrun_type()} getGuestIPAddress "{vmx_path}" -wait',
            shell=True, text=True, capture_output=True, encoding="utf-8",
        )
        if result.returncode == 0:
            ip = result.stdout.strip()
            break
        sleep(RETRY_INTERVAL)
    if not ip:
        raise RuntimeError("Failed to get VM IP.")

    # Wait for server ready
    logger.info("Waiting for VM server to be ready ...")
    while True:
        try:
            if requests.get(f"http://{ip}:5000/screenshot", timeout=10).status_code == 200:
                break
        except Exception:
            sleep(RETRY_INTERVAL)

    # Create initial snapshot
    logger.info("Creating init_state snapshot ...")
    for attempt in range(MAX_RETRY):
        result = subprocess.run(
            f'"{VMRUN}" {_vmrun_type()} snapshot "{vmx_path}" "init_state"',
            shell=True, text=True, capture_output=True, encoding="utf-8",
        )
        if result.returncode == 0:
            break
        sleep(RETRY_INTERVAL)

    return vmx_path


# ---------------------------------------------------------------------------
# VMware VM Manager
# ---------------------------------------------------------------------------

class VMwareVMManager(VMManager):
    """File-based registry of VMware VMs with file locking for multi-process safety."""

    def __init__(self, registry_path: str = REGISTRY_PATH) -> None:
        self.registry_path = registry_path
        self.lock = FileLock(LOCK_FILE, timeout=60)
        self.initialize_registry()

    def initialize_registry(self) -> None:
        with self.lock:
            if not os.path.exists(self.registry_path):
                Path(self.registry_path).touch()

    def add_vm(self, vm_path: str, **kwargs: Any) -> None:
        with self.lock:
            with open(self.registry_path, "a") as fh:
                fh.write(f"{vm_path}|free\n")

    def delete_vm(self, vm_path: str, **kwargs: Any) -> None:
        pass

    def occupy_vm(self, vm_path: str, pid: int, **kwargs: Any) -> None:
        with self.lock:
            lines = Path(self.registry_path).read_text().splitlines()
            new = []
            for line in lines:
                stripped = line.strip()
                if not stripped or "|" not in stripped:
                    continue
                p, _ = stripped.split("|", 1)
                new.append(f"{p}|{pid}" if p == vm_path else stripped)
            Path(self.registry_path).write_text("\n".join(new) + "\n")

    def list_free_vms(self, **kwargs: Any) -> List[str]:
        with self.lock:
            result = []
            for line in Path(self.registry_path).read_text().splitlines():
                if not line.strip():
                    continue
                p, status = line.strip().split("|")
                if status == "free":
                    result.append(p)
            return result

    def check_and_clean(self, **kwargs: Any) -> None:
        with self.lock:
            active_pids = {p.pid for p in psutil.process_iter()}
            lines = Path(self.registry_path).read_text().splitlines()
            new = []
            for line in lines:
                stripped = line.strip()
                if not stripped or "|" not in stripped:
                    continue
                p, status = stripped.split("|", 1)
                if not os.path.exists(p):
                    continue
                if status == "free" or (status.isdigit() and int(status) in active_pids):
                    new.append(stripped)
                else:
                    new.append(f"{p}|free")
            Path(self.registry_path).write_text("\n".join(new) + "\n")

    def _discover_unregistered_vms(self, vms_dir: str) -> None:
        """Scan the VM directory for .vmx files not in the registry and add them."""
        if not os.path.isdir(vms_dir):
            return
        registered = set()
        reg_path = Path(self.registry_path)
        if reg_path.exists():
            for line in reg_path.read_text().splitlines():
                line = line.strip()
                if line and "|" in line:
                    registered.add(line.split("|")[0])

        for entry in os.listdir(vms_dir):
            subdir = os.path.join(vms_dir, entry)
            if not os.path.isdir(subdir):
                continue
            vmx = os.path.join(subdir, f"{entry}.vmx")
            if os.path.isfile(vmx) and vmx not in registered:
                logger.info("Discovered unregistered VM: %s -- adding to registry.", vmx)
                self.add_vm(vmx)

    def get_vm_path(self, os_type: str = "Ubuntu", region: Optional[str] = None, screen_size=(1920, 1080), **kwargs: Any) -> str:
        with self.lock:
            if not VMwareVMManager.checked_and_cleaned:
                VMwareVMManager.checked_and_cleaned = True
                self.check_and_clean()
                self._discover_unregistered_vms(VMS_DIR)

        with self.lock:
            free = self.list_free_vms()
            if free:
                chosen = free[0]
                self.occupy_vm(chosen, os.getpid())
                logger.info("Using existing VM: %s", chosen)
                return chosen

        logger.info("No free VM -- provisioning a new one (this may take a while) ...")
        name = _generate_vm_name(VMS_DIR, os_type)
        path = _download_and_install_vm(name, VMS_DIR, os_type)
        with self.lock:
            self.add_vm(path)
            self.occupy_vm(path, os.getpid())
        return path
