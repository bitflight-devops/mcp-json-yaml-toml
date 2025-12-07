"""LMQL-based constraint validation for MCP server inputs.

This module provides server-side validation using LMQL's Regex class for pattern
matching with partial/incremental validation support. Constraints can validate
complete inputs or check if partial inputs could still become valid.

The constraints defined here are exposed to LLM clients via MCP resources,
enabling client-side constrained generation using LMQL or similar tools.
"""

from __future__ import annotations

import string
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import orjson
from fastmcp.exceptions import ToolError
from lmql.ops.regex import Regex


@dataclass
class ValidationResult:
    """Result of validating a value against a constraint.

    Attributes:
        valid: Whether the value fully satisfies the constraint
        error: Error message if validation failed
        is_partial: True if input is incomplete but could become valid
        remaining_pattern: Regex pattern for what's still needed (if partial)
        suggestions: Optional list of valid completions or corrections
    """

    valid: bool
    error: str | None = None
    is_partial: bool = False
    remaining_pattern: str | None = None
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {"valid": self.valid}
        if self.error:
            result["error"] = self.error
        if self.is_partial:
            result["is_partial"] = True
        if self.remaining_pattern:
            result["remaining_pattern"] = self.remaining_pattern
        if self.suggestions:
            result["suggestions"] = self.suggestions
        return result


class Constraint(ABC):
    """Base class for LMQL-style constraints.

    Constraints provide validation logic that can:
    1. Validate complete values (like traditional validation)
    2. Check if partial/incomplete values could become valid
    3. Export constraint definitions for client-side use
    """

    # Human-readable name for the constraint
    name: ClassVar[str] = ""

    # Description for documentation/LLM context
    description: ClassVar[str] = ""

    @classmethod
    @abstractmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a value against this constraint.

        Args:
            value: The string value to validate

        Returns:
            ValidationResult with validation outcome and details
        """

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition for LLM clients.

        Returns:
            Dictionary with constraint metadata for client-side use
        """
        return {
            "name": cls.name,
            "description": cls.description,
            "lmql_syntax": f"{cls.name}(VAR)",
            "supports_partial": True,
        }


class ConstraintRegistry:
    """Registry for named constraints.

    Provides lookup and management of constraint classes by name.
    Constraints are registered using the @register decorator.
    """

    _constraints: ClassVar[dict[str, type[Constraint]]] = {}

    @classmethod
    def register(cls, name: str) -> Any:
        """Decorator to register a constraint class.

        Args:
            name: Unique name for the constraint

        Returns:
            Decorator function that registers the class
        """

        def decorator(constraint_cls: type[Constraint]) -> type[Constraint]:
            constraint_cls.name = name
            cls._constraints[name] = constraint_cls
            return constraint_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type[Constraint] | None:
        """Get a constraint class by name.

        Args:
            name: Constraint name

        Returns:
            Constraint class or None if not found
        """
        return cls._constraints.get(name)

    @classmethod
    def validate(cls, name: str, value: str) -> ValidationResult:
        """Validate a value against a named constraint.

        Args:
            name: Constraint name
            value: Value to validate

        Returns:
            ValidationResult from the constraint
        """
        constraint = cls.get(name)
        if not constraint:
            return ValidationResult(valid=False, error=f"Unknown constraint: {name}")
        return constraint.validate(value)

    @classmethod
    def list_constraints(cls) -> list[str]:
        """List all registered constraint names.

        Returns:
            List of constraint names
        """
        return list(cls._constraints.keys())

    @classmethod
    def get_all_definitions(cls) -> dict[str, dict[str, Any]]:
        """Get definitions for all registered constraints.

        Returns:
            Dictionary mapping names to constraint definitions
        """
        return {name: c.get_definition() for name, c in cls._constraints.items()}


# =============================================================================
# Built-in Constraints
# =============================================================================


@ConstraintRegistry.register("YQ_PATH")
class YQPathConstraint(Constraint):
    """Validates yq path expressions.

    Valid patterns:
    - Simple paths: .name, .users, .config
    - Nested paths: .data.users.name
    - Array indexing: .users[0], .items[*]
    - Mixed: .users[0].name, .data.items[*].id
    """

    description = "Valid yq path expression starting with dot"

    # Pattern for valid yq path components
    # Allows: .key, .key.subkey, .key[0], .key[*], .key[0].subkey
    PATTERN = r"\.[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\]|\[\*\])*"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a yq path expression."""
        if not value:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error="Empty path. yq paths must start with '.'",
                remaining_pattern=cls.PATTERN,
            )

        regex = Regex(cls.PATTERN)

        # Check full match
        if regex.fullmatch(value):
            return ValidationResult(valid=True)

        # Check if partial input could become valid
        if regex.is_prefix(value):
            derivative = regex.d(value)
            remaining = derivative.pattern if derivative else None
            return ValidationResult(
                valid=False,
                is_partial=True,
                error=f"Incomplete yq path. Continue with: {remaining or '...'}",
                remaining_pattern=remaining,
            )

        # Invalid - provide helpful error
        if not value.startswith("."):
            return ValidationResult(
                valid=False,
                error="yq paths must start with '.'",
                suggestions=[f".{value}"] if value else ["."],
            )

        return ValidationResult(
            valid=False,
            error=f"Invalid yq path syntax. Must match pattern: {cls.PATTERN}",
        )

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["pattern"] = cls.PATTERN
        base["examples"] = [".name", ".users[0]", ".config.database.host"]
        return base


@ConstraintRegistry.register("YQ_EXPRESSION")
class YQExpressionConstraint(Constraint):
    """Validates yq expressions including pipes and functions.

    Supports full yq expression syntax including:
    - Simple paths: .name
    - Pipes: .users | length
    - Filters: .users[] | select(.active)
    - Functions: .items | map(.name)
    """

    description = "Valid yq expression with optional pipes and functions"

    # More permissive pattern for full expressions
    # Allows pipes, functions, select, map, etc.
    PATTERN = r"\.[@a-zA-Z_][\w\.\[\]\*]*(\s*\|\s*[a-zA-Z_][\w]*(\([^)]*\))?)*"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a yq expression."""
        if not value:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error="Empty expression",
                remaining_pattern=cls.PATTERN,
            )

        regex = Regex(cls.PATTERN)

        if regex.fullmatch(value):
            return ValidationResult(valid=True)

        if regex.is_prefix(value):
            derivative = regex.d(value)
            remaining = derivative.pattern if derivative else None
            return ValidationResult(
                valid=False,
                is_partial=True,
                error="Incomplete expression",
                remaining_pattern=remaining,
            )

        if not value.startswith("."):
            return ValidationResult(
                valid=False,
                error="yq expressions must start with '.'",
                suggestions=[f".{value}"],
            )

        return ValidationResult(
            valid=False, error=f"Invalid yq expression. Pattern: {cls.PATTERN}"
        )

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["pattern"] = cls.PATTERN
        base["examples"] = [".users", ".items | length", ".data[] | select(.active)"]
        return base


@ConstraintRegistry.register("CONFIG_FORMAT")
class ConfigFormatConstraint(Constraint):
    """Validates configuration file format identifiers."""

    description = "Valid configuration format: json, yaml, toml, or xml"

    ALLOWED: ClassVar[frozenset[str]] = frozenset({"json", "yaml", "toml", "xml"})

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a config format string."""
        if not value:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error="Empty format",
                suggestions=list(cls.ALLOWED),
            )

        value_lower = value.lower()

        if value_lower in cls.ALLOWED:
            return ValidationResult(valid=True)

        # Check for partial matches
        partial_matches = [f for f in cls.ALLOWED if f.startswith(value_lower)]
        if partial_matches:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error=f"Incomplete format. Could be: {', '.join(partial_matches)}",
                suggestions=partial_matches,
            )

        return ValidationResult(
            valid=False,
            error=f"Invalid format '{value}'. Must be one of: {', '.join(sorted(cls.ALLOWED))}",
            suggestions=list(cls.ALLOWED),
        )

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["allowed_values"] = sorted(cls.ALLOWED)
        base["lmql_syntax"] = f"VAR in {sorted(cls.ALLOWED)}"
        return base


@ConstraintRegistry.register("INT")
class IntConstraint(Constraint):
    """Validates integer values.

    Based on LMQL's IntOp - validates that input contains only digits.
    """

    description = "Valid integer (digits only)"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate an integer string."""
        if not value:
            return ValidationResult(
                valid=False, is_partial=True, error="Empty value - expecting integer"
            )

        # Strip leading whitespace (LMQL IntOp behavior)
        stripped = value.lstrip()

        if not stripped:
            return ValidationResult(
                valid=False, is_partial=True, error="Whitespace only - expecting digits"
            )

        # Allow optional negative sign
        check_value = stripped.removeprefix("-")

        if all(c in string.digits for c in check_value):
            return ValidationResult(valid=True)

        # Find first non-digit
        for i, c in enumerate(check_value):
            if c not in string.digits:
                return ValidationResult(
                    valid=False,
                    error=f"Invalid character '{c}' at position {i}. Integers must contain only digits.",
                )

        return ValidationResult(valid=False, error="Invalid integer format")

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["pattern"] = r"-?\d+"
        base["lmql_syntax"] = "INT(VAR)"
        return base


@ConstraintRegistry.register("KEY_PATH")
class KeyPathConstraint(Constraint):
    """Validates dot-separated key paths.

    Used for the key_path parameter in data operations.
    More permissive than YQ_PATH - doesn't require leading dot.
    """

    description = "Dot-separated key path (e.g., 'users.0.name')"

    # Pattern allows: key, key.subkey, key.0, key.0.subkey
    PATTERN = r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)*"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a key path."""
        if not value:
            return ValidationResult(
                valid=False, is_partial=True, error="Empty key path"
            )

        # If starts with dot, it's a yq path - validate accordingly
        if value.startswith("."):
            return YQPathConstraint.validate(value)

        regex = Regex(cls.PATTERN)

        if regex.fullmatch(value):
            return ValidationResult(valid=True)

        if regex.is_prefix(value):
            derivative = regex.d(value)
            remaining = derivative.pattern if derivative else None
            return ValidationResult(
                valid=False,
                is_partial=True,
                error="Incomplete key path",
                remaining_pattern=remaining,
            )

        return ValidationResult(
            valid=False,
            error=f"Invalid key path. Must match: {cls.PATTERN}",
            suggestions=["users", "config.database", "items.0.name"],
        )

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["pattern"] = cls.PATTERN
        base["examples"] = ["name", "users.0", "config.database.host"]
        return base


@ConstraintRegistry.register("JSON_VALUE")
class JSONValueConstraint(Constraint):
    """Validates JSON-parseable values.

    Checks if the value is valid JSON syntax.
    """

    description = "Valid JSON value (string, number, boolean, null, array, or object)"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a JSON value string."""
        if not value:
            return ValidationResult(
                valid=False, is_partial=True, error="Empty value - expecting JSON"
            )

        try:
            orjson.loads(value)
            return ValidationResult(valid=True)
        except orjson.JSONDecodeError as e:
            # Check for common partial patterns
            stripped = value.strip()

            # Incomplete string
            if stripped.startswith('"') and not stripped.endswith('"'):
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Incomplete string - missing closing quote",
                )

            # Incomplete array
            if stripped.startswith("[") and not stripped.endswith("]"):
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Incomplete array - missing closing bracket",
                )

            # Incomplete object
            if stripped.startswith("{") and not stripped.endswith("}"):
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Incomplete object - missing closing brace",
                )

            return ValidationResult(valid=False, error=f"Invalid JSON: {e}")

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["examples"] = [
            '"hello"',
            "42",
            "true",
            "null",
            '["a", "b"]',
            '{"key": "value"}',
        ]
        return base


@ConstraintRegistry.register("FILE_PATH")
class FilePathConstraint(Constraint):
    """Validates file path syntax.

    Checks for valid file path characters and structure.
    Does NOT check if file exists - that's a separate concern.
    """

    description = "Valid file path syntax"

    # Pattern for Unix-style paths (also works for most Windows paths)
    PATTERN = r"[~./]?[\w./-]+"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a file path string."""
        if not value:
            return ValidationResult(valid=False, error="Empty file path")

        # Check for obviously invalid characters
        invalid_chars = set('<>"|?*') if not value.startswith("\\\\") else set('<>"|?')
        found_invalid = [c for c in value if c in invalid_chars]
        if found_invalid:
            return ValidationResult(
                valid=False,
                error=f"Invalid characters in path: {', '.join(repr(c) for c in found_invalid)}",
            )

        # Check for null bytes
        if "\x00" in value:
            return ValidationResult(
                valid=False, error="Null bytes not allowed in paths"
            )

        # Basic structure check
        regex = Regex(cls.PATTERN)
        if regex.fullmatch(value):
            return ValidationResult(valid=True)

        return ValidationResult(valid=True)  # Be permissive for complex paths

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        """Export constraint definition."""
        base = super().get_definition()
        base["pattern"] = cls.PATTERN
        base["examples"] = ["config.json", "./data/settings.yaml", "~/configs/app.toml"]
        return base


# =============================================================================
# Schema-derived constraints
# =============================================================================


def create_enum_constraint(name: str, allowed_values: list[str]) -> type[Constraint]:
    """Dynamically create an enum constraint from a list of values.

    Args:
        name: Name for the constraint
        allowed_values: List of allowed string values

    Returns:
        New Constraint class for the enum
    """
    allowed_set = frozenset(allowed_values)

    class EnumConstraint(Constraint):
        """Dynamically created enum constraint."""

        description = f"One of: {', '.join(sorted(allowed_set))}"
        ALLOWED: ClassVar[frozenset[str]] = allowed_set

        @classmethod
        def validate(cls, value: str) -> ValidationResult:
            if not value:
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Empty value",
                    suggestions=list(cls.ALLOWED),
                )

            if value in cls.ALLOWED:
                return ValidationResult(valid=True)

            # Partial matches
            partial = [v for v in cls.ALLOWED if v.startswith(value)]
            if partial:
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Incomplete",
                    suggestions=partial,
                )

            return ValidationResult(
                valid=False,
                error=f"Must be one of: {', '.join(sorted(cls.ALLOWED))}",
                suggestions=list(cls.ALLOWED),
            )

        @classmethod
        def get_definition(cls) -> dict[str, Any]:
            base = super().get_definition()
            base["allowed_values"] = sorted(cls.ALLOWED)
            return base

    EnumConstraint.name = name
    return EnumConstraint


def create_pattern_constraint(
    name: str, pattern: str, description: str = ""
) -> type[Constraint]:
    """Dynamically create a regex pattern constraint.

    Args:
        name: Name for the constraint
        pattern: Regex pattern to match
        description: Human-readable description

    Returns:
        New Constraint class for the pattern
    """

    class PatternConstraint(Constraint):
        """Dynamically created pattern constraint."""

        PATTERN: ClassVar[str] = pattern

        @classmethod
        def validate(cls, value: str) -> ValidationResult:
            if not value:
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Empty value",
                    remaining_pattern=cls.PATTERN,
                )

            regex = Regex(cls.PATTERN)

            if regex.fullmatch(value):
                return ValidationResult(valid=True)

            if regex.is_prefix(value):
                derivative = regex.d(value)
                remaining = derivative.pattern if derivative else None
                return ValidationResult(
                    valid=False,
                    is_partial=True,
                    error="Incomplete input",
                    remaining_pattern=remaining,
                )

            return ValidationResult(
                valid=False, error=f"Must match pattern: {cls.PATTERN}"
            )

        @classmethod
        def get_definition(cls) -> dict[str, Any]:
            base = super().get_definition()
            base["pattern"] = cls.PATTERN
            return base

    PatternConstraint.name = name
    PatternConstraint.description = description or f"Matches pattern: {pattern}"
    return PatternConstraint


# =============================================================================
# Validation helpers for server integration
# =============================================================================


def validate_tool_input(
    constraint_name: str, value: str, raise_on_invalid: bool = False
) -> ValidationResult:
    """Validate a tool input value against a named constraint.

    This is the main entry point for server-side validation.

    Args:
        constraint_name: Name of the constraint to use
        value: Value to validate
        raise_on_invalid: If True, raise ToolError on invalid input

    Returns:
        ValidationResult

    Raises:
        ToolError: If raise_on_invalid=True and validation fails
    """
    result = ConstraintRegistry.validate(constraint_name, value)

    if raise_on_invalid and not result.valid and not result.is_partial:
        error_msg = result.error or "Validation failed"
        if result.suggestions:
            error_msg += f" Suggestions: {', '.join(result.suggestions)}"
        raise ToolError(error_msg)

    return result


def get_constraint_hint(constraint_name: str, value: str) -> str | None:
    """Get a hint for fixing an invalid value.

    Useful for including in error messages to help LLMs self-correct.

    Args:
        constraint_name: Name of the constraint
        value: The invalid value

    Returns:
        Hint string or None
    """
    result = ConstraintRegistry.validate(constraint_name, value)

    if result.valid:
        return None

    hints = []
    if result.error:
        hints.append(result.error)
    if result.remaining_pattern:
        hints.append(f"Pattern to complete: {result.remaining_pattern}")
    if result.suggestions:
        hints.append(f"Try: {', '.join(result.suggestions[:3])}")

    return " ".join(hints) if hints else None
