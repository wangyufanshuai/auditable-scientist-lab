"""The package metadata must match the interpreter features used by source."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_python_floor_covers_enum_strenum_and_bundled_metadata() -> None:
    project = (ROOT / "pyproject.toml").read_bytes()
    bundled = (ROOT / "src/auditable_scientist/_resources/pyproject.toml").read_bytes()
    assert project == bundled
    metadata = tomllib.loads(project.decode("utf-8"))["project"]
    assert metadata["requires-python"] == ">=3.11"
    imports_strenum = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "enum"
        and any(alias.name == "StrEnum" for alias in node.names)
        for source in (ROOT / "src/auditable_scientist").rglob("*.py")
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
    )
    assert imports_strenum
