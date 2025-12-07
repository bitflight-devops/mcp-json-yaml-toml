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

    def test_valid_result(self):
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.error is None
        assert result.is_partial is False

    def test_invalid_result(self):
        result = ValidationResult(valid=False, error="Invalid input")
        assert result.valid is False
        assert result.error == "Invalid input"

    def test_partial_result(self):
        result = ValidationResult(
            valid=False,
            is_partial=True,
            remaining_pattern="[a-z]+",
        )
        assert result.is_partial is True
        assert result.remaining_pattern == "[a-z]+"

    def test_to_dict_minimal(self):
        result = ValidationResult(valid=True)
        d = result.to_dict()
        assert d == {"valid": True}

    def test_to_dict_full(self):
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

    def test_valid_simple_path(self):
        result = YQPathConstraint.validate(".name")
        assert result.valid is True

    def test_valid_nested_path(self):
        result = YQPathConstraint.validate(".users.name")
        assert result.valid is True

    def test_valid_array_index(self):
        result = YQPathConstraint.validate(".users[0]")
        assert result.valid is True

    def test_valid_array_wildcard(self):
        result = YQPathConstraint.validate(".users[*]")
        assert result.valid is True

    def test_valid_complex_path(self):
        result = YQPathConstraint.validate(".data.users[0].name")
        assert result.valid is True

    def test_empty_path(self):
        result = YQPathConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_missing_dot(self):
        result = YQPathConstraint.validate("users")
        assert result.valid is False
        assert ".users" in result.suggestions

    def test_partial_path(self):
        # .us is actually valid (a complete path)
        result = YQPathConstraint.validate(".us")
        assert result.valid is True

        # A truly partial path would be just "." - incomplete identifier
        result = YQPathConstraint.validate(".")
        assert result.valid is False
        assert result.is_partial is True

    def test_get_definition(self):
        defn = YQPathConstraint.get_definition()
        assert defn["name"] == "YQ_PATH"
        assert "pattern" in defn
        assert "examples" in defn


class TestYQExpressionConstraint:
    """Tests for YQ_EXPRESSION constraint."""

    def test_valid_simple(self):
        result = YQExpressionConstraint.validate(".name")
        assert result.valid is True

    def test_valid_with_pipe(self):
        result = YQExpressionConstraint.validate(".items | length")
        assert result.valid is True

    def test_valid_with_function(self):
        result = YQExpressionConstraint.validate(".users | map(name)")
        assert result.valid is True

    def test_empty(self):
        result = YQExpressionConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_missing_dot(self):
        result = YQExpressionConstraint.validate("items | length")
        assert result.valid is False


class TestConfigFormatConstraint:
    """Tests for CONFIG_FORMAT constraint."""

    def test_valid_json(self):
        result = ConfigFormatConstraint.validate("json")
        assert result.valid is True

    def test_valid_yaml(self):
        result = ConfigFormatConstraint.validate("yaml")
        assert result.valid is True

    def test_valid_toml(self):
        result = ConfigFormatConstraint.validate("toml")
        assert result.valid is True

    def test_valid_xml(self):
        result = ConfigFormatConstraint.validate("xml")
        assert result.valid is True

    def test_case_insensitive(self):
        result = ConfigFormatConstraint.validate("JSON")
        assert result.valid is True

    def test_invalid_format(self):
        result = ConfigFormatConstraint.validate("csv")
        assert result.valid is False
        assert "json" in result.suggestions

    def test_partial_match(self):
        result = ConfigFormatConstraint.validate("js")
        assert result.valid is False
        assert result.is_partial is True
        assert "json" in result.suggestions

    def test_empty(self):
        result = ConfigFormatConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True

    def test_get_definition(self):
        defn = ConfigFormatConstraint.get_definition()
        assert "allowed_values" in defn
        assert "json" in defn["allowed_values"]


class TestIntConstraint:
    """Tests for INT constraint."""

    def test_valid_positive(self):
        result = IntConstraint.validate("42")
        assert result.valid is True

    def test_valid_zero(self):
        result = IntConstraint.validate("0")
        assert result.valid is True

    def test_valid_negative(self):
        result = IntConstraint.validate("-123")
        assert result.valid is True

    def test_valid_with_leading_space(self):
        result = IntConstraint.validate(" 42")
        assert result.valid is True

    def test_invalid_float(self):
        result = IntConstraint.validate("3.14")
        assert result.valid is False

    def test_invalid_letters(self):
        result = IntConstraint.validate("12a")
        assert result.valid is False
        assert "Invalid character" in result.error

    def test_empty(self):
        result = IntConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True


class TestKeyPathConstraint:
    """Tests for KEY_PATH constraint."""

    def test_valid_simple(self):
        result = KeyPathConstraint.validate("name")
        assert result.valid is True

    def test_valid_nested(self):
        result = KeyPathConstraint.validate("users.name")
        assert result.valid is True

    def test_valid_with_number(self):
        result = KeyPathConstraint.validate("users.0.name")
        assert result.valid is True

    def test_with_leading_dot_delegates_to_yq(self):
        result = KeyPathConstraint.validate(".name")
        assert result.valid is True

    def test_empty(self):
        result = KeyPathConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True


class TestJSONValueConstraint:
    """Tests for JSON_VALUE constraint."""

    def test_valid_string(self):
        result = JSONValueConstraint.validate('"hello"')
        assert result.valid is True

    def test_valid_number(self):
        result = JSONValueConstraint.validate("42")
        assert result.valid is True

    def test_valid_boolean(self):
        result = JSONValueConstraint.validate("true")
        assert result.valid is True

    def test_valid_null(self):
        result = JSONValueConstraint.validate("null")
        assert result.valid is True

    def test_valid_array(self):
        result = JSONValueConstraint.validate('["a", "b"]')
        assert result.valid is True

    def test_valid_object(self):
        result = JSONValueConstraint.validate('{"key": "value"}')
        assert result.valid is True

    def test_incomplete_string(self):
        result = JSONValueConstraint.validate('"hello')
        assert result.valid is False
        assert result.is_partial is True
        assert "Incomplete string" in result.error

    def test_incomplete_array(self):
        result = JSONValueConstraint.validate('["a", "b"')
        assert result.valid is False
        assert result.is_partial is True
        assert "Incomplete array" in result.error

    def test_incomplete_object(self):
        result = JSONValueConstraint.validate('{"key": "value"')
        assert result.valid is False
        assert result.is_partial is True
        assert "Incomplete object" in result.error

    def test_empty(self):
        result = JSONValueConstraint.validate("")
        assert result.valid is False
        assert result.is_partial is True


class TestFilePathConstraint:
    """Tests for FILE_PATH constraint."""

    def test_valid_simple(self):
        result = FilePathConstraint.validate("config.json")
        assert result.valid is True

    def test_valid_relative(self):
        result = FilePathConstraint.validate("./data/settings.yaml")
        assert result.valid is True

    def test_valid_home(self):
        result = FilePathConstraint.validate("~/configs/app.toml")
        assert result.valid is True

    def test_valid_absolute(self):
        result = FilePathConstraint.validate("/etc/config.json")
        assert result.valid is True

    def test_empty(self):
        result = FilePathConstraint.validate("")
        assert result.valid is False

    def test_invalid_chars(self):
        result = FilePathConstraint.validate('config<test>.json')
        assert result.valid is False
        assert "Invalid characters" in result.error

    def test_null_byte(self):
        result = FilePathConstraint.validate("config\x00.json")
        assert result.valid is False
        assert "Null bytes" in result.error


class TestConstraintRegistry:
    """Tests for ConstraintRegistry."""

    def test_get_registered_constraint(self):
        constraint = ConstraintRegistry.get("YQ_PATH")
        assert constraint is YQPathConstraint

    def test_get_unknown_constraint(self):
        constraint = ConstraintRegistry.get("UNKNOWN")
        assert constraint is None

    def test_validate_with_registry(self):
        result = ConstraintRegistry.validate("YQ_PATH", ".name")
        assert result.valid is True

    def test_validate_unknown_constraint(self):
        result = ConstraintRegistry.validate("UNKNOWN", "value")
        assert result.valid is False
        assert "Unknown constraint" in result.error

    def test_list_constraints(self):
        constraints = ConstraintRegistry.list_constraints()
        assert "YQ_PATH" in constraints
        assert "CONFIG_FORMAT" in constraints
        assert "INT" in constraints

    def test_get_all_definitions(self):
        definitions = ConstraintRegistry.get_all_definitions()
        assert "YQ_PATH" in definitions
        assert "name" in definitions["YQ_PATH"]


class TestDynamicConstraints:
    """Tests for dynamically created constraints."""

    def test_create_enum_constraint(self):
        StatusConstraint = create_enum_constraint("STATUS", ["active", "inactive", "pending"])

        result = StatusConstraint.validate("active")
        assert result.valid is True

        result = StatusConstraint.validate("invalid")
        assert result.valid is False

        result = StatusConstraint.validate("act")
        assert result.valid is False
        assert result.is_partial is True
        assert "active" in result.suggestions

    def test_create_pattern_constraint(self):
        EmailConstraint = create_pattern_constraint(
            "EMAIL",
            r"[a-z]+@[a-z]+\.[a-z]+",
            "Valid email address",
        )

        result = EmailConstraint.validate("test@example.com")
        assert result.valid is True

        result = EmailConstraint.validate("invalid")
        assert result.valid is False


class TestValidationHelpers:
    """Tests for validation helper functions."""

    def test_validate_tool_input_valid(self):
        result = validate_tool_input("YQ_PATH", ".name")
        assert result.valid is True

    def test_validate_tool_input_invalid(self):
        result = validate_tool_input("YQ_PATH", "invalid")
        assert result.valid is False

    def test_validate_tool_input_raises(self):
        with pytest.raises(Exception):  # ToolError
            validate_tool_input("YQ_PATH", "invalid", raise_on_invalid=True)

    def test_get_constraint_hint_valid(self):
        hint = get_constraint_hint("YQ_PATH", ".name")
        assert hint is None

    def test_get_constraint_hint_invalid(self):
        hint = get_constraint_hint("YQ_PATH", "users")
        assert hint is not None
        assert "." in hint  # Should mention the missing dot


class TestLMQLRegexIntegration:
    """Tests verifying LMQL Regex integration works correctly."""

    def test_regex_fullmatch(self):
        """Test that LMQL Regex.fullmatch works as expected."""
        from lmql.ops.regex import Regex

        r = Regex(r"\.[a-z]+")
        assert r.fullmatch(".test") is True
        assert r.fullmatch("test") is False

    def test_regex_is_prefix(self):
        """Test that LMQL Regex.is_prefix works for partial validation."""
        from lmql.ops.regex import Regex

        r = Regex(r"\.[a-z]+\.[a-z]+")
        assert r.is_prefix(".test") is True  # Could complete to .test.more
        assert r.is_prefix(".test.") is True  # Could complete to .test.x
        assert r.is_prefix("test") is False  # Can never match

    def test_regex_derivative(self):
        """Test that LMQL Regex.d (derivative) works."""
        from lmql.ops.regex import Regex

        r = Regex(r"\.[a-z]+\.[a-z]+")
        d = r.d(".test")
        assert d is not None
        assert d.pattern  # Should have remaining pattern
