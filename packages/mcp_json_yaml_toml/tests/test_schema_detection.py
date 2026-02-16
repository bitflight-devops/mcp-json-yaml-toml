from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from mcp_json_yaml_toml.schemas import SchemaManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def schema_manager() -> SchemaManager:
    return SchemaManager()


def test_detect_schema_when_json_with_schema_url_then_returns_schema_info(
    tmp_path: Path, schema_manager: SchemaManager
) -> None:
    """Verify schema detection in JSON files."""
    schema_url = "http://example.com/schema.json"
    file_path = tmp_path / "test.json"
    content = {"$schema": schema_url, "foo": "bar"}
    file_path.write_text(json.dumps(content))

    detected = schema_manager.get_schema_info_for_file(file_path)
    assert detected is not None
    assert detected.url == schema_url


def test_detect_schema_when_yaml_with_language_server_comment_then_returns_schema_info(
    tmp_path: Path, schema_manager: SchemaManager
) -> None:
    """Verify schema detection in YAML files."""
    schema_url = "http://example.com/schema.yaml"
    file_path = tmp_path / "test.yaml"
    content = f"""# yaml-language-server: $schema={schema_url}
foo: bar
"""
    file_path.write_text(content)

    detected = schema_manager.get_schema_info_for_file(file_path)
    assert detected is not None
    assert detected.url == schema_url


def test_detect_schema_when_yaml_with_schema_key_then_returns_schema_info(
    tmp_path: Path, schema_manager: SchemaManager
) -> None:
    """Verify schema detection in YAML files using $schema key."""
    schema_url = "http://example.com/schema.yaml"
    file_path = tmp_path / "test_key.yaml"
    content = f"""$schema: "{schema_url}"
foo: bar
"""
    file_path.write_text(content)

    detected = schema_manager.get_schema_info_for_file(file_path)
    assert detected is not None
    assert detected.url == schema_url


def test_detect_schema_when_toml_with_schema_comment_then_returns_schema_info(
    tmp_path: Path, schema_manager: SchemaManager
) -> None:
    """Verify schema detection in TOML files."""
    schema_url = "http://example.com/schema.json"
    file_path = tmp_path / "test.toml"
    content = f"""#:schema {schema_url}
foo = "bar"
"""
    file_path.write_text(content)

    detected = schema_manager.get_schema_info_for_file(file_path)
    assert detected is not None
    assert detected.url == schema_url


def test_detect_schema_when_toml_with_schema_key_then_returns_schema_info(
    tmp_path: Path, schema_manager: SchemaManager
) -> None:
    """Verify schema detection in TOML files using $schema key.

    Note: In TOML, $schema must be a quoted key since bare keys cannot contain $.
    """
    schema_url = "http://example.com/schema.json"
    file_path = tmp_path / "test_key.toml"
    content = f""""$schema" = "{schema_url}"
foo = "bar"
"""
    file_path.write_text(content)

    detected = schema_manager.get_schema_info_for_file(file_path)
    assert detected is not None
    assert detected.url == schema_url
