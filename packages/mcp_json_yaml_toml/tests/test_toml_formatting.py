"""Test that tomlkit preserves comments and formatting."""

from pathlib import Path

import pytest

from mcp_json_yaml_toml import server


@pytest.mark.integration
def test_toml_preserves_comments(tmp_path: Path) -> None:
    """Test that SET operation preserves comments in TOML files."""
    # Create a TOML file with comments
    test_file = tmp_path / "config.toml"
    test_file.write_text("""# Database configuration
[database]
host = "localhost"  # Production host
port = 5432

# Application settings
[app]
name = "myapp"
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

    # Read the file and verify comments are preserved
    modified_content = test_file.read_text()
    assert "# Database configuration" in modified_content
    assert "# Production host" in modified_content
    assert "# Application settings" in modified_content
    assert "username" in modified_content
    assert "admin" in modified_content


@pytest.mark.integration
def test_toml_delete_preserves_comments(tmp_path: Path) -> None:
    """Test that DELETE operation preserves comments in TOML files."""
    test_file = tmp_path / "config.toml"
    test_file.write_text("""# Database configuration
[database]
host = "localhost"
port = 5432  # Default PostgreSQL port
username = "admin"
""")

    # Delete a key
    result = server.data.fn(
        file_path=str(test_file), operation="delete", key_path="database.username"
    )

    # Should succeed
    assert result["success"] is True

    # Read the file and verify comments are preserved
    modified_content = test_file.read_text()
    assert "# Database configuration" in modified_content
    assert "# Default PostgreSQL port" in modified_content
    assert "username" not in modified_content
