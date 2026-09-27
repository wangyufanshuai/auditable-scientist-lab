from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert run["agent"]["agent_id"] == "offline-bounded-agent-v1"
    assert run["tools"][0]["tool_id"] == "hohmann-benchmark"
    assert run["memories"][0]["memory_id"] == "evidence-policy-memory-v1"
    assert run["evaluators"][0]["evaluator_id"] == "hohmann-holdout-v1"
    assert run["providers"][0]["provider_id"] == "internal-bounded-generator"
    assert run["policy"]["network"] == "disabled"
    assert [event["event_type"] for event in run["events"]] == [
        "run.initialized",
        "plan.created",
        "policy.applied",
        "data.summarized",
        "tool.invoked",
        "candidate_set.committed",
        "holdout.evaluated",
        "calculation.completed",
        "failure.checked",
        "approval.recorded",
        "run.completed",
    ]
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


@pytest.mark.parametrize("target", ["input.json", "experiment.json", "run.json", "events.jsonl", "project05-snapshot.json"])
def test_cli_replay_rejects_tampered_artifact(tmp_path: Path, capsys, target: str) -> None:
    output_root = tmp_path / "runs"
    assert main(["run", "examples/hohmann/run.json", "--offline", "--seed", "17", "--output-dir", str(output_root)]) == 0
    run_dir = Path(capsys.readouterr().out.strip())
    target_path = run_dir / target
    text = target_path.read_text(encoding="utf-8")
    original_text = text
    if target == "events.jsonl":
        text = text.replace("run.initialized", "run.tampered", 1)
    elif target == "input.json":
        text = text.replace('"seed":17', '"seed":18', 1)
    elif target == "experiment.json":
        text = text.replace('"selected_candidate_id":"tof-hohmann-v1"', '"selected_candidate_id":"tampered"', 1)
    elif target == "run.json":
        text = text.replace('"status":"completed"', '"status":"failed"', 1)
    else:
        text = text.replace("project-05-hohmann-v1", "tampered-source-snapshot", 1)
    target_path.write_text(text, encoding="utf-8")
    assert text != original_text
    assert main(["replay", str(run_dir)]) == 2
    assert "error:" in capsys.readouterr().err
