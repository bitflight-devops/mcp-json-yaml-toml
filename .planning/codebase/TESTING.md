# Testing Patterns

**Analysis Date:** 2026-02-14

## Test Framework

**Runner:**

- pytest 9.0.2+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`

**Assertion Library:**

- pytest built-in assertions (no external library)
- Custom Pydantic model validation using `.model_fields` introspection

**Run Commands:**

```bash
uv run pytest                    # Run all tests with coverage and parallel execution
uv run pytest -k test_pattern    # Run specific test by name pattern
uv run pytest -m integration     # Run only integration tests
uv run pytest -m "not slow"      # Run all tests except slow ones
uv run pytest -v                 # Verbose output (included in default addopts)
uv run pytest -n auto            # Parallel execution (included in default addopts)
uv run pytest --cov-report=html # Generate HTML coverage report
```

**Coverage Configuration:**

- Minimum threshold: 60% (enforced via `tool.coverage.report.fail_under`)
- Excludes test code and scripts from coverage measurement
- Enabled by default in CI via `addopts = ["--cov-report=term-missing", "--cov=packages/mcp_json_yaml_toml"]`
- Current coverage: ~79%

**Test Markers:**

- `@pytest.mark.integration`: Tests requiring real yq binary execution
- `@pytest.mark.slow`: Tests with significant runtime
- `@pytest.mark.unit`: Tests with mocked dependencies (implicit, not heavily used)
- `@pytest.mark.protocol`: Tests using actual MCP JSON-RPC protocol

## Test File Organization

**Location:**

- Co-located with source under `packages/mcp_json_yaml_toml/tests/`
- Separate directory (not alongside source) following pytest convention

**Naming:**

- `test_*.py` for test modules
- Corresponding to module being tested: `test_yq_wrapper.py` for `yq_wrapper.py`
- Fixtures in `conftest.py` at package root

**Directory Structure:**

```
packages/mcp_json_yaml_toml/
├── tests/
│   ├── conftest.py                      # Shared fixtures
│   ├── fixtures/                        # Fixture data files (if needed)
│   ├── test_config.py
│   ├── test_lmql_constraints.py
│   ├── test_pagination.py
│   ├── test_schemas.py
│   ├── test_server.py                   # Main tool tests
│   ├── test_yq_wrapper.py
│   ├── test_yaml_optimizer.py
│   ├── test_toml_write.py
│   ├── mcp_protocol_client.py           # Helper for protocol tests
│   └── verify_features.py               # Manual feature verification script
├── yq_wrapper.py
├── server.py
└── [other modules]
```

## Test Structure

**Suite Organization:**

```python
class TestGetYQBinaryPath:
    """Test get_yq_binary_path function."""

    def test_get_yq_binary_path_returns_path(self) -> None:
        """Test get_yq_binary_path returns a Path object.

        Tests: Binary path resolution
        How: Call get_yq_binary_path and check return type
        Why: Verify binary can be located for current platform
        """
        # Arrange - system with yq binary
        # Act - get binary path
        result = get_yq_binary_path()

        # Assert - returns Path object
        assert isinstance(result, Path)
        assert result.exists()
```

**Patterns:**

- Classes for grouping related tests: `class TestFunctionName:`
- Method per test case: `def test_specific_behavior(self):`
- Docstring per test method with Tests/How/Why format
- Setup section with comments: `# Arrange -`, `# Act -`, `# Assert -`
- No setup/teardown methods; use fixtures instead

**Test Naming Convention:**

```
test_<function>_<scenario>_<expected_result>

Examples:
- test_parse_yq_error_empty_string
- test_parse_yq_error_strips_error_prefix
- test_get_yq_binary_path_returns_path
- test_data_query_json_success
- test_data_query_file_not_found
```

## Mocking

**Framework:** `pytest-mock` (via `MockerFixture` parameter)

**Patterns:**

```python
# From conftest.py
@pytest.fixture
def mock_yq_success(mocker: MockerFixture) -> Any:
    """Mock successful yq subprocess execution.

    Tests: Successful yq execution path
    How: Mock subprocess.run to return successful result
    Why: Enable unit testing without real yq binary
    """
    mock_result = mocker.Mock()
    mock_result.returncode = 0
    mock_result.stdout = b'{"result": "success"}'
    mock_result.stderr = b""
    return mocker.patch("subprocess.run", return_value=mock_result)

# Usage in test
def test_with_mock(mock_yq_success: Any) -> None:
    # Test code that uses subprocess.run
    pass
```

**What to Mock:**

- Subprocess calls (real yq binary execution)
- File I/O when testing logic that doesn't depend on actual files
- HTTP requests (schema store downloads)
- System calls that are platform-dependent

**What NOT to Mock:**

- File operations in integration tests (use `tmp_path` fixture instead)
- Dataclass/Pydantic model validation (test actual behavior)
- JSON/YAML parsing/formatting (test real libraries for correct behavior)
- Internal helper functions (test through public API)

## Fixtures and Factories

**Test Data Patterns:**

Fixtures provide sample configuration files in multiple formats:

```python
# From conftest.py - sample config fixtures
@pytest.fixture
def sample_json_config(tmp_path: Path) -> Path:
    """Create sample JSON file for testing.

    Tests: JSON format handling
    How: Write sample JSON config to temp file
    Why: Enable testing without hardcoded paths
    """
    config_data = {
        "name": "test-app",
        "version": "1.0.0",
        "database": {
            "host": "localhost",
            "port": 5432,
            "credentials": {"username": "admin", "password": "secret"},
        },
        "features": {"enabled": True, "beta": False},
        "servers": ["server1.example.com", "server2.example.com"],
    }
    file_path = tmp_path / "config.json"
    file_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
    return file_path
```

**Location:**

- All fixtures in `packages/mcp_json_yaml_toml/tests/conftest.py`
- Organized into sections: Sample Configs, Schemas, Invalid Configs, Mock Subprocess, Environment Variables, Protocol Client
- Each fixture has docstring explaining Tests/How/Why

**Fixture Types:**

1. **Sample Configs**: `sample_json_config`, `sample_yaml_config`, `sample_toml_config`, `sample_xml_config`
2. **Invalid Configs**: `invalid_json_config`, `invalid_yaml_config` (for error testing)
3. **Schemas**: `sample_json_schema` (for validation testing)
4. **Mocks**: `mock_yq_success`, `mock_yq_failure` (subprocess mocking)
5. **Environment**: `clean_environment`, `json_only_environment`, `multi_format_environment`
6. **Protocol**: `mcp_client` (function-scoped), `mcp_client_module` (module-scoped)

## Coverage

**Requirements:**

- Minimum 60% coverage enforced (can be increased)
- Current coverage: ~79% (tracked in project metrics)
- Omits test code and scripts from measurement

**View Coverage:**

```bash
uv run pytest --cov-report=html --cov=packages/mcp_json_yaml_toml
# Opens htmlcov/index.html in browser to see coverage by file/line
```

**Coverage Gaps Acceptable:**

- Platform-specific code with `# pragma: no cover`
- Error recovery paths that are hard to trigger in tests
- Mock object interaction code

## Test Types

**Unit Tests:**

- Scope: Single function/class with dependencies mocked
- Approach: Fast execution (< 1ms per test), no I/O
- Example: `test_parse_yq_error_empty_string()` - pure string parsing with assertions
- Location: Most tests in each `test_*.py` file

**Integration Tests:**

- Scope: Real yq binary execution, file I/O, real parsing
- Approach: Marked with `@pytest.mark.integration`, slower but verify real behavior
- Example: `test_data_query_json_success()` - creates real JSON file, executes real query
- Location: Mixed with unit tests, run separately with `-m integration`

**E2E Tests:**

- Scope: Full MCP protocol communication via JSON-RPC
- Framework: Custom `MCPClient` class in `mcp_protocol_client.py`
- Approach: Spawn server subprocess, send JSON-RPC requests, verify protocol behavior
- Example: Tests in `test_fastmcp_integration.py` using `mcp_client` fixture
- Location: `test_fastmcp_integration.py`, marked with `@pytest.mark.protocol`

## Common Patterns

**Async Testing:**

- Framework: `pytest-asyncio` (included in dev dependencies)
- Pattern: Async functions marked with `async def test_*`
- Usage: Not extensively used in current codebase (sync subprocess-based)

**Error Testing:**

```python
def test_data_query_file_not_found(self) -> None:
    """Test data_query raises error for missing file.

    Tests: Missing file handling
    How: Query non-existent file
    Why: Verify error handling for missing files
    """
    # Arrange - non-existent file path
    # Act & Assert - raises ToolError
    with pytest.raises(ToolError, match="File not found"):
        data_query_fn("/nonexistent/file.json", ".name")
```

**Validation Testing:**

```python
def test_valid_result(self) -> None:
    result = ValidationResult(valid=True)
    assert result.valid is True
    assert result.error is None
    assert result.is_partial is False

def test_invalid_result(self) -> None:
    result = ValidationResult(valid=False, error="Invalid input")
    assert result.valid is False
    assert result.error == "Invalid input"
```

**Dataclass Serialization Testing:**

```python
def test_to_dict_full(self) -> None:
    result = ValidationResult(
        valid=False,
        error="test error",
        is_partial=True,
        remaining_pattern=".*",
        suggestions=["a", "b"],
    )
    d = result.to_dict()
    assert d["valid"] is False
    assert d["error"] == "test error"
    assert d["is_partial"] is True
    assert d["remaining_pattern"] == ".*"
    assert d["suggestions"] == ["a", "b"]
```

**Pagination Testing:**

```python
def test_cursor_roundtrip(self) -> None:
    """Test that cursor encoding/decoding is reversible."""
    test_offsets = [0, 100, 1000, 10000, 50000, 100000]

    for offset in test_offsets:
        cursor = _encode_cursor(offset)
        decoded = _decode_cursor(cursor)
        assert decoded == offset, f"Roundtrip failed for offset {offset}"
```

**Environment Variable Testing:**

```python
def test_data_query_disabled_format(
    self, sample_json_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test data_query raises error for disabled format."""
    # Arrange - disable JSON format
    monkeypatch.setenv("MCP_CONFIG_FORMATS", "yaml,toml")

    # Act & Assert - raises ToolError
    with pytest.raises(ToolError, match="Format 'json' is not enabled"):
        data_query_fn(str(sample_json_config), ".name")
```

---

_Testing analysis: 2026-02-14_
