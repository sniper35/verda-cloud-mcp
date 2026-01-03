# Verda Cloud MCP Server

An MCP (Model Context Protocol) server for managing Verda Cloud GPU instances through Claude. Deploy spot B300 GPU instances, attach volumes, apply startup scripts, and get notified when your instance is ready.

## Features

- **List instances** - View all your running and stopped instances
- **Check spot availability** - Find available B300 (or other) GPU spot instances
- **Deploy spot instances** - Create new spot GPU instances with one command
- **Attach volumes** - Attach your data volumes to instances
- **Apply startup scripts** - Automatically run setup scripts on boot
- **Wait for ready** - Polls until your instance is running and returns SSH info

## Quick Start

### 1. Install dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Configure credentials

```bash
# Copy the example config
cp config.yaml.example config.yaml

# Edit with your credentials
# Get your API credentials from: https://console.verda.com/dashboard/api
```

Edit `config.yaml`:

```yaml
client_id: "your-actual-client-id"
client_secret: "your-actual-client-secret"

defaults:
  project: "vllm-omni"
  gpu_type: "B300"
  volume_id: "your-volume-id"  # Optional
  script_id: "your-script-id"  # Optional
```

### 3. Run the server

```bash
# Using uv
uv run python -m verda_mcp

# Or directly
python -m verda_mcp
```

## Claude Desktop Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "verda-cloud": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/verda-cloud-mcp",
        "run",
        "python",
        "-m",
        "verda_mcp"
      ]
    }
  }
}
```

Or if installed globally:

```json
{
  "mcpServers": {
    "verda-cloud": {
      "command": "verda-mcp"
    }
  }
}
```

Restart Claude Desktop after updating the configuration.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_instances` | List all your Verda Cloud instances |
| `check_instance_status` | Get detailed status of a specific instance |
| `check_spot_availability` | Check available spot GPU instances (default: B300) |
| `list_volumes` | List your block storage volumes |
| `list_scripts` | List your startup scripts |
| `list_ssh_keys` | List your SSH keys |
| `deploy_spot_instance` | Deploy a new spot GPU instance |
| `delete_instance` | Delete an instance (requires confirmation) |
| `shutdown_instance` | Shutdown a running instance |
| `start_instance` | Start a stopped instance |
| `attach_volume` | Attach a volume to an instance |
| `detach_volume` | Detach a volume from an instance |
| `create_startup_script` | Create a new startup script |

## Example Usage

Once configured with Claude Desktop, you can ask Claude:

### Check availability
> "Check if there are any B300 spot instances available"

### Deploy an instance
> "Deploy a B300 spot instance with my data volume and startup script"

### Quick workflow
> "Check for B300 availability, and if available, deploy one with volume abc123 and script xyz789"

### Monitor instances
> "List all my instances and their status"

### Get SSH info
> "Check the status of instance inst-12345 and give me the SSH command"

## Configuration Reference

### config.yaml

```yaml
# Required: Verda API credentials
client_id: "your-client-id"
client_secret: "your-client-secret"

# Optional: Default values for deployments
defaults:
  project: "your-project-name"
  gpu_type: "B300"
  volume_id: ""  # Pre-configured volume to attach
  script_id: ""  # Pre-configured startup script
  image: "ubuntu-24.04-cuda-12.8-open-docker"
  hostname_prefix: "spot-gpu"

# Optional: Deployment behavior
deployment:
  ready_timeout: 600  # Max seconds to wait for instance
  poll_interval: 10   # Seconds between status checks
  use_spot: true      # Default to spot instances
```

### Default Project

The `defaults.project` setting determines how your instances are named and organized:
- **project** - A project identifier used for organizing instances (e.g., "vllm-omni", "sglang-slime")
- **hostname_prefix** - Automatically set to `{project}-{gpu_type}` (e.g., "vllm-omni-B300")

When you deploy a new instance, it will be named with the hostname prefix followed by a timestamp.

### Switching Projects

To switch to a different project during a session, use the `/verda-project` command:

```
/verda-project
```

This will:
1. Show your current project and hostname prefix
2. Ask which project you want to switch to
3. Update the config.yaml with the new project name and hostname prefix

You can also provide the project name directly:

```
/verda-project my-new-project
```

The hostname prefix will automatically be updated to `{project}-B300`.

### Environment Variables

You can also set the config path via environment variable:

```bash
export VERDA_MCP_CONFIG=/path/to/config.yaml
```

## Getting Your API Credentials

1. Log in to [Verda Console](https://console.verda.com)
2. Go to **Dashboard** → **API**
3. Create new API credentials
4. Copy the `Client ID` and `Client Secret`

## Project Structure

```
verda-cloud-mcp/
├── pyproject.toml           # Project configuration
├── config.yaml.example      # Configuration template
├── config.yaml              # Your credentials (gitignored)
├── README.md
└── src/
    └── verda_mcp/
        ├── __init__.py
        ├── __main__.py      # Entry point
        ├── server.py        # MCP server with tools
        ├── client.py        # Verda API client
        └── config.py        # Configuration loader
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run server in development mode
uv run python -m verda_mcp
```

## Troubleshooting

### "Config file not found"
Copy `config.yaml.example` to `config.yaml` and fill in your credentials.

### "No SSH keys found"
Add an SSH key in the Verda console before deploying instances.

### Instance never becomes ready
Check the Verda console for any deployment errors. The instance may have failed to start.

### Connection refused
Ensure your firewall allows SSH (port 22) from your IP.

## License

MIT
# verda-cloud-mcp
