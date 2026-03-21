"""Docker provider -- runs the VM as a container using QEMU inside Docker."""

from __future__ import annotations

import os
import platform
import time
import zipfile
from pathlib import Path
from typing import Any, List, Optional

import psutil
import requests
from filelock import FileLock
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

from new_osworld.environment.providers.base import Provider, VMManager
from new_osworld.logging_setup import get_logger

logger = get_logger("provider.docker")

WAIT_TIME = 3
RETRY_INTERVAL = 1

UBUNTU_URL = "https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu.qcow2.zip"
WINDOWS_URL = "https://huggingface.co/datasets/xlangai/windows_osworld/resolve/main/Windows-10-x64.qcow2.zip"
VMS_DIR = "./docker_vm_data"

if platform.system() == "Windows":
    _docker_path = r"C:\Program Files\Docker\Docker"
    if _docker_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] += os.pathsep + _docker_path


class PortAllocationError(Exception):
    pass


class DockerProvider(Provider):
    """Runs an OSWorld VM image inside a Docker container."""

    def __init__(self, region: Optional[str] = None) -> None:
        super().__init__(region)
        import docker as docker_lib
        self.client = docker_lib.from_env()
        self.server_port: Optional[int] = None
        self.vnc_port: Optional[int] = None
        self.chromium_port: Optional[int] = None
        self.vlc_port: Optional[int] = None
        self.container = None
        self.env_vars = {"DISK_SIZE": "32G", "RAM_SIZE": "4G", "CPU_CORES": "4"}

        tmp = Path(os.getenv("TEMP", "/tmp"))
        self._lock_file = tmp / "docker_port_allocation.lck"
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)

    def _used_ports(self) -> set:
        ports = {c.laddr.port for c in psutil.net_connections()}
        for ctr in self.client.containers.list():
            mapping = ctr.attrs["NetworkSettings"]["Ports"] or {}
            for bindings in mapping.values():
                if bindings:
                    ports.update(int(b["HostPort"]) for b in bindings)
        return ports

    def _next_port(self, start: int) -> int:
        used = self._used_ports()
        port = start
        while port < 65354:
            if port not in used:
                return port
            port += 1
        raise PortAllocationError(f"No available port from {start}")

    def _wait_ready(self, timeout: int = 300) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if requests.get(f"http://localhost:{self.server_port}/screenshot", timeout=10).status_code == 200:
                    return
            except Exception:
                pass
            logger.info("Waiting for VM to become ready ...")
            time.sleep(RETRY_INTERVAL)
        raise TimeoutError("VM did not become ready.")

    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str = "Ubuntu") -> None:
        lock = FileLock(str(self._lock_file), timeout=10)
        try:
            with lock:
                self.vnc_port = self._next_port(8006)
                self.server_port = self._next_port(5000)
                self.chromium_port = self._next_port(9222)
                self.vlc_port = self._next_port(8080)

                devices = []
                env = dict(self.env_vars)
                if os.path.exists("/dev/kvm"):
                    devices.append("/dev/kvm")
                    logger.info("KVM available -- using hardware acceleration.")
                else:
                    env["KVM"] = "N"
                    logger.warning("KVM not available -- VM will be slower.")

                self.container = self.client.containers.run(
                    "happysixd/osworld-docker",
                    environment=env,
                    cap_add=["NET_ADMIN"],
                    devices=devices,
                    volumes={os.path.abspath(path_to_vm): {"bind": "/System.qcow2", "mode": "ro"}},
                    ports={8006: self.vnc_port, 5000: self.server_port, 9222: self.chromium_port, 8080: self.vlc_port},
                    detach=True,
                )

            logger.info(
                "Container started (VNC=%d, Server=%d, Chrome=%d, VLC=%d).",
                self.vnc_port, self.server_port, self.chromium_port, self.vlc_port,
            )
            self._wait_ready()
        except Exception:
            if self.container:
                try:
                    self.container.stop()
                    self.container.remove()
                except Exception:
                    pass
            raise

    def get_ip_address(self, path_to_vm: str) -> str:
        if not all([self.server_port, self.chromium_port, self.vnc_port, self.vlc_port]):
            raise RuntimeError("VM not started.")
        return f"localhost:{self.server_port}:{self.chromium_port}:{self.vnc_port}:{self.vlc_port}"

    def save_state(self, path_to_vm: str, snapshot_name: str) -> None:
        raise NotImplementedError("Snapshots not supported for Docker provider.")

    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str) -> Optional[str]:
        self.stop_emulator(path_to_vm)
        return None

    def stop_emulator(self, path_to_vm: str) -> None:
        if self.container:
            logger.info("Stopping Docker container ...")
            try:
                self.container.stop()
                self.container.remove()
                time.sleep(WAIT_TIME)
            except Exception as exc:
                logger.error("Error stopping container: %s", exc)
            finally:
                self.container = None
                self.server_port = self.vnc_port = self.chromium_port = self.vlc_port = None


# ---------------------------------------------------------------------------

def _download_file(url: str, dest: str) -> None:
    """Download *url* to *dest* with resume support and corruption detection."""
    downloaded = os.path.getsize(dest) if os.path.exists(dest) else 0

    while True:
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=(15, 30))
            if resp.status_code == 416:
                logger.info("File fully downloaded (HTTP 416).")
                break
            resp.raise_for_status()

            if downloaded > 0 and resp.status_code == 200:
                logger.warning("Server ignored Range header -- restarting from scratch.")
                downloaded = 0

            content_length = int(resp.headers.get("content-length", 0))
            total_size = downloaded + content_length
            file_mode = "ab" if (downloaded > 0 and resp.status_code == 206) else "wb"

            with open(dest, file_mode) as fh, Progress(
                "[progress.description]{task.description}",
                BarColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("Downloading VM", total=total_size, completed=downloaded)
                for chunk in resp.iter_content(65536):
                    fh.write(chunk)
                    progress.advance(task, len(chunk))
            logger.info("Download complete.")
            break
        except (requests.RequestException, IOError) as exc:
            logger.error("Download error: %s -- retrying", exc)
            time.sleep(5)
            downloaded = os.path.getsize(dest) if os.path.exists(dest) else 0


def _download_vm(vms_dir: str, url: str) -> None:
    os.makedirs(vms_dir, exist_ok=True)
    hf = os.environ.get("HF_ENDPOINT", "")
    if "hf-mirror.com" in hf:
        url = url.replace("huggingface.co", "hf-mirror.com")

    filename = url.split("/")[-1]
    dest = os.path.join(vms_dir, filename)

    _download_file(url, dest)

    if filename.endswith(".zip"):
        try:
            with zipfile.ZipFile(dest, "r") as zf:
                bad = zf.testzip()
                if bad:
                    raise zipfile.BadZipFile(f"Corrupt entry: {bad}")
        except zipfile.BadZipFile:
            logger.error("Downloaded zip is corrupted -- deleting. Re-run to retry.")
            os.remove(dest)
            raise RuntimeError("Downloaded VM image is corrupted. Re-run to try again.")
        logger.info("Extracting ...")
        with zipfile.ZipFile(dest, "r") as zf:
            zf.extractall(vms_dir)


class DockerVMManager(VMManager):
    """Minimal manager for Docker -- just ensures the qcow2 image is downloaded."""

    def initialize_registry(self, **kw: Any) -> None:
        pass

    def add_vm(self, vm_path: str, **kw: Any) -> None:
        pass

    def delete_vm(self, vm_path: str, **kw: Any) -> None:
        pass

    def occupy_vm(self, vm_path: str, pid: int, **kw: Any) -> None:
        pass

    def list_free_vms(self, **kw: Any) -> List[str]:
        return []

    def check_and_clean(self, **kw: Any) -> None:
        pass

    def get_vm_path(self, os_type: str = "Ubuntu", region: Optional[str] = None, screen_size=(1920, 1080), **kw: Any) -> str:
        url = UBUNTU_URL if os_type == "Ubuntu" else WINDOWS_URL
        hf = os.environ.get("HF_ENDPOINT", "")
        if "hf-mirror.com" in hf:
            url = url.replace("huggingface.co", "hf-mirror.com")
        filename = url.split("/")[-1]
        vm_name = filename[:-4] if filename.endswith(".zip") else filename

        if not os.path.exists(os.path.join(VMS_DIR, vm_name)):
            _download_vm(VMS_DIR, url)
        return os.path.join(VMS_DIR, vm_name)
