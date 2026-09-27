"""Check a fresh Windows Python environment against committed replay receipts.

This checks interpreter identity and the exact installed dependency closure. The
normal acceptance verifier separately recomputes all five Run replays.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "requirements-replay-win-py312.txt"
RUNS = {
    "T1": ROOT / "artifacts/acceptance-runs-v17/run-02a00f229aabd3d2/replay-manifest.json",
    "T2": ROOT / "artifacts/track-runs-v11/run-t2-e8c0533775f1ab69/replay-manifest.json",
    "T2P": ROOT / "artifacts/track-runs-v11/run-t2p-0971a9036e84aa5a/replay-manifest.json",
    "T3": ROOT / "artifacts/track-runs-v11/run-t3-1c4eb6b867515637/replay-manifest.json",
    "T3N": ROOT / "artifacts/track-runs-v11/run-t3n-7ea57acea8cc3bb1/replay-manifest.json",
    "T4": ROOT / "artifacts/track-runs-v11/run-t4-6497f62cc5a8ff84/replay-manifest.json",
    "T5": ROOT / "artifacts/track-runs-v11/run-t5-cc6170f111df81a8/replay-manifest.json",
}
BUILD_TOOLS = {"pip", "setuptools", "wheel"}


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pinned_versions() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise ValueError(f"replay constraint is not an exact version: {line}")
        name, version = line.split("==")
        key = normalized(name)
        if not name or not version or key in pins:
            raise ValueError(f"invalid or duplicate replay constraint: {line}")
        pins[key] = version
    if not pins:
        raise ValueError("replay constraint file is empty")
    return pins


def verify() -> dict[str, object]:
    if sys.prefix == sys.base_prefix:
        raise ValueError("replay environment must be an isolated virtual environment")
    actual_platform = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
    }
    if actual_platform != {
        "python": "3.12.3",
        "implementation": "CPython",
        "system": "Windows",
        "machine": "AMD64",
    }:
        raise ValueError(f"replay interpreter differs from recorded platform: {actual_platform}")

    pins = pinned_versions()
    installed = {normalized(dist.metadata["Name"]): dist.version for dist in importlib.metadata.distributions()}
    expected = {**pins, "auditable-scientist-lab": "0.1.0"}
    actual = {name: version for name, version in installed.items() if name not in BUILD_TOOLS}
    if actual != expected:
        missing = {name: version for name, version in expected.items() if actual.get(name) != version}
        extra = {name: version for name, version in actual.items() if name not in expected}
        raise ValueError(f"replay dependency closure changed: missing_or_wrong={missing}, extra={extra}")

    manifests: dict[str, str] = {}
    for track_id, path in RUNS.items():
        raw = path.read_bytes()
        manifest = json.loads(raw)
        recorded = manifest["environment"]
        if manifest["schema_version"] != "replay-manifest-v2":
            raise ValueError(f"{track_id} replay manifest version differs")
        for name, value in actual_platform.items():
            if recorded.get(name) != value:
                raise ValueError(f"{track_id} replay platform differs: {name}")
        for name, version in recorded["packages"].items():
            if installed.get(normalized(name)) != version:
                raise ValueError(f"{track_id} replay package differs: {name}")
        manifests[track_id] = hashlib.sha256(raw).hexdigest()

    return {
        "schema_version": "replay-environment-audit-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "matched-committed-replay-environment",
        "isolated_venv": True,
        "platform": actual_platform,
        "installed_packages": actual,
        "constraints_sha256": hashlib.sha256(CONSTRAINTS.read_bytes()).hexdigest(),
        "manifest_sha256": manifests,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Version pins do not lock downloaded wheel bytes or Python executable bytes.",
            "This audit checks the environment; scripts/verify_acceptance.py checks replay outputs.",
            "The seven committed Runs cover five tracks and two bounded subtracks; they are fixture evidence, not real-world scientific validation or publication approval.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the audit JSON to this path")
    args = parser.parse_args()
    result = verify()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")


if __name__ == "__main__":
    main()
