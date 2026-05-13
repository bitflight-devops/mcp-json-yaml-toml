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

from mcp_json_yaml_toml.backends.base import FormatType, YQError
from mcp_json_yaml_toml.backends.yq import execute_yq
from mcp_json_yaml_toml.formats.base import (
    _detect_file_format,
    _parse_content_for_validation,
)

if TYPE_CHECKING:
    from pathlib import Path


def _validate_against_schema_documents(
    data: Any, schema_path: Path, document_index: int | None = None
) -> tuple[bool, str, list[dict[str, Any]] | None]:
    """Validate data against schema, including YAML multi-document content.

    Args:
        data: Parsed data value or list of parsed YAML documents.
        schema_path: Path to schema file.
        document_index: Optional specific document index to validate.

    Returns:
        Tuple of (is_valid, message, per_document_results).
    """
    if not isinstance(data, list):
        # For single-document content, index 0 refers to that only document.
        if document_index is not None and document_index != 0:
            return (
                False,
                f"Document index {document_index} out of range for single document",
                None,
            )
        is_valid, message = _validate_against_schema(data, schema_path)
        return is_valid, message, None

    if document_index is None:
        documents_to_validate = list(enumerate(data))
    else:
        if document_index < 0:
            return False, "document_index must be >= 0", None
        if document_index >= len(data):
            return (
                False,
                f"Document index {document_index} out of range (found {len(data)} documents)",
                None,
            )
        documents_to_validate = [(document_index, data[document_index])]

    per_document_results: list[dict[str, Any]] = []
    all_valid = True
    for idx, document_data in documents_to_validate:
        is_valid, message = _validate_against_schema(document_data, schema_path)
        per_document_results.append({
            "document_index": idx,
            "valid": is_valid,
            "message": message,
        })
        all_valid = all_valid and is_valid

    if all_valid:
        return (
            True,
            "Schema validation passed for all checked documents",
            per_document_results,
        )

    failed_indexes = [
        str(result["document_index"])
        for result in per_document_results
        if not result["valid"]
    ]
    return (
        False,
        f"Schema validation failed for document(s): {', '.join(failed_indexes)}",
        per_document_results,
    )


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


__all__ = [
    "_parse_content_for_validation",
    "_validate_against_schema",
    "_validate_against_schema_documents",
]
