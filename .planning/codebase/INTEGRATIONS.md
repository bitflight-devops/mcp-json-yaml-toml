# External Integrations

**Analysis Date:** 2025-02-14

## APIs & External Services

**Schema Store:**

- SchemaStore.org - JSON Schema catalog and definitions
  - Catalog URL: `https://www.schemastore.org/api/json/catalog.json`
  - Used for: Auto-discovery of schemas for common file types
  - SDK/Client: httpx
  - Caching: Local disk cache at `~/.cache/mcp-json-yaml-toml/schemas/`
  - Cache TTL: 24 hours
  - Location: `packages/mcp_json_yaml_toml/schemas.py:SchemaManager`

**GitHub:**

- GitHub Releases API - yq binary distribution
  - Repository: `mikefarah/yq`
  - Used for: Auto-download of platform-specific yq binaries
  - SDK/Client: httpx
  - Timeout: 60 seconds for download, 30 seconds for metadata fetch
  - Checksum verification: SHA256 validation against releases checksums
  - Location: `packages/mcp_json_yaml_toml/yq_wrapper.py`
  - Platforms supported:
    - Linux x86_64, ARM64 (yq_linux_amd64, yq_linux_arm64)
    - macOS x86_64, ARM64 (yq_darwin_amd64, yq_darwin_arm64)
    - Windows x86_64 (yq_windows_amd64.exe)

## Data Storage

**Databases:**

- None - Local-first architecture, no persistent database required

**File Storage:**

- Local filesystem only
  - Working files: User-specified JSON, YAML, TOML files
  - Schema cache: `~/.cache/mcp-json-yaml-toml/schemas/`
  - IDE schema locations checked: VS Code, JetBrains IDEs, Sublime Text cache directories
  - Configuration: `~/.cache/mcp-json-yaml-toml/schemas/schema_config.json`

**Caching:**

- In-memory: SchemaManager maintains `_cache` for current session
- Disk cache: Schemas cached locally to reduce network requests
  - Format: JSON files stored with hash-based names
  - TTL: 24 hours (configurable via cache validation)
  - Fallback: Stale cache used if network unavailable

## Authentication & Identity

**Auth Provider:**

- None - MCP server uses stdio transport, no authentication required
- Assumption: Running on trusted local machine or secure development environment

## Monitoring & Observability

**Error Tracking:**

- None - No external error tracking service
- Local error handling via FastMCP exception propagation

**Logs:**

- Console/stderr via FastMCP logging
- Python logging module used for debug output
- Log format: Configurable via logging configuration

## CI/CD & Deployment

**Hosting:**

- PyPI (Python Package Index)
  - Package name: `mcp-json-yaml-toml`
  - Distribution methods:
    - `pip install mcp-json-yaml-toml`
    - `uvx mcp-json-yaml-toml` (standalone execution)

**CI Pipeline:**

- GitHub Actions (inferred from workflow badges in README)
  - Test workflow: `.github/workflows/test.yml`
  - Auto-publish workflow: `.github/workflows/auto-publish.yml`
  - Triggers: On push to branches, release events

**Version Management:**

- Git tags for versioning (via hatch-vcs)
- Semantic versioning inferred from commit history
- Version retrieval: `packages/mcp_json_yaml_toml/version.py` reads from git tags or hatch metadata

## Environment Configuration

**Required env vars:**

- `MCP_CONFIG_FORMATS` (optional) - Comma-separated list of enabled formats
  - Default: `json,yaml,toml`
  - Parsing: `packages/mcp_json_yaml_toml/config.py:parse_enabled_formats()`
  - Example: `MCP_CONFIG_FORMATS=json,yaml`

**Optional env vars:**

- None identified in current codebase

**Secrets location:**

- Not applicable - No authentication secrets required
- No `.env` files needed for operation

## Webhooks & Callbacks

**Incoming:**

- None - MCP server uses stdio transport, no webhook receivers

**Outgoing:**

- None - Server does not emit webhooks
- Exception: GitHub Actions CI may trigger on events (external to this repo)

## Schema & Validation Integration

**Schema Discovery:**

- Filename matching: `.schemastore.org/api/json/catalog.json` entries matched against file names
  - Location: `packages/mcp_json_yaml_toml/schemas.py:SchemaManager.find_schema_for_file()`

- Directive support: Multiple schema detection methods
  - `# yaml-language-server: $schema=<url>` (YAML)
  - `#:schema <url>` (custom directive)
  - `$schema` key in JSON/YAML root object
  - User-provided schema associations

**IDE Cache Integration:**

- Reads schemas from IDE cache directories:
  - VS Code YAML extension: `.config/Code/User/extensions/redhat.vscode-yaml-*/`
  - JetBrains IDEs: `.cache/JetBrains/*/extensions/python/cache/schemas/`
  - Sublime Text: `.cache/sublime-schemas/`
  - vscode-yaml hash-based cache lookup

**JSON Schema Validation:**

- Validators: Draft7Validator, Draft202012Validator from jsonschema library
- Remote reference resolution: Custom httpx-based retriever
  - Location: `packages/mcp_json_yaml_toml/server.py:retrieve_via_httpx()`
  - Timeout: 10 seconds
  - Error handling: Fails gracefully if remote schema unreachable

## Binary Management

**yq Binary:**

- Auto-download mechanism: `packages/mcp_json_yaml_toml/yq_wrapper.py:ensure_yq_binary()`
- Download coordination: File locking via portalocker for concurrent access
- Checksum verification: SHA256 validation against GitHub releases checksums
- Platforms: Linux/macOS/Windows with amd64/arm64 support
- Caching: Downloaded to `~/.local/share/mcp-json-yaml-toml/yq_binaries/`
- Error handling: Graceful fallback if download fails (assumes yq in PATH)

---

_Integration audit: 2025-02-14_
