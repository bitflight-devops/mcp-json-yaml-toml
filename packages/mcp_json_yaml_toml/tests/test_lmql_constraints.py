"""Tests for LMQL constraint validation."""

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

    def test_valid_simple_path(self) -> None:
        result = YQPathConstraint.validate(".name")
        assert result.valid is True

    def test_valid_nested_path(self) -> None:
        result = YQPathConstraint.validate(".users.name")
        assert result.valid is True

    def test_valid_array_index(self) -> None:
        result = YQPathConstraint.validate(".users[0]")
        assert result.valid is True

    def test_valid_array_wildcard(self) -> None:
        result = YQPathConstraint.validate(".users[*]")
        assert result.valid is True

    def test_valid_complex_path(self) -> None:
        result = YQPathConstraint.validate(".data.users[0].name")
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

    def test_valid_simple(self) -> None:
        result = YQExpressionConstraint.validate(".name")
        assert result.valid is True

    def test_valid_with_pipe(self) -> None:
        result = YQExpressionConstraint.validate(".items | length")
        assert result.valid is True

    def test_valid_with_function(self) -> None:
        result = YQExpressionConstraint.validate(".users | map(name)")
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

    def test_valid_json(self) -> None:
        result = ConfigFormatConstraint.validate("json")
        assert result.valid is True

    def test_valid_yaml(self) -> None:
        result = ConfigFormatConstraint.validate("yaml")
        assert result.valid is True

    def test_valid_toml(self) -> None:
        result = ConfigFormatConstraint.validate("toml")
        assert result.valid is True

    def test_case_insensitive(self) -> None:
        result = ConfigFormatConstraint.validate("JSON")
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

    def test_valid_positive(self) -> None:
        result = IntConstraint.validate("42")
        assert result.valid is True

    def test_valid_zero(self) -> None:
        result = IntConstraint.validate("0")
        assert result.valid is True

    def test_valid_negative(self) -> None:
        result = IntConstraint.validate("-123")
        assert result.valid is True

    def test_valid_with_leading_space(self) -> None:
        """
        Checks that IntConstraint.validate accepts an integer string with leading whitespace.

        Asserts that the validation result is valid for the input " 42".
        """
        result = IntConstraint.validate(" 42")
        assert result.valid is True

    def test_invalid_float(self) -> None:
        result = IntConstraint.validate("3.14")
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

    def test_valid_simple(self) -> None:
        result = KeyPathConstraint.validate("name")
        assert result.valid is True

    def test_valid_nested(self) -> None:
        result = KeyPathConstraint.validate("users.name")
        assert result.valid is True

    def test_valid_with_number(self) -> None:
        result = KeyPathConstraint.validate("users.0.name")
        assert result.valid is True

    def test_with_leading_dot_delegates_to_yq(self) -> None:
        result = KeyPathConstraint.validate(".name")
        assert result.valid is True

    def test_empty(self) -> None:
        result = KeyPathConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True


class TestJSONValueConstraint:
    """Tests for JSON_VALUE constraint."""

    def test_valid_string(self) -> None:
        result = JSONValueConstraint.validate('"hello"')
        assert result.valid is True

    def test_valid_number(self) -> None:
        result = JSONValueConstraint.validate("42")
        assert result.valid is True

    def test_valid_boolean(self) -> None:
        result = JSONValueConstraint.validate("true")
        assert result.valid is True

    def test_valid_null(self) -> None:
        result = JSONValueConstraint.validate("null")
        assert result.valid is True

    def test_valid_array(self) -> None:
        result = JSONValueConstraint.validate('["a", "b"]')
        assert result.valid is True

    def test_valid_object(self) -> None:
        result = JSONValueConstraint.validate('{"key": "value"}')
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

    def test_valid_simple(self) -> None:
        result = FilePathConstraint.validate("config.json")
        assert result.valid is True

    def test_valid_relative(self) -> None:
        result = FilePathConstraint.validate("./data/settings.yaml")
        assert result.valid is True

    def test_valid_home(self) -> None:
        result = FilePathConstraint.validate("~/configs/app.toml")
        assert result.valid is True

    def test_valid_absolute(self) -> None:
        result = FilePathConstraint.validate("/etc/config.json")
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
