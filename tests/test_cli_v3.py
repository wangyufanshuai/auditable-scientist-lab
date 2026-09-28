"""Historical source routing must preserve replay and reject forged artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from auditable_scientist.cli_v3 import _bundle_manifest, _extract_bundle, _version, main


ROOT = Path(__file__).resolve().parents[1]
OLD_T1 = ROOT / "artifacts/acceptance-runs-v18/run-02a00f229aabd3d2"
OLD_T2 = ROOT / "artifacts/track-runs-v16/run-t2-e8c0533775f1ab69"
OLD_V2 = ROOT / "artifacts/t1-combined-runs-v3/run-t1-v2-bd8e4e217fae77f1"


@pytest.mark.parametrize("run_dir", [OLD_T1, OLD_T2, OLD_V2])
def test_historical_runs_replay_through_router(run_dir: Path, capsys) -> None:
    assert _version(run_dir).startswith("historical-")
    report_before = (run_dir / "report.md").read_bytes()
    assert main(["replay", str(run_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
    assert (run_dir / "report.md").read_bytes() == report_before
    assert main(["inspect", str(run_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == run_dir.name


def test_bundle_is_pinned_to_historical_source_bytes() -> None:
    manifest = _bundle_manifest()
    assert manifest["git_commit"] == "8c26a263ab3584cb0dd809e4a0914f1f34fe3a58"
    assert "src/auditable_scientist/cli.py" in manifest["files"]
    assert "src/auditable_scientist/__main__.py" in manifest["files"]


@pytest.mark.parametrize("target", ["report", "source-route", "missing-numerical"])
def test_historical_router_rejects_tamper_before_export(target: str, tmp_path: Path, capsys) -> None:
    source = OLD_T1 if target != "missing-numerical" else OLD_V2
    run_dir = tmp_path / source.name
    shutil.copytree(source, run_dir)
    if target == "report":
        (run_dir / "report.md").write_text("forged report", encoding="utf-8")
    elif target == "source-route":
        manifest_path = run_dir / "replay-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        from auditable_scientist.runtime.paths import resource_path
        from auditable_scientist.runtime.replay import fingerprint_file
        for item in manifest["source_files"]:
            if item["path"] == "root://pyproject.toml":
                item["sha256"] = fingerprint_file(resource_path("pyproject.toml")).sha256
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        (run_dir / "numerical.json").unlink()
    exported = tmp_path / "forged.md"
    assert main(["export-report", str(run_dir), "--output", str(exported)]) == 2
    assert "error:" in capsys.readouterr().err
    assert not exported.exists()


def test_current_runs_route_without_historical_bundle(tmp_path: Path, capsys) -> None:
    config = tmp_path / "config.json"
    assert main(["init", str(config)]) == 0
    capsys.readouterr()
    assert main(["run", str(config), "--offline", "--output-dir", str(tmp_path / "runs")]) == 0
    run_dir = Path(capsys.readouterr().out.strip())
    assert _version(run_dir) == "current-v2"
    assert main(["replay", str(run_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True

    fixture = tmp_path / "causal.json"
    assert main(["init-track", "T2", str(fixture)]) == 0
    capsys.readouterr()
    assert main(["run-track", "T2", str(fixture), "--output-dir", str(tmp_path / "tracks")]) == 0
    track = Path(capsys.readouterr().out.strip())
    assert _version(track) == "current-cli"
    assert main(["replay", str(track)]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True


def test_historical_installed_layout_replays_from_current_router(tmp_path: Path, capsys) -> None:
    old_runtime = tmp_path / "historical"
    _extract_bundle(old_runtime, installed_layout=True)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(old_runtime / "site")
    config = tmp_path / "old-wheel-config.json"
    for arguments in (["init", str(config)],
                      ["run", str(config), "--offline", "--seed", "17",
                       "--output-dir", str(tmp_path / "old-wheel-runs")]):
        completed = subprocess.run(
            [sys.executable, "-m", "auditable_scientist", *arguments],
            cwd=old_runtime, env=environment, capture_output=True, text=True,
            check=False, timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
    run_dir = Path(completed.stdout.strip())
    assert _version(run_dir) == "historical-v2"
    assert main(["replay", str(run_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
