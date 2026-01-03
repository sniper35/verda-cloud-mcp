"""Verda Cloud API client wrapper using official SDK."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any

from verda import VerdaClient
from verda.images import ImagesService
from verda.instances import InstancesService
from verda.ssh_keys import SSHKeysService
from verda.startup_scripts import StartupScriptsService
from verda.volumes import VolumesService

from .config import Config, get_config

logger = logging.getLogger(__name__)

# Thread pool for running sync SDK calls
_executor = ThreadPoolExecutor(max_workers=4)

# Location codes to check for availability
LOCATION_CODES = ["FIN-01", "FIN-02", "FIN-03"]


def get_instance_type_from_gpu_type_and_count(
    gpu_type: str = "B300",
    gpu_count: int = 1,
) -> str:
    """Map GPU type and count to Verda instance type string.

    Args:
        gpu_type: GPU type (B300, B200, GB300, H200, etc.)
        gpu_count: Number of GPUs (1, 2, 4, 8)

    Returns:
        Instance type string (e.g., "1B300.30V") or empty string if not found.
    """
    mapping = {
        "B300": {
            1: "1B300.30V",
            2: "2B300.60V",
            4: "4B300.120V",
            8: "8B300.240V",
        },
        "B200": {
            1: "1B200.30V",
            2: "2B200.60V",
            4: "4B200.120V",
            8: "8B200.240V",
        },
        "GB300": {
            1: "1GB300.36V",
            2: "2GB300.72V",
            4: "4GB300.144V",
        },
        "H200": {
            1: "1H200.141S.44V",
        },
    }
    return mapping.get(gpu_type.upper(), {}).get(gpu_count, "")


@dataclass
class AvailabilityResult:
    """Result of an availability check."""

    available: bool
    location: str
    instance_type: str
    gpu_type: str
    gpu_count: int


@dataclass
class Instance:
    """Simplified instance representation."""

    id: str
    hostname: str
    status: str
    instance_type: str
    ip_address: str | None
    location: str | None = None
    startup_script_id: str | None = None

    @classmethod
    def from_sdk(cls, inst: Any) -> "Instance":
        """Create from SDK Instance object."""
        return cls(
            id=inst.id,
            hostname=getattr(inst, "hostname", ""),
            status=getattr(inst, "status", "unknown"),
            instance_type=getattr(inst, "instance_type", ""),
            ip_address=getattr(inst, "ip", None),
            location=getattr(inst, "location", None),
            startup_script_id=getattr(inst, "startup_script_id", None),
        )


@dataclass
class Volume:
    """Simplified volume representation."""

    id: str
    name: str
    size_gb: int
    status: str
    attached_to: str | None

    @classmethod
    def from_sdk(cls, vol: Any) -> "Volume":
        """Create from SDK Volume object."""
        return cls(
            id=vol.id,
            name=getattr(vol, "name", ""),
            size_gb=getattr(vol, "size", 0),
            status=getattr(vol, "status", "unknown"),
            attached_to=getattr(vol, "instance_id", None),
        )


@dataclass
class Script:
    """Simplified script representation."""

    id: str
    name: str
    content: str | None = None

    @classmethod
    def from_sdk(cls, script: Any) -> "Script":
        """Create from SDK StartupScript object."""
        return cls(
            id=script.id,
            name=getattr(script, "name", ""),
            content=getattr(script, "script", None),
        )


@dataclass
class SSHKey:
    """Simplified SSH key representation."""

    id: str
    name: str

    @classmethod
    def from_sdk(cls, key: Any) -> "SSHKey":
        """Create from SDK SSHKey object."""
        return cls(
            id=key.id,
            name=getattr(key, "name", ""),
        )


@dataclass
class Image:
    """Simplified image representation."""

    id: str
    name: str
    image_type: str

    @classmethod
    def from_sdk(cls, img: Any) -> "Image":
        """Create from SDK Image object."""
        return cls(
            id=img.id,
            name=getattr(img, "name", ""),
            image_type=getattr(img, "image_type", ""),
        )


class VerdaSDKClient:
    """Async wrapper around the official Verda SDK."""

    def __init__(self, config: Config | None = None):
        """Initialize the client.

        Args:
            config: Configuration instance. If None, loads from default location.
        """
        self.config = config or get_config()
        self._client: VerdaClient | None = None
        self._instances: InstancesService | None = None
        self._volumes: VolumesService | None = None
        self._scripts: StartupScriptsService | None = None
        self._ssh_keys: SSHKeysService | None = None
        self._images: ImagesService | None = None

    def _ensure_client(self) -> None:
        """Ensure SDK client is initialized."""
        if self._client is None:
            self._client = VerdaClient(
                self.config.client_id,
                self.config.client_secret,
            )
            http_client = self._client._http_client
            self._instances = InstancesService(http_client)
            self._volumes = VolumesService(http_client)
            self._scripts = StartupScriptsService(http_client)
            self._ssh_keys = SSHKeysService(http_client)
            self._images = ImagesService(http_client)
            logger.info("Verda SDK client initialized")

    async def _run_sync(self, func, *args, **kwargs):
        """Run a sync function in the thread pool.

        Args:
            func: Sync function to run.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            partial(func, *args, **kwargs),
        )

    # =========================================================================
    # Availability Methods
    # =========================================================================

    async def check_spot_availability(
        self,
        gpu_type: str | None = None,
        gpu_count: int | None = None,
        location: str | None = None,
    ) -> AvailabilityResult:
        """Check if a spot instance is available.

        Args:
            gpu_type: GPU type (default from config).
            gpu_count: Number of GPUs (default from config).
            location: Specific location to check (default: check all).

        Returns:
            AvailabilityResult with status and location if available.
        """
        self._ensure_client()

        gpu_type = gpu_type or self.config.defaults.gpu_type
        gpu_count = gpu_count or self.config.defaults.gpu_count
        instance_type = get_instance_type_from_gpu_type_and_count(gpu_type, gpu_count)

        if not instance_type:
            logger.warning(f"Unknown instance type for {gpu_type} x{gpu_count}")
            return AvailabilityResult(
                available=False,
                location="",
                instance_type="",
                gpu_type=gpu_type,
                gpu_count=gpu_count,
            )

        locations_to_check = [location] if location else LOCATION_CODES

        for loc in locations_to_check:
            try:
                available = await self._run_sync(
                    self._instances.is_available,
                    instance_type,
                    True,  # is_spot
                    loc,
                )
                if available:
                    logger.info(f"Spot available: {instance_type} at {loc}")
                    return AvailabilityResult(
                        available=True,
                        location=loc,
                        instance_type=instance_type,
                        gpu_type=gpu_type,
                        gpu_count=gpu_count,
                    )
            except Exception as e:
                logger.debug(f"Error checking {loc}: {e}")
                continue

        return AvailabilityResult(
            available=False,
            location="",
            instance_type=instance_type,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
        )

    # =========================================================================
    # Instance Methods
    # =========================================================================

    async def list_instances(self, status: str | None = None) -> list[Instance]:
        """List all instances.

        Args:
            status: Optional status filter.

        Returns:
            List of Instance objects.
        """
        self._ensure_client()
        instances = await self._run_sync(self._instances.get, status)
        return [Instance.from_sdk(i) for i in instances]

    async def get_instance(self, instance_id: str) -> Instance:
        """Get instance details.

        Args:
            instance_id: Instance ID.

        Returns:
            Instance object.
        """
        self._ensure_client()
        inst = await self._run_sync(self._instances.get_by_id, instance_id)
        return Instance.from_sdk(inst)

    async def create_instance(
        self,
        gpu_type: str | None = None,
        gpu_count: int | None = None,
        location: str | None = None,
        image: str | None = None,
        hostname: str | None = None,
        volume_ids: list[str] | None = None,
        script_id: str | None = None,
        is_spot: bool = True,
        description: str = "Created by Verda MCP Server",
    ) -> Instance:
        """Create a new instance.

        Args:
            gpu_type: GPU type (default from config).
            gpu_count: Number of GPUs (default from config).
            location: Datacenter location (default from config).
            image: OS image (default from config).
            hostname: Instance hostname (auto-generated if not provided).
            volume_ids: List of volume IDs to attach.
            script_id: Startup script ID.
            is_spot: Whether to create as spot instance.
            description: Instance description.

        Returns:
            Created Instance object.
        """
        self._ensure_client()

        gpu_type = gpu_type or self.config.defaults.gpu_type
        gpu_count = gpu_count or self.config.defaults.gpu_count
        location = location or self.config.defaults.location
        image = image or self.config.defaults.image

        instance_type = get_instance_type_from_gpu_type_and_count(gpu_type, gpu_count)
        if not instance_type:
            raise ValueError(f"Unknown instance type for {gpu_type} x{gpu_count}")

        # Get SSH keys
        ssh_keys = await self._run_sync(self._ssh_keys.get)
        if not ssh_keys:
            raise ValueError("No SSH keys found. Please add one in the Verda console.")
        ssh_key_ids = [k.id for k in ssh_keys]

        # Build creation kwargs
        kwargs: dict[str, Any] = {
            "instance_type": instance_type,
            "image": image,
            "hostname": hostname or (
                f"{self.config.defaults.hostname_prefix}-{gpu_count}"
            ),
            "description": description,
            "ssh_key_ids": ssh_key_ids,
            "location": location,
            "is_spot": is_spot,
        }

        if volume_ids:
            kwargs["existing_volumes"] = volume_ids

        if script_id:
            kwargs["startup_script_id"] = script_id

        logger.info(f"Creating instance: {instance_type} at {location}")
        inst = await self._run_sync(self._instances.create, **kwargs)
        return Instance.from_sdk(inst)

    async def instance_action(self, instance_id: str, action: str) -> None:
        """Perform an action on an instance.

        Args:
            instance_id: Instance ID.
            action: Action name (delete, shutdown, boot, etc.).
        """
        self._ensure_client()
        await self._run_sync(self._instances.action, instance_id, action)

    async def delete_instance(self, instance_id: str) -> None:
        """Delete an instance."""
        await self.instance_action(instance_id, "delete")

    async def wait_for_ready(
        self,
        instance_id: str,
        timeout: int | None = None,
        poll_interval: int | None = None,
    ) -> Instance:
        """Wait for an instance to be ready.

        Args:
            instance_id: Instance ID.
            timeout: Max wait time in seconds.
            poll_interval: Time between checks in seconds.

        Returns:
            Instance when ready.

        Raises:
            TimeoutError: If instance doesn't become ready in time.
            RuntimeError: If instance enters error state.
        """
        timeout = timeout or self.config.deployment.ready_timeout
        poll_interval = poll_interval or self.config.deployment.poll_interval

        elapsed = 0
        while elapsed < timeout:
            instance = await self.get_instance(instance_id)

            if instance.status == "running":
                logger.info(f"Instance {instance_id} is ready")
                return instance
            elif instance.status in ("error", "failed", "terminated"):
                raise RuntimeError(f"Instance entered error state: {instance.status}")

            logger.info(f"Instance status: {instance.status}, waiting...")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Instance not ready after {timeout}s")

    # =========================================================================
    # Volume Methods
    # =========================================================================

    async def list_volumes(self, status: str | None = None) -> list[Volume]:
        """List all volumes.

        Args:
            status: Optional status filter.

        Returns:
            List of Volume objects.
        """
        self._ensure_client()
        volumes = await self._run_sync(self._volumes.get, status)
        return [Volume.from_sdk(v) for v in volumes]

    async def attach_volume(self, volume_id: str, instance_id: str) -> None:
        """Attach a volume to an instance.

        Note: Instance must be shut down.
        """
        self._ensure_client()
        await self._run_sync(self._volumes.attach, volume_id, instance_id)

    async def detach_volume(self, volume_id: str) -> None:
        """Detach a volume from its instance.

        Note: Instance must be shut down.
        """
        self._ensure_client()
        await self._run_sync(self._volumes.detach, volume_id)

    async def create_volume(
        self,
        name: str,
        size: int | None = None,
        volume_type: str = "NVMe",
        location: str | None = None,
        instance_id: str | None = None,
    ) -> Volume:
        """Create a new block storage volume.

        Args:
            name: Volume name.
            size: Volume size in GB (default from config: 150GB).
            volume_type: Volume type (default: "NVMe").
            location: Datacenter location (default from config).
            instance_id: Optional instance to attach to immediately.

        Returns:
            Created Volume object.
        """
        self._ensure_client()

        size = size or self.config.defaults.volume_size
        location = location or self.config.defaults.location

        logger.info(f"Creating volume: {name}, {size}GB, {volume_type} at {location}")
        vol = await self._run_sync(
            self._volumes.create,
            type=volume_type,
            name=name,
            size=size,
            instance_id=instance_id,
            location=location,
        )
        return Volume.from_sdk(vol)

    # =========================================================================
    # Script Methods
    # =========================================================================

    async def list_scripts(self) -> list[Script]:
        """List all startup scripts."""
        self._ensure_client()
        scripts = await self._run_sync(self._scripts.get)
        return [Script.from_sdk(s) for s in scripts]

    async def create_script(self, name: str, content: str) -> Script:
        """Create a new startup script."""
        self._ensure_client()
        script = await self._run_sync(self._scripts.create, name, content)
        return Script.from_sdk(script)

    async def get_script_by_id(self, script_id: str) -> Script:
        """Get a script by its ID."""
        self._ensure_client()
        script = await self._run_sync(self._scripts.get_by_id, script_id)
        return Script.from_sdk(script)

    async def get_current_script(self, instance_id: str) -> Script | None:
        """Get the startup script for an instance.

        Args:
            instance_id: The ID of the instance.

        Returns:
            The Script object if one is attached, None otherwise.
        """
        self._ensure_client()
        instance = await self.get_instance(instance_id)
        if not instance.startup_script_id:
            return None
        script = await self._run_sync(
            self._scripts.get_by_id, instance.startup_script_id
        )
        return Script.from_sdk(script)

    # =========================================================================
    # SSH Key Methods
    # =========================================================================

    async def list_ssh_keys(self) -> list[SSHKey]:
        """List all SSH keys."""
        self._ensure_client()
        keys = await self._run_sync(self._ssh_keys.get)
        return [SSHKey.from_sdk(k) for k in keys]

    # =========================================================================
    # Image Methods
    # =========================================================================

    async def list_images(self) -> list[Image]:
        """List available OS images."""
        self._ensure_client()
        images = await self._run_sync(self._images.get)
        return [Image.from_sdk(i) for i in images]


# Convenience function to get a client
def get_client(config: Config | None = None) -> VerdaSDKClient:
    """Get a Verda SDK client instance."""
    return VerdaSDKClient(config)
