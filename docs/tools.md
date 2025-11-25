# Tool Reference

**Audience:** AI agents using the MCP server, and developers integrating the server into applications. This document provides API-level reference for all tools and parameters.

For client setup instructions, see [clients.md](clients.md). For configuration options, see the [README.md](../README.md).

## Overview

The server provides 5 focused tools optimized for LLM interaction with JSON, YAML, and TOML files:

| Tool                            | Purpose                          | Key Features                            |
| ------------------------------- | -------------------------------- | --------------------------------------- |
| [`data`](#data)                 | Get, set, delete data            | Get, set, delete values at any path     |
| [`data_query`](#data_query)     | Advanced data extraction         | Use yq expressions for complex queries  |
| [`data_schema`](#data_schema)   | Schema validation and management | Validate syntax, manage schema catalogs |
| [`data_convert`](#data_convert) | Format conversion                | Convert between JSON, YAML, TOML        |
| [`data_merge`](#data_merge)     | Configuration merging            | Deep merge with environment overrides   |

---

## `data`

Get, set, or delete data at specific paths in JSON, YAML, or TOML files.

### Parameters

| Parameter       | Type    | Required | Description                                                                                                       |
| --------------- | ------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `file_path`     | string  | Yes      | Path to JSON, YAML, or TOML file                                                                                  |
| `operation`     | enum    | Yes      | One of: `get`, `set`, `delete`                                                                                    |
| `key_path`      | string  | No\*     | Dot-separated path (e.g., `project.name`)                                                                         |
| `value`         | string  | No\*     | Value for `set` operation (interpretation depends on `value_type`)                                                |
| `value_type`    | enum    | No       | For `set`: How to interpret `value` parameter: `string`, `number`, `boolean`, `null`, or `json` (default: `json`) |
| `return_type`   | enum    | No       | For `get`: `keys` (structure) or `all` (full data)                                                                |
| `data_type`     | enum    | No       | For `get`: `data` or `schema` (default: `data`)                                                                   |
| `in_place`      | boolean | No       | Modify file directly (default: false)                                                                             |
| `output_format` | enum    | No       | Output format: `json`, `yaml`, `toml`                                                                             |
| `cursor`        | string  | No       | Pagination cursor for large results                                                                               |

\*Required for certain operations

### Examples

#### Get a value

```json
{
  "file_path": "pyproject.toml",
  "operation": "get",
  "key_path": "project.name"
}
```

Returns: `"mcp-json-yaml-toml"`

#### Set a value (with JSON parsing)

```json
{
  "file_path": "config.json",
  "operation": "set",
  "key_path": "database.host",
  "value": "\"localhost\"",
  "in_place": true
}
```

#### Set a string value (literal text, no JSON parsing)

```json
{
  "file_path": "config.yaml",
  "operation": "set",
  "key_path": "description",
  "value": "This is a literal string",
  "value_type": "string",
  "in_place": true
}
```

#### Set a numeric value

```json
{
  "file_path": "config.json",
  "operation": "set",
  "key_path": "timeout_seconds",
  "value": "30",
  "value_type": "number",
  "in_place": true
}
```

#### Set a boolean value

```json
{
  "file_path": "settings.toml",
  "operation": "set",
  "key_path": "features.experimental",
  "value": "true",
  "value_type": "boolean",
  "in_place": true
}
```

#### Set to null

```json
{
  "file_path": "config.yaml",
  "operation": "set",
  "key_path": "legacy_field",
  "value_type": "null",
  "in_place": true
}
```

#### Delete a key

```json
{
  "file_path": "settings.yaml",
  "operation": "delete",
  "key_path": "deprecated.feature",
  "in_place": true
}
```

#### Get structure only

```json
{
  "file_path": "complex.json",
  "operation": "get",
  "return_type": "keys"
}
```

---

## `data_query`

Extract and transform data using yq expressions (jq-compatible syntax).

### Parameters

| Parameter       | Type   | Required | Description                                     |
| --------------- | ------ | -------- | ----------------------------------------------- |
| `file_path`     | string | Yes      | Path to JSON, YAML, or TOML file                |
| `expression`    | string | Yes      | yq expression (e.g., `.items[]`, `.data.users`) |
| `output_format` | enum   | No       | Output format: `json`, `yaml`, `toml`           |
| `cursor`        | string | No       | Pagination cursor for large results             |

### Examples

#### Query array elements

```json
{
  "file_path": ".gitlab-ci.yml",
  "expression": ".stages"
}
```

Returns: `["build", "test", "deploy"]`

#### Filter and transform

```json
{
  "file_path": "package.json",
  "expression": ".dependencies | keys"
}
```

Returns list of dependency names

#### Complex queries

```json
{
  "file_path": "config.yaml",
  "expression": ".servers[] | select(.environment == \"production\") | .host"
}
```

Returns production server hosts

#### Nested data extraction

```json
{
  "file_path": "k8s-deployment.yaml",
  "expression": ".spec.template.spec.containers[0].image"
}
```

---

## `data_schema`

Manage and validate against JSON schemas.

### Parameters

| Parameter      | Type    | Required | Description                                        |
| -------------- | ------- | -------- | -------------------------------------------------- |
| `action`       | enum    | Yes      | Action to perform (see below)                      |
| `file_path`    | string  | No\*     | Path to file (for validate/associate/disassociate) |
| `schema_path`  | string  | No       | Path to schema file                                |
| `schema_url`   | string  | No       | Schema URL                                         |
| `schema_name`  | string  | No       | Schema name from catalog                           |
| `path`         | string  | No       | Directory path (for add_dir)                       |
| `name`         | string  | No       | Catalog name (for add_catalog)                     |
| `uri`          | string  | No       | Catalog URI (for add_catalog)                      |
| `search_paths` | array   | No       | Paths to scan (for scan)                           |
| `max_depth`    | integer | No       | Max search depth (default: 5)                      |

\*Required for certain actions

### Actions

#### `validate`

Validate file syntax and optionally against schema:

```json
{
  "action": "validate",
  "file_path": ".gitlab-ci.yml"
}
```

#### `associate`

Bind file to schema:

```json
{
  "action": "associate",
  "file_path": ".gitlab-ci.yml",
  "schema_name": "gitlab-ci"
}
```

#### `disassociate`

Remove file-to-schema binding:

```json
{
  "action": "disassociate",
  "file_path": "config.json"
}
```

#### `scan`

Search for schema directories:

```json
{
  "action": "scan",
  "search_paths": ["/home/user/.config"],
  "max_depth": 3
}
```

#### `list`

Show current schema configuration:

```json
{
  "action": "list"
}
```

---

## `data_convert`

Convert JSON, YAML, or TOML files between formats.

### Parameters

| Parameter       | Type   | Required | Description                                   |
| --------------- | ------ | -------- | --------------------------------------------- |
| `file_path`     | string | Yes      | Source file path                              |
| `output_format` | enum   | Yes      | Target format: `json`, `yaml`, `toml`         |
| `output_file`   | string | No       | Output file path (returns content if omitted) |

### Examples

#### Convert TOML to YAML

```json
{
  "file_path": "pyproject.toml",
  "output_format": "yaml"
}
```

#### Convert and save

```json
{
  "file_path": "config.json",
  "output_format": "toml",
  "output_file": "config.toml"
}
```

#### Convert YAML to JSON

```json
{
  "file_path": "docker-compose.yml",
  "output_format": "json"
}
```

---

## `data_merge`

Deep merge two JSON, YAML, or TOML files.

### Parameters

| Parameter       | Type   | Required | Description                                      |
| --------------- | ------ | -------- | ------------------------------------------------ |
| `file_path1`    | string | Yes      | Base file (JSON, YAML, or TOML)                  |
| `file_path2`    | string | Yes      | Overlay file (JSON, YAML, or TOML)               |
| `output_format` | enum   | No       | Output format (defaults to format of first file) |
| `output_file`   | string | No       | Output file path (returns content if omitted)    |

### Examples

#### Merge configurations

```json
{
  "file_path1": "base-config.yaml",
  "file_path2": "production-override.yaml"
}
```

#### Merge and save

```json
{
  "file_path1": "default.json",
  "file_path2": "custom.json",
  "output_file": "merged.json"
}
```

#### Merge with format conversion

```json
{
  "file_path1": "base.toml",
  "file_path2": "override.toml",
  "output_format": "yaml"
}
```

---

## Common Patterns

### Pagination

For large results (>10KB), use the cursor for pagination:

```json
// First request
{
  "file_path": "large-file.json",
  "operation": "get"
}
// Returns: {"result": "...", "cursor": "abc123"}

// Next page
{
  "file_path": "large-file.json",
  "operation": "get",
  "cursor": "abc123"
}
```

### Format Detection

The server automatically detects file format from extensions:

- `.json` → JSON
- `.yaml`, `.yml` → YAML
- `.toml` → TOML

### Error Handling

All tools return structured responses:

```json
{
  "success": true|false,
  "result": "...",
  "error": "Error message if success=false",
  "format": "json|yaml|toml",
  "file": "/path/to/file"
}
```

### yq Expression Reference

The `data_query` tool uses yq v4 syntax (jq-compatible):

| Expression             | Description       |
| ---------------------- | ----------------- |
| `.`                    | Root object       |
| `.field`               | Access field      |
| `.field.nested`        | Nested access     |
| `.[]`                  | Array elements    |
| `.[0]`                 | First element     |
| `.[-1]`                | Last element      |
| `\| select(condition)` | Filter            |
| `\| keys`              | Object keys       |
| `\| length`            | Count items       |
| `\| map(expr)`         | Transform         |
| `\| sort`              | Sort array        |
| `\| unique`            | Remove duplicates |

### Advanced Examples

#### Extract and format

```json
{
  "file_path": "users.json",
  "expression": ".users | map({name: .fullName, email: .email})"
}
```

#### Conditional selection

```json
{
  "file_path": "config.yaml",
  "expression": ".environments[] | select(.active == true) | .name"
}
```

#### Complex transformation

```json
{
  "file_path": "package.json",
  "expression": ".dependencies | to_entries | map(select(.value | startswith(\"^1.\"))) | from_entries"
}
```

---

## Environment Variables

Configure server behavior:

| Variable                     | Default                       | Description                         |
| ---------------------------- | ----------------------------- | ----------------------------------- |
| `MCP_CONFIG_FORMATS`         | `json,yaml,toml`              | Enabled formats                     |
| `MCP_SCHEMA_CACHE_DIRS`      | `~/.cache/mcp-json-yaml-toml` | Schema search paths                 |
| `YAML_ANCHOR_OPTIMIZATION`   | `true`                        | Auto-generate YAML anchors          |
| `YAML_ANCHOR_MIN_SIZE`       | `3`                           | Min structure size for anchoring    |
| `YAML_ANCHOR_MIN_DUPLICATES` | `2`                           | Min duplicates to trigger anchoring |

---

## Limitations

- Maximum file size: 100MB
- Pagination kicks in at 10KB per response
- TOML write operations use tomlkit (not yq)
- Binary formats not supported
- Comments preserved in YAML/TOML only

---

## Troubleshooting

### Common Issues

**"Format not enabled"**

- Check `MCP_CONFIG_FORMATS` environment variable
- Ensure format is in the enabled list

**"File not found"**

- Use absolute paths or ensure working directory is correct
- Check file permissions

**"Invalid expression"**

- Verify yq syntax (use jq documentation as reference)
- Test expression with command-line yq first

**"Schema not found"**

- Run scan action to discover schemas
- Add schema directory with add_dir action
- Check SchemaStore.org catalog availability

### Debug Mode

Enable debug output by setting environment variable:

```bash
export YQ_DEBUG=true
```

This will show yq command execution details in server logs.
