# MCP Config Tools

A Model Context Protocol (MCP) server for querying and modifying JSON, YAML, and TOML configuration files using the powerful `yq` command-line tool.

## Overview

This MCP server provides AI agents with the ability to:

- Query configuration files using yq's expressive query language
- Modify configuration values safely and efficiently
- Support multiple configuration formats (JSON, YAML, TOML)
- Handle complex nested structures and arrays
- Validate configuration changes before applying

## Features

- **Multi-format Support**: Works seamlessly with JSON, YAML, and TOML files
- **Powerful Querying**: Leverages yq's jq-compatible query syntax
- **Safe Modifications**: Validates changes before writing to disk
- **Smart YAML Optimization**: Automatically maintains DRY principles by generating anchors/aliases for duplicate structures
- **Fidelity Preservation**: Preserves comments and formatting for both YAML (via ruamel.yaml) and TOML (via tomlkit)
- **Cross-Platform**: Bundles yq binaries for Linux, macOS, and Windows
- **Type-Safe**: Full Python type hints and strict mypy compliance
- **Fast**: Uses orjson for high-performance JSON processing

## Installation

```bash
# Using uv (recommended)
uv pip install mcp-config-tools

# Using pip
pip install mcp-config-tools
```

## Usage

### As MCP Server

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "config-tools": {
      "command": "mcp-config-tools",
      "args": []
    }
  }
}
```

### Available Tools

The MCP server provides 5 focused tools:

- **data**: Unified CRUD for configuration files
  - `operation="get"`: Retrieve data, schema, or structure
    - `type="data", return_type="all"`: Get data at key_path
    - `type="data", return_type="keys"`: Get structure (keys only)  
    - `type="schema"`: Get JSON schema from Schema Store
  - `operation="set"`: Update/create value
  - `operation="delete"`: Remove key/element
  
- **data_query**: Execute advanced yq expressions against files

- **data_schema**: Unified schema operations
  - `action="validate"`: Validate syntax and schema
  - `action="scan"`: Recursively search for schema directories
  - `action="add_dir"`: Add custom schema directory
  - `action="add_catalog"`: Add custom schema catalog  
  - `action="list"`: Show schema configuration

- **data_convert**: Transform files between JSON, YAML, and TOML formats

- **data_merge**: Deep merge two configuration files

### Prompts

The server provides pre-defined prompts to help AI agents interact with configuration files:

- **explain_config**: Analyze and explain a configuration file
- **suggest_improvements**: Suggest security, performance, and structural improvements
- **convert_to_schema**: Generate a JSON schema from a configuration file

### Schema Store Integration

The server integrates with [SchemaStore.org](https://www.schemastore.org/json/) for automatic JSON schema discovery and validation.

**Features:**
- Automatic schema discovery for common file types (`pyproject.toml`, `package.json`, `.gitlab-ci.yml`, etc.)
- Checks IDE caches first (VS Code, Cursor, JetBrains) to avoid network requests
- Local schema caching (~/.cache/mcp-json-yaml-toml/schemas, 24h expiry)
- Concurrent schema checking using ThreadPoolExecutor for performance
- Configurable discovery with `data_schema`

### Configuration

The server can be configured via environment variables:

- **MCP_CONFIG_FORMATS**: Comma-separated list of enabled formats (default: "json,yaml,toml"). Example: `export MCP_CONFIG_FORMATS="json,yaml"`
- **MCP_SCHEMA_CACHE_DIRS**: Colon-separated list of additional directories to search for schemas. Example: `export MCP_SCHEMA_CACHE_DIRS="/opt/schemas:/usr/local/share/schemas"`

### YAML Anchor Optimization

The server automatically detects duplicate structures in YAML files and generates anchors/aliases to maintain DRY principles. This feature is **context-aware** and only activates if the file already uses anchors.

Configuration variables:
- **YAML_ANCHOR_OPTIMIZATION**: Enable/disable optimization (default: `true`)
- **YAML_ANCHOR_MIN_SIZE**: Minimum number of keys/items for a structure to be anchored (default: `3`)
- **YAML_ANCHOR_MIN_DUPLICATES**: Minimum number of occurrences to trigger anchoring (default: `2`)

**Runtime Configuration:**
```bash
# Scan directories for schemas (persists results)
data_schema(action="scan", search_paths=["~/.config"])

# Add custom schema directory
data_schema(action="add_dir", path="/path/to/schemas")

# Add custom schema catalog
data_schema(action="add_catalog", name="company", uri="https://...")
```

Schema discovery looks for:
- Directories named `schemas` or `jsonSchemas`
- Directories containing `catalog.json`
- Directories with `.schema.json` files


## Development

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/mcp-config-tools.git
cd mcp-config-tools

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
uv run pytest tests/test_server.py

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
uv run mypy src/

# Run all checks
uv run pre-commit run --all-files
```

## Project Structure

```
mcp-config-tools/
├── src/
│   └── mcp_config_tools/
│       ├── __init__.py
│       ├── server.py           # Main MCP server
│       ├── yq_wrapper.py       # yq binary wrapper
│       └── binaries/           # Platform-specific yq binaries
│           ├── yq-linux-amd64
│           ├── yq-darwin-amd64
│           └── yq-windows-amd64.exe
├── tests/
│   ├── __init__.py
│   └── test_server.py
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.11 or higher
- Bundled yq binaries (no external installation required)

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please ensure all tests pass and code quality checks succeed before submitting a pull request.

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Uses [yq](https://github.com/mikefarah/yq) for configuration file processing
