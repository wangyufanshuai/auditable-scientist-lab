"""Build the immutable replay runtime for Runs bound to the 8c26a26 tree.

The bundle is made from Git blobs, not the mutable working tree. It contains
only code and read-only resources needed by the historical offline runners.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "8c26a263ab3584cb0dd809e4a0914f1f34fe3a58"
BUNDLE = ROOT / "src/auditable_scientist/_resources/legacy-runtime-8c26a26.zip"
PREFIXES = ("src/", "docs/", "schemas/", "examples/")
EXTRA = {"pyproject.toml", "scripts/generate_track_artifacts.py"}


def _git(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True,
    ).stdout


def build_bytes() -> bytes:
    paths = sorted(
        path for path in _git("ls-tree", "-r", "--name-only", COMMIT).decode().splitlines()
        if path.startswith(PREFIXES) or path in EXTRA
    )
    if not paths or "pyproject.toml" not in paths or "src/auditable_scientist/cli.py" not in paths:
        raise RuntimeError("historical source inventory is incomplete")
    contents = {path: _git("show", f"{COMMIT}:{path}") for path in paths}
    manifest = {
        "schema_version": "legacy-runtime-bundle-v1",
        "git_commit": COMMIT,
        "purpose": "execute historical Runs against their original source bytes",
        "files": {path: sha256(content).hexdigest() for path, content in contents.items()},
    }
    contents["legacy-runtime.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in sorted(contents.items()):
            entry = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, content, compress_type=ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    expected = build_bytes()
    if arguments.write:
        if BUNDLE.exists() and BUNDLE.read_bytes() != expected:
            raise RuntimeError("refusing to replace a different legacy bundle")
        BUNDLE.write_bytes(expected)
    elif BUNDLE.read_bytes() != expected:
        raise RuntimeError("legacy bundle differs from the pinned Git revision")
    print(json.dumps({"commit": COMMIT, "sha256": sha256(expected).hexdigest(),
                      "bytes": len(expected), "verified": True}, sort_keys=True))


if __name__ == "__main__":
    main()
