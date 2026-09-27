"""The versioned package CLI binds discovery and propagation to one Run."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from auditable_scientist import cli as legacy_cli
from auditable_scientist.cli_v2 import main, replay_run
from auditable_scientist.benchmark.hohmann import HohmannCase
from auditable_scientist.tools.numerical import hohmann_baseline
from auditable_scientist.tools.orbit_audit_v2 import evaluate_orbit_grid


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def combined_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("t1-combined-cli")
    config = directory / "hohmann.json"
    assert main(["init", str(config)]) == 0
    assert main(["run", str(config), "--offline", "--seed", "17",
                 "--output-dir", str(directory / "runs")]) == 0
    runs = list((directory / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def test_package_cli_round_trip_and_claim_boundary(combined_run: Path, tmp_path: Path, capsys) -> None:
    assert main(["replay", str(combined_run)]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["verified"] is True and len(replay["checks"]) == 8
    assert main(["inspect", str(combined_run)]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert inspection["status"] == "completed"
    assert inspection["claims"][0]["status"] == "reproduced"
    assert inspection["claims"][0]["level"] == "validated-reproduction"
    assert inspection["claims"][1]["status"] == "unverified"
    assert inspection["claims"][1]["level"] == "demo"
    assert inspection["numerical"]["relative_tof_error"] < 1e-9
    run = json.loads((combined_run / "run.json").read_text(encoding="utf-8"))
    assert len(run["tools"]) == 2 and len(run["providers"]) == 2
    assert run["policy"]["network"] == "disabled"
    exported = tmp_path / "report.md"
    assert main(["export-report", str(combined_run), "--output", str(exported)]) == 0
    assert exported.read_bytes() == (combined_run / "report.md").read_bytes()


@pytest.mark.parametrize("target", ["numerical", "event", "dataset", "claim", "missing-numerical"])
def test_combined_replay_rejects_tampering(combined_run: Path, tmp_path: Path, target: str) -> None:
    moved = tmp_path / combined_run.name
    shutil.copytree(combined_run, moved)
    if target == "numerical":
        path = moved / "numerical.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["summary"]["relative_tof_error"] = 0.5
        path.write_text(json.dumps(value), encoding="utf-8")
    elif target == "event":
        path = moved / "events.jsonl"
        rows = path.read_text(encoding="utf-8").splitlines()
        changed = json.loads(rows[3])
        changed["payload"]["calls_used"] = 1
        rows[3] = json.dumps(changed)
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elif target == "dataset":
        path = moved / "dataset.json"
        path.write_bytes(path.read_bytes() + b"\n ")
    elif target == "claim":
        path = moved / "run.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["claims"][1]["status"] = "candidate"
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        (moved / "numerical.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        replay_run(moved)
    if target in ("claim", "missing-numerical"):
        assert main(["inspect", str(moved)]) == 2
        assert main(["export-report", str(moved), "--output", str(tmp_path / "forged.md")]) == 2
        assert not (tmp_path / "forged.md").exists()


def test_new_entry_replays_legacy_run(tmp_path: Path, capsys) -> None:
    old_run = legacy_cli._build_run(
        ROOT / "examples/hohmann/run.json", seed=17,
        output_dir=tmp_path / "legacy", offline=True,
    )
    assert main(["replay", str(old_run)]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True


def test_orbit_evaluator_handles_unseen_radius_ratios() -> None:
    mu, r1 = 132_712_440_018.0, 149_597_870.7
    cases = [
        HohmannCase(case_id=f"novel-{index}", split="train" if index == 0 else "holdout",
                    r1_km=r1, r2_km=r1 * ratio, mu_km3_s2=mu,
                    target_tof_days=hohmann_baseline(r1, r1 * ratio, mu).time_of_flight_days)
        for index, ratio in enumerate((1.12, 2.6))
    ]
    result = evaluate_orbit_grid(cases)
    assert result["status"] == "passed-synthetic-two-body"
    assert result["case_count"] == 2
    assert all(result["checks"].values())
