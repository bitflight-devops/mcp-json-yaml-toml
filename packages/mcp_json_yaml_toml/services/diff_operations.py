"""Diff operations business logic for the data_diff tool.

Wraps DeepDiff to provide structured comparison of configuration data
with human-readable summaries and statistics.
"""

from __future__ import annotations

from typing import Any

from deepdiff import DeepDiff

__all__ = ["build_diff_statistics", "build_diff_summary", "compute_diff"]

# DeepDiff change types we track in statistics
_CHANGE_TYPES = (
    "values_changed",
    "dictionary_item_added",
    "dictionary_item_removed",
    "iterable_item_added",
    "iterable_item_removed",
    "type_changes",
)

# Human-readable labels for each change type
_CHANGE_LABELS: dict[str, str] = {
    "values_changed": "values changed",
    "dictionary_item_added": "items added",
    "dictionary_item_removed": "items removed",
    "iterable_item_added": "list items added",
    "iterable_item_removed": "list items removed",
    "type_changes": "type changes",
}


def compute_diff(
    data1: Any, data2: Any, *, ignore_order: bool = False
) -> dict[str, Any]:
    """Compute structured diff between two data structures.

    Args:
        data1: First (base) data structure.
        data2: Second (comparison) data structure.
        ignore_order: If True, ignore list/array ordering.

    Returns:
        DeepDiff result as a plain dict (via ``to_dict()``).
        Empty dict when data is identical.
    """
    diff = DeepDiff(data1, data2, verbose_level=2, ignore_order=ignore_order)
    return dict(diff.to_dict()) if diff else {}


def build_diff_statistics(diff_dict: dict[str, Any]) -> dict[str, int]:
    """Count changes by type from a DeepDiff dict.

    Args:
        diff_dict: Output of ``compute_diff`` (or ``DeepDiff.to_dict()``).

    Returns:
        Mapping of change type to count.  Only types with non-zero counts
        are included.
    """
    stats: dict[str, int] = {}
    for change_type in _CHANGE_TYPES:
        if change_type in diff_dict:
            value = diff_dict[change_type]
            count = len(value) if isinstance(value, dict) else 1
            stats[change_type] = count
    return stats


def build_diff_summary(stats: dict[str, int], *, has_differences: bool) -> str:
    """Produce a human-readable one-line summary of diff statistics.

    Args:
        stats: Output of ``build_diff_statistics``.
        has_differences: Whether the diff found any changes.

    Returns:
        Summary string, e.g. "3 values changed, 1 item added, 2 items removed"
        or "Files are identical" when no differences exist.
    """
    if not has_differences:
        return "Files are identical"

    parts: list[str] = []
    for change_type in _CHANGE_TYPES:
        if change_type in stats:
            count = stats[change_type]
            label = _CHANGE_LABELS.get(change_type, change_type)
            parts.append(f"{count} {label}")

    return ", ".join(parts) if parts else "Differences detected"
