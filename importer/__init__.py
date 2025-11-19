"""Importer package for dbt Cloud account migration tooling."""

from importlib import resources


def get_version() -> str:
    """Return the semantic version for the importer from importer/VERSION."""
    version_path = resources.files(__package__).joinpath("VERSION")
    return version_path.read_text(encoding="utf-8").strip()


__all__ = ["get_version"]

