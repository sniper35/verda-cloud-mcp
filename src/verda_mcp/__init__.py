"""Verda Cloud MCP Server - GPU instance management for Claude."""

from .client import VerdaSDKClient, get_client
from .config import Config, get_config
from .server import mcp

__version__ = "0.1.0"

__all__ = [
    "Config",
    "VerdaSDKClient",
    "get_client",
    "get_config",
    "mcp",
]
