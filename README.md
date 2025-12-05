# mcp-json-yaml-toml

[![Test](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml/badge.svg)](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml)
[![Publish](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml/badge.svg)](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml)
[![PyPI version](https://badge.fury.io/py/mcp-json-yaml-toml.svg)](https://badge.fury.io/py/mcp-json-yaml-toml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Smart JSON/YAML/TOML tools for MCP agents.**

Safely query, modify, validate, and convert JSON, YAML, and TOML files while preserving comments, formatting, and structure. Perfect for working with configuration files, API responses, manifests, and any structured data across multiple formats.

---

## What You Get

This MCP server gives AI agents intelligent tools for configuration management:

- **Multi-format support**: Seamlessly work with JSON, YAML, and TOML files using a unified interface
- **Powerful querying**: Use yq's jq-compatible expressions to extract and analyze nested data
- **Safe modifications**: Validate changes before writing; preserve comments and formatting
- **Format conversion**: Automatically convert between JSON, YAML, and TOML with zero data loss
- **Config merging**: Intelligently merge base configs with environment-specific overrides
- **Schema validation**: Leverage SchemaStore.org catalogs or custom schemas for validation
- **YAML optimization**: Automatically generate anchors/aliases for duplicate structures to maintain DRY
- **Cross-platform**: Works on Linux, macOS, and Windows with bundled yq binaries

## Why It Matters

Configuration management is error-prone when done manually:

- Editing YAML indentation mistakes break deployments
- Format conversions introduce subtle bugs
- Duplicate config sections violate DRY principles
- Manual schema validation catches problems only in production

**With mcp-json-yaml-toml**, your AI assistant can:

- Safely validate and modify configs before pushing to infrastructure
- Convert legacy configs to modern formats without losing data
- Detect and fix common configuration problems
- Ensure consistency across deployment environments

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- An MCP client (Claude Desktop, Cursor, VS Code, etc.)

### Installation

MCP servers run as external processes and are not installed as libraries. They communicate via stdio with your MCP client.

### Claude Code (CLI)

```bash
# Basic install
claude mcp add --scope user mcp-json-yaml-toml -- uvx mcp-json-yaml-toml

# With environment variables (e.g., to limit formats)
claude mcp add --scope user mcp-json-yaml-toml -e MCP_CONFIG_FORMATS=json,yaml -- uvx mcp-json-yaml-toml
```

### Updating

When using `uvx`, clear the cache to get the latest version:

```bash
uv cache clean mcp-json-yaml-toml
```

The next time the MCP server runs, `uvx` will download the latest version.

### Claude Desktop Configuration

1. Open your Claude Desktop configuration file:

   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the server to your `mcpServers` section:

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

This configuration uses `uvx` to automatically download and run the server in an isolated environment.

3. Restart Claude Desktop to activate the server.

### Try It Now

Here are real examples you can use with Claude Desktop:

#### Query Configuration Files

- **"What stages are defined in my GitLab CI?"** - Returns: `build`, `test`, `deploy`, etc.
- **"Show me the project name from pyproject.toml"** - Extracts: `mcp-json-yaml-toml`
- **"Get all dependencies from package.json"** - Lists npm packages with versions

#### Convert Between Formats

- **"Convert this config.toml to YAML"** - Preserves all data in new format
- **"Convert this config.toml to JSON"** - Export TOML to JSON format
- **"Convert GitLab CI YAML to JSON for API use"** - Enables programmatic access

> **Note:** Conversion to TOML format from JSON/YAML is not supported due to yq limitations. See [docs/tools.md](docs/tools.md#supported-conversions) for the full conversion matrix.

#### Validate and Fix

- **"Check if my YAML file is valid"** - Validates syntax before deployment
- **"Validate against schema from SchemaStore"** - Ensures compliance with specs
- **"Fix YAML indentation issues"** - Corrects formatting problems

#### Advanced Operations

- **"Extract all job names from .gitlab-ci.yml"** - Query: `.* | select(type == "object") | keys`
- **"Merge base config with production overrides"** - Deep merges configurations
- **"Show config structure without values"** - Returns keys only for overview

---

## Available Tools

The server provides 5 tools: `data`, `data_query`, `data_schema`, `data_convert`, and `data_merge`.

See [docs/tools.md](docs/tools.md) for parameters, examples, and usage reference.

---

## Configuration

See [docs/tools.md](docs/tools.md) for environment variables and configuration options.

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/bitflight-devops/mcp-json-yaml-toml.git
cd mcp-json-yaml-toml

# Install with development dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py

# Run with verbose output
uv run pytest -v
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code
uv run ruff check --fix

# Type check
uv run mypy packages/

# Run all checks
uv run pre-commit run --all-files
```

---

## Project Structure

```text
mcp-json-yaml-toml/
├── packages/mcp_json_yaml_toml/  # Main package
│   ├── server.py                 # MCP server implementation
│   ├── yq_wrapper.py             # yq binary wrapper
│   ├── schemas.py                # JSON Schema management
│   ├── yaml_optimizer.py         # YAML anchor/alias optimization
│   ├── toml_utils.py             # TOML file operations
│   ├── config.py                 # Configuration management
│   └── tests/                    # Test suite
├── docs/                         # Documentation
│   ├── tools.md                  # Tool reference
│   ├── clients.md                # Client setup guides
│   ├── module-usage.md           # Module dependencies
│   └── yq-wrapper.md             # yq wrapper usage
├── scripts/                      # Utility scripts
├── fixtures/                     # Test fixtures
├── pyproject.toml                # Project configuration
└── README.md                     # This file
```

---

## Requirements

- Python 3.11 or higher
- Bundled yq binaries (no external installation required)

---

## License

MIT License - see LICENSE file for details

---

## Contributing

Contributions are welcome! Please ensure all tests pass and code quality checks succeed before submitting a pull request.

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Uses [yq](https://github.com/mikefarah/yq) for configuration file processing
