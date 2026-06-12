"""Mneno package version helpers for CLI output."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed Mneno package version."""
    try:
        return version("mneno")
    except PackageNotFoundError:
        return "unknown"
