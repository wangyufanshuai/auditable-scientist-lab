from __future__ import annotations

import json
from pathlib import Path

from auditable_scientist.cli import main


def test_cli_hohmann_offline_vertical_slice(tmp_path: Path, capsys) -> None:
    # The test name is kept ASCII-only so source parsing remains portable.
    output_root = tmp_path / "runs"
    assert main(["run", "examples/hohmann/run.json", "--offline", "--seed", "17", "--output-dir", str(output_root)]) == 0
    run_dir = Path(capsys.readouterr().out.strip())
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "replay-manifest.json").is_file()
    study = json.loads((run_dir / "study.json").read_text(encoding="utf-8"))
    assert study["research_question"]["question_id"] == "rq-hohmann-time-of-flight-v1"
    assert study["hypothesis"]["status"] == "reproduced"
    assert study["experiment_plan"]["holdout_split"] == "holdout"
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "completed"
    assert run["claims"][0]["status"] == "reproduced"
    assert main(["replay", str(run_dir)]) == 0
    replay_output = capsys.readouterr().out
    assert '"verified": true' in replay_output
    report_path = tmp_path / "report.md"
    assert main(["export-report", str(run_dir), "--output", str(report_path)]) == 0
    capsys.readouterr()
    assert "Holdout gate" in report_path.read_text(encoding="utf-8")


def test_cli_init_refuses_overwrite(tmp_path: Path, capsys) -> None:
    path = tmp_path / "config.json"
    assert main(["init", str(path)]) == 0
    capsys.readouterr()
    assert main(["init", str(path)]) == 2
    capsys.readouterr()
