"""Resolve source and bundled data in a checkout or an installed wheel."""

from __future__ import annotations

from pathlib import Path
from importlib.metadata import version


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_CHECKOUT_ROOT = PACKAGE_ROOT.parents[1]


def checkout_root() -> Path | None:
    if (_CHECKOUT_ROOT / "pyproject.toml").is_file() and (_CHECKOUT_ROOT / "schemas/run.schema.json").is_file():
        return _CHECKOUT_ROOT
    return None


def project_root() -> Path:
    """Root used for relative evidence references in the current installation."""

    return checkout_root() or PACKAGE_ROOT


def installation_revision() -> str:
    if checkout_root() is not None:
        return "local-working-tree"
    return f"installed-wheel-{version('auditable-scientist-lab')}"


def source_path(relative: str) -> Path:
    prefix = "src/auditable_scientist/"
    if not relative.startswith(prefix):
        raise ValueError(f"not a package source path: {relative}")
    path = PACKAGE_ROOT / relative[len(prefix):]
    if not path.is_file():
        raise FileNotFoundError(f"package source is missing: {relative}")
    return path


def resource_path(relative: str) -> Path:
    """Find canonical checkout data or its byte-identical packaged copy."""

    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"resource path is unsafe: {relative}")
    root = checkout_root()
    path = (root / relative) if root is not None else (PACKAGE_ROOT / "_resources" / relative)
    if not path.is_file():
        raise FileNotFoundError(f"package resource is missing: {relative}")
    return path
