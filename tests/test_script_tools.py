"""Test script for the new startup script MCP tools."""

import asyncio
import sys

from verda_mcp.client import get_client
from verda_mcp.config import get_config, update_config_file


async def test_list_scripts():
    """Test listing all scripts."""
    print("\n" + "=" * 60)
    print("TEST: list_scripts")
    print("=" * 60)

    client = get_client()
    scripts = await client.list_scripts()

    print(f"Found {len(scripts)} scripts:")
    for script in scripts:
        print(f"  - {script.name} (ID: {script.id})")
        if script.content:
            preview = script.content[:100].replace("\n", "\\n")
            print(f"    Content preview: {preview}...")

    return scripts


async def test_get_script_by_id(script_id: str):
    """Test getting a script by ID."""
    print("\n" + "=" * 60)
    print(f"TEST: get_script_by_id({script_id})")
    print("=" * 60)

    client = get_client()
    script = await client.get_script_by_id(script_id)

    print(f"Script: {script.name}")
    print(f"ID: {script.id}")
    print(f"Content length: {len(script.content or '')} chars")
    if script.content:
        print(f"Content preview:\n{script.content[:200]}...")

    return script


async def test_get_current_script_for_instance(instance_id: str):
    """Test getting the startup script for an instance."""
    print("\n" + "=" * 60)
    print(f"TEST: get_current_script({instance_id})")
    print("=" * 60)

    client = get_client()

    # First get instance info
    instance = await client.get_instance(instance_id)
    print(f"Instance: {instance.hostname}")
    print(f"Status: {instance.status}")
    print(f"Startup Script ID: {instance.startup_script_id}")

    script = await client.get_current_script(instance_id)

    if script is None:
        print("No startup script attached to this instance.")
    else:
        print(f"Script: {script.name}")
        print(f"ID: {script.id}")
        if script.content:
            print(f"Content preview:\n{script.content[:200]}...")

    return script


async def test_create_script():
    """Test creating a new script."""
    print("\n" + "=" * 60)
    print("TEST: create_script")
    print("=" * 60)

    client = get_client()

    name = "test-script-mcp"
    content = """#!/bin/bash
# Test script created by MCP
echo "Hello from MCP test script!"
date
"""

    script = await client.create_script(name, content)

    print(f"Created script: {script.name}")
    print(f"ID: {script.id}")

    return script


def test_update_config_file(script_id: str):
    """Test updating the config file."""
    print("\n" + "=" * 60)
    print(f"TEST: update_config_file (setting script_id to {script_id})")
    print("=" * 60)

    # Get current config
    config = get_config()
    old_script_id = config.defaults.script_id
    print(f"Current default script_id: {old_script_id}")

    # Update config
    update_config_file({"defaults": {"script_id": script_id}})

    # Verify the change
    new_config = get_config()
    new_script_id = new_config.defaults.script_id
    print(f"New default script_id: {new_script_id}")

    if new_script_id == script_id:
        print("SUCCESS: Config updated correctly!")
    else:
        print("FAILED: Config was not updated correctly!")

    # Restore old value
    print(f"\nRestoring original script_id: {old_script_id}")
    update_config_file({"defaults": {"script_id": old_script_id}})

    return new_script_id == script_id


async def test_list_instances():
    """Test listing instances to find one for testing."""
    print("\n" + "=" * 60)
    print("TEST: list_instances")
    print("=" * 60)

    client = get_client()
    instances = await client.list_instances()

    print(f"Found {len(instances)} instances:")
    for inst in instances:
        print(f"  - {inst.hostname} (ID: {inst.id})")
        print(f"    Status: {inst.status}, Script ID: {inst.startup_script_id}")

    return instances


async def main():
    """Run all tests."""
    print("=" * 60)
    print("VERDA MCP SCRIPT TOOLS TEST SUITE")
    print("=" * 60)

    try:
        # Test 1: List all scripts
        scripts = await test_list_scripts()

        # Test 2: Get script by ID (use the first script found)
        if scripts:
            await test_get_script_by_id(scripts[0].id)

        # Test 3: List instances
        instances = await test_list_instances()

        # Test 4: Get current script for an instance (if any exist)
        if instances:
            await test_get_current_script_for_instance(instances[0].id)

        # Test 5: Test config update (non-destructive - restores original)
        if scripts:
            test_update_config_file(scripts[0].id)

        # Test 6: Create a new script (optional - uncomment to test)
        # new_script = await test_create_script()
        # print(f"\nCreated new script with ID: {new_script.id}")

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
