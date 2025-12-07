# mcp-json-yaml-toml

[![Test](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml/badge.svg)](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml)
[![Publish](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml/badge.svg)](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml)
[![PyPI version](https://badge.fury.io/py/mcp-json-yaml-toml.svg)](https://badge.fury.io/py/mcp-json-yaml-toml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**A token-efficient, schema-aware MCP server for safely reading and modifying JSON, YAML, and TOML files.**

Stop AI coding tools from breaking your data files. No more grep guesswork, hallucinated fields, or invalid configs. This MCP server gives AI assistants a strict, round-trip safe interface for working with structured data.

---

## The Problem

AI coding tools often destroy structured data files:

- They grep through huge configs and guess at keys
- They hallucinate fields that never existed
- They use sed and regex that leave files in invalid states
- They break YAML indentation and TOML syntax
- They can't validate changes before writing

**The result**: Broken deployments, corrupted configs, and manual cleanup work.

## The Solution

**mcp-json-yaml-toml** provides AI assistants with proper tools for structured data:

- **Token-efficient queries**: Extract exactly what you need without loading entire files
- **Schema validation**: Enforce correctness using SchemaStore.org or custom schemas
- **Safe modifications**: Validate before writing; preserve comments and formatting
- **Multi-format support**: JSON, YAML, and TOML through a unified interface
- **Local operation**: No cloud dependency, no indexing, no external services
- **Cross-platform**: Works on Linux, macOS, and Windows with bundled yq binaries

**Compatible with any MCP client**: Claude Code CLI, Cursor, Windsurf, VS Code with MCP extensions, and more.

### What It Provides

The server provides 5 MCP tools for structured data manipulation:

- **`data`**: Get, set, or delete values at specific paths in configuration files
- **`data_query`**: Run advanced yq expressions for complex queries and transformations
- **`data_schema`**: Validate files against JSON schemas and manage schema catalogs
- **`data_convert`**: Convert between JSON, YAML, and TOML formats
- **`data_merge`**: Deep merge two configuration files with environment overrides

See [docs/tools.md](docs/tools.md) for detailed API reference and examples.

### Key Features

- **Powerful querying**: Use yq's jq-compatible expressions to extract nested data
- **Format conversion**: Convert between JSON, YAML, and TOML (with limitations)
- **Config merging**: Intelligently merge base configs with environment-specific overrides
- **YAML optimization**: Auto-generate anchors/aliases for duplicate structures (DRY principle)
- **Comment preservation**: Modifications maintain existing comments and formatting

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- An MCP-compatible client (Claude Code CLI, Cursor, Windsurf, etc.)

### Installation

MCP servers run as external processes and communicate via stdio with your MCP client.

### Claude Code (CLI Tool)

The Claude Code CLI tool provides the easiest installation experience:

```bash
# Basic install
claude mcp add --scope user mcp-json-yaml-toml -- uvx mcp-json-yaml-toml

# With environment variables (e.g., to limit formats)
claude mcp add --scope user mcp-json-yaml-toml -e MCP_CONFIG_FORMATS=json,yaml -- uvx mcp-json-yaml-toml
```

**Updating**: When using `uvx`, clear the cache to get the latest version:

```bash
uv cache clean mcp-json-yaml-toml
```

The next time the MCP server runs, `uvx` will download the latest version.

### Claude Desktop

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

3. Restart Claude Desktop to activate the server.

### Other MCP Clients

For Cursor, Windsurf, VS Code with MCP extensions, and other clients, see [docs/clients.md](docs/clients.md) for detailed setup instructions.

### Try It Now

Here are real examples you can use with any MCP client:

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
