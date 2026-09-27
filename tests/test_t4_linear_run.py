"""Portable replay and mutation checks for the optional T4 exact proof Run."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest
from pydantic import ValidationError

from auditable_scientist.runtime.event_log import EventLogError
from auditable_scientist.runtime.replay import ReplayMismatch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_t4_linear_run import AUDIT, RUNS, input_payload, replay_run, verify_policy_denials  # noqa: E402


def _run_dir() -> Path:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    return RUNS / audit["run_id"]


def test_exact_proof_run_replays_from_a_moved_directory(tmp_path: Path) -> None:
    source = _run_dir()
    moved = tmp_path / source.name
    shutil.copytree(source, moved)
    assert replay_run(source) == replay_run(moved)
    run = json.loads((moved / "run.json").read_text(encoding="utf-8"))
    assert run["claims"][0]["status"] == "unverified"
    assert run["policy"]["network"] == "disabled"
    assert len([event for event in run["events"] if event["event_type"] == "tool.invoked"]) == 1
    assert verify_policy_denials(input_payload(), source / "fixture.json") == {
        "wrong_provider_rejected": True, "out_of_scope_path_rejected": True,
    }


@pytest.mark.parametrize("filename,error_type", [
    ("events.jsonl", EventLogError),
    ("run.json", json.JSONDecodeError),
    ("report.md", ReplayMismatch),
    ("replay-manifest.json", ValidationError),
])
def test_exact_proof_run_rejects_tampered_record(tmp_path: Path, filename: str, error_type: type[Exception]) -> None:
    source = _run_dir()
    moved = tmp_path / source.name
    shutil.copytree(source, moved)
    target = moved / filename
    target.write_bytes(target.read_bytes() + b"\nchanged\n")
    with pytest.raises(error_type):
        replay_run(moved)
