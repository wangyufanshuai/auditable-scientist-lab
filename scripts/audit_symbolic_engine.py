"""Read-only source/rights preflight for the optional local symbolic provider."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("E:/86137/myai/symbolic-physics-engine")
OUTPUT = ROOT / "artifacts/symbolic-engine-audit.json"


def file_record(source_root: Path, path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.resolve().is_relative_to(source_root):
        raise ValueError("external source file escapes the audited directory")
    raw = path.read_bytes()
    return {"path": path.relative_to(source_root).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def discover_is_stub(path: Path) -> bool:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "AIFeynmanEngine":
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and method.name == "discover":
                    last = method.body[-1]
                    return isinstance(last, ast.Raise) and isinstance(last.exc, (ast.Name, ast.Call)) and (
                        (isinstance(last.exc, ast.Name) and last.exc.id == "NotImplementedError")
                        or (isinstance(last.exc, ast.Call) and isinstance(last.exc.func, ast.Name) and last.exc.func.id == "NotImplementedError")
                    )
    raise ValueError("AIFeynmanEngine.discover entrypoint was not found")


def audit(source: Path) -> dict[str, object]:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError("symbolic provider directory is missing")
    readme = source / "README.md"
    entrypoint = source / "src/ai_feynman.py"
    if not readme.is_file() or not entrypoint.is_file():
        raise ValueError("symbolic provider README or entrypoint is missing")
    files = sorted(path for path in source.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    records = [file_record(source, path) for path in files]
    licenses = [item["path"] for item in records if Path(str(item["path"])).name.lower().startswith(("license", "licence", "copying"))]
    tracked = subprocess.run(
        ["git", "-C", str(source), "ls-files", "--error-unmatch", "--", "src/ai_feynman.py"],
        capture_output=True, text=True, check=False, timeout=15,
    ).returncode == 0
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False, timeout=15,
    ).stdout.strip() if tracked else None
    stub = discover_is_stub(entrypoint)
    return {
        "schema_version": "external-symbolic-audit-v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_path": source.as_posix(),
        "source_revision": revision,
        "source_tracked_by_parent_git": tracked,
        "entrypoint": "src/ai_feynman.py::AIFeynmanEngine.discover",
        "entrypoint_unconditionally_raises_not_implemented": stub,
        "license_files": licenses,
        "license_status": "missing-scoped-license" if not licenses else "file-present-not-reviewed",
        "source_files": records,
        "adapter_status": "blocked",
        "execution_allowed": False,
        "code_reuse_allowed": False,
        "reasons": [
            *(["entrypoint is an unconditional NotImplementedError stub"] if stub else []),
            *(["source directory is untracked; no scoped commit revision"] if not tracked else []),
            *(["no scoped LICENSE/COPYING file"] if not licenses else []),
        ],
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "boundary": "Read-only metadata inspection; no external source code was imported or copied.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: result[key] for key in ("source_path", "adapter_status", "reasons")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
