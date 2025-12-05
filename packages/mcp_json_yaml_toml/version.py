# /// script
# List dependencies for linting only
# dependencies = [
#   "hatchling>=1.14.0",
# ]
# ///
"""Compute the version number and store it in the `__version__` variable.

Based on <https://github.com/maresb/hatch-vcs-footgun-example>.
"""

import pathlib


def _get_hatch_version() -> str | None:
    """Compute the most up-to-date version number in a development environment.

    For more details, see <https://github.com/maresb/hatch-vcs-footgun-example/>.

    Returns:
        Version string if Hatchling is installed, None otherwise (e.g., in production).
    """
    try:
        from hatchling.metadata.core import ProjectMetadata
        from hatchling.plugin.manager import PluginManager
        from hatchling.utils.fs import locate_file
    except ImportError:
        # Hatchling is not installed, so probably we are not in
        # a development environment.
        return None

    pyproject_toml = locate_file(__file__, "pyproject.toml")
    if pyproject_toml is None:
        raise RuntimeError("pyproject.toml not found although hatchling is installed")
    root = pathlib.Path(pyproject_toml).parent
    metadata = ProjectMetadata(root=str(root), plugin_manager=PluginManager())
    # Version can be either statically set in pyproject.toml or computed dynamically:
    return str(metadata.core.version or metadata.hatch.version.cached)


def _get_importlib_metadata_version() -> str:
    """Compute the version number using importlib.metadata.

    This is the official Pythonic way to get the version number of an installed
    package. However, it is only updated when a package is installed. Thus, if a
    package is installed in editable mode, and a different version is checked out,
    then the version number will not be updated.

    Returns:
        Version string from package metadata.
    """
    from importlib.metadata import version

    return version(__package__ or __name__)


__version__ = _get_hatch_version() or _get_importlib_metadata_version()
