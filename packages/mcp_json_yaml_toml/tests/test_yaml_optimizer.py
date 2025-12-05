"""Tests for YAML optimizer module."""

from mcp_json_yaml_toml.yaml_optimizer import (
    assign_anchors,
    find_duplicates,
    get_optimization_stats,
    optimize_yaml,
)


class TestFindDuplicates:
    """Test duplicate structure detection."""

    def test_find_duplicates_simple_dict(self) -> None:
        """Test finding duplicate dict structures."""
        data = {
            "job1": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
            "job2": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
            "job3": {"image": "python:3.11"},
        }

        duplicates = find_duplicates(data)

        # Should find the duplicate job config
        assert len(duplicates) == 1

        # Should have 2 occurrences
        duplicate_group = next(iter(duplicates.values()))
        assert len(duplicate_group) == 2

        # Paths should be job1 and job2
        paths = {path for path, _ in duplicate_group}
        assert paths == {"job1", "job2"}

    def test_find_duplicates_nested(self) -> None:
        """Test finding nested duplicate structures."""
        data = {
            "services": {
                "web": {"image": "nginx", "ports": ["80:80"], "restart": "always"},
                "api": {"image": "nginx", "ports": ["80:80"], "restart": "always"},
            }
        }

        duplicates = find_duplicates(data)

        # Should find duplicate service configs
        assert len(duplicates) >= 1

    def test_find_duplicates_below_threshold(self) -> None:
        """Test that small structures below threshold are not flagged."""
        data = {
            "job1": {"name": "test"},  # Only 1 key, below default threshold of 3
            "job2": {"name": "test"},
        }

        duplicates = find_duplicates(data)

        # Should not find duplicates (below size threshold)
        assert len(duplicates) == 0

    def test_find_duplicates_single_occurrence(self) -> None:
        """Test that single occurrences are not flagged."""
        data = {
            "job1": {"image": "node:22", "cache": {"paths": ["node_modules/"]}},
            "job2": {"image": "python:3.11", "cache": {"paths": ["dist/"]}},
        }

        duplicates = find_duplicates(data)

        # Should not find duplicates (each structure is unique)
        assert len(duplicates) == 0

    def test_find_duplicates_list_structures(self) -> None:
        """Test finding duplicate list structures."""
        data = {
            "workflow1": {
                "steps": ["checkout", "npm install", "npm test"],
                "timeout": "10m",
                "retry": 3,
            },
            "workflow2": {
                "steps": ["checkout", "npm install", "npm test"],
                "timeout": "10m",
                "retry": 3,
            },
        }

        duplicates = find_duplicates(data)

        # Should find duplicate steps list
        assert len(duplicates) >= 1


class TestAssignAnchors:
    """Test anchor name assignment."""

    def test_assign_anchors_simple(self) -> None:
        """Test basic anchor assignment."""
        duplicates = {
            "hash1": [("job1", {"image": "node:22"}), ("job2", {"image": "node:22"})]
        }

        anchors = assign_anchors(duplicates)

        # Should assign anchor to first occurrence
        assert "job1" in anchors
        assert anchors["job1"] == "job1"

    def test_assign_anchors_sanitization(self) -> None:
        """Test anchor name sanitization."""
        duplicates = {
            "hash1": [
                ("jobs.build-prod", {"image": "node:22"}),
                ("jobs.build-dev", {"image": "node:22"}),
            ]
        }

        anchors = assign_anchors(duplicates)

        # Should sanitize the name (replace hyphens)
        first_anchor = anchors.get("jobs.build-prod")
        assert first_anchor is not None
        assert "-" not in first_anchor  # Hyphens should be replaced

    def test_assign_anchors_collision_handling(self) -> None:
        """Test handling of anchor name collisions."""
        duplicates = {
            "hash1": [("config", {"a": 1}), ("other.config", {"a": 1})],
            "hash2": [("another.config", {"b": 2}), ("yet.another.config", {"b": 2})],
        }

        anchors = assign_anchors(duplicates)

        # Should have unique anchor names
        anchor_names = list(anchors.values())
        assert len(anchor_names) == len(set(anchor_names))  # All unique


class TestOptimizeYaml:
    """Test YAML optimization."""

    def test_optimize_yaml_creates_anchors(self) -> None:
        """Test that optimization creates anchors and aliases."""
        data = {
            "default_config": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
            "job1": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
            "job2": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
        }

        result = optimize_yaml(data)

        # Should return optimized YAML
        assert result is not None

        # Should contain anchor syntax
        assert "&" in result  # Anchor marker
        assert "*" in result  # Alias marker

    def test_optimize_yaml_no_duplicates(self) -> None:
        """Test that optimization returns None when no duplicates found."""
        data = {
            "job1": {"image": "node:22", "script": ["npm test"]},
            "job2": {"image": "python:3.11", "script": ["pytest"]},
        }

        result = optimize_yaml(data)

        # Should return None (no optimization needed)
        assert result is None

    def test_optimize_yaml_preserves_data(self) -> None:
        """Test that optimization preserves all data."""
        data = {
            "config": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "env": {"NODE_ENV": "production"},
            },
            "job1": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "env": {"NODE_ENV": "production"},
            },
            "job2": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "env": {"NODE_ENV": "production"},
            },
        }

        result = optimize_yaml(data)

        assert result is not None

        # Parse the result back and verify data is preserved
        from ruamel.yaml import YAML

        yaml = YAML()
        from io import StringIO

        parsed = yaml.load(StringIO(result))

        # Should have all three keys
        assert "config" in parsed
        assert "job1" in parsed
        assert "job2" in parsed


class TestGetOptimizationStats:
    """Test optimization statistics."""

    def test_get_optimization_stats(self) -> None:
        """Test getting optimization statistics."""
        data = {
            "job1": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
            "job2": {
                "image": "node:22",
                "cache": {"paths": ["node_modules/"]},
                "timeout": "30m",
            },
            "job3": {"image": "python:3.11"},
        }

        stats = get_optimization_stats(data)

        # Should report duplicates found
        assert stats["duplicates_found"] >= 1
        assert stats["total_occurrences"] >= 2
        assert len(stats["anchor_names"]) >= 1
        assert len(stats["duplicate_groups"]) >= 1

        # Check duplicate group structure
        first_group = stats["duplicate_groups"][0]
        assert "anchor" in first_group
        assert "occurrences" in first_group
        assert "paths" in first_group
        assert "size" in first_group
        assert first_group["occurrences"] >= 2
