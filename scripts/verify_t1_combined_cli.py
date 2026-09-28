"""Accept a versioned T1 CLI Run while preserving historical replay."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from auditable_scientist.cli_v3 import replay_verified_run
from auditable_scientist.runtime.replay import ReplayMismatch


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "artifacts/t1-combined-runs-v3"
AUDIT = ROOT / "artifacts/t1-combined-cli-audit-v4.json"
METHOD = ROOT / "docs/T1_COMBINED_CLI_V2.md"
LEGACY_RUN = ROOT / "artifacts/acceptance-runs-v18/run-02a00f229aabd3d2"
SOURCE_FILES = (
    Path(__file__).resolve(), METHOD,
    ROOT / "src/auditable_scientist/__main__.py",
    ROOT / "src/auditable_scientist/cli_v2.py",
    ROOT / "src/auditable_scientist/cli_v3.py",
    ROOT / "src/auditable_scientist/_resources/legacy-runtime-8c26a26.zip",
    ROOT / "pyproject.toml",
    ROOT / "src/auditable_scientist/tools/orbit_audit_v2.py",
)


def _fingerprint(path: Path) -> dict[str, str | int]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def _invoke(arguments: list[str]) -> str:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "auditable_scientist", *arguments],
        cwd=ROOT, env=environment, capture_output=True, text=True,
        timeout=120, check=False,
    )
    if completed.returncode != 0:
        raise ReplayMismatch(f"T1 v2 CLI command failed: {arguments[0]}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _tamper_rejected(source: Path, *, target: str, temporary: Path) -> bool:
    moved = temporary / f"mutation-{target}" / source.name
    moved.parent.mkdir()
    shutil.copytree(source, moved)
    if target == "numerical":
        path = moved / "numerical.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["summary"]["relative_tof_error"] = 0.5
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif target == "dataset":
        path = moved / "dataset.json"
        path.write_bytes(path.read_bytes() + b"\n ")
    elif target == "event":
        path = moved / "events.jsonl"
        rows = path.read_text(encoding="utf-8").splitlines()
        event = json.loads(rows[3])
        event["payload"]["calls_used"] = 1
        rows[3] = json.dumps(event)
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elif target == "claim":
        path = moved / "run.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claims"][1]["status"] = "candidate"
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif target == "missing_numerical":
        (moved / "numerical.json").unlink()
    else:
        raise ValueError(f"unsupported mutation: {target}")
    try:
        replay_verified_run(moved)
    except (ValueError, FileNotFoundError):
        replay_rejected = True
    else:
        replay_rejected = False
    if target != "missing_numerical":
        return replay_rejected
    try:
        _invoke(["inspect", str(moved)])
    except ReplayMismatch:
        inspect_rejected = True
    else:
        inspect_rejected = False
    forged_export = temporary / "missing-numerical-forged-report.md"
    try:
        _invoke(["export-report", str(moved), "--output", str(forged_export)])
    except ReplayMismatch:
        export_rejected = True
    else:
        export_rejected = False
    return replay_rejected and inspect_rejected and export_rejected and not forged_export.exists()


def build_audit(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    if not run_dir.is_relative_to(RUNS.resolve()) or run_dir.parent != RUNS.resolve():
        raise ReplayMismatch("T1 combined Run is outside its artifact directory")
    original = replay_verified_run(run_dir)
    cli_replay = json.loads(_invoke(["replay", str(run_dir)]))
    inspected = json.loads(_invoke(["inspect", str(run_dir)]))
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    orbit = json.loads((run_dir / "numerical.json").read_text(encoding="utf-8"))
    experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    old_replay = replay_verified_run(LEGACY_RUN)
    with tempfile.TemporaryDirectory(prefix="scientist-t1-combined-audit-") as temporary:
        temporary_root = Path(temporary).resolve()
        if not temporary_root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ReplayMismatch("temporary T1 combined audit escaped the temp directory")
        relocated = temporary_root / run_dir.name
        shutil.copytree(run_dir, relocated)
        moved_replay = replay_verified_run(relocated)
        exported = temporary_root / "exported-report.md"
        _invoke(["export-report", str(run_dir), "--output", str(exported)])
        report_equal = exported.read_bytes() == (run_dir / "report.md").read_bytes()
        mutations = {
            target: _tamper_rejected(run_dir, target=target, temporary=temporary_root)
            for target in ("numerical", "dataset", "event", "claim", "missing_numerical")
        }
    checks = {
        "one_combined_run": run["run_id"] == run_dir.name and len(run["tools"]) == 2
        and len(run["providers"]) == 2,
        "fixed_holdout_passed": experiment["gate"]["passed"] is True,
        "numerical_grid_passed": orbit["status"] == "passed-synthetic-two-body"
        and orbit["case_count"] == 9 and all(orbit["checks"].values()),
        "mission_claim_unverified": [claim["status"] for claim in run["claims"]]
        == ["reproduced", "unverified"] and [claim["level"] for claim in run["claims"]]
        == ["validated-reproduction", "demo"],
        "network_disabled": run["policy"]["network"] == "disabled",
        "cli_replay_equal": cli_replay == original and original["verified"] is True,
        "cli_inspect_bound": inspected["run_id"] == run_dir.name
        and inspected["numerical"] == orbit["summary"],
        "report_export_equal": report_equal,
        "relocated_replay_equal": moved_replay == original,
        "legacy_t1_replay_preserved": old_replay["verified"] is True,
        **{f"{target}_tamper_rejected": value for target, value in mutations.items()},
    }
    return {
        "schema_version": "t1-combined-cli-audit-v4",
        "status": "verified-bounded-combined-cli-run" if all(checks.values()) else "failed",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name,
        "replay": original,
        "legacy_replay": old_replay,
        "checks": checks,
        "source_files": [_fingerprint(path) for path in SOURCE_FILES],
        "boundaries": {
            "package_module_cli_integrated": True,
            "console_script_versioned_router": True,
            "independent_time_propagation": True,
            "independent_orbit_derivation": False,
            "synthetic_fixture_only": True,
            "real_data": False,
            "dated_ephemeris": False,
            "mission_trajectory_validated": False,
            "publication_ready": False,
        },
    }


def _write_run() -> Path:
    existing = list(RUNS.glob("run-t1-v2-*/replay-manifest.json")) if RUNS.is_dir() else []
    if len(existing) == 1:
        return existing[0].parent
    if existing:
        raise ReplayMismatch("T1 combined artifact directory has multiple Runs")
    with tempfile.TemporaryDirectory(prefix="scientist-t1-combined-build-") as temporary:
        temporary_root = Path(temporary).resolve()
        if not temporary_root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ReplayMismatch("temporary T1 combined build escaped the temp directory")
        config = temporary_root / "hohmann.json"
        _invoke(["init", str(config)])
        generated = Path(_invoke([
            "run", str(config), "--offline", "--seed", "17",
            "--output-dir", str(temporary_root / "runs"),
        ])).resolve()
        replay_verified_run(generated)
        destination = RUNS / generated.name
        if destination.exists():
            raise FileExistsError(f"refusing to overwrite existing T1 combined Run: {destination}")
        RUNS.mkdir(parents=True, exist_ok=True)
        shutil.copytree(generated, destination)
        return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write:
        run_dir = _write_run()
        result = build_audit(run_dir)
        if result["status"] != "verified-bounded-combined-cli-run":
            raise ReplayMismatch(f"T1 combined CLI gates failed: {result['checks']}")
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        relative = Path(saved.get("run_path", ""))
        if (relative.parts[:2] != ("artifacts", "t1-combined-runs-v3")
                or len(relative.parts) != 3):
            raise ReplayMismatch("saved T1 combined Run path is unsafe")
        result = build_audit(ROOT / relative)
        recorded_at = saved.pop("recorded_at", None)
        if (not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None
                or result["status"] != "verified-bounded-combined-cli-run" or saved != result):
            raise ReplayMismatch("T1 combined CLI audit differs from recomputation")
    print(json.dumps({"status": result["status"], "run_id": result["run_id"],
                      "checks": result["checks"], "replay": result["replay"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
