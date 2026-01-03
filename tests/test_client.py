"""Integration test for basic Verda client operations.

This test requires valid VERDA_CLIENT_ID and VERDA_CLIENT_SECRET environment
variables and will create/delete a real instance. Skip in CI environments.
"""

import os

import pytest
from verda import VerdaClient
from verda.constants import Actions


@pytest.mark.skipif(
    not os.environ.get("VERDA_CLIENT_ID"),
    reason="VERDA_CLIENT_ID not set",
)
def test_create_and_delete_instance():
    """Test creating and deleting an instance using the Verda SDK."""
    # Get credentials from environment variables
    client_id = os.environ["VERDA_CLIENT_ID"]
    client_secret = os.environ["VERDA_CLIENT_SECRET"]

    # Create client
    verda = VerdaClient(client_id, client_secret)

    # Get all SSH keys
    ssh_keys = [key.id for key in verda.ssh_keys.get()]

    # Create a new instance
    instance = verda.instances.create(
        instance_type="1V100.6V",
        image="ubuntu-24.04-cuda-12.8-open-docker",
        ssh_key_ids=ssh_keys,
        hostname="example",
        description="example instance",
    )

    assert instance.id is not None

    # Delete instance
    verda.instances.action(instance.id, Actions.DELETE)
