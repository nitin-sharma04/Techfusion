"""VM provider factory -- lazy imports to avoid pulling in unused cloud SDKs."""

from __future__ import annotations

from typing import Tuple

from new_osworld.environment.providers.base import Provider, VMManager


def create_provider(
    provider_name: str,
    region: str | None = None,
) -> Tuple[VMManager, Provider]:
    """Instantiate a VM manager and provider pair.

    Args:
        provider_name: One of ``vmware``, ``virtualbox``, ``docker``, ``aws``,
            ``azure``, ``aliyun``, ``volcengine``.
        region: Cloud region (only relevant for cloud providers).

    Returns:
        A ``(VMManager, Provider)`` tuple.

    Raises:
        NotImplementedError: If the provider is not recognised.
    """
    name = provider_name.lower().strip()

    if name == "vmware":
        from new_osworld.environment.providers.vmware import VMwareVMManager, VMwareProvider
        return VMwareVMManager(), VMwareProvider(region)

    if name == "virtualbox":
        from new_osworld.environment.providers.virtualbox import VirtualBoxVMManager, VirtualBoxProvider
        return VirtualBoxVMManager(), VirtualBoxProvider(region)

    if name in ("aws", "amazon web services"):
        from new_osworld.environment.providers.aws import AWSVMManager, AWSProvider
        return AWSVMManager(), AWSProvider(region)

    if name == "azure":
        from new_osworld.environment.providers.azure import AzureVMManager, AzureProvider
        return AzureVMManager(), AzureProvider(region)

    if name == "docker":
        from new_osworld.environment.providers.docker import DockerVMManager, DockerProvider
        return DockerVMManager(), DockerProvider(region)

    if name == "aliyun":
        from new_osworld.environment.providers.aliyun import AliyunVMManager, AliyunProvider
        return AliyunVMManager(), AliyunProvider()

    if name == "volcengine":
        from new_osworld.environment.providers.volcengine import VolcengineVMManager, VolcengineProvider
        return VolcengineVMManager(), VolcengineProvider()

    raise NotImplementedError(
        f"Provider '{provider_name}' is not supported.  "
        f"Choose from: vmware, virtualbox, docker, aws, azure, aliyun, volcengine."
    )


__all__ = ["Provider", "VMManager", "create_provider"]
