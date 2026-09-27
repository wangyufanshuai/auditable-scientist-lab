"""Replay the current committed-style acceptance runs from a copied checkout.

Run this with the dependency environment recorded in the checked-in manifests.
The temporary checkout intentionally excludes the original example fixtures.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "T1": "acceptance-runs-v16/run-02a00f229aabd3d2",
    "T2": "track-runs-v10/run-t2-e8c0533775f1ab69",
    "T3": "track-runs-v10/run-t3-1c4eb6b867515637",
    "T3N": "track-runs-v10/run-t3n-7ea57acea8cc3bb1",
    "T4": "track-runs-v10/run-t4-6497f62cc5a8ff84",
    "T5": "track-runs-v10/run-t5-cc6170f111df81a8",
}


def _invoke(root: Path, relative: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "auditable_scientist.cli", "replay", str(root / "artifacts" / relative)],
        cwd=root, env=environment, capture_output=True, text=True, timeout=60, check=False,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="scientist-relocation-") as temporary:
        moved = Path(temporary).resolve() / "checkout"
        if not moved.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("temporary checkout escaped the temporary directory")
        moved.mkdir()
        for directory in ("src", "docs", "schemas"):
            shutil.copytree(ROOT / directory, moved / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (moved / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/generate_track_artifacts.py", moved / "scripts/generate_track_artifacts.py")
        shutil.copy2(ROOT / "pyproject.toml", moved / "pyproject.toml")
        for relative in RUNS.values():
            destination = moved / "artifacts" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT / "artifacts" / relative, destination)
        if (moved / "examples").exists():
            raise RuntimeError("copied checkout unexpectedly contains original fixtures")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(moved / "src")
        module_check = subprocess.run(
            [sys.executable, "-c", "import auditable_scientist; print(auditable_scientist.__file__)"],
            cwd=moved, env=environment, capture_output=True, text=True, timeout=30, check=False,
        )
        if module_check.returncode != 0 or not Path(module_check.stdout.strip()).resolve().is_relative_to(moved / "src"):
            raise RuntimeError("replay did not import the copied checkout")
        receipts: dict[str, dict] = {}
        for track_id, relative in RUNS.items():
            outcome = _invoke(moved, relative, environment)
            if outcome.returncode != 0:
                raise RuntimeError(f"{track_id} relocated replay failed: {outcome.stderr.strip()}")
            receipt = json.loads(outcome.stdout)
            if receipt.get("verified") is not True or len(receipt.get("checks", [])) != 8:
                raise RuntimeError(f"{track_id} relocated replay omitted required checks")
            receipts[track_id] = receipt
        t3 = moved / "artifacts" / RUNS["T3"] / "fixture.json"
        t3.write_text("tampered copied fixture", encoding="utf-8")
        tampered = _invoke(moved, RUNS["T3"], environment)
        if tampered.returncode != 2:
            raise RuntimeError("tampered relocated T3 fixture was not rejected")
    result = {
        "schema_version": "relocation-audit-v1",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "verified-in-recorded-environment",
        "copied_checkout": True,
        "original_examples_copied": False,
        "copied_module_imported": True,
        "runs_replayed": receipts,
        "tampered_t3_fixture_rejected": True,
        "limitations": [
            "The copied checkout used the same Python and dependency environment as the recorded runs.",
            "Cross-OS and dependency-version changes were not accepted by this check.",
            "The project-05 upstream source path remains an origin record, not a relocated source audit.",
        ],
    }
    destination = ROOT / "artifacts/relocation-audit.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
