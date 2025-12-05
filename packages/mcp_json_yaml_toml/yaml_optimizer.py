"""YAML anchor optimization module.

This module provides functionality to detect duplicate structures in YAML data
and optimize them using anchors and aliases to maintain DRY principles.
"""

import hashlib
import os
from collections import defaultdict
from typing import Any

import orjson
from ruamel.yaml import YAML

# Configuration from environment variables
YAML_ANCHOR_MIN_SIZE = int(os.getenv("YAML_ANCHOR_MIN_SIZE", "3"))
YAML_ANCHOR_MIN_DUPLICATES = int(os.getenv("YAML_ANCHOR_MIN_DUPLICATES", "2"))
YAML_ANCHOR_OPTIMIZATION = (
    os.getenv("YAML_ANCHOR_OPTIMIZATION", "true").lower() == "true"
)


def _compute_structure_hash(value: Any) -> str | None:
    """Compute a hash for a data structure.

    Args:
        value: The value to hash (dict, list, or primitive)

    Returns:
        Hash string if value is a dict or list, None otherwise
    """
    if not isinstance(value, dict | list):
        return None

    # For dicts and lists, create a stable JSON representation
    try:
        # Sort keys for dicts to ensure consistent hashing
        # orjson produces compact output by default (equivalent to separators=(",", ":"))
        json_bytes = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
        return hashlib.sha256(json_bytes).hexdigest()
    except (TypeError, ValueError, orjson.JSONEncodeError):
        # Can't hash this structure (e.g., contains non-serializable objects)
        return None


def _get_structure_size(value: Any) -> int:
    """Get the size of a structure for threshold checking.

    Args:
        value: The value to measure

    Returns:
        Number of keys (for dict) or items (for list), 0 for primitives
    """
    if isinstance(value, (dict, list)):
        return len(value)
    return 0


def _traverse_structure(data: Any, path: str = "") -> list[tuple[str, Any, str | None]]:
    """Traverse a data structure and collect all nodes with their paths and hashes.

    Args:
        data: The data structure to traverse
        path: Current path in dot notation (e.g., "jobs.build")

    Returns:
        List of (path, value, hash) tuples for all nodes
    """
    nodes: list[tuple[str, Any, str | None]] = []

    if isinstance(data, dict):
        # Add this dict node
        struct_hash = _compute_structure_hash(data)
        nodes.append((path or ".", data, struct_hash))

        # Traverse children
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            nodes.extend(_traverse_structure(value, child_path))

    elif isinstance(data, list):
        # Add this list node
        struct_hash = _compute_structure_hash(data)
        nodes.append((path or ".", data, struct_hash))

        # Traverse children
        for i, item in enumerate(data):
            child_path = f"{path}[{i}]"
            nodes.extend(_traverse_structure(item, child_path))

    return nodes


def find_duplicates(data: Any) -> dict[str, list[tuple[str, Any]]]:
    """Find duplicate structures in YAML data.

    Args:
        data: The parsed YAML data structure

    Returns:
        Dict mapping structure hash -> list of (path, value) tuples
        Only includes hashes with 2+ occurrences that meet size threshold
    """
    # Traverse and collect all nodes
    nodes = _traverse_structure(data)

    # Group by hash
    hash_groups: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for path, value, struct_hash in nodes:
        if struct_hash is not None:
            hash_groups[struct_hash].append((path, value))

    # Filter to only duplicates that meet thresholds
    duplicates: dict[str, list[tuple[str, Any]]] = {}
    for struct_hash, occurrences in hash_groups.items():
        if len(occurrences) < YAML_ANCHOR_MIN_DUPLICATES:
            continue

        # Check size threshold (use first occurrence as representative)
        _, first_value = occurrences[0]
        if _get_structure_size(first_value) < YAML_ANCHOR_MIN_SIZE:
            continue

        duplicates[struct_hash] = occurrences

    return duplicates


def _sanitize_anchor_name(name: str) -> str:
    """Sanitize a string to be a valid YAML anchor name.

    Args:
        name: The proposed anchor name

    Returns:
        Sanitized anchor name (alphanumeric + underscore)
    """
    # Replace invalid characters with underscores
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

    # Ensure it starts with a letter
    if sanitized and not sanitized[0].isalpha():
        sanitized = "anchor_" + sanitized

    # Ensure it's not empty
    if not sanitized:
        sanitized = "anchor"

    return sanitized


def assign_anchors(duplicates: dict[str, list[tuple[str, Any]]]) -> dict[str, str]:
    """Assign anchor names to duplicate structures.

    Args:
        duplicates: Dict from find_duplicates() mapping hash -> occurrences

    Returns:
        Dict mapping path -> anchor_name
        First occurrence gets anchor name, others get None (will use alias)
    """
    path_to_anchor: dict[str, str] = {}
    used_names: set[str] = set()

    for occurrences in duplicates.values():
        # Get anchor name from first occurrence's path
        first_path, _ = occurrences[0]

        # Extract a meaningful name from the path
        # E.g., "jobs.build" -> "build", "default_config" -> "default_config"
        path_parts = first_path.replace("[", ".").replace("]", "").split(".")
        base_name = path_parts[-1] if path_parts[-1] != "." else "config"
        base_name = _sanitize_anchor_name(base_name)

        # Handle name collisions
        anchor_name = base_name
        counter = 1
        while anchor_name in used_names:
            anchor_name = f"{base_name}_{counter}"
            counter += 1

        used_names.add(anchor_name)

        # Assign anchor to first occurrence
        path_to_anchor[first_path] = anchor_name

    return path_to_anchor


def _replace_duplicates_recursive(
    obj: Any, hash_to_shared: dict[str, Any], current_path: str = ""
) -> Any:
    """Recursively replace duplicate structures with shared objects.

    Args:
        obj: The object to process
        hash_to_shared: Map of structure hash to shared object
        current_path: Current path in the structure (for debugging)

    Returns:
        The object with duplicates replaced by shared objects
    """
    # Compute hash for this object
    obj_hash = _compute_structure_hash(obj)

    # If this object is a duplicate, replace with shared object
    if obj_hash and obj_hash in hash_to_shared:
        return hash_to_shared[obj_hash]

    # Otherwise, recurse into children
    if isinstance(obj, dict):
        result: dict[Any, Any] = {}
        for key, value in obj.items():
            child_path = f"{current_path}.{key}" if current_path else key
            result[key] = _replace_duplicates_recursive(
                value, hash_to_shared, child_path
            )
        return result
    if isinstance(obj, list):
        result_list: list[Any] = []
        for i, item in enumerate(obj):
            child_path = f"{current_path}[{i}]"
            result_list.append(
                _replace_duplicates_recursive(item, hash_to_shared, child_path)
            )
        return result_list
    return obj


def _build_shared_objects(
    duplicates: dict[str, list[tuple[str, Any]]], path_to_anchor: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build shared objects for duplicate structures.

    Args:
        duplicates: Dict from find_duplicates()
        path_to_anchor: Dict mapping path to anchor name

    Returns:
        Tuple of (hash_to_shared, shared_objects_map)
    """
    hash_to_shared: dict[str, Any] = {}
    shared_objects_map: dict[str, Any] = {}

    for struct_hash, occurrences in duplicates.items():
        first_path, first_value = occurrences[0]
        anchor_name = path_to_anchor.get(first_path)

        if anchor_name:
            # Create a shallow copy as the shared object
            shared_obj: Any
            if isinstance(first_value, dict):
                shared_obj = dict(first_value)
            elif isinstance(first_value, list):
                shared_obj = list(first_value)
            else:
                shared_obj = first_value

            hash_to_shared[struct_hash] = shared_obj
            shared_objects_map[anchor_name] = shared_obj

    return hash_to_shared, shared_objects_map


def _create_shared_objects(
    data: Any, duplicates: dict[str, list[tuple[str, Any]]]
) -> tuple[Any, dict[str, Any]]:
    """Create shared Python objects for duplicate structures.

    This is the key to making ruamel.yaml generate anchors: we need to use
    the exact same Python object (by identity) for all duplicate occurrences.

    Args:
        data: The original data structure
        duplicates: Dict from find_duplicates()

    Returns:
        Tuple of (modified_data, shared_objects_map)
        where shared_objects_map is {anchor_name: shared_object}
    """
    # Assign anchors
    path_to_anchor = assign_anchors(duplicates)

    # Build shared objects for each duplicate group
    hash_to_shared, shared_objects_map = _build_shared_objects(
        duplicates, path_to_anchor
    )

    # Traverse the data and replace duplicates with shared objects
    modified_data = _replace_duplicates_recursive(data, hash_to_shared)
    return modified_data, shared_objects_map


def optimize_yaml(data: Any) -> str | None:
    """Optimize YAML data by detecting duplicates and creating anchors.

    Args:
        data: Parsed YAML data structure (dict, list, or primitive)

    Returns:
        Optimized YAML string with anchors/aliases, or None if no optimization needed
    """
    if not YAML_ANCHOR_OPTIMIZATION:
        return None

    # Find duplicates
    duplicates = find_duplicates(data)

    if not duplicates:
        # No duplicates found, no optimization needed
        return None

    # Create shared objects
    modified_data, _shared_objects = _create_shared_objects(data, duplicates)

    # Use ruamel.yaml to dump with anchors
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.width = 4096  # Avoid line wrapping

    from io import StringIO

    stream = StringIO()
    yaml.dump(modified_data, stream)
    return stream.getvalue()


def optimize_yaml_file(data: Any) -> str | None:
    """Main entry point for optimizing YAML data.

    This is the function that should be called from server.py.

    Args:
        data: Parsed YAML data structure

    Returns:
        Optimized YAML string, or None if no optimization was performed
    """
    return optimize_yaml(data)


def get_optimization_stats(data: Any) -> dict[str, Any]:
    """Get statistics about potential optimizations without applying them.

    Useful for debugging and testing.

    Args:
        data: Parsed YAML data structure

    Returns:
        Dict with statistics about duplicates found
    """
    duplicates = find_duplicates(data)
    path_to_anchor = assign_anchors(duplicates)

    return {
        "duplicates_found": len(duplicates),
        "total_occurrences": sum(
            len(occurrences) for occurrences in duplicates.values()
        ),
        "anchor_names": list(path_to_anchor.values()),
        "duplicate_groups": [
            {
                "anchor": path_to_anchor.get(occurrences[0][0]),
                "occurrences": len(occurrences),
                "paths": [path for path, _ in occurrences],
                "size": _get_structure_size(occurrences[0][1]),
            }
            for occurrences in duplicates.values()
        ],
    }
