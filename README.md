# mcp-json-yaml-toml

[![Test](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml/badge.svg)](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml)
[![Publish](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml/badge.svg)](https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml)
[![PyPI version](https://badge.fury.io/py/mcp-json-yaml-toml.svg)](https://badge.fury.io/py/mcp-json-yaml-toml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

<img src="https://github.com/user-attachments/assets/bc1d4078-a72a-4def-8c5b-a1c653e98816" alt="JYT Logo" width="200">

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
- **Constraint validation**: LMQL-powered input validation with partial match support for guided generation
- **Local operation**: No cloud dependency, no indexing, no external services
- **Cross-platform**: Works on Linux, macOS, and Windows with bundled yq binaries

**Compatible with any MCP client**: Claude Code CLI, Cursor, Windsurf, VS Code with MCP extensions, and more.

### What It Provides

The server provides 7 MCP tools for structured data manipulation:

- **`data`**: Get, set, or delete values at specific paths in configuration files
- **`data_query`**: Run advanced yq expressions for complex queries and transformations
- **`data_schema`**: Validate files against JSON schemas and manage schema catalogs
- **`data_convert`**: Convert between JSON, YAML, and TOML formats
- **`data_merge`**: Deep merge two configuration files with environment overrides
- **`constraint_validate`**: Validate inputs against LMQL constraints with partial match support
- **`constraint_list`**: List available constraints for guided generation

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
- An MCP-compatible client (see [docs/clients.md](docs/clients.md) for supported clients)

### Installation

MCP servers run as external processes and communicate via stdio with your MCP client. This server uses `uvx` for automatic dependency management.

#### Claude Code (CLI)

```bash
claude mcp add --scope user mcp-json-yaml-toml -- uvx mcp-json-yaml-toml
```

#### Other MCP Clients

Most MCP clients use a JSON configuration format. Add this to your client's MCP configuration file:

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

See [docs/clients.md](docs/clients.md) for detailed setup instructions for specific clients including Cursor, VS Code with Continue, Windsurf, Zed Editor, and other MCP-compatible tools.

### Example Usage

Once configured, you can ask your AI assistant to perform operations like:

**Reading configuration values:**
- "What stages are defined in my GitLab CI file?"
- "Show me the project name from pyproject.toml"
- "Get all dependencies from package.json"

**Converting between formats:**
- "Convert config.yaml to JSON format"
- "Export this TOML file as YAML"

> **Note:** Conversion TO TOML is not supported. See [docs/tools.md](docs/tools.md#supported-conversions) for details.

**Validation:**
- "Validate this YAML file syntax"
- "Check if config.json matches its schema from SchemaStore"

**Advanced queries:**
- "Extract all job names from .gitlab-ci.yml"
- "Merge base.yaml with production.yaml"
- "Show the structure of config.json without values"

These natural language prompts are translated by your AI assistant into the appropriate MCP tool calls.

---

## Available Tools

The server provides 7 tools: `data`, `data_query`, `data_schema`, `data_convert`, `data_merge`, `constraint_validate`, and `constraint_list`.

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

# Install dependencies (including dev dependencies)
uv sync
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
│   ├── lmql_constraints.py       # LMQL constraint validation
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
- Uses [LMQL](https://github.com/eth-sri/lmql) regex derivatives for constraint validation
