"""VirtualBox provider stub -- import from old repo or implement as needed."""

from new_osworld.environment.providers.base import Provider, VMManager


class VirtualBoxProvider(Provider):
    def start_emulator(self, path_to_vm, headless, os_type="Ubuntu"):
        raise NotImplementedError("VirtualBox provider not yet ported. Use vmware or docker.")

    def get_ip_address(self, path_to_vm):
        raise NotImplementedError

    def save_state(self, path_to_vm, snapshot_name):
        raise NotImplementedError

    def revert_to_snapshot(self, path_to_vm, snapshot_name):
        raise NotImplementedError

    def stop_emulator(self, path_to_vm):
        raise NotImplementedError


class VirtualBoxVMManager(VMManager):
    def initialize_registry(self, **kw): pass
    def add_vm(self, vm_path, **kw): pass
    def delete_vm(self, vm_path, **kw): pass
    def occupy_vm(self, vm_path, pid, **kw): pass
    def list_free_vms(self, **kw): return []
    def check_and_clean(self, **kw): pass
    def get_vm_path(self, **kw): raise NotImplementedError
