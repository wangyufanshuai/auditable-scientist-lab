"""End-to-end evidence that each bounded track executes and replays through the CLI."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from auditable_scientist.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "T2": "examples/causal/fixture.json",
    "T2P": "examples/causal/physical-fixture.json",
    "T3": "examples/dynamics/fixture.json",
    "T3N": "examples/dynamics/nbody-fixture.json",
    "T4": "examples/proof/fixture.json",
    "T4O": "examples/proof/oscillator-fixture.json",
    "T5": "examples/protocol/fixture.json",
}


@pytest.mark.parametrize("track_id", FIXTURES)
def test_init_track_copies_bundled_fixture_without_overwrite(track_id: str, tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "fixture.json"
    assert main(["init-track", track_id, str(fixture)]) == 0
    capsys.readouterr()
    assert json.loads(fixture.read_text(encoding="utf-8")) == json.loads((ROOT / FIXTURES[track_id]).read_text(encoding="utf-8"))
    assert main(["init-track", track_id, str(fixture)]) == 2
    assert "refusing to overwrite" in capsys.readouterr().err


@pytest.mark.parametrize("track_id", FIXTURES)
def test_bounded_track_cli_run_replay_and_inspect(track_id: str, tmp_path: Path, capsys) -> None:
    assert main(["run-track", track_id, str(ROOT / FIXTURES[track_id]), "--output-dir", str(tmp_path)]) == 0
    run_dir = Path(capsys.readouterr().out.strip())
    assert all(bytes([13, 10]) not in path.read_bytes() for path in run_dir.iterdir() if path.is_file())
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["policy"]["network"] == "disabled"
    assert run["environment"]["network"] == "disabled"
    assert {"auditable-scientist-lab", "pydantic", "sympy", "jsonschema"}.issubset(run["environment"]["packages"])
    assert run["claims"][0]["status"] == "unverified"
    if track_id == "T5":
        assert run["claims"][0]["level"] == "demo"
    assert [event["event_type"] for event in run["events"]] == [
        "run.initialized", "policy.applied", "tool.invoked", "evaluator.completed",
        "negative_case.checked", "run.completed",
    ]
    assert run["events"][2]["payload"]["calls_used"] == 1
    assert main(["replay", str(run_dir)]) == 0
    assert '"verified": true' in capsys.readouterr().out
    assert main(["inspect", str(run_dir)]) == 0
    assert f'"track_id": "{track_id}"' in capsys.readouterr().out
    report = tmp_path / "copy.md"
    assert main(["export-report", str(run_dir), "--output", str(report)]) == 0
    assert "Real-data, research-candidate, and publication claims: `false`" in report.read_text(encoding="utf-8")


@pytest.mark.parametrize("tamper", ["result", "event", "fixture", "environment"])
def test_track_replay_rejects_tampering(tamper: str, tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "fixture.json"
    shutil.copy2(ROOT / FIXTURES["T2"], fixture)
    assert main(["run-track", "T2", str(fixture), "--output-dir", str(tmp_path / "runs")]) == 0
    run_dir = Path(capsys.readouterr().out.strip())
    target = {"result": run_dir / "result.json", "event": run_dir / "events.jsonl", "fixture": run_dir / "fixture.json", "environment": run_dir / "run.json"}[tamper]
    original = target.read_text(encoding="utf-8")
    changed = {
        "result": original.replace('"coefficient":2.0', '"coefficient":9.0', 1),
        "event": original.replace("tool.invoked", "tool.hidden", 1),
        "fixture": original.replace('"expected_outcome": 7.0', '"expected_outcome": 9.0', 1),
        "environment": original.replace('"network":"disabled"', '"network":"enabled"', 1),
    }[tamper]
    assert changed != original
    target.write_text(changed, encoding="utf-8")
    assert main(["replay", str(run_dir)]) == 2
    assert "error:" in capsys.readouterr().err


def test_track_replay_uses_snapshotted_fixture_after_origin_changes(tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "origin.json"
    shutil.copy2(ROOT / FIXTURES["T2"], fixture)
    assert main(["run-track", "T2", str(fixture), "--output-dir", str(tmp_path / "runs")]) == 0
    run_dir = Path(capsys.readouterr().out.strip())
    fixture.write_text("origin changed after run", encoding="utf-8")
    assert main(["replay", str(run_dir)]) == 0
    assert '"verified": true' in capsys.readouterr().out
