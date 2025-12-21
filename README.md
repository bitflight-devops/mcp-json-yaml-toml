<p align="center">
  <img src=".github/logo.png" alt="JYT Logo" width="600">
</p>

<h1 align="center">mcp-json-yaml-toml</h1>

<p align="center">
  <em>A token-efficient, schema-aware MCP server for safely reading and modifying JSON, YAML, and TOML files</em>
</p>

<p align="center">
  <a href="#getting-started">Getting Started</a> •
  <a href="#claude-code-cli">CLI Usage</a> •
  <a href="#available-tools">Available Tools</a> •
  <a href="#development">Development</a>
</p>

<p align="center">
  <a href="https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml"><img src="https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/test.yml/badge.svg" alt="Test"></a>
  <a href="https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml"><img src="https://github.com/bitflight-devops/mcp-json-yaml-toml/actions/workflows/auto-publish.yml/badge.svg" alt="Publish"></a>
  <a href="https://badge.fury.io/py/mcp-json-yaml-toml"><img src="https://badge.fury.io/py/mcp-json-yaml-toml.svg" alt="PyPI version"></a>
</p>

---

Stop AI coding tools from breaking your data files. No more grep guesswork, hallucinated fields, or non-schema-compliant data added to files. This MCP server gives AI assistants a strict, round-trip safe interface for working with structured data.

## The Problem

AI coding tools often destroy structured data files:

- They **grep** through huge json, yaml, and toml files (like json logs, or AI transcript files) and guess at keys.
- They **hallucinate** fields that never existed.
- They use **sed and regex** that leave files in invalid states.
- They break **YAML indentation** and **TOML syntax**.
- They can't **validate** changes before writing.

## The Solution

**mcp-json-yaml-toml** provides AI assistants with proper tools for structured data:

- **Token-efficient**: Extract exactly what you need without loading entire files.
- **Schema validation**: Enforce correctness using SchemaStore.org or custom schemas.
- **Safe modifications**: **Enforced validation on write**; preserve comments and formatting.
- **Multi-format**: JSON, YAML, and TOML through a unified interface.
- **Directive-based detection**: Support for `# yaml-language-server`, `#:schema`, and `$schema` keys in all formats.
- **Constraint-based guided generation**: Native LMQL support for proactive validation of partial inputs.
- **Local-First**: All processing happens locally. No data ever leaves your machine.
- **Transparent JIT Assets**: The server auto-downloads `yq` if missing and fetches missing schemas from SchemaStore.org for local caching.

> [!NOTE]
>
> **JSONC Support**: Files with `.jsonc` extension (JSON with Comments) are fully supported for **reading**, **querying**, and **schema validation**. However, **write operations will strip comments** due to library limitations.

---

## Getting Started

### Prerequisites

- **Python ≥ 3.11** installed.
- An **MCP-compatible client** (Claude Code, Cursor, Windsurf, Gemini 2.0, n8n, etc.).

### Installation

The server uses `uvx` for automatic dependency management and zero-config execution.

#### AI Agents & CLI Tools

```bash
uvx mcp-json-yaml-toml
```

#### Claude Code (CLI)

```bash
claude mcp add --scope user mcp-json-yaml-toml -- uvx mcp-json-yaml-toml
```

#### Other MCP Clients

Add this to your client's MCP configuration:

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

> [!TIP]
> See [docs/clients.md](docs/clients.md) for detailed setup guides for Cursor, VS Code, and more.

---

## Schema Discovery & Recognition

The server automatically identifies the correct JSON schema for your files using multiple strategies:

1.  **Directives**: Recognizes `# yaml-language-server: $schema=...` and `#:schema ...` directives.
2.  **In-File Keys**: Detects `$schema` keys in JSON and YAML (also supports quoted `"$schema"` in TOML).
3.  **Local IDE Config**: Discovers schemas from VS Code/Cursor extension settings and caches.
4.  **SchemaStore.org**: Performs glob-based auto-detection against thousands of known formats.
5.  **Manual Association**: Use the `data_schema` tool to bind a file to a specific schema URL or name.

---

## LMQL & Guided Generation

This server provides native support for **LMQL (Language Model Query Language)** to enable **Guided Generation**. This allows AI agents to validate partial inputs (e.g., path expressions) incrementally before execution.

- **Incremental Validation**: Check partial inputs (e.g., `.data.us`) and get the remaining pattern needed.
- **Improved Reliability**: Eliminate syntax errors by guiding the LLM toward valid tool inputs.
- **Rich Feedback**: Get suggestions and detailed error messages for common mistakes.

> [!TIP]
> See the [Deep Dive: LMQL Constraints](docs/tools.md#deep-dive-lmql-constraints) for detailed usage examples.

---

## Available Tools

| Tool                  | Description                                    |
| --------------------- | ---------------------------------------------- |
| `data`                | Get, set, or delete values at specific paths   |
| `data_query`          | Advanced yq/jq expressions for transformations |
| `data_schema`         | Manage schemas and validate files              |
| `data_convert`        | Convert between JSON, YAML, and TOML           |
| `data_merge`          | Deep merge structured data files               |
| `constraint_validate` | Validate inputs against LMQL constraints       |
| `constraint_list`     | List available generation constraints          |

> [!NOTE]
> Conversion **TO TOML** is not supported due to yq's internal encoder limitations for complex structures.

---

## Development

### Setup

```bash
git clone https://github.com/bitflight-devops/mcp-json-yaml-toml.git
cd mcp-json-yaml-toml
uv sync
```

### Testing

ash

# Run all tests (coverage included)

uv run pytest

````

### Code Quality

The project uses `prek` (a Rust-based pre-commit tool) for unified linting and formatting. AI Agents MUST use the scoped verification command:

```bash
# Recommended: Verify only touched files
uv run prek run --files <file edited>
````

> [!IMPORTANT]
> Avoid `--all-files` during feature development to keep PR diffs clean and preserve git history.

---

## Project Structure

```text
mcp-json-yaml-toml/
├── packages/mcp_json_yaml_toml/  # Core logic
│   ├── server.py                 # MCP implementation
│   ├── yq_wrapper.py             # Binary management
│   ├── schemas.py                # Schema validation
├── .github/                      # CI/CD and assets
├── docs/                         # Documentation
└── pyproject.toml                # Project config
```

```bash
# Run all tests (coverage included)
uv run pytest
```

### Code Quality

The project uses `prek` (a Rust-based pre-commit tool) for unified linting and formatting. AI Agents MUST use the scoped verification command:

```bash
# Recommended: Verify only touched files
uv run prek run --files <file edited>
```

> [!IMPORTANT]
> Avoid `--all-files` during feature development to keep PR diffs clean and preserve git history.

---

## Project Structure

```mermaid
graph TD
    Repo[mcp-json-yaml-toml]
    Repo --> Packages[packages/mcp_json_yaml_toml]
    Repo --> Github[.github]
    Repo --> Docs[docs]
    Repo --> Config[pyproject.toml]

    subgraph "Core Logic"
        Packages --> Server[server.py<br/>MCP Server & Tools]
        Packages --> Schemas[schemas.py<br/>Schema Validation]
        Packages --> Constraints[lmql_constraints.py<br/>LMQL Constraints]
        Packages --> YQ[yq_wrapper.py<br/>Binary Manager]
        Packages --> YAML[yaml_optimizer.py<br/>YAML Anchors]
        Packages --> TOML[toml_utils.py<br/>TOML Utils]
        Packages --> Conf[config.py<br/>Config Manager]
    end

    style Packages fill:#f9f,stroke:#333,stroke-width:2px
    style Repo fill:#eee,stroke:#333,stroke-width:4px
```

---

<p align="center">
  Built with <a href="https://github.com/jlowin/fastmcp">FastMCP</a>, <a href="https://github.com/mikefarah/yq">yq</a>, and <a href="https://github.com/eth-sri/lmql">LMQL</a>
</p>
