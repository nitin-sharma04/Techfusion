"""Abstract base classes for virtualisation providers and VM managers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class Provider(ABC):
    """Interface that every virtualisation back-end must implement.

    A *Provider* controls a single VM's lifecycle: start, stop, snapshot, and
    networking.
    """

    def __init__(self, region: Optional[str] = None) -> None:
        self.region = region

    @abstractmethod
    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str = "Ubuntu") -> None:
        """Power on the virtual machine."""

    @abstractmethod
    def get_ip_address(self, path_to_vm: str) -> str:
        """Return the VM's IP address (and optional port info separated by ``:``)."""

    @abstractmethod
    def save_state(self, path_to_vm: str, snapshot_name: str) -> None:
        """Save the current VM state to a named snapshot."""

    @abstractmethod
    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str) -> Optional[str]:
        """Revert the VM to a named snapshot; optionally return a new path."""

    @abstractmethod
    def stop_emulator(self, path_to_vm: str) -> None:
        """Shut down (release) the virtual machine."""


class VMManager(ABC):
    """Manages a pool of VMs -- tracks which ones are free, occupied, etc."""

    checked_and_cleaned: bool = False

    @abstractmethod
    def initialize_registry(self, **kwargs: Any) -> None:
        """Set up the internal VM registry."""

    @abstractmethod
    def add_vm(self, vm_path: str, **kwargs: Any) -> None:
        """Register a new VM."""

    @abstractmethod
    def delete_vm(self, vm_path: str, **kwargs: Any) -> None:
        """Remove a VM from the registry."""

    @abstractmethod
    def occupy_vm(self, vm_path: str, pid: int, **kwargs: Any) -> None:
        """Mark a VM as occupied by the given process."""

    @abstractmethod
    def list_free_vms(self, **kwargs: Any) -> List[str]:
        """List paths of VMs that are available for use."""

    @abstractmethod
    def check_and_clean(self, **kwargs: Any) -> None:
        """Audit the registry and remove stale entries."""

    @abstractmethod
    def get_vm_path(self, **kwargs: Any) -> str:
        """Acquire a free VM path, provisioning one if necessary."""
