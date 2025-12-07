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
from typing import TYPE_CHECKING, ClassVar

import orjson
from fastmcp.exceptions import ToolError
from lmql.ops.regex import Regex

if TYPE_CHECKING:
    from collections.abc import Callable


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

    def to_dict(self) -> dict[str, bool | str | list[str] | None]:
        """Serialize the ValidationResult to a JSON-serializable dictionary.

        Returns:
            A dictionary containing the validation outcome. Always contains:
                - `valid` (bool): whether the value is fully valid.
            May include:
                - `error` (str): error message when invalid.
                - `is_partial` (bool): true if the input could still become valid.
                - `remaining_pattern` (str): regex pattern describing required continuation when partial.
                - `suggestions` (list[str]): suggested completions or corrections.
        """
        result: dict[str, bool | str | list[str] | None] = {"valid": self.valid}
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
        """Validate an input string against this constraint and produce a ValidationResult describing validity, partial status, and any suggestions.

        Returns:
            ValidationResult: Describes whether the input is valid; if not, whether it is a partial match that could become valid with more input (is_partial) and the remaining pattern to complete (remaining_pattern); includes an error message and optional suggestions.
        """

    @classmethod
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Provide a client-facing definition of the constraint for LLM integration.

        Returns:
            dict: Mapping with keys:
                - "name": human-readable constraint name
                - "description": human-readable description
                - "lmql_syntax": LMQL invocation syntax for the constraint (e.g., "NAME(VAR)")
                - "supports_partial": `True` when the constraint supports partial/incremental validation
        """
        return {
            "name": cls.name,
            "description": cls.description,
            "lmql_syntax": f"{cls.name}(VAR)",
            "supports_partial": True,
        }


class RegexConstraint(Constraint):
    """Base class for regex-pattern-based constraints.

    Subclasses only need to define PATTERN and optionally override
    empty_error, invalid_error, and get_suggestions.
    """

    PATTERN: ClassVar[str] = ""

    @classmethod
    def empty_error(cls) -> str:
        """Provide the default error message for an empty input.

        Returns:
            str: The error message string.
        """
        return "Empty input"

    @classmethod
    def invalid_error(cls, value: str) -> str:
        """Produce an error message indicating the input is invalid and showing the expected regex pattern.

        Parameters:
            value (str): The input string that failed validation.

        Returns:
            str: Error message stating the input is invalid and containing the expected pattern.
        """
        return f"Invalid input. Must match pattern: {cls.PATTERN}"

    @classmethod
    def get_suggestions(cls, value: str) -> list[str]:
        """Provide correction suggestions or completions for an invalid or partial input.

        Parameters:
            value (str): The input string to analyze for suggested fixes or completions.

        Returns:
            suggestions (list[str]): Suggested corrections or completions for `value`; empty list if none. Override in subclasses to provide domain-specific suggestions.
        """
        return []

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a string against the constraint's LMQL regex and detect partial matches that can be completed.

        Returns:
            ValidationResult: Outcome of validation. `valid` is `True` for a full match. If not valid, `is_partial` is `True` when the input could be completed to a valid value and `remaining_pattern` contains the regex fragment expected next. `error` contains a human-readable message for empty, incomplete, or invalid input; `suggestions` may include possible corrections.
        """
        if not value:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error=cls.empty_error(),
                remaining_pattern=cls.PATTERN,
            )

        regex = Regex(cls.PATTERN)

        # Full match - valid
        if regex.fullmatch(value):
            return ValidationResult(valid=True)

        # Partial match - could become valid
        if regex.is_prefix(value):
            derivative = regex.d(value)
            remaining = derivative.pattern if derivative else None
            return ValidationResult(
                valid=False,
                is_partial=True,
                error=f"Incomplete input. Continue with: {remaining or '...'}",
                remaining_pattern=remaining,
            )

        # Invalid - provide suggestions if available
        suggestions = cls.get_suggestions(value)
        return ValidationResult(
            valid=False, error=cls.invalid_error(value), suggestions=suggestions
        )

    @classmethod
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Provide the constraint's exported definition including its regex pattern.

        Returns:
            dict[str, str | bool | list[str]]: Constraint metadata (e.g., name, description, lmql_syntax, supports_partial) extended with a "pattern" key containing the constraint's regex pattern string.
        """
        base = super().get_definition()
        base["pattern"] = cls.PATTERN
        return base


class EnumConstraint(Constraint):
    """Base class for enum/choice-based constraints.

    Subclasses only need to define ALLOWED as a frozenset of valid values.
    """

    ALLOWED: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a string against the constraint's allowed values, supporting exact and prefix (partial) matches.

        Returns:
            ValidationResult: `valid` is true for an exact allowed-value match.
            If the input is empty the result is partial and suggests all allowed values.
            If the input is a prefix of one or more allowed values the result is partial and suggests possible completions.
            Otherwise the result is invalid and includes a suggestion list of allowed values.
        """
        if not value:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error="Empty value",
                suggestions=sorted(cls.ALLOWED),
            )

        value_lower = value.lower()

        if value_lower in cls.ALLOWED:
            return ValidationResult(valid=True)

        # Check for partial matches (prefix)
        partial_matches = [f for f in cls.ALLOWED if f.startswith(value_lower)]
        if partial_matches:
            return ValidationResult(
                valid=False,
                is_partial=True,
                error=f"Incomplete. Could be: {', '.join(partial_matches)}",
                suggestions=partial_matches,
            )

        return ValidationResult(
            valid=False,
            error=f"Invalid. Must be one of: {', '.join(sorted(cls.ALLOWED))}",
            suggestions=sorted(cls.ALLOWED),
        )

    @classmethod
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Provide a serializable definition of the enum constraint for client consumption.

        Returns:
            dict: Constraint metadata including base fields from the parent definition plus:
                - "allowed_values": a sorted list of permitted string values.
                - "lmql_syntax": a string showing the membership expression for the allowed set.
        """
        base = super().get_definition()
        base["allowed_values"] = sorted(cls.ALLOWED)
        base["lmql_syntax"] = f"VAR in {sorted(cls.ALLOWED)}"
        return base


class ConstraintRegistry:
    """Registry for named constraints.

    Provides lookup and management of constraint classes by name.
    Constraints are registered using the @register decorator.
    """

    _constraints: ClassVar[dict[str, type[Constraint]]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[Constraint]], type[Constraint]]:
        """Register a constraint class under a given unique name in the registry.

        Args:
            name: Unique registry name to assign to the constraint class.

        Returns:
            A decorator that assigns `name` to a `Constraint` subclass, stores it in the registry, and returns the class.
        """

        def decorator(constraint_cls: type[Constraint]) -> type[Constraint]:
            """Register the given Constraint subclass under the enclosing registry name and return it.

            Parameters:
                constraint_cls (type[Constraint]): The Constraint subclass to register.

            Returns:
                type[Constraint]: The same class that was registered.
            """
            constraint_cls.name = name
            cls._constraints[name] = constraint_cls
            return constraint_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type[Constraint] | None:
        """Retrieve a registered constraint class by its registry name.

        Parameters:
            name (str): The registry name of the constraint to look up.

        Returns:
            type[Constraint] | None: The Constraint subclass for `name`, or `None` if no such constraint is registered.
        """
        return cls._constraints.get(name)

    @classmethod
    def validate(cls, name: str, value: str) -> ValidationResult:
        """Validate a value against a registered constraint identified by name.

        Returns:
            ValidationResult: outcome of validating `value` against the named constraint. If the named constraint is not found, `valid` is `False` and `error` describes the unknown constraint.
        """
        constraint = cls.get(name)
        if not constraint:
            return ValidationResult(valid=False, error=f"Unknown constraint: {name}")
        return constraint.validate(value)

    @classmethod
    def list_constraints(cls) -> list[str]:
        """Return the names of all registered constraints.

        Returns:
            list[str]: Registered constraint names.
        """
        return list(cls._constraints.keys())

    @classmethod
    def get_all_definitions(cls) -> dict[str, dict[str, str | bool | list[str]]]:
        """Collect client-facing definitions for every registered constraint.

        Returns:
            definitions (dict[str, dict[str, str | bool | list[str]]]): Mapping from constraint name to its exported definition (e.g., name, description, lmql_syntax, pattern, allowed_values, and supports_partial).
        """
        return {name: c.get_definition() for name, c in cls._constraints.items()}


# =============================================================================
# Built-in Constraints
# =============================================================================


@ConstraintRegistry.register("YQ_PATH")
class YQPathConstraint(RegexConstraint):
    """Validates yq path expressions.

    Valid patterns:
    - Simple paths: .name, .users, .config
    - Nested paths: .data.users.name
    - Array indexing: .users[0], .items[*]
    - Mixed: .users[0].name, .data.items[*].id
    """

    description = "Valid yq path expression starting with dot"
    PATTERN = r"\.[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\]|\[\*\])*"

    @classmethod
    def empty_error(cls) -> str:
        """Error message used when a yq path input is empty.

        Returns:
            error_message (str): Message indicating the path must start with '.'.
        """
        return "Empty path. yq paths must start with '.'"

    @classmethod
    def invalid_error(cls, value: str) -> str:
        """Produce an error message explaining why a yq path value is invalid.

        Parameters:
            value (str): The yq path string that failed validation.

        Returns:
            str: An error message describing the invalidity; may instruct that the path must start with "." or include the expected pattern.
        """
        if not value.startswith("."):
            return "yq paths must start with '.'"
        return f"Invalid yq path syntax. Must match pattern: {cls.PATTERN}"

    @classmethod
    def get_suggestions(cls, value: str) -> list[str]:
        """Return a suggested yq path completion when a leading dot is missing.

        Parameters:
            value (str): Input path fragment to check.

        Returns:
            list[str]: A list containing a corrected path starting with '.' (or "." for empty input), or an empty list if no suggestion is needed.
        """
        if not value.startswith("."):
            return [f".{value}"] if value else ["."]
        return []

    @classmethod
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Return the constraint definition augmented with example yq paths.

        Returns:
            dict: Constraint metadata dictionary including an "examples" key with sample yq paths (e.g., ".name", ".users[0]", ".config.database.host").
        """
        base = super().get_definition()
        base["examples"] = [".name", ".users[0]", ".config.database.host"]
        return base


@ConstraintRegistry.register("YQ_EXPRESSION")
class YQExpressionConstraint(RegexConstraint):
    """Validates yq expressions including pipes and functions.

    Supports full yq expression syntax including:
    - Simple paths: .name
    - Pipes: .users | length
    - Filters: .users[] | select(.active)
    - Functions: .items | map(.name)
    """

    description = "Valid yq expression with optional pipes and functions"
    PATTERN = r"\.[@a-zA-Z_][\w\.\[\]\*]*(\s*\|\s*[a-zA-Z_][\w]*(\([^)]*\))?)*"

    @classmethod
    def empty_error(cls) -> str:
        """Error message used when the expression input is empty.

        Returns:
            A string describing the empty-expression error.
        """
        return "Empty expression"

    @classmethod
    def invalid_error(cls, value: str) -> str:
        """Produce a human-readable error message for an invalid yq expression.

        Parameters:
            value (str): The yq expression being validated.

        Returns:
            str: Error message explaining why the expression is invalid; when the expression starts with '.', the message includes the expected pattern.
        """
        if not value.startswith("."):
            return "yq expressions must start with '.'"
        return f"Invalid yq expression. Pattern: {cls.PATTERN}"

    @classmethod
    def get_suggestions(cls, value: str) -> list[str]:
        """Suggest a corrected expression by adding a leading dot when the input does not start with one.

        Returns:
            list[str]: A list containing the corrected expression with a leading dot if the input lacked one, otherwise an empty list.
        """
        if not value.startswith("."):
            return [f".{value}"]
        return []

    @classmethod
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Provide the constraint's metadata for client use, including example expressions.

        Returns:
            dict: Mapping of constraint metadata with an "examples" key containing sample expressions (e.g., ".users", ".items | length", ".data[] | select(.active)").
        """
        base = super().get_definition()
        base["examples"] = [".users", ".items | length", ".data[] | select(.active)"]
        return base


@ConstraintRegistry.register("CONFIG_FORMAT")
class ConfigFormatConstraint(EnumConstraint):
    """Validates configuration file format identifiers."""

    description = "Valid configuration format: json, yaml, or toml"
    ALLOWED: ClassVar[frozenset[str]] = frozenset({"json", "yaml", "toml"})


@ConstraintRegistry.register("INT")
class IntConstraint(Constraint):
    """Validates integer values.

    Based on LMQL's IntOp - validates that input contains only digits.
    """

    description = "Valid integer (digits only)"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Determine whether a string represents a valid integer.

        Returns:
            ValidationResult with valid=True for properly formatted integers,
            is_partial=True for incomplete input (empty, whitespace, lone minus),
            and error message when invalid.
        """
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
        has_minus = stripped.startswith("-")
        check_value = stripped.removeprefix("-")

        # Lone minus sign is partial (could become valid with digits)
        if has_minus and not check_value:
            return ValidationResult(valid=False, is_partial=True, error=None)

        if check_value and all(c in string.digits for c in check_value):
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
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        r"""Return the constraint definition metadata for integer validation.

        Returns:
            dict: Definition mapping including keys:
                - "name": constraint name,
                - "description": human-readable description,
                - "supports_partial": whether partial/incremental validation is supported,
                - "pattern": the regex "-?\d+" describing valid integer text,
                - "lmql_syntax": the LMQL syntax hint "INT(VAR)".
        """
        base = super().get_definition()
        base["pattern"] = r"-?\d+"
        base["lmql_syntax"] = "INT(VAR)"
        return base


@ConstraintRegistry.register("KEY_PATH")
class KeyPathConstraint(RegexConstraint):
    """Validates dot-separated key paths.

    Used for the key_path parameter in data operations.
    More permissive than YQ_PATH - doesn't require leading dot.
    """

    description = "Dot-separated key path (e.g., 'users.0.name')"
    PATTERN = r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)*"

    @classmethod
    def validate(cls, value: str) -> ValidationResult:
        """Validate a dot-separated key path; if the input starts with '.', delegate validation to YQPathConstraint.

        Parameters:
            value (str): The key path to validate.

        Returns:
            ValidationResult: Result describing whether the key path is valid. If the input is incomplete the result will have `is_partial=True` and may include `remaining_pattern` for completion; invalid results include an `error` message and optional `suggestions`.
        """
        if not value:
            return ValidationResult(
                valid=False, is_partial=True, error="Empty key path"
            )

        # If starts with dot, it's a yq path - delegate
        if value.startswith("."):
            return YQPathConstraint.validate(value)

        # Use base regex validation
        return super().validate(value)

    @classmethod
    def get_suggestions(cls, value: str) -> list[str]:
        """Provide example key path suggestions.

        Returns:
            A list of example key path suggestions.
        """
        return ["users", "config.database", "items.0.name"]

    @classmethod
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Return the constraint definition extended with example key paths.

        Returns:
            Dictionary of constraint metadata (name, description, lmql_syntax, supports_partial, etc.)
            with an added "examples" entry containing sample key paths like "name", "users.0", and "config.database.host".
        """
        base = super().get_definition()
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
        """Validate a JSON value represented as a string.

        Parses the input as JSON and reports whether it is valid, invalid, or a partial/incomplete JSON fragment.
        If the value is empty, returns a partial result with an "expecting JSON" error. If parsing fails, detects common incomplete forms (unterminated string, unterminated array, unterminated object) and returns a partial result with a specific error; otherwise returns an invalid result with the JSON decode error message.

        Returns:
            ValidationResult: `valid` is `true` when parsing succeeds; when `valid` is `false`, `is_partial` is `true` for incomplete fragments and `error` contains a short diagnostic message.
        """
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
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Provide the constraint definition augmented with representative JSON value examples.

        Returns:
            Dictionary with constraint metadata, including an ``examples`` key containing a list of sample JSON value strings.
        """
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
        """Validate a file path string's syntax.

        Returns:
            ValidationResult: Describes whether the path syntax is valid; when invalid, `error` contains a message. The validator is permissive and may accept complex or unusual paths as valid.
        """
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
    def get_definition(cls) -> dict[str, str | bool | list[str]]:
        """Return the constraint definition extended with the file-path regex pattern and examples.

        Returns:
            dict: Constraint metadata including base definition keys plus:
                - "pattern": the regex pattern string for validating file paths.
                - "examples": a list of example file paths (e.g., "config.json", "./data/settings.yaml", "~/configs/app.toml").
        """
        base = super().get_definition()
        base["pattern"] = cls.PATTERN
        base["examples"] = ["config.json", "./data/settings.yaml", "~/configs/app.toml"]
        return base


# =============================================================================
# Dynamic constraint factories
# =============================================================================


def create_enum_constraint(name: str, allowed_values: list[str]) -> type[Constraint]:
    """Create a Constraint subclass enforcing membership in a fixed set of string values.

    Parameters:
        name (str): Public name assigned to the generated constraint class.
        allowed_values (list[str]): Exact string values that will be accepted by the constraint (used as provided).

    Returns:
        type[Constraint]: A new EnumConstraint subclass with `ALLOWED` set to the provided values and with `.name` and `.description` populated.
    """

    class DynamicEnumConstraint(EnumConstraint):
        """Dynamically created enum constraint."""

        ALLOWED: ClassVar[frozenset[str]] = frozenset(allowed_values)

    DynamicEnumConstraint.name = name
    DynamicEnumConstraint.description = f"One of: {', '.join(sorted(allowed_values))}"
    return DynamicEnumConstraint


def create_pattern_constraint(
    name: str, pattern: str, description: str = ""
) -> type[Constraint]:
    """Create a RegexConstraint subclass that validates values against the provided pattern.

    Parameters:
        name (str): The registry name assigned to the generated constraint class.
        pattern (str): The regex pattern string used for validation (assigned to the class's `PATTERN`).
        description (str): Human-readable description for the constraint; if empty, a default description is generated.

    Returns:
        constraint_cls (type[Constraint]): A new Constraint subclass whose `PATTERN` is set to `pattern` and whose `name` and `description` are set as provided.
    """

    class DynamicPatternConstraint(RegexConstraint):
        """Dynamically created pattern constraint."""

        PATTERN: ClassVar[str] = pattern

    DynamicPatternConstraint.name = name
    DynamicPatternConstraint.description = description or f"Matches pattern: {pattern}"
    return DynamicPatternConstraint


# =============================================================================
# Validation helpers for server integration
# =============================================================================


def validate_tool_input(
    constraint_name: str, value: str, raise_on_invalid: bool = False
) -> ValidationResult:
    """Validate a value against a named constraint and return the corresponding ValidationResult.

    Arguments:
        constraint_name: Name of the registered constraint to use for validation.
        value: The input string to validate.
        raise_on_invalid: If True, raise ToolError when validation is invalid and not partial;
            the raised error message includes the constraint error and any suggestions.

    Returns:
        ValidationResult: Outcome of validating `value` against the named constraint.

    Raises:
        ToolError: If `raise_on_invalid` is True and the validation result is invalid (not partial).
    """
    result = ConstraintRegistry.validate(constraint_name, value)

    if raise_on_invalid and not result.valid and not result.is_partial:
        error_msg = result.error or "Validation failed"
        if result.suggestions:
            error_msg += f" Suggestions: {', '.join(result.suggestions)}"
        raise ToolError(error_msg)

    return result


def get_constraint_hint(constraint_name: str, value: str) -> str | None:
    """Produce a concise hint to help fix a value that does not satisfy the named constraint.

    Parameters:
        constraint_name (str): Registered constraint name to validate against.
        value (str): Value to validate.

    Returns:
        hint (str | None): Concatenated hint containing the validation error, a "Pattern to complete: ..." entry if applicable, and up to three suggested completions (joined with commas); returns `None` if the value is valid or no hintable information is available.
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
