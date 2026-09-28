"""Build the current wheel and replay all bounded tracks outside the checkout."""

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
    "T2P": "physical",
    "T3": "dynamics",
    "T3N": "nbody",
    "T4": "proof",
    "T4O": "oscillator-proof",
    "T5": "protocol",
}
COMMITTED_RUNS = {
    "T1": "acceptance-runs-v18/run-02a00f229aabd3d2",
    "T2": "track-runs-v16/run-t2-e8c0533775f1ab69",
    "T2P": "track-runs-v16/run-t2p-0971a9036e84aa5a",
    "T3": "track-runs-v16/run-t3-1c4eb6b867515637",
    "T3N": "track-runs-v16/run-t3n-7ea57acea8cc3bb1",
    "T4": "track-runs-v16/run-t4-6497f62cc5a8ff84",
    "T4O": "track-runs-v16/run-t4o-1d00e31fd06b3dde",
    "T5": "track-runs-v16/run-t5-beabca5b5d2177aa",
    "T1V2": "t1-combined-runs-v3/run-t1-v2-bd8e4e217fae77f1",
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


def replay(python: Path, run_dir: Path, *, cwd: Path, environment: dict[str, str],
           module: str = "auditable_scientist.cli") -> dict[str, object]:
    result = json.loads(invoke(
        [str(python), "-m", module, "replay", str(run_dir)],
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
        if resource_count < 25:
            raise RuntimeError("wheel omitted an offline resource")
        t2_sensitivity = json.loads(invoke(
            [str(python), "-c",
             "import json; from auditable_scientist.tracks.causal_sensitivity import evaluate_context_sensitivity, load_builtin_cases, candidate_set_hash; e, r = evaluate_context_sensitivity(load_builtin_cases()); print(json.dumps({'status': 'verified-synthetic-context-sensitivity-only' if e.passed else 'failed', 'candidate_set_sha256': candidate_set_hash(), 'baseline_holdout_rmse': e.baseline_holdout_rmse, 'context_leak_holdout_rmse': e.context_leak_holdout_rmse, 'context_leakage_rejected': e.context_leakage_rejected}, sort_keys=True))"],
            cwd=temporary_root, environment=base_environment,
        ))
        if (t2_sensitivity.get("status") != "verified-synthetic-context-sensitivity-only"
                or t2_sensitivity.get("baseline_holdout_rmse") != 0.0
                or t2_sensitivity.get("context_leakage_rejected") is not True
                or t2_sensitivity.get("context_leak_holdout_rmse", 0.0) <= 1.0):
            raise RuntimeError("wheel T2 context sensitivity evaluator differs")
        t3_convergence = json.loads(invoke(
            [str(python), "-c",
             "import json; from auditable_scientist.tracks.convergence import build_receipt; print(json.dumps(build_receipt(), sort_keys=True))"],
            cwd=temporary_root, environment=base_environment,
        ))
        if (t3_convergence.get("schema_version") != "t3-sweep-v1"
                or t3_convergence.get("passed") is not True
                or t3_convergence.get("summary", {}).get("case_count") != 27
                or not all(t3_convergence.get("checks", {}).values())
                or t3_convergence.get("boundaries", {}).get("real_mission_validation") is not False
                or t3_convergence.get("boundaries", {}).get("multi_body_validation") is not False):
            raise RuntimeError("wheel T3 convergence evaluator differs")
        console = venv / "Scripts/auditable-scientist.exe"
        invoke([str(console), "--help"], cwd=temporary_root, environment=base_environment)

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
        invoke([str(python), "-m", "auditable_scientist", "--help"], cwd=temporary_root, environment=base_environment)
        v2_config = temporary_root / "hohmann-v2.json"
        invoke([str(python), "-m", "auditable_scientist", "init", str(v2_config)], cwd=temporary_root, environment=base_environment)
        runs["T1V2"] = Path(invoke(
            [str(python), "-m", "auditable_scientist", "run", str(v2_config), "--offline", "--seed", "17", "--output-dir", str(temporary_root / "runs-v2")],
            cwd=temporary_root, environment=base_environment,
        ))
        invoke([str(python), "-m", "auditable_scientist", "inspect", str(runs["T1V2"])], cwd=temporary_root, environment=base_environment)
        v2_report = temporary_root / "hohmann-v2-report.md"
        invoke([str(python), "-m", "auditable_scientist", "export-report", str(runs["T1V2"]), "--output", str(v2_report)], cwd=temporary_root, environment=base_environment)
        if not v2_report.is_file():
            raise RuntimeError("wheel did not export the combined T1 report")
        v2_run = json.loads((runs["T1V2"] / "run.json").read_text(encoding="utf-8"))
        v2_orbit = json.loads((runs["T1V2"] / "numerical.json").read_text(encoding="utf-8"))
        if (v2_run["status"] != "completed" or len(v2_run["tools"]) != 2
                or len(v2_run["providers"]) != 2
                or [claim["status"] for claim in v2_run["claims"]] != ["reproduced", "unverified"]
                or [claim["level"] for claim in v2_run["claims"]] != ["validated-reproduction", "demo"]
                or v2_run["policy"]["network"] != "disabled"
                or v2_orbit["status"] != "passed-synthetic-two-body"
                or not all(v2_orbit["checks"].values())):
            raise RuntimeError("wheel T1 combined CLI Run or scientific boundary differs")
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
        t4o_result = json.loads((runs["T4O"] / "result.json").read_text(encoding="utf-8"))
        t4o_run = json.loads((runs["T4O"] / "run.json").read_text(encoding="utf-8"))
        if t4o_result["receipt"]["result"]["claim_status"] != "bounded-verified" or t4o_run["claims"][0]["status"] != "unverified":
            raise RuntimeError("wheel T4O proof boundary differs")
        t5_result = json.loads((runs["T5"] / "result.json").read_text(encoding="utf-8"))
        t5_run = json.loads((runs["T5"] / "run.json").read_text(encoding="utf-8"))
        if (t5_result["receipt"]["result"]["review_status"] != "text-reviewed"
                or t5_result["receipt"]["evidence_level"] != "demo"
                or t5_run["claims"][0]["level"] != "demo"
                or t5_run["claims"][0]["status"] != "unverified"):
            raise RuntimeError("wheel T5 text-review boundary differs")

        original = {
            track_id: replay(python, path, cwd=temporary_root, environment=base_environment,
                             module="auditable_scientist" if track_id == "T1V2" else "auditable_scientist.cli")
            for track_id, path in runs.items()
        }
        moved_root = temporary_root / "moved-runs"
        moved_root.mkdir()
        moved: dict[str, dict[str, object]] = {}
        for track_id, path in runs.items():
            destination = moved_root / path.name
            shutil.copytree(path, destination)
            moved[track_id] = replay(
                python, destination, cwd=temporary_root, environment=base_environment,
                module="auditable_scientist" if track_id == "T1V2" else "auditable_scientist.cli",
            )
            if moved[track_id] != original[track_id]:
                raise RuntimeError(f"wheel run changed on relocation: {track_id}")

        historical: dict[str, dict[str, object]] = {}
        for track_id, relative in COMMITTED_RUNS.items():
            source = ROOT / "artifacts" / relative
            destination = temporary_root / "committed" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
            receipt = json.loads(invoke(
                [str(console), "replay", str(destination)],
                cwd=temporary_root, environment=base_environment,
            ))
            if receipt.get("verified") is not True or len(receipt.get("checks", [])) != 8:
                raise RuntimeError(f"installed console did not replay historical {track_id}")
            historical[track_id] = receipt

    result = {
        "schema_version": "wheel-audit-v7",
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
        "t2_context_sensitivity_wheel_replay": t2_sensitivity,
        "t3_convergence_wheel_replay": {
            "schema_version": t3_convergence["schema_version"],
            "case_count": t3_convergence["summary"]["case_count"],
            "checks": t3_convergence["checks"],
            "boundaries": t3_convergence["boundaries"],
        },
        "manifest_schema": "replay-manifest-v2",
        "replay_manifest_hashes": {track_id: receipt["manifest_hash"] for track_id, receipt in original.items()},
        "all_nine_relocated_replays_equal": moved == original,
        "all_nine_committed_console_replays_verified": len(historical) == 9,
        "committed_manifest_hashes": {track_id: receipt["manifest_hash"] for track_id, receipt in historical.items()},
        "t1v2_combined_run_and_unverified_mission_claim": True,
        "t4_bounded_result_and_unverified_run_claim": True,
        "t4o_bounded_result_and_unverified_run_claim": True,
        "t5_demo_text_review_and_unverified_run_claim": True,
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
