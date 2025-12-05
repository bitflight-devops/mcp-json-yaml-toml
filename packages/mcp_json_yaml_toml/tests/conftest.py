"""Shared pytest fixtures for mcp_json_yaml_toml testing.

This module provides reusable test infrastructure following modern pytest patterns
with comprehensive type hints, proper fixture scoping, and external fixture files
for better maintainability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from mcp_json_yaml_toml.tests.mcp_protocol_client import MCPClient

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

# ==============================================================================
# Test Configuration
# ==============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ==============================================================================
# Sample Config Fixtures
# ==============================================================================


@pytest.fixture
def sample_json_config(tmp_path: Path) -> Path:
    """Create sample JSON configuration file for testing.

    Tests: JSON format handling
    How: Write sample JSON config to temp file
    Why: Enable testing without hardcoded paths

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created JSON config file
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

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
    return config_path


@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Create sample YAML configuration file for testing.

    Tests: YAML format handling
    How: Write sample YAML config to temp file
    Why: Enable testing YAML-specific features

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created YAML config file
    """
    yaml_content = """name: test-app
version: 1.0.0
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: secret
features:
  enabled: true
  beta: false
servers:
  - server1.example.com
  - server2.example.com
"""

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")
    return config_path


@pytest.fixture
def sample_toml_config(tmp_path: Path) -> Path:
    """Create sample TOML configuration file for testing.

    Tests: TOML format handling
    How: Write sample TOML config to temp file
    Why: Enable testing TOML-specific features

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created TOML config file
    """
    toml_content = """name = "test-app"
version = "1.0.0"

[database]
host = "localhost"
port = 5432

[database.credentials]
username = "admin"
password = "secret"

[features]
enabled = true
beta = false

servers = ["server1.example.com", "server2.example.com"]
"""

    config_path = tmp_path / "config.toml"
    config_path.write_text(toml_content, encoding="utf-8")
    return config_path


@pytest.fixture
def sample_xml_config(tmp_path: Path) -> Path:
    """Create sample XML configuration file for testing.

    Tests: XML format handling
    How: Write sample XML config to temp file
    Why: Enable testing XML-specific features

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created XML config file
    """
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<config>
    <name>test-app</name>
    <version>1.0.0</version>
    <database>
        <host>localhost</host>
        <port>5432</port>
        <credentials>
            <username>admin</username>
            <password>secret</password>
        </credentials>
    </database>
    <features>
        <enabled>true</enabled>
        <beta>false</beta>
    </features>
    <servers>
        <server>server1.example.com</server>
        <server>server2.example.com</server>
    </servers>
</config>
"""

    config_path = tmp_path / "config.xml"
    config_path.write_text(xml_content, encoding="utf-8")
    return config_path


# ==============================================================================
# Schema Fixtures
# ==============================================================================


@pytest.fixture
def sample_json_schema(tmp_path: Path) -> Path:
    """Create sample JSON schema file for validation testing.

    Tests: Schema validation functionality
    How: Write JSON schema to temp file
    Why: Enable testing schema validation

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created JSON schema file
    """
    schema_data = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "version": {"type": "string"},
            "database": {
                "type": "object",
                "properties": {"host": {"type": "string"}, "port": {"type": "number"}},
                "required": ["host", "port"],
            },
        },
        "required": ["name", "version"],
    }

    schema_path = tmp_path / "config.schema.json"
    schema_path.write_text(json.dumps(schema_data, indent=2), encoding="utf-8")
    return schema_path


# ==============================================================================
# Invalid Config Fixtures
# ==============================================================================


@pytest.fixture
def invalid_json_config(tmp_path: Path) -> Path:
    """Create invalid JSON configuration file for error testing.

    Tests: JSON syntax error handling
    How: Write malformed JSON to temp file
    Why: Verify error handling for invalid syntax

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created invalid JSON file
    """
    config_path = tmp_path / "invalid.json"
    config_path.write_text('{"name": "test", "unclosed": ', encoding="utf-8")
    return config_path


@pytest.fixture
def invalid_yaml_config(tmp_path: Path) -> Path:
    """Create invalid YAML configuration file for error testing.

    Tests: YAML syntax error handling
    How: Write malformed YAML to temp file
    Why: Verify error handling for invalid syntax

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to created invalid YAML file
    """
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(
        "name: test\n  bad_indent: value\nmore: [unclosed", encoding="utf-8"
    )
    return config_path


# ==============================================================================
# Mock Subprocess Fixtures
# ==============================================================================


@pytest.fixture
def mock_yq_success(mocker: MockerFixture) -> Any:
    """Mock successful yq subprocess execution.

    Tests: Successful yq execution path
    How: Mock subprocess.run to return successful result
    Why: Enable unit testing without real yq binary

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mocked subprocess.run function
    """
    mock_result = mocker.Mock()
    mock_result.returncode = 0
    mock_result.stdout = b'{"result": "success"}'
    mock_result.stderr = b""

    return mocker.patch("subprocess.run", return_value=mock_result)


@pytest.fixture
def mock_yq_failure(mocker: MockerFixture) -> Any:
    """Mock failed yq subprocess execution.

    Tests: Failed yq execution path
    How: Mock subprocess.run to return error result
    Why: Enable testing error handling without triggering real errors

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mocked subprocess.run function
    """
    mock_result = mocker.Mock()
    mock_result.returncode = 1
    mock_result.stdout = b""
    mock_result.stderr = b"Error: invalid expression"

    return mocker.patch("subprocess.run", return_value=mock_result)


# ==============================================================================
# Environment Variable Fixtures
# ==============================================================================


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean environment variables for isolated testing.

    Tests: Environment variable isolation
    How: Remove MCP_CONFIG_FORMATS env var
    Why: Ensure tests don't interfere with each other

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    monkeypatch.delenv("MCP_CONFIG_FORMATS", raising=False)


@pytest.fixture
def json_only_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment to enable only JSON format.

    Tests: Format filtering via environment
    How: Set MCP_CONFIG_FORMATS to "json"
    Why: Test format-specific behavior

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    monkeypatch.setenv("MCP_CONFIG_FORMATS", "json")


@pytest.fixture
def multi_format_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment to enable multiple formats.

    Tests: Multiple format configuration
    How: Set MCP_CONFIG_FORMATS to "json,yaml,toml"
    Why: Test multi-format scenarios

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    monkeypatch.setenv("MCP_CONFIG_FORMATS", "json,yaml,toml")


# ==============================================================================
# Pytest Configuration
# ==============================================================================


def pytest_configure(config: Any) -> None:
    """Configure pytest with custom markers.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers", "unit: marks unit tests with mocked dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests with real yq binary"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "protocol: marks tests that use actual MCP JSON-RPC protocol"
    )


# ==============================================================================
# MCP Protocol Client Fixtures
# ==============================================================================


@pytest.fixture
def mcp_client() -> Generator[MCPClient, None, None]:
    """Provide an MCP client connected via JSON-RPC protocol.

    Tests: MCP protocol communication
    How: Spawn MCP server subprocess, yield initialized client, cleanup on exit
    Why: Enable tests to verify actual protocol behavior including serialization

    This fixture spawns a new MCP server process for each test function,
    ensuring complete isolation. The server communicates via stdin/stdout
    using JSON-RPC 2.0 protocol.

    Yields:
        MCPClient: Initialized client ready for tool calls
    """
    client = MCPClient()
    client.start()
    yield client
    client.stop()


@pytest.fixture(scope="module")
def mcp_client_module() -> Generator[MCPClient, None, None]:
    """Provide an MCP client shared across a test module.

    Tests: MCP protocol communication (shared instance)
    How: Spawn MCP server subprocess once per module
    Why: Improve test performance when isolation per-test is not needed

    Use this fixture when tests within a module don't modify shared state
    and can safely reuse the same MCP server process.

    Yields:
        MCPClient: Initialized client ready for tool calls
    """
    client = MCPClient()
    client.start()
    yield client
    client.stop()
