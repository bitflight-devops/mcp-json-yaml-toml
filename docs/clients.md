# Client Configuration Guide

**Audience:** End users and developers configuring MCP clients (Claude Desktop, Cursor, VS Code, etc.) to use the `mcp-json-yaml-toml` server.

This guide shows how to configure `mcp-json-yaml-toml` with various MCP clients. All examples use `uvx` for automatic dependency management.

## Claude Desktop

### Installation

Claude Desktop uses `uvx` to automatically manage the MCP server.

#### Configuration File Location

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

#### Basic Configuration

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"]
    }
  }
}
```

#### With Environment Variables

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "env": {
        "MCP_CONFIG_FORMATS": "json,yaml",
        "YAML_ANCHOR_OPTIMIZATION": "false"
      }
    }
  }
}
```

### Restart Required

After modifying the configuration, restart Claude Desktop for changes to take effect.

---

## Cursor IDE

### Installation

Cursor uses the same MCP protocol but with a slightly different configuration format.

#### Configuration File

Edit `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

#### Global Configuration

For global installation, edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"]
    }
  }
}
```

---

## VS Code with Continue

### Installation

The Continue extension for VS Code supports MCP servers.

#### Configuration

Edit `~/.continue/config.json`:

```json
{
  "models": [
    // Your model configuration
  ],
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"]
    }
  }
}
```

#### Workspace Configuration

For project-specific configuration, create `.continue/config.json` in your workspace:

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "env": {
        "MCP_SCHEMA_CACHE_DIRS": "${workspaceFolder}/.schemas"
      }
    }
  }
}
```

---

## Windsurf Editor

### Installation

Windsurf has native MCP support with automatic server discovery.

#### Configuration

Edit `~/.windsurf/mcp/servers.json`:

```json
{
  "servers": [
    {
      "name": "json-yaml-toml",
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "enabled": true
    }
  ]
}
```

#### Project Configuration

Create `.windsurf/mcp.json` in your project:

```json
{
  "servers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "autoStart": true
    }
  }
}
```

---

## Zed Editor

### Installation

Zed supports MCP through its assistant panel.

#### Configuration

Edit `~/.config/zed/settings.json`:

```json
{
  "assistant": {
    "mcp_servers": {
      "json-yaml-toml": {
        "command": "uvx",
        "args": ["mcp-json-yaml-toml"]
      }
    }
  }
}
```

---

## Terminal/CLI Usage

### Using MCP Inspector for Testing

For interactive testing and debugging, use the official MCP Inspector:

```bash
# Install the inspector
npm install -g @modelcontextprotocol/inspector

# Test the server (opens browser UI at localhost:5173)
mcp-inspector uvx mcp-json-yaml-toml
```

---

## Local Development

When developing or testing locally, use `uv run` instead of `uvx`:

### Development Configuration

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uv",
      "args": ["run", "mcp-json-yaml-toml"],
      "env": {
        "YQ_DEBUG": "true"
      }
    }
  }
}
```

This uses your local development version instead of the published package.

---

## Environment Variables

All clients support passing environment variables to customize behavior:

| Variable                   | Purpose                       | Example                   |
| -------------------------- | ----------------------------- | ------------------------- |
| `MCP_CONFIG_FORMATS`       | Enable specific formats       | `"json,yaml"`             |
| `MCP_SCHEMA_CACHE_DIRS`    | Additional schema directories | `"/schemas:/app/schemas"` |
| `YAML_ANCHOR_OPTIMIZATION` | Enable/disable YAML anchors   | `"false"`                 |
| `YQ_DEBUG`                 | Enable debug output           | `"true"`                  |

### Example with Multiple Variables

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "env": {
        "MCP_CONFIG_FORMATS": "yaml,toml",
        "YAML_ANCHOR_OPTIMIZATION": "true",
        "YAML_ANCHOR_MIN_SIZE": "5",
        "YAML_ANCHOR_MIN_DUPLICATES": "3"
      }
    }
  }
}
```

---

## Troubleshooting

### Server Not Starting

1. **Check Installation**:

   ```bash
   uvx mcp-json-yaml-toml --help
   ```

2. **Verify Configuration Path**:

   - Ensure config file is in correct location
   - Check JSON syntax is valid

3. **Check Configuration**:
   - Review your MCP client's configuration file for syntax errors
   - Ensure the server command path is correct

### Permission Issues

If the server can't access files:

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "cwd": "/path/to/config/files"
    }
  }
}
```

### Format Not Supported

Check enabled formats:

```bash
MCP_CONFIG_FORMATS=json,yaml,toml uvx mcp-json-yaml-toml
```

### Schema Validation Issues

Add schema directories:

```json
{
  "env": {
    "MCP_SCHEMA_CACHE_DIRS": "~/.schemas:/usr/share/schemas"
  }
}
```

---

## Advanced Configurations

### Custom Working Directory

Set specific working directory for file operations:

```json
{
  "mcpServers": {
    "json-yaml-toml": {
      "command": "uvx",
      "args": ["mcp-json-yaml-toml"],
      "cwd": "${workspaceFolder}/configs"
    }
  }
}
```

---

## Platform-Specific Notes

### Windows

- Use forward slashes in paths: `C:/Users/name/configs`
- Or escape backslashes: `C:\\Users\\name\\configs`

### macOS

- Grant terminal/IDE permissions for file access if prompted
- Homebrew Python may require additional PATH configuration

### Linux

- Ensure `~/.local/bin` is in PATH for uvx
- May need to install `python3-venv` package on some distributions

---

## Getting Help

1. **Check server is accessible**:

   ```bash
   which uvx
   uvx --version
   ```

2. **Test server directly**:

   ```bash
   uvx mcp-json-yaml-toml
   ```

3. **Enable debug mode**:
   Add `"YQ_DEBUG": "true"` to environment variables

4. **Report issues**:
   <https://github.com/bitflight-devops/mcp-json-yaml-toml/issues>
