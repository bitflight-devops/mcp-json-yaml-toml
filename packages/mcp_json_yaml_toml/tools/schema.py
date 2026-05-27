"""The ``data_schema`` tool -- unified schema operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.backends.base import FormatType, YQExecutionError
from mcp_json_yaml_toml.backends.yq import execute_yq
from mcp_json_yaml_toml.config import require_format_enabled
from mcp_json_yaml_toml.formats.base import (
    MultiDocumentYaml,
    _detect_file_format,
    _parse_content_for_validation,
    resolve_file_path,
)
from mcp_json_yaml_toml.server import mcp, schema_manager
from mcp_json_yaml_toml.services.schema_validation import (
    _validate_against_schema_documents,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp_json_yaml_toml.schemas.manager import SchemaManager


# ---------------------------------------------------------------------------
# Schema action handlers
# ---------------------------------------------------------------------------


def _handle_schema_validate(
    file_path: str | None,
    schema_path: str | None,
    schema_paths: list[str] | None,
    document_index: int | None,
    schema_manager: SchemaManager,
) -> dict[str, Any]:
    """Handle validate action."""
    if not file_path:
        raise ToolError("file_path required for validate action")
    file_path_obj = resolve_file_path(file_path)

    input_format = _detect_file_format(file_path_obj)
    require_format_enabled(input_format)

    validation_results: dict[str, Any] = {
        "file": str(file_path_obj),
        "format": input_format,
        "syntax_valid": False,
        "schema_validated": False,
    }

    try:
        execute_yq(
            ".",
            input_file=file_path_obj,
            input_format=input_format,
            output_format=FormatType.JSON,
        )
        validation_results["syntax_valid"] = True
        validation_results["syntax_message"] = "Syntax is valid"
        parsed_data = _parse_content_for_validation(
            file_path_obj.read_text(encoding="utf-8"), input_format
        )
        schema_file, per_document_schema_files = _resolve_schema_targets(
            file_path_obj, schema_path, schema_paths, schema_manager
        )
        validation_results.update(
            _run_schema_validation(
                parsed_data, schema_file, per_document_schema_files, document_index
            )
        )
        schema_was_checked = bool(schema_file or per_document_schema_files)
        validation_results["overall_valid"] = validation_results["syntax_valid"] and (
            validation_results["schema_validated"] if schema_was_checked else True
        )
    except YQExecutionError as e:
        validation_results["syntax_message"] = f"Syntax error: {e}"
        validation_results["overall_valid"] = False

    return validation_results


def _resolve_schema_targets(
    file_path_obj: Path,
    schema_path: str | None,
    schema_paths: list[str] | None,
    schema_manager: SchemaManager,
) -> tuple[Path | None, list[Path] | None]:
    """Resolve schema target(s) for validation."""
    if schema_paths:
        return None, [resolve_file_path(path) for path in schema_paths]
    if schema_path:
        return resolve_file_path(schema_path), None
    return schema_manager.get_schema_path_for_file(file_path_obj), None


def _validate_with_schema_paths(
    parsed_data: Any, per_document_schema_files: list[Path], document_index: int | None
) -> dict[str, Any]:
    """Validate multi-document YAML with per-document schema files."""
    if not isinstance(parsed_data, MultiDocumentYaml):
        return {
            "schema_validated": False,
            "schema_message": "schema_paths parameter requires multi-document YAML input (file contains single document)",
        }

    indexes_to_validate = (
        [document_index]
        if document_index is not None
        else list(range(len(parsed_data)))
    )
    if document_index is not None and (
        document_index < 0 or document_index >= len(parsed_data)
    ):
        return {
            "schema_validated": False,
            "schema_message": f"Document index {document_index} out of range (found {len(parsed_data)} documents)",
        }

    document_results: list[dict[str, Any]] = []
    all_valid = True
    for idx in indexes_to_validate:
        if idx >= len(per_document_schema_files):
            document_results.append({
                "document_index": idx,
                "valid": False,
                "message": f"No schema path provided for document index {idx}",
            })
            all_valid = False
            continue
        is_valid, message, _ = _validate_against_schema_documents(
            parsed_data, per_document_schema_files[idx], idx
        )
        all_valid = all_valid and is_valid
        document_results.append({
            "document_index": idx,
            "valid": is_valid,
            "message": message,
            "schema_file": str(per_document_schema_files[idx]),
        })

    return {
        "schema_validated": all_valid,
        "schema_message": "Schema validation passed for all checked documents"
        if all_valid
        else "Schema validation failed for one or more checked documents",
        "document_results": document_results,
        "schema_files": [str(path) for path in per_document_schema_files],
    }


def _validate_with_single_schema(
    parsed_data: Any, schema_file: Path, document_index: int | None
) -> dict[str, Any]:
    """Validate parsed content with one schema file."""
    is_valid = False
    message = "Unable to parse content for schema validation"
    document_results: list[dict[str, Any]] | None = None
    if parsed_data is not None:
        is_valid, message, document_results = _validate_against_schema_documents(
            parsed_data, schema_file, document_index
        )

    response: dict[str, Any] = {
        "schema_file": str(schema_file),
        "schema_validated": is_valid,
        "schema_message": message,
    }
    if document_results is not None:
        response["document_results"] = document_results
    return response


def _run_schema_validation(
    parsed_data: Any,
    schema_file: Path | None,
    per_document_schema_files: list[Path] | None,
    document_index: int | None,
) -> dict[str, Any]:
    """Run schema validation and return response fields."""
    if per_document_schema_files is not None:
        return _validate_with_schema_paths(
            parsed_data, per_document_schema_files, document_index
        )
    if schema_file is not None:
        return _validate_with_single_schema(parsed_data, schema_file, document_index)
    return {"schema_message": "No schema file found or provided"}


def _handle_schema_scan(
    search_paths: list[str] | None, max_depth: int, schema_manager: SchemaManager
) -> dict[str, Any]:
    """Handle scan action."""
    if not search_paths:
        raise ToolError("search_paths required for scan action")
    paths = [Path(p).expanduser().resolve() for p in search_paths]
    discovered = schema_manager.scan_for_schema_dirs(paths, max_depth=max_depth)
    return {
        "success": True,
        "action": "scan",
        "discovered_count": len(discovered),
        "discovered_dirs": [str(p) for p in discovered],
    }


def _handle_schema_add_dir(
    path: str | None, schema_manager: SchemaManager
) -> dict[str, Any]:
    """Handle add_dir action."""
    if not path:
        raise ToolError("path required for add_dir action")
    dir_path = Path(path).expanduser().resolve()
    if not dir_path.exists():
        raise ToolError(f"Directory not found: {path}")
    if not dir_path.is_dir():
        raise ToolError(f"Not a directory: {path}")

    schema_manager.add_custom_dir(dir_path)
    return {
        "success": True,
        "action": "add_dir",
        "directory": str(dir_path),
        "message": "Directory added to schema cache locations",
    }


def _handle_schema_add_catalog(
    name: str | None, uri: str | None, schema_manager: SchemaManager
) -> dict[str, Any]:
    """Handle add_catalog action."""
    if not name or not uri:
        raise ToolError("name and uri required for add_catalog action")
    schema_manager.add_custom_catalog(name, uri)
    return {
        "success": True,
        "action": "add_catalog",
        "name": name,
        "uri": uri,
        "message": "Custom catalog added",
    }


def _handle_schema_associate(
    file_path: str | None,
    schema_url: str | None,
    schema_name: str | None,
    schema_manager: SchemaManager,
) -> dict[str, Any]:
    """Handle associate action."""
    if not file_path:
        raise ToolError("file_path required for associate action")
    file_path_obj = resolve_file_path(file_path)

    url = schema_url
    name = schema_name

    if not url and schema_name:
        catalog = schema_manager.get_catalog()
        if catalog:
            for schema_entry in catalog.schemas:
                if schema_entry.name == schema_name:
                    url = schema_entry.url
                    break
        if not url:
            raise ToolError(f"Schema '{schema_name}' not found in catalog")

    if not url:
        raise ToolError("Either schema_url or schema_name must be provided")

    schema_manager.add_file_association(file_path_obj, url, name)
    return {
        "success": True,
        "action": "associate",
        "file": str(file_path_obj),
        "schema_name": name or "unknown",
        "schema_url": url,
        "message": "File associated with schema",
    }


def _handle_schema_disassociate(
    file_path: str | None, schema_manager: SchemaManager
) -> dict[str, Any]:
    """Handle disassociate action."""
    if not file_path:
        raise ToolError("file_path required for disassociate action")
    file_path_obj = resolve_file_path(file_path, must_exist=False)
    removed = schema_manager.remove_file_association(file_path_obj)
    return {
        "success": True,
        "action": "disassociate",
        "file": str(file_path_obj),
        "removed": removed,
        "message": "Association removed" if removed else "No association found",
    }


def _handle_schema_list(schema_manager: SchemaManager) -> dict[str, Any]:
    """Handle list action."""
    config = schema_manager.get_config()
    return {"success": True, "action": "list", "config": config}


# ---------------------------------------------------------------------------
# Tool decorator
# ---------------------------------------------------------------------------


@mcp.tool(
    timeout=60.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def data_schema(
    action: Annotated[
        Literal[
            "validate",
            "scan",
            "add_dir",
            "add_catalog",
            "associate",
            "disassociate",
            "list",
        ],
        Field(
            description="Action: validate, scan, add_dir, add_catalog, associate, disassociate, or list"
        ),
    ],
    file_path: Annotated[
        str | None,
        Field(description="Path to file (for validate/associate/disassociate actions)"),
    ] = None,
    schema_path: Annotated[
        str | None, Field(description="Path to schema file (for validate action)")
    ] = None,
    schema_paths: Annotated[
        list[str] | None,
        Field(
            description="Optional per-document schema file paths for multi-document YAML (for validate action)"
        ),
    ] = None,
    document_index: Annotated[
        int | None,
        Field(
            description="Optional YAML document index for validate action in multi-document files (0-based)"
        ),
    ] = None,
    schema_url: Annotated[
        str | None, Field(description="Schema URL (for associate action)")
    ] = None,
    schema_name: Annotated[
        str | None, Field(description="Schema name from catalog (for associate action)")
    ] = None,
    search_paths: Annotated[
        list[str] | None, Field(description="Paths to scan (for scan action)")
    ] = None,
    path: Annotated[
        str | None, Field(description="Directory path (for add_dir action)")
    ] = None,
    name: Annotated[
        str | None, Field(description="Catalog name (for add_catalog action)")
    ] = None,
    uri: Annotated[
        str | None, Field(description="Catalog URI (for add_catalog action)")
    ] = None,
    max_depth: Annotated[
        int, Field(description="Max search depth (for scan action)")
    ] = 5,
) -> dict[str, Any]:
    """Unified schema operations tool.

    Actions:
    - validate: Validate file syntax and optionally against schema
    - scan: Recursively search for schema directories
    - add_dir: Add custom schema directory
    - add_catalog: Add custom schema catalog
    - associate: Bind file to schema URL or name
    - disassociate: Remove file-to-schema association
    - list: Show current schema configuration

    Examples:
      - action="validate", file_path="config.json"
      - action="associate", file_path=".gitlab-ci.yml", schema_name="gitlab-ci"
      - action="disassociate", file_path=".gitlab-ci.yml"
      - action="list"
    """
    handlers: dict[str, Callable[[], dict[str, Any]]] = {
        "validate": lambda: _handle_schema_validate(
            file_path, schema_path, schema_paths, document_index, schema_manager
        ),
        "scan": lambda: _handle_schema_scan(search_paths, max_depth, schema_manager),
        "add_dir": lambda: _handle_schema_add_dir(path, schema_manager),
        "add_catalog": lambda: _handle_schema_add_catalog(name, uri, schema_manager),
        "associate": lambda: _handle_schema_associate(
            file_path, schema_url, schema_name, schema_manager
        ),
        "disassociate": lambda: _handle_schema_disassociate(file_path, schema_manager),
        "list": lambda: _handle_schema_list(schema_manager),
    }
    return handlers[action]()
