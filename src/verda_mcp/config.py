"""Configuration loader for Verda MCP Server."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DeploymentConfig:
    """Deployment-related settings."""

    ready_timeout: int = 600
    poll_interval: int = 10
    use_spot: bool = True


@dataclass
class DefaultsConfig:
    """Default values for instance deployment."""

    project: str = ""
    gpu_type: str = "B300"
    gpu_count: int = 1
    location: str = "FIN-03"
    volume_id: str = ""
    volume_size: int = 150  # Default volume size in GB
    script_id: str = ""
    image: str = "ubuntu-24.04-cuda-12.8-open-docker"
    hostname_prefix: str = "spot-gpu"


@dataclass
class Config:
    """Main configuration for Verda MCP Server."""

    client_id: str
    client_secret: str
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Config":
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file. If None, searches in standard locations.

        Returns:
            Loaded Config instance.

        Raises:
            FileNotFoundError: If no config file is found.
            ValueError: If required fields are missing.
        """
        if config_path is None:
            config_path = cls._find_config_file()

        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                "Please copy config.yaml.example to config.yaml and "
                "fill in your credentials."
            )

        with open(config_path) as f:
            data = yaml.safe_load(f)

        # Validate required fields
        client_id = data.get("client_id", "")
        client_secret = data.get("client_secret", "")

        if not client_id or client_id == "your-client-id-here":
            raise ValueError(
                "client_id is required. Please set it in config.yaml"
            )
        if not client_secret or client_secret == "your-client-secret-here":
            raise ValueError(
                "client_secret is required. Please set it in config.yaml"
            )

        # Parse defaults
        defaults_data = data.get("defaults", {})
        defaults = DefaultsConfig(
            project=defaults_data.get("project", ""),
            gpu_type=defaults_data.get("gpu_type", "B300"),
            gpu_count=defaults_data.get("gpu_count", 1),
            location=defaults_data.get("location", "FIN-03"),
            volume_id=defaults_data.get("volume_id", ""),
            volume_size=defaults_data.get("volume_size", 150),
            script_id=defaults_data.get("script_id", ""),
            image=defaults_data.get("image", "ubuntu-24.04-cuda-12.8-open-docker"),
            hostname_prefix=defaults_data.get("hostname_prefix", "spot-gpu"),
        )

        # Parse deployment settings
        deployment_data = data.get("deployment", {})
        deployment = DeploymentConfig(
            ready_timeout=deployment_data.get("ready_timeout", 600),
            poll_interval=deployment_data.get("poll_interval", 10),
            use_spot=deployment_data.get("use_spot", True),
        )

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            defaults=defaults,
            deployment=deployment,
        )

    @staticmethod
    def _find_config_file() -> Path:
        """Find config file in standard locations.

        Search order:
        1. VERDA_MCP_CONFIG environment variable
        2. ./config.yaml (current directory)
        3. ~/.config/verda-mcp/config.yaml
        """
        # Check environment variable
        env_path = os.environ.get("VERDA_MCP_CONFIG")
        if env_path:
            return Path(env_path)

        # Check current directory
        cwd_config = Path.cwd() / "config.yaml"
        if cwd_config.exists():
            return cwd_config

        # Check user config directory
        user_config = Path.home() / ".config" / "verda-mcp" / "config.yaml"
        if user_config.exists():
            return user_config

        # Default to current directory (will raise error if not found)
        return cwd_config


# Global config instance (loaded on first access)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        The loaded Config instance.
    """
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config(config_path: str | Path | None = None) -> Config:
    """Reload the configuration from file.

    Args:
        config_path: Optional path to config file.

    Returns:
        The newly loaded Config instance.
    """
    global _config
    _config = Config.load(config_path)
    return _config


def update_config_file(updates: dict) -> None:
    """Update specific fields in the config file.

    Updates the YAML config file with the provided values and reloads the
    global config. Supports nested keys using nested dicts.

    Args:
        updates: Dict with nested structure, e.g., {"defaults": {"script_id": "abc123"}}

    Example:
        update_config_file({"defaults": {"script_id": "new-script-id"}})
    """
    config_path = Config._find_config_file()

    with open(config_path) as f:
        data = yaml.safe_load(f)

    # Deep merge updates into data
    def deep_merge(base: dict, updates: dict) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                deep_merge(base[key], value)
            else:
                base[key] = value

    deep_merge(data, updates)

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    # Reload the global config to reflect changes
    reload_config()
