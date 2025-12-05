"""Tests for TOML write operations."""

from pathlib import Path

import pytest

from mcp_json_yaml_toml import server


class TestTOMLWriteOperations:
    """Test TOML SET and DELETE operations using tomli/tomli_w."""

    @pytest.mark.integration
    def test_toml_set_operation(self, tmp_path: Path) -> None:
        """Test that SET operation works for TOML files."""
        # Create a TOML file
        test_file = tmp_path / "config.toml"
        test_file.write_text("""[database]
host = "localhost"
port = 5432
""")

        # Add a new key
        result = server.data.fn(
            file_path=str(test_file),
            operation="set",
            key_path="database.username",
            value='"admin"',
        )

        # Should succeed
        assert result["success"] is True
        assert result["result"] == "File modified successfully"

        # Read the file and verify
        modified_content = test_file.read_text()
        assert "username" in modified_content
        assert "admin" in modified_content

    @pytest.mark.integration
    def test_toml_set_nested_table(self, tmp_path: Path) -> None:
        """Test setting a nested table in TOML."""
        test_file = tmp_path / "config.toml"
        test_file.write_text("""[app]
name = "myapp"
""")

        # Add nested config
        result = server.data.fn(
            file_path=str(test_file),
            operation="set",
            key_path="app.database",
            value='{"host": "localhost", "port": 5432}',
        )

        assert result["success"] is True

        # Verify
        modified_content = test_file.read_text()
        assert "[app.database]" in modified_content or "database" in modified_content
        assert "localhost" in modified_content

    @pytest.mark.integration
    def test_toml_delete_operation(self, tmp_path: Path) -> None:
        """Test that DELETE operation works for TOML files."""
        test_file = tmp_path / "config.toml"
        test_file.write_text("""[database]
host = "localhost"
port = 5432
username = "admin"
""")

        # Delete a key
        result = server.data.fn(
            file_path=str(test_file), operation="delete", key_path="database.username"
        )

        # Should succeed
        assert result["success"] is True
        assert result["result"] == "File modified successfully"

        # Read the file and verify
        modified_content = test_file.read_text()
        assert "username" not in modified_content
        assert "host" in modified_content  # Other keys should remain
