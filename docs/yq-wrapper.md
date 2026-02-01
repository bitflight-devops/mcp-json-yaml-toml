# YQ Wrapper Usage Guide

## Overview

The `yq_wrapper` module provides a Python interface to the yq binary for querying and manipulating YAML, JSON, TOML, and other configuration formats. It uses a pinned, tested version of yq by default (configurable via environment variable) and automatically downloads the binary on first use.

## Features

- **Cross-platform support**: Automatic binary selection for Linux (amd64), macOS (amd64, arm64), Windows (amd64)
- **Type-safe**: Full type hints with mypy --strict compliance
- **Error handling**: Structured exceptions with AI-friendly error messages
- **Format conversion**: Seamless conversion between JSON, YAML, TOML, XML, CSV, TSV, and properties files
- **Pydantic models**: Structured result objects with automatic JSON parsing

## Installation

The yq wrapper includes intelligent binary management:

- **Pinned version**: Uses a tested, pinned yq version by default (currently v4.52.2)
- **User override**: Set `YQ_VERSION` environment variable to use a different version
- **Auto-download**: Automatically downloads the binary from GitHub on first use
- **Checksum verification**: All downloads are verified against SHA256 checksums
- **Storage**: Downloaded binaries are cached at `~/.local/bin/` (with fallback to package directory)
- **Cross-platform**: Supports Linux (amd64/arm64), macOS (amd64/arm64), and Windows (amd64)
- **No external dependencies** required beyond Python 3.11+

The wrapper will automatically handle binary discovery, downloading, and verification on first use.

## Quick Start

```python
from mcp_json_yaml_toml.yq_wrapper import execute_yq, get_yq_binary_path

# Simple YAML to JSON conversion
yaml_data = """
name: myapp
version: 1.0.0
"""

result = execute_yq(
    ".",  # Expression: select everything
    input_data=yaml_data,
    input_format="yaml",
    output_format="json"
)

print(result.data)
# Output: {'name': 'myapp', 'version': '1.0.0'}
```

## API Reference

### Functions

#### `get_yq_binary_path() -> Path`

Get the path to the platform-specific yq binary.

**Returns:**

- Path to the yq binary executable

**Raises:**

- `YQBinaryNotFoundError`: If the binary for this platform cannot be found

**Example:**

```python
from mcp_json_yaml_toml.yq_wrapper import get_yq_binary_path

binary_path = get_yq_binary_path()
print(f"Using yq at: {binary_path}")
```

#### `execute_yq(...) -> YQResult`

Execute yq command with the given expression and input.

**Parameters:**

- `expression` (str): yq expression to evaluate (e.g., '.name', '.items[]', '.users[] | select(.age > 25)')
- `input_data` (str | None): Input data as string (mutually exclusive with input_file)
- `input_file` (Path | str | None): Path to input file (mutually exclusive with input_data)
- `input_format` (FormatType): Format of input data (default: "yaml")
- `output_format` (FormatType): Format for output (default: "json")
- `in_place` (bool): Modify file in place (only valid with input_file)
- `null_input` (bool): Don't read input, useful for creating new content

**Returns:**

- `YQResult`: Object with stdout, stderr, returncode, and parsed data

**Raises:**

- `YQBinaryNotFoundError`: If yq binary cannot be found
- `YQExecutionError`: If yq execution fails
- `ValueError`: If arguments are invalid

#### `validate_yq_binary() -> tuple[bool, str]`

Validate that the yq binary exists and is executable.

**Returns:**

- Tuple of (is_valid, message) where message describes the result

**Example:**

```python
from mcp_json_yaml_toml.yq_wrapper import validate_yq_binary

is_valid, message = validate_yq_binary()
if is_valid:
    print(f"✓ {message}")
else:
    print(f"✗ {message}")
```

### Models

#### `YQResult`

Pydantic model representing the result of a yq execution.

**Fields:**

- `stdout` (str): Standard output from yq command
- `stderr` (str): Standard error from yq command (default: "")
- `returncode` (int): Exit code from yq process (default: 0)
- `data` (Any): Parsed output data if output_format="json" (default: None)

### Exceptions

#### `YQError`

Base exception for yq execution errors.

#### `YQBinaryNotFoundError(YQError)`

Raised when the platform-specific yq binary cannot be found.

#### `YQExecutionError(YQError)`

Raised when yq execution fails.

**Attributes:**

- `stderr` (str): Raw stderr output from yq
- `returncode` (int): Process exit code

## Usage Examples

### Example 1: Query JSON Data

```python
from mcp_json_yaml_toml.yq_wrapper import execute_yq

json_data = '''
{
  "users": [
    {"name": "alice", "age": 30, "active": true},
    {"name": "bob", "age": 25, "active": false},
    {"name": "charlie", "age": 35, "active": true}
  ]
}
'''

# Get all active users
result = execute_yq(
    '.users[] | select(.active == true)',
    input_data=json_data,
    input_format="json",
    output_format="json"
)

print(result.stdout)
```

### Example 2: Convert TOML to YAML

```python
from pathlib import Path
from mcp_json_yaml_toml.yq_wrapper import execute_yq

# Assuming you have a pyproject.toml file
result = execute_yq(
    '.',
    input_file=Path("pyproject.toml"),
    input_format="toml",
    output_format="yaml"
)

print(result.stdout)
```

### Example 3: Modify YAML File In-Place

```python
from pathlib import Path
from mcp_json_yaml_toml.yq_wrapper import execute_yq

config_file = Path("config.yaml")

# Update version field in YAML file
execute_yq(
    '.version = "2.0.0"',
    input_file=config_file,
    input_format="yaml",
    output_format="yaml",
    in_place=True
)

print(f"Updated {config_file}")
```

### Example 4: Create New YAML from Scratch

```python
from mcp_json_yaml_toml.yq_wrapper import execute_yq

# Create new YAML structure using null input
result = execute_yq(
    '''{
        "name": "myapp",
        "version": "1.0.0",
        "dependencies": ["dep1", "dep2"]
    }''',
    null_input=True,
    output_format="yaml"
)

print(result.stdout)
# Output:
# name: myapp
# version: 1.0.0
# dependencies:
#   - dep1
#   - dep2
```

### Example 5: Error Handling

```python
from mcp_json_yaml_toml.yq_wrapper import execute_yq, YQExecutionError

try:
    result = execute_yq(
        '.invalid.path',
        input_data='{"name": "test"}',
        input_format="json",
        output_format="json"
    )
except YQExecutionError as e:
    print(f"Error: {e}")
    print(f"Exit code: {e.returncode}")
    print(f"Details: {e.stderr}")
```

### Example 6: Complex Filtering

```python
from mcp_json_yaml_toml.yq_wrapper import execute_yq

yaml_data = """
services:
  - name: web
    port: 80
    replicas: 3
  - name: api
    port: 8080
    replicas: 5
  - name: db
    port: 5432
    replicas: 1
"""

# Get services with more than 2 replicas
result = execute_yq(
    '.services[] | select(.replicas > 2)',
    input_data=yaml_data,
    input_format="yaml",
    output_format="json"
)

# Note: For multiple results, yq returns newline-separated JSON objects
for line in result.stdout.strip().split('\n'):
    import orjson
    service = orjson.loads(line)
    print(f"{service['name']}: {service['replicas']} replicas")
```

## Supported Formats

The wrapper supports all formats that the current yq version supports:

- **json**: JavaScript Object Notation
- **yaml**: YAML Ain't Markup Language
- **toml**: Tom's Obvious Minimal Language
- **xml**: eXtensible Markup Language
- **csv**: Comma-Separated Values
- **tsv**: Tab-Separated Values
- **props**: Java properties files

## Platform Support

The wrapper automatically detects your platform and uses the appropriate binary:

| Platform | Architecture | Binary Name (example)        |
| -------- | ------------ | ---------------------------- |
| Linux    | x86_64/amd64 | yq-linux-amd64-v4.52.2       |
| macOS    | x86_64/amd64 | yq-darwin-amd64-v4.52.2      |
| macOS    | arm64        | yq-darwin-arm64-v4.52.2      |
| Windows  | x86_64/amd64 | yq-windows-amd64-v4.52.2.exe |

## Binary Management

### Automatic Download and Caching

The wrapper automatically manages yq binaries with these features:

**Version Selection:**

- Uses a pinned, tested version by default (e.g., `v4.52.2`)
- Override with `YQ_VERSION` environment variable (e.g., `YQ_VERSION=v4.50.0`)
- No GitHub API calls required—downloads directly from release CDN

**Binary Discovery Priority:**

1. Check if binary already exists in storage location
2. If missing, download the pinned version from GitHub releases
3. Verify SHA256 checksums from GitHub releases
4. Fall back to package-bundled binaries if download fails

**Storage Locations (in order of preference):**

- `~/.local/bin/yq-<platform>-<arch>-<version>` - User binary directory (preferred)
- `<package>/binaries/yq-<platform>-<arch>-<version>` - Package directory (fallback)

**Version-Aware Caching:**

Binary filenames include the version (e.g., `yq-linux-amd64-v4.52.2`), which means:

- Updating the pinned version automatically triggers a new download
- Old versions are automatically cleaned up after successful download
- Setting `YQ_VERSION` env var uses a separate cached binary per version

**First-Use Setup:**

On first execution, the wrapper will:

1. Detect your platform and architecture
2. Download the pinned yq version (or version from `YQ_VERSION` env var)
3. Verify checksums for security
4. Cache the binary for future use

No manual setup required—everything happens automatically on first use.

### Version Management

**Check current configuration:**

```python
from mcp_json_yaml_toml.yq_wrapper import get_yq_version, get_yq_binary_path

# Get the version that will be downloaded
print(f"Configured version: {get_yq_version()}")
# Output: v4.52.2

# Get the binary path
binary_path = get_yq_binary_path()
print(f"yq binary: {binary_path}")
# Output: /home/user/.local/bin/yq-linux-amd64-v4.52.2
```

**Override the version:**

```bash
# Use a specific yq version
export YQ_VERSION=v4.50.0
uvx mcp-json-yaml-toml
```

**Note:** The pinned version is updated weekly via automated CI when new yq releases pass our test suite.

## Performance Notes

- Subprocess overhead: ~10-50ms per execution
- Binary size: ~10-12 MB per platform
- Timeout: 30 seconds (configurable in code)
- Memory: Minimal (subprocess-based)
- Auto-download: One-time cost on first execution (~2-5 seconds depending on network)

## Troubleshooting

### Binary Not Found

If you get `YQBinaryNotFoundError`:

**Auto-download issues:**

1. Check network connectivity (GitHub releases must be reachable)
2. Verify `~/.local/bin/` is writable (or package binaries/ directory)
3. Check that your platform is supported (Linux amd64/arm64, macOS amd64/arm64, Windows amd64)
4. If using `YQ_VERSION` override, ensure the version exists on GitHub

**Manual fallback:**

If auto-download fails, you can manually:

1. Download yq from <https://github.com/mikefarah/yq/releases>
2. Place it in `~/.local/bin/` with appropriate name (`yq-linux-amd64`, `yq-darwin-amd64`, etc.)
3. Make it executable: `chmod +x ~/.local/bin/yq-*`

**Check your setup:**

```python
from mcp_json_yaml_toml.yq_wrapper import validate_yq_binary

is_valid, message = validate_yq_binary()
print(f"Valid: {is_valid}")
print(f"Message: {message}")
```

### Execution Timeout

If operations timeout (30s default), you may need to:

1. Process data in smaller chunks
2. Modify the timeout in the source code
3. Use streaming for large files

### Parse Errors

If JSON parsing fails but yq succeeds:

- Check the `stdout` field for raw output
- The `data` field will be None
- A warning will be added to `stderr`
