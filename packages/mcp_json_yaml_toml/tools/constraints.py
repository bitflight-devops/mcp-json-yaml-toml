"""Constraint tools, resources, and prompts for LMQL-style validation."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.lmql_constraints import (
    ConstraintRegistry,
    get_constraint_hint,
    validate_tool_input,
)
from mcp_json_yaml_toml.models.responses import (
    ConstraintListResponse,
    ConstraintValidateResponse,
)
from mcp_json_yaml_toml.server import mcp

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("lmql://constraints")
def list_all_constraints() -> dict[str, Any]:
    """Provide metadata and definitions for all registered LMQL constraints.

    Returns:
        A dictionary with:
        - "constraints": a mapping of all constraint definitions keyed by name.
        - "description": a short human-readable description of the constraint collection.
        - "usage": a brief usage note for applying these constraints in constrained generation.
    """
    return {
        "constraints": ConstraintRegistry.get_all_definitions(),
        "description": "LMQL-style constraints for validating tool inputs",
        "usage": "Use these constraints with LMQL or similar tools for constrained generation",
    }


@mcp.resource("lmql://constraints/{name}")
def get_constraint_definition(name: str) -> dict[str, Any]:
    """Retrieve the definition of a named LMQL constraint.

    Raises:
        ToolError: If the constraint name is not registered; the error message lists available constraints.

    Returns:
        dict: Constraint definition containing fields such as pattern, examples, and LMQL syntax.
    """
    constraint = ConstraintRegistry.get(name)
    if not constraint:
        available = ConstraintRegistry.list_constraints()
        raise ToolError(
            f"Unknown constraint: '{name}'. Available: {', '.join(available)}"
        )
    return constraint.get_definition()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def constraint_validate(
    constraint_name: Annotated[
        str,
        Field(
            description="Name of the constraint to validate against (e.g., 'YQ_PATH', 'CONFIG_FORMAT', 'INT')"
        ),
    ],
    value: Annotated[str, Field(description="Value to validate")],
) -> ConstraintValidateResponse:
    """Validate a value against an LMQL-style constraint.

    Use this tool to check if a value satisfies a constraint before using it
    in other operations. Supports partial validation - can tell if an incomplete
    input could still become valid.

    Output contract: Returns {"valid": bool, "error": str?, "is_partial": bool?, ...}.
    Side effects: None (read-only validation).
    Failure modes: ToolError if constraint name unknown.

    Available constraints:
    - YQ_PATH: Valid yq path (e.g., '.users[0].name')
    - YQ_EXPRESSION: Valid yq expression with pipes (e.g., '.items | length')
    - CONFIG_FORMAT: Valid format ('json', 'yaml', 'toml', 'xml')
    - KEY_PATH: Dot-separated key path (e.g., 'config.database.host')
    - INT: Valid integer
    - JSON_VALUE: Valid JSON syntax
    - FILE_PATH: Valid file path syntax
    """
    result = validate_tool_input(constraint_name, value)

    # Build hint for invalid values
    hint_value: str | None = None
    if not result.valid:
        hint_value = get_constraint_hint(constraint_name, value)

    # Collect dynamic extras (suggestions, remaining_pattern) for
    # Pydantic's extra="allow" bucket -- exclude known model fields.
    result_dict = result.to_dict()
    known_fields = ConstraintValidateResponse.model_fields
    extras = {k: v for k, v in result_dict.items() if k not in known_fields}

    return ConstraintValidateResponse(
        valid=result.valid,
        constraint=constraint_name,
        value=value,
        error=result.error,
        is_partial=result.is_partial or None,
        hint=hint_value,
        **extras,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def constraint_list() -> ConstraintListResponse:
    """Return a list of all registered LMQL constraints with their metadata.

    Returns:
        ConstraintListResponse with keys:
            - "constraints": a list of constraint objects; each object includes a "name" key and the constraint's definition fields (e.g., "description", any other metadata).
            - "usage": a string describing how to validate a value against a constraint (e.g., call `constraint_validate(constraint_name, value)`).
    """
    definitions = ConstraintRegistry.get_all_definitions()
    return ConstraintListResponse(
        constraints=[{"name": name, **defn} for name, defn in definitions.items()],
        usage=(
            "Use constraint_validate(constraint_name, value) to validate inputs. "
            "Access constraint definitions via lmql://constraints/{name} resource."
        ),
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def explain_config(file_path: str) -> str:
    """Produce a natural-language prompt that requests an analysis of a configuration file.

    The generated prompt asks an assistant to:
    1. Identify the file format (JSON, YAML, TOML).
    2. Summarize the file's key sections and their purpose.
    3. Highlight critical settings and potential misconfigurations.
    4. Check adherence to an available schema, if one exists.

    Parameters:
        file_path (str): Path to the configuration file to be analyzed.

    Returns:
        prompt (str): A formatted prompt string referring to the provided file path.
    """
    return f"""Please analyze and explain the configuration file at '{file_path}'.

    1. Identify the file format (JSON, YAML, TOML).
    2. Summarize the key sections and their purpose.
    3. Highlight any critical settings or potential misconfigurations.
    4. If a schema is available, check if the config adheres to it.
    """


@mcp.prompt()
def suggest_improvements(file_path: str) -> str:
    """Generate a prompt to suggest improvements for a configuration file."""
    return f"""Please review the configuration file at '{file_path}' and suggest improvements.

    Consider:
    1. Security best practices (e.g., exposed secrets).
    2. Performance optimizations.
    3. Readability and structure (e.g., comments, organization).
    4. Redundant or deprecated settings.
    """


@mcp.prompt()
def convert_to_schema(file_path: str) -> str:
    """Generate a prompt to create a JSON schema from a configuration file."""
    return f"""Please generate a JSON schema based on the configuration file at '{file_path}'.

    1. Infer types for all fields.
    2. Mark fields as required or optional based on common patterns.
    3. Add descriptions for fields where the purpose is clear.
    4. Use standard JSON Schema Draft 7 or later.
    """
