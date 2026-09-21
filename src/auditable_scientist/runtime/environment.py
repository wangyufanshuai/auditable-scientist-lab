"""Small, deterministic-enough environment receipt for a Run."""

from __future__ import annotations

import importlib.metadata
import platform
import sys
from typing import Iterable


def capture_environment(packages: Iterable[str] = ()) -> dict[str, object]:
    """Capture runtime identifiers without reading credentials or user data."""

    versions: dict[str, str | None] = {}
    for package in sorted(set(packages)):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": versions,
    }
