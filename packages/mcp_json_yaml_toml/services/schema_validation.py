"""JSON Schema validation logic extracted from server.py.

Provides schema validation using jsonschema with Draft 7 and Draft 2020-12 support.
Uses referencing.Registry for $ref resolution via httpx.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

from mcp_json_yaml_toml.formats.base import (
    _detect_file_format,
    _parse_content_for_validation,
)
from mcp_json_yaml_toml.yq_wrapper import FormatType, YQError, execute_yq

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["_parse_content_for_validation", "_validate_against_schema"]


def _validate_against_schema(data: Any, schema_path: Path) -> tuple[bool, str]:
    """Validate data against JSON schema.

    Uses referencing.Registry to handle $ref resolution without deprecated auto-fetch.

    Args:
        data: Data to validate (parsed from JSON/YAML)
        schema_path: Path to schema file

    Returns:
        Tuple of (is_valid, message)
    """

    def retrieve_via_httpx(uri: str) -> Resource:
        """Retrieve schema from HTTP(S) URI using httpx."""
        try:
            response = httpx.get(uri, follow_redirects=True, timeout=10.0)
            response.raise_for_status()
            contents = response.json()
            return Resource.from_contents(contents)
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise NoSuchResource(ref=uri) from e

    try:
        # Load schema
        schema_format = _detect_file_format(schema_path)
        schema_result = execute_yq(
            ".",
            input_file=schema_path,
            input_format=schema_format,
            output_format=FormatType.JSON,
        )

        if schema_result.data is None:
            return False, f"Failed to parse schema file: {schema_path}"

        schema = schema_result.data

        # Create registry with httpx retrieval for remote $refs
        registry: Registry = Registry(retrieve=retrieve_via_httpx)

        # Choose validator based on schema's $schema field or default to Draft 2020-12
        schema_dialect = schema.get("$schema", "")
        if "draft-07" in schema_dialect or "draft/7" in schema_dialect:
            Draft7Validator(schema, registry=registry).validate(data)
        else:
            # Default to Draft 2020-12 (current JSON Schema standard)
            Draft202012Validator(schema, registry=registry).validate(data)

    except ValidationError as e:
        return False, f"Schema validation failed: {e.message}"
    except SchemaError as e:
        return False, f"Invalid schema: {e.message}"
    except YQError as e:
        return False, f"Failed to load schema: {e}"
    except (OSError, ValueError) as e:
        return False, f"Schema validation error: {e}"
    else:
        return True, "Schema validation passed"
