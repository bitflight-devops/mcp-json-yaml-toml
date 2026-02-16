"""Tests for LMQL constraint validation."""

from __future__ import annotations

import pytest

from mcp_json_yaml_toml.lmql_constraints import (
    ConfigFormatConstraint,
    ConstraintRegistry,
    FilePathConstraint,
    IntConstraint,
    JSONValueConstraint,
    KeyPathConstraint,
    ValidationResult,
    YQExpressionConstraint,
    YQPathConstraint,
    create_enum_constraint,
    create_pattern_constraint,
    get_constraint_hint,
    validate_tool_input,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self) -> None:
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.error is None
        assert result.is_partial is False

    def test_invalid_result(self) -> None:
        result = ValidationResult(valid=False, error="Invalid input")
        assert result.valid is False
        assert result.error == "Invalid input"

    def test_partial_result(self) -> None:
        result = ValidationResult(
            valid=False, is_partial=True, remaining_pattern="[a-z]+"
        )
        assert result.is_partial is True
        assert result.remaining_pattern == "[a-z]+"

    def test_to_dict_minimal(self) -> None:
        result = ValidationResult(valid=True)
        d = result.to_dict()
        assert d == {"valid": True}

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


class TestYQPathConstraint:
    """Tests for YQ_PATH constraint."""

    @pytest.mark.parametrize(
        "path",
        [".name", ".users.name", ".users[0]", ".users[*]", ".data.users[0].name"],
    )
    def test_valid_paths(self, path: str) -> None:
        result = YQPathConstraint.validate(path)
        assert result.valid is True

    def test_empty_path(self) -> None:
        result = YQPathConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_missing_dot(self) -> None:
        result = YQPathConstraint.validate("users")
        assert result.valid is False
        assert ".users" in result.suggestions

    def test_partial_path(self) -> None:
        # .us is actually valid (a complete path)
        result = YQPathConstraint.validate(".us")
        assert result.valid is True

        # A truly partial path would be just "." - incomplete identifier
        result = YQPathConstraint.validate(".")
        assert result.valid is False
        assert result.is_partial is True

    def test_get_definition(self) -> None:
        """
        Verify that YQPathConstraint.get_definition() returns a definition dict containing the expected keys.

        Asserts that the definition's "name" is "YQ_PATH" and that the keys "pattern" and "examples" are present.
        """
        defn = YQPathConstraint.get_definition()
        assert defn["name"] == "YQ_PATH"
        assert "pattern" in defn
        assert "examples" in defn


class TestYQExpressionConstraint:
    """Tests for YQ_EXPRESSION constraint."""

    @pytest.mark.parametrize(
        "expression", [".name", ".items | length", ".users | map(name)"]
    )
    def test_valid_expressions(self, expression: str) -> None:
        result = YQExpressionConstraint.validate(expression)
        assert result.valid is True

    def test_empty(self) -> None:
        result = YQExpressionConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_missing_dot(self) -> None:
        """
        Verify that YQExpressionConstraint rejects expressions missing a leading dot.

        Calls YQExpressionConstraint.validate with "items | length" and asserts the validation result is invalid.
        """
        result = YQExpressionConstraint.validate("items | length")
        assert result.valid is False


class TestConfigFormatConstraint:
    """Tests for CONFIG_FORMAT constraint."""

    @pytest.mark.parametrize("fmt", ["json", "yaml", "toml", "JSON"])
    def test_valid_formats(self, fmt: str) -> None:
        result = ConfigFormatConstraint.validate(fmt)
        assert result.valid is True

    def test_invalid_format(self) -> None:
        result = ConfigFormatConstraint.validate("csv")
        assert result.valid is False
        assert "json" in result.suggestions

    def test_partial_match(self) -> None:
        result = ConfigFormatConstraint.validate("js")
        assert result.valid is False
        assert result.is_partial is True
        assert "json" in result.suggestions

    def test_empty(self) -> None:
        result = ConfigFormatConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_get_definition(self) -> None:
        defn = ConfigFormatConstraint.get_definition()
        assert "allowed_values" in defn
        allowed = defn["allowed_values"]
        assert isinstance(allowed, list)
        assert "json" in allowed


class TestIntConstraint:
    """Tests for INT constraint."""

    @pytest.mark.parametrize("value", ["42", "0", "-123", " 42"])
    def test_valid_integers(self, value: str) -> None:
        result = IntConstraint.validate(value)
        assert result.valid is True

    @pytest.mark.parametrize("value", ["3.14", "abc"])
    def test_invalid_values(self, value: str) -> None:
        result = IntConstraint.validate(value)
        assert result.valid is False

    def test_invalid_letters(self) -> None:
        result = IntConstraint.validate("12a")
        assert result.valid is False
        assert result.error is not None
        assert "Invalid character" in result.error

    def test_empty(self) -> None:
        result = IntConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_lone_minus_is_partial(self) -> None:
        """Lone minus sign is incomplete, not invalid."""
        result = IntConstraint.validate("-")
        assert result.valid is False
        assert result.is_partial is True
        assert result.error is None


class TestKeyPathConstraint:
    """Tests for KEY_PATH constraint."""

    @pytest.mark.parametrize("key", ["name", "users.name", "users.0.name", ".name"])
    def test_valid_keys(self, key: str) -> None:
        result = KeyPathConstraint.validate(key)
        assert result.valid is True

    def test_empty(self) -> None:
        result = KeyPathConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True


class TestJSONValueConstraint:
    """Tests for JSON_VALUE constraint."""

    @pytest.mark.parametrize(
        "value", ['"hello"', "42", "true", "null", '["a", "b"]', '{"key": "value"}']
    )
    def test_valid_values(self, value: str) -> None:
        result = JSONValueConstraint.validate(value)
        assert result.valid is True

    def test_incomplete_string(self) -> None:
        result = JSONValueConstraint.validate('"hello')
        assert result.valid is False
        assert result.is_partial is True
        assert result.error is not None
        assert "Incomplete string" in result.error

    def test_incomplete_array(self) -> None:
        result = JSONValueConstraint.validate('["a", "b"')
        assert result.valid is False
        assert result.is_partial is True
        assert result.error is not None
        assert "Incomplete array" in result.error

    def test_incomplete_object(self) -> None:
        result = JSONValueConstraint.validate('{"key": "value"')
        assert result.valid is False
        assert result.is_partial is True
        assert result.error is not None
        assert "Incomplete object" in result.error

    def test_empty(self) -> None:
        result = JSONValueConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True


class TestFilePathConstraint:
    """Tests for FILE_PATH constraint."""

    @pytest.mark.parametrize(
        "path",
        [
            "config.json",
            "./data/settings.yaml",
            "~/configs/app.toml",
            "/etc/config.json",
        ],
    )
    def test_valid_paths(self, path: str) -> None:
        result = FilePathConstraint.validate(path)
        assert result.valid is True

    def test_empty(self) -> None:
        result = FilePathConstraint.validate("")
        assert result.valid is False

    def test_invalid_chars(self) -> None:
        result = FilePathConstraint.validate("config<test>.json")
        assert result.valid is False
        assert result.error is not None
        assert "Invalid characters" in result.error

    def test_null_byte(self) -> None:
        result = FilePathConstraint.validate("config\x00.json")
        assert result.valid is False
        assert result.error is not None
        assert "Null bytes" in result.error


class TestConstraintRegistry:
    """Tests for ConstraintRegistry."""

    def test_get_registered_constraint(self) -> None:
        constraint = ConstraintRegistry.get("YQ_PATH")
        assert constraint is YQPathConstraint

    def test_get_unknown_constraint(self) -> None:
        constraint = ConstraintRegistry.get("UNKNOWN")
        assert constraint is None

    def test_validate_with_registry(self) -> None:
        result = ConstraintRegistry.validate("YQ_PATH", ".name")
        assert result.valid is True

    def test_validate_unknown_constraint(self) -> None:
        result = ConstraintRegistry.validate("UNKNOWN", "value")
        assert result.valid is False
        assert result.error is not None
        assert "Unknown constraint" in result.error

    def test_list_constraints(self) -> None:
        constraints = ConstraintRegistry.list_constraints()
        assert "YQ_PATH" in constraints
        assert "CONFIG_FORMAT" in constraints
        assert "INT" in constraints

    def test_get_all_definitions(self) -> None:
        definitions = ConstraintRegistry.get_all_definitions()
        assert "YQ_PATH" in definitions
        assert "name" in definitions["YQ_PATH"]


class TestDynamicConstraints:
    """Tests for dynamically created constraints."""

    def test_create_enum_constraint(self) -> None:
        StatusConstraint = create_enum_constraint(
            "STATUS", ["active", "inactive", "pending"]
        )

        result = StatusConstraint.validate("active")
        assert result.valid is True

        result = StatusConstraint.validate("invalid")
        assert result.valid is False

        result = StatusConstraint.validate("act")
        assert result.valid is False
        assert result.is_partial is True
        assert "active" in result.suggestions

    def test_create_pattern_constraint(self) -> None:
        EmailConstraint = create_pattern_constraint(
            "EMAIL", r"[a-z]+@[a-z]+\.[a-z]+", "Valid email address"
        )

        result = EmailConstraint.validate("test@example.com")
        assert result.valid is True

        result = EmailConstraint.validate("invalid")
        assert result.valid is False


class TestValidationHelpers:
    """Tests for validation helper functions."""

    def test_validate_tool_input_valid(self) -> None:
        result = validate_tool_input("YQ_PATH", ".name")
        assert result.valid is True

    def test_validate_tool_input_invalid(self) -> None:
        result = validate_tool_input("YQ_PATH", "invalid")
        assert result.valid is False

    def test_validate_tool_input_raises(self) -> None:
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError):
            validate_tool_input("YQ_PATH", "invalid", raise_on_invalid=True)

    def test_get_constraint_hint_valid(self) -> None:
        hint = get_constraint_hint("YQ_PATH", ".name")
        assert hint is None

    def test_get_constraint_hint_invalid(self) -> None:
        hint = get_constraint_hint("YQ_PATH", "users")
        assert hint is not None
        assert "." in hint  # Should mention the missing dot


class TestLMQLRegexIntegration:
    """Tests verifying LMQL Regex integration works correctly."""

    def test_regex_fullmatch(self) -> None:
        """Test that LMQL Regex.fullmatch works as expected."""
        from lmql.ops.regex import Regex

        r = Regex(r"\.[a-z]+")
        assert r.fullmatch(".test") is True
        assert r.fullmatch("test") is False

    def test_regex_is_prefix(self) -> None:
        """Test that LMQL Regex.is_prefix works for partial validation."""
        from lmql.ops.regex import Regex

        r = Regex(r"\.[a-z]+\.[a-z]+")
        assert r.is_prefix(".test") is True  # Could complete to .test.more
        assert r.is_prefix(".test.") is True  # Could complete to .test.x
        assert r.is_prefix("test") is False  # Can never match

    def test_regex_derivative(self) -> None:
        """Test that LMQL Regex.d (derivative) works."""
        from lmql.ops.regex import Regex

        r = Regex(r"\.[a-z]+\.[a-z]+")
        d = r.d(".test")
        assert d is not None
        assert d.pattern  # Should have remaining pattern
