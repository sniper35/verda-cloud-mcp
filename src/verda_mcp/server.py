"""Verda Cloud MCP Server - GPU instance management for Claude."""

import asyncio
import logging
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from .client import (
    VerdaSDKClient,
    get_client,
    get_instance_type_from_gpu_type_and_count,
)
from .config import get_config, update_config_file

# Configure logging to stderr (required for MCP servers)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("verda-cloud")

# Global client instance
_client: VerdaSDKClient | None = None


def _get_client() -> VerdaSDKClient:
    """Get the global Verda client instance."""
    global _client
    if _client is None:
        _client = get_client()
    return _client


# =============================================================================
# Instance Management Tools
# =============================================================================


@mcp.tool()
async def list_instances() -> str:
    """List all your Verda Cloud instances with their status.

    Returns:
        A formatted list of all instances with ID, hostname, status, type, and IP.
    """
    client = _get_client()
    instances = await client.list_instances()

    if not instances:
        return "No instances found."

    lines = ["# Your Verda Cloud Instances\n"]
    for inst in instances:
        ip_info = f", IP: {inst.ip_address}" if inst.ip_address else ""
        lines.append(
            f"- **{inst.hostname}** (`{inst.id}`)\n"
            f"  Status: {inst.status}, Type: {inst.instance_type}{ip_info}"
        )

    return "\n".join(lines)


@mcp.tool()
async def check_instance_status(instance_id: str) -> str:
    """Check the status of a specific instance.

    Args:
        instance_id: The ID of the instance to check.

    Returns:
        Instance status details including SSH connection info if running.
    """
    client = _get_client()
    instance = await client.get_instance(instance_id)

    result = [
        f"# Instance: {instance.hostname}",
        f"- **ID**: `{instance.id}`",
        f"- **Status**: {instance.status}",
        f"- **Type**: {instance.instance_type}",
    ]

    if instance.ip_address:
        result.append(f"- **IP Address**: {instance.ip_address}")
        result.append("\n## SSH Connection")
        result.append("```bash")
        result.append(f"ssh root@{instance.ip_address}")
        result.append("```")

    return "\n".join(result)


# =============================================================================
# Spot Availability Tools
# =============================================================================


@mcp.tool()
async def check_spot_availability(
    gpu_type: str | None = None,
    gpu_count: int | None = None,
) -> str:
    """Check if spot GPU instances are available.

    Uses the official Verda SDK is_available() method to check across all locations.

    Args:
        gpu_type: GPU type to check (default from config, e.g., "B300", "B200").
        gpu_count: Number of GPUs (default from config, e.g., 1, 2, 4, 8).

    Returns:
        Availability status with location if available.
    """
    client = _get_client()
    config = get_config()

    gpu_type = gpu_type or config.defaults.gpu_type
    gpu_count = gpu_count or config.defaults.gpu_count

    result = await client.check_spot_availability(gpu_type, gpu_count)

    instance_type = get_instance_type_from_gpu_type_and_count(gpu_type, gpu_count)

    lines = [
        "# Spot Availability Check",
        "",
        f"**GPU Type**: {gpu_type}",
        f"**GPU Count**: {gpu_count}",
        f"**Instance Type**: {instance_type or 'Unknown'}",
        "",
    ]

    if result.available:
        lines.append("## ✓ AVAILABLE")
        lines.append("")
        lines.append(f"**Location**: {result.location}")
        lines.append("")
        lines.append(
            "Ready to deploy! Use `deploy_spot_instance` to create an instance."
        )
    else:
        lines.append("## ✗ NOT AVAILABLE")
        lines.append("")
        lines.append(
            "No spot instances available across all locations "
            "(FIN-01, FIN-02, FIN-03)."
        )
        lines.append("")
        lines.append("Options:")
        lines.append("- Use `monitor_spot_availability` to wait for availability")
        lines.append("- Try a different GPU type or count")

    return "\n".join(lines)


@mcp.tool()
async def monitor_spot_availability(
    gpu_type: str | None = None,
    gpu_count: int | None = None,
    check_interval: int = 30,
    max_checks: int = 60,
    auto_deploy: bool = False,
    volume_id: str | None = None,
    script_id: str | None = None,
) -> str:
    """Monitor for spot GPU availability and optionally auto-deploy when available.

    Polls using the official Verda SDK is_available() method until a spot
    becomes available.

    Args:
        gpu_type: GPU type to monitor (default from config).
        gpu_count: Number of GPUs (default from config).
        check_interval: Seconds between checks (default: 30).
        max_checks: Maximum number of checks before giving up (default: 60 = 30 min).
        auto_deploy: If True, automatically deploy when available (default: False).
        volume_id: Volume to attach if auto-deploying (default from config).
        script_id: Startup script if auto-deploying (default from config).

    Returns:
        Status updates and deployment info if auto_deploy is enabled.
    """
    client = _get_client()
    config = get_config()

    gpu_type = gpu_type or config.defaults.gpu_type
    gpu_count = gpu_count or config.defaults.gpu_count

    instance_type = get_instance_type_from_gpu_type_and_count(gpu_type, gpu_count)

    results = [
        f"# Monitoring {gpu_type} x{gpu_count} Spot Availability",
        "",
        f"Instance type: {instance_type}",
        f"Checking every {check_interval}s, max {max_checks} checks "
        f"({max_checks * check_interval // 60} min)",
        "",
    ]

    for check_num in range(1, max_checks + 1):
        availability = await client.check_spot_availability(gpu_type, gpu_count)

        if availability.available:
            results.append(f"## ✓ SPOT AVAILABLE! (Check #{check_num})")
            results.append("")
            results.append(f"**Location**: {availability.location}")
            results.append(f"**Instance Type**: {availability.instance_type}")
            results.append("")

            if auto_deploy:
                results.append("### Auto-deploying...")

                try:
                    final_volume_id = volume_id or config.defaults.volume_id or None
                    final_script_id = script_id or config.defaults.script_id or None
                    volume_ids = [final_volume_id] if final_volume_id else None

                    instance = await client.create_instance(
                        gpu_type=gpu_type,
                        gpu_count=gpu_count,
                        location=availability.location,
                        volume_ids=volume_ids,
                        script_id=final_script_id,
                    )

                    results.append("")
                    results.append(f"**Instance Created**: `{instance.id}`")
                    results.append(f"**Hostname**: {instance.hostname}")
                    results.append("")
                    results.append("Waiting for instance to be ready...")

                    instance = await client.wait_for_ready(instance.id)

                    results.append("")
                    results.append("## Instance Ready!")
                    results.append("")
                    results.append(f"**IP**: {instance.ip_address}")
                    results.append("")
                    results.append("```bash")
                    results.append(f"ssh root@{instance.ip_address}")
                    results.append("```")

                except Exception as e:
                    results.append("")
                    results.append(f"**Error**: {e}")
            else:
                results.append(
                    "Use `deploy_spot_instance` to deploy, "
                    "or re-run with `auto_deploy=True`"
                )

            return "\n".join(results)

        # Not available yet
        logger.info(f"Check #{check_num}: No {gpu_type} x{gpu_count} spots available")

        if check_num < max_checks:
            await asyncio.sleep(check_interval)

    # Timed out
    results.append("## ✗ Timed Out")
    results.append("")
    results.append(f"No spots became available after {max_checks} checks.")
    results.append("Try again later or consider on-demand instances.")

    return "\n".join(results)


# =============================================================================
# Deployment Tools
# =============================================================================


@mcp.tool()
async def deploy_spot_instance(
    gpu_type: str | None = None,
    gpu_count: int | None = None,
    volume_id: str | None = None,
    script_id: str | None = None,
    hostname: str | None = None,
    image: str | None = None,
    wait_for_ready: bool = True,
) -> str:
    """Deploy a new spot GPU instance.

    Args:
        gpu_type: GPU type (default from config, e.g., "B300").
        gpu_count: Number of GPUs (default from config, e.g., 1, 2, 4, 8).
        volume_id: Block volume ID to attach (default from config).
        script_id: Startup script ID (default from config).
        hostname: Instance hostname (auto-generated if not provided).
        image: OS image (default from config).
        wait_for_ready: If True, wait for instance to be ready (default: True).

    Returns:
        Instance details and SSH connection info when ready.
    """
    client = _get_client()
    config = get_config()

    gpu_type = gpu_type or config.defaults.gpu_type
    gpu_count = gpu_count or config.defaults.gpu_count

    # Check availability first
    availability = await client.check_spot_availability(gpu_type, gpu_count)

    if not availability.available:
        return (
            f"# Deployment Failed\n\n"
            f"No spot instances available for {gpu_type} x{gpu_count}.\n\n"
            f"Use `monitor_spot_availability` to wait for availability."
        )

    # Prepare volume IDs
    final_volume_id = volume_id or config.defaults.volume_id
    volume_ids = [final_volume_id] if final_volume_id else None

    # Create instance
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    final_hostname = hostname or f"{config.defaults.hostname_prefix}-{ts}"

    instance = await client.create_instance(
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        location=availability.location,
        image=image,
        hostname=final_hostname,
        volume_ids=volume_ids,
        script_id=script_id or config.defaults.script_id or None,
    )

    result = [
        "# Instance Created Successfully!",
        "",
        f"- **ID**: `{instance.id}`",
        f"- **Hostname**: {instance.hostname}",
        f"- **Type**: {instance.instance_type}",
        f"- **Location**: {availability.location}",
        f"- **Status**: {instance.status}",
    ]

    if volume_ids:
        result.append(f"- **Volume**: {volume_ids[0]}")

    if wait_for_ready:
        result.append("")
        timeout = config.deployment.ready_timeout
        result.append(f"Waiting for instance to be ready (timeout: {timeout}s)...")

        try:
            instance = await client.wait_for_ready(instance.id)
            result.append("")
            result.append("## Instance is Ready!")
            result.append("")
            result.append(f"- **Status**: {instance.status}")
            result.append(f"- **IP Address**: {instance.ip_address}")
            result.append("")
            result.append("## Connect via SSH")
            result.append("```bash")
            result.append(f"ssh root@{instance.ip_address}")
            result.append("```")
        except TimeoutError as e:
            result.append("")
            result.append(f"**Warning**: {e}")
            result.append("Use `check_instance_status` to monitor progress.")
        except RuntimeError as e:
            result.append("")
            result.append(f"**Error**: {e}")

    return "\n".join(result)


# =============================================================================
# Instance Control Tools
# =============================================================================


@mcp.tool()
async def delete_instance(instance_id: str, confirm: bool = False) -> str:
    """Delete an instance.

    Args:
        instance_id: The ID of the instance to delete.
        confirm: Must be True to actually delete (safety check).

    Returns:
        Confirmation of deletion.
    """
    if not confirm:
        return (
            "**Safety Check**: To delete an instance, you must set confirm=True.\n"
            f"Are you sure you want to delete instance `{instance_id}`?"
        )

    client = _get_client()
    await client.delete_instance(instance_id)
    return f"Instance `{instance_id}` has been deleted."


@mcp.tool()
async def shutdown_instance(instance_id: str) -> str:
    """Shutdown a running instance (can be restarted later).

    Args:
        instance_id: The ID of the instance to shutdown.

    Returns:
        Confirmation of shutdown.
    """
    client = _get_client()
    await client.instance_action(instance_id, "shutdown")
    return f"Instance `{instance_id}` shutdown initiated."


@mcp.tool()
async def start_instance(instance_id: str) -> str:
    """Start a stopped instance.

    Args:
        instance_id: The ID of the instance to start.

    Returns:
        Confirmation that start was initiated.
    """
    client = _get_client()
    await client.instance_action(instance_id, "boot")
    return (
        f"Instance `{instance_id}` start initiated. "
        "Use `check_instance_status` to monitor."
    )


# =============================================================================
# Resource Listing Tools
# =============================================================================


@mcp.tool()
async def list_volumes() -> str:
    """List your block storage volumes.

    Returns:
        A list of volumes with ID, name, size, and attachment status.
    """
    client = _get_client()
    volumes = await client.list_volumes()

    if not volumes:
        return "No volumes found."

    lines = ["# Your Block Volumes\n"]
    for vol in volumes:
        if vol.attached_to:
            attached = f"Attached to: {vol.attached_to}"
        else:
            attached = "Not attached"
        lines.append(
            f"- **{vol.name}** (`{vol.id}`)\n"
            f"  Size: {vol.size_gb} GB, Status: {vol.status}, {attached}"
        )

    return "\n".join(lines)


@mcp.tool()
async def list_scripts() -> str:
    """List your startup scripts.

    Returns:
        A list of scripts with ID and name.
    """
    client = _get_client()
    scripts = await client.list_scripts()

    if not scripts:
        return "No startup scripts found."

    lines = ["# Your Startup Scripts\n"]
    for script in scripts:
        lines.append(f"- **{script.name}** (ID: `{script.id}`)")

    return "\n".join(lines)


@mcp.tool()
async def list_ssh_keys() -> str:
    """List your SSH keys.

    Returns:
        A list of SSH keys with ID and name.
    """
    client = _get_client()
    keys = await client.list_ssh_keys()

    if not keys:
        return "No SSH keys found. Please add an SSH key in the Verda console."

    lines = ["# Your SSH Keys\n"]
    for key in keys:
        lines.append(f"- **{key.name}** (ID: `{key.id}`)")

    return "\n".join(lines)


@mcp.tool()
async def list_images() -> str:
    """List available OS images.

    Returns:
        A list of available OS images.
    """
    client = _get_client()
    images = await client.list_images()

    if not images:
        return "No images found."

    # Filter for Ubuntu images
    ubuntu_images = [img for img in images if "ubuntu" in img.name.lower()]

    lines = ["# Available Ubuntu Images\n"]
    for img in ubuntu_images[:10]:  # Show first 10
        lines.append(f"- **{img.name}** (`{img.image_type}`)")

    if len(ubuntu_images) > 10:
        lines.append(f"\n... and {len(ubuntu_images) - 10} more")

    return "\n".join(lines)


# =============================================================================
# Volume Management Tools
# =============================================================================


@mcp.tool()
async def attach_volume(volume_id: str, instance_id: str) -> str:
    """Attach a volume to an instance.

    Note: The instance must be shut down first.

    Args:
        volume_id: The ID of the volume to attach.
        instance_id: The ID of the instance to attach to.

    Returns:
        Confirmation of attachment.
    """
    client = _get_client()
    await client.attach_volume(volume_id, instance_id)
    return f"Volume `{volume_id}` attached to instance `{instance_id}`."


@mcp.tool()
async def detach_volume(volume_id: str) -> str:
    """Detach a volume from its current instance.

    Note: The instance must be shut down first.

    Args:
        volume_id: The ID of the volume to detach.

    Returns:
        Confirmation of detachment.
    """
    client = _get_client()
    await client.detach_volume(volume_id)
    return f"Volume `{volume_id}` detached."


@mcp.tool()
async def create_volume(
    name: str,
    size: int | None = None,
    volume_type: str = "NVMe",
) -> str:
    """Create a new block storage volume.

    Args:
        name: Name for the volume (e.g., "my-data-volume").
        size: Volume size in GB (default: 150GB from config).
        volume_type: Volume type (default: "NVMe").

    Returns:
        Created volume details with ID.
    """
    client = _get_client()
    config = get_config()

    size = size or config.defaults.volume_size

    volume = await client.create_volume(
        name=name,
        size=size,
        volume_type=volume_type,
    )

    return (
        f"# Volume Created Successfully!\n\n"
        f"- **Name**: {volume.name}\n"
        f"- **ID**: `{volume.id}`\n"
        f"- **Size**: {volume.size_gb} GB\n"
        f"- **Type**: {volume_type}\n"
        f"- **Status**: {volume.status}\n\n"
        f"Add this to your config.yaml to use as default:\n"
        f"```yaml\n"
        f"defaults:\n"
        f'  volume_id: "{volume.id}"\n'
        f"```"
    )


# =============================================================================
# Script Management Tools
# =============================================================================

@mcp.tool()
async def get_instance_startup_script(instance_id: str) -> str:
    """Get the startup script attached to a specific Verda Cloud instance.

    Args:
        instance_id: The ID of the instance.

    Returns:
        The script name, ID, and content, or a message if no script is attached.
    """
    client = _get_client()
    script = await client.get_current_script(instance_id)

    if script is None:
        return "No startup script attached to this instance."

    return f"""# Startup Script: {script.name}
**ID**: `{script.id}`

## Content
```bash
{script.content}
```"""


@mcp.tool()
async def create_startup_script(name: str, content: str) -> str:
    """Create a new startup script.

    Args:
        name: Name for the script.
        content: Bash script content.

    Returns:
        Created script ID.
    """
    client = _get_client()
    script = await client.create_script(name, content)
    return f"Script created: **{script.name}** (ID: `{script.id}`)"


@mcp.tool()
async def create_and_set_default_script(name: str, content: str) -> str:
    """Create a new startup script and set it as the default for new instances.

    This creates a new script and updates config.yaml to use it as the default
    script_id for future instance deployments.

    Args:
        name: Name for the new script.
        content: Bash script content.

    Returns:
        Confirmation with script ID and updated config status.
    """
    client = _get_client()

    # Create the new script
    script = await client.create_script(name, content)

    # Update the config file to set this as default
    update_config_file({"defaults": {"script_id": script.id}})

    return f"""# Script Created and Set as Default

**Name**: {script.name}
**ID**: `{script.id}`

The config.yaml has been updated. All new instances will use this script by default."""


@mcp.tool()
async def set_default_script(script_id: str) -> str:
    """Set an existing script as the default for new Verda Cloud instances.

    Args:
        script_id: The ID of an existing script to set as default.

    Returns:
        Confirmation of the updated default.
    """
    client = _get_client()

    # Verify the script exists
    script = await client.get_script_by_id(script_id)

    # Update the config file
    update_config_file({"defaults": {"script_id": script.id}})

    return f"""# Default Script Updated

**Name**: {script.name}
**ID**: `{script.id}`

All new instances will now use this script by default."""


# =============================================================================
# Configuration Info Tool
# =============================================================================


@mcp.tool()
async def show_config() -> str:
    """Show the current MCP server configuration (without secrets).

    Returns:
        Current configuration settings.
    """
    config = get_config()

    instance_type = get_instance_type_from_gpu_type_and_count(
        config.defaults.gpu_type,
        config.defaults.gpu_count,
    )

    lines = [
        "# Current Configuration",
        "",
        "## GPU Defaults",
        f"- **GPU Type**: {config.defaults.gpu_type}",
        f"- **GPU Count**: {config.defaults.gpu_count}",
        f"- **Instance Type**: {instance_type}",
        f"- **Location**: {config.defaults.location}",
        "",
        "## Deployment Defaults",
        f"- **Image**: {config.defaults.image}",
        f"- **Hostname Prefix**: {config.defaults.hostname_prefix}",
        f"- **Volume ID**: {config.defaults.volume_id or '(not set)'}",
        f"- **Script ID**: {config.defaults.script_id or '(not set)'}",
        "",
        "## Deployment Settings",
        f"- **Ready Timeout**: {config.deployment.ready_timeout}s",
        f"- **Poll Interval**: {config.deployment.poll_interval}s",
        f"- **Use Spot**: {config.deployment.use_spot}",
    ]

    return "\n".join(lines)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Run the MCP server."""
    logger.info("Starting Verda Cloud MCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
