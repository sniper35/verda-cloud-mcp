"""Test the MCP server tools directly."""

import asyncio
import sys

from verda_mcp import server
from verda_mcp.config import get_config


async def test_list_scripts_tool():
    """Test the list_scripts MCP tool."""
    print("\n" + "=" * 60)
    print("TEST: list_scripts MCP tool")
    print("=" * 60)

    result = await server.list_scripts()
    print(result)
    return result


async def test_get_instance_startup_script_tool():
    """Test the get_instance_startup_script MCP tool."""
    print("\n" + "=" * 60)
    print("TEST: get_instance_startup_script MCP tool")
    print("=" * 60)

    # First get an instance
    client = server._get_client()
    instances = await client.list_instances()

    if not instances:
        print("No instances found. Skipping this test.")
        return None

    result = await server.get_instance_startup_script(instances[0].id)
    print(result)
    return result


async def test_create_and_set_default_script_tool():
    """Test the create_and_set_default_script MCP tool."""
    print("\n" + "=" * 60)
    print("TEST: create_and_set_default_script MCP tool")
    print("=" * 60)

    # Get original config for restoration
    config = get_config()
    original_script_id = config.defaults.script_id
    print(f"Original default script_id: {original_script_id}")

    # Create and set a new script as default
    result = await server.create_and_set_default_script(
        name="mcp-test-script",
        content="""#!/bin/bash
echo "MCP test script created at $(date)"
""",
    )
    print(result)

    # Verify the config was updated
    from verda_mcp.config import reload_config

    new_config = reload_config()
    print(f"\nNew default script_id: {new_config.defaults.script_id}")

    # Restore original script_id
    print(f"\nRestoring original script_id: {original_script_id}")
    from verda_mcp.config import update_config_file

    update_config_file({"defaults": {"script_id": original_script_id}})

    return result


async def test_set_default_script_tool():
    """Test the set_default_script MCP tool."""
    print("\n" + "=" * 60)
    print("TEST: set_default_script MCP tool")
    print("=" * 60)

    # Get original config for restoration
    config = get_config()
    original_script_id = config.defaults.script_id
    print(f"Original default script_id: {original_script_id}")

    # Get a different script to set as default
    client = server._get_client()
    scripts = await client.list_scripts()

    if len(scripts) < 2:
        print("Not enough scripts to test. Skipping.")
        return None

    # Pick a script that's different from the current default
    test_script = None
    for s in scripts:
        if s.id != original_script_id:
            test_script = s
            break

    if not test_script:
        print("No different script found. Skipping.")
        return None

    print(f"Setting {test_script.name} ({test_script.id}) as default...")

    result = await server.set_default_script(test_script.id)
    print(result)

    # Verify the config was updated
    from verda_mcp.config import reload_config

    new_config = reload_config()
    print(f"\nVerified new default script_id: {new_config.defaults.script_id}")

    # Restore original script_id
    print(f"\nRestoring original script_id: {original_script_id}")
    from verda_mcp.config import update_config_file

    update_config_file({"defaults": {"script_id": original_script_id}})

    return result


async def test_show_config_tool():
    """Test the show_config MCP tool."""
    print("\n" + "=" * 60)
    print("TEST: show_config MCP tool")
    print("=" * 60)

    result = await server.show_config()
    print(result)
    return result


async def main():
    """Run all MCP tool tests."""
    print("=" * 60)
    print("VERDA MCP TOOLS TEST SUITE")
    print("=" * 60)

    try:
        # Test 1: list_scripts
        await test_list_scripts_tool()

        # Test 2: get_instance_startup_script (if instances exist)
        await test_get_instance_startup_script_tool()

        # Test 3: show_config
        await test_show_config_tool()

        # Test 4: set_default_script
        await test_set_default_script_tool()

        # Test 5: create_and_set_default_script (creates a new script)
        # Uncomment to test - this creates a real script in Verda
        # await test_create_and_set_default_script_tool()

        print("\n" + "=" * 60)
        print("ALL MCP TOOL TESTS COMPLETED SUCCESSFULLY!")
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
