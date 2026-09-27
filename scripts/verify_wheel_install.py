"""Build the current wheel and replay T1-T5 plus T3N outside the checkout."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/wheel-audit.json"
TRACKS = {
    "T2": "causal",
    "T3": "dynamics",
    "T3N": "nbody",
    "T4": "proof",
    "T5": "protocol",
}


def source_snapshot_hash() -> str:
    digest = hashlib.sha256()
    paths = [ROOT / "pyproject.toml", *sorted(
        path for path in (ROOT / "src/auditable_scientist").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )]
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def invoke(command: list[str], *, cwd: Path, environment: dict[str, str], timeout: int = 120) -> str:
    completed = subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True,
        text=True, timeout=timeout, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command[:4])}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def replay(python: Path, run_dir: Path, *, cwd: Path, environment: dict[str, str]) -> dict[str, object]:
    result = json.loads(invoke(
        [str(python), "-m", "auditable_scientist.cli", "replay", str(run_dir)],
        cwd=cwd, environment=environment,
    ))
    if result.get("verified") is not True or len(result.get("checks", [])) != 8:
        raise RuntimeError(f"wheel replay did not verify all eight fields: {run_dir.name}")
    return result


def main() -> None:
    base_environment = os.environ.copy()
    base_environment.pop("PYTHONPATH", None)
    base_environment.pop("PYTHONHOME", None)
    with tempfile.TemporaryDirectory(prefix="scientist-wheel-audit-") as temporary:
        temporary_root = Path(temporary).resolve()
        if not temporary_root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("temporary wheel audit escaped the temporary directory")
        wheel_dir = temporary_root / "wheel"
        wheel_dir.mkdir()
        invoke(
            [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--wheel-dir", str(wheel_dir), "--disable-pip-version-check", "--quiet"],
            cwd=ROOT, environment=base_environment, timeout=180,
        )
        wheels = list(wheel_dir.glob("auditable_scientist_lab-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("wheel build did not produce exactly one project wheel")
        wheel = wheels[0]
        wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()

        venv = temporary_root / "venv"
        invoke([sys.executable, "-m", "venv", str(venv)], cwd=temporary_root, environment=base_environment)
        python = venv / "Scripts/python.exe"
        invoke(
            [str(python), "-m", "pip", "install", str(wheel), "-c", str(ROOT / "requirements-replay-win-py312.txt"), "--disable-pip-version-check", "--quiet"],
            cwd=temporary_root, environment=base_environment, timeout=180,
        )
        invoke([str(python), "-m", "pip", "check", "--disable-pip-version-check"], cwd=temporary_root, environment=base_environment)
        installed_root = invoke(
            [str(python), "-c", "from auditable_scientist.runtime.paths import checkout_root; print(checkout_root())"],
            cwd=temporary_root, environment=base_environment,
        )
        if installed_root != "None":
            raise RuntimeError("installed wheel resolved an unexpected source checkout")
        resource_count = int(invoke(
            [str(python), "-c", "from auditable_scientist.runtime.paths import PACKAGE_ROOT; print(sum(p.is_file() for p in (PACKAGE_ROOT / '_resources').rglob('*')))"],
            cwd=temporary_root, environment=base_environment,
        ))
        if resource_count < 19:
            raise RuntimeError("wheel omitted an offline resource")
        invoke([str(venv / "Scripts/auditable-scientist.exe"), "--help"], cwd=temporary_root, environment=base_environment)

        runs: dict[str, Path] = {}
        config = temporary_root / "hohmann.json"
        invoke([str(python), "-m", "auditable_scientist.cli", "init", str(config)], cwd=temporary_root, environment=base_environment)
        runs["T1"] = Path(invoke(
            [str(python), "-m", "auditable_scientist.cli", "run", str(config), "--offline", "--seed", "17", "--output-dir", str(temporary_root / "runs")],
            cwd=temporary_root, environment=base_environment,
        ))
        invoke([str(python), "-m", "auditable_scientist.cli", "inspect", str(runs["T1"])], cwd=temporary_root, environment=base_environment)
        report = temporary_root / "hohmann-report.md"
        invoke([str(python), "-m", "auditable_scientist.cli", "export-report", str(runs["T1"]), "--output", str(report)], cwd=temporary_root, environment=base_environment)
        if not report.is_file():
            raise RuntimeError("wheel did not export the T1 report")
        for track_id, fixture_name in TRACKS.items():
            fixture = temporary_root / f"{fixture_name}.json"
            invoke([str(python), "-m", "auditable_scientist.cli", "init-track", track_id, str(fixture)], cwd=temporary_root, environment=base_environment)
            runs[track_id] = Path(invoke(
                [str(python), "-m", "auditable_scientist.cli", "run-track", track_id, str(fixture), "--output-dir", str(temporary_root / "track-runs")],
                cwd=temporary_root, environment=base_environment,
            ))
        t4_result = json.loads((runs["T4"] / "result.json").read_text(encoding="utf-8"))
        t4_run = json.loads((runs["T4"] / "run.json").read_text(encoding="utf-8"))
        if t4_result["receipt"]["result"]["claim_status"] != "bounded-verified" or t4_run["claims"][0]["status"] != "unverified":
            raise RuntimeError("wheel T4 proof boundary differs")

        original = {track_id: replay(python, path, cwd=temporary_root, environment=base_environment) for track_id, path in runs.items()}
        moved_root = temporary_root / "moved-runs"
        moved_root.mkdir()
        moved: dict[str, dict[str, object]] = {}
        for track_id, path in runs.items():
            destination = moved_root / path.name
            shutil.copytree(path, destination)
            moved[track_id] = replay(python, destination, cwd=temporary_root, environment=base_environment)
            if moved[track_id] != original[track_id]:
                raise RuntimeError(f"wheel run changed on relocation: {track_id}")

    result = {
        "schema_version": "wheel-audit-v2",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "verified-within-offline-fixtures",
        "build_command": "python -m pip wheel . --no-deps --wheel-dir <temporary-directory>",
        "wheel_filename": wheel.name,
        "wheel_sha256": wheel_hash,
        "source_snapshot_sha256": source_snapshot_hash(),
        "wheel_artifact_committed": False,
        "python": platform.python_version(),
        "checkout_root_in_installed_process": None,
        "bundled_resource_count": resource_count,
        "manifest_schema": "replay-manifest-v2",
        "replay_manifest_hashes": {track_id: receipt["manifest_hash"] for track_id, receipt in original.items()},
        "all_six_relocated_replays_equal": moved == original,
        "t4_bounded_result_and_unverified_run_claim": True,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "boundaries": {
            "scientific_validity": False,
            "real_data": False,
            "research_candidate": False,
            "publication_ready": False,
            "public_release": False,
        },
        "limitations": [
            "The audited wheel was built and installed in a temporary directory; it is not committed.",
            "The runtime CLI tests used only bundled offline fixtures and the same installed wheel environment.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
