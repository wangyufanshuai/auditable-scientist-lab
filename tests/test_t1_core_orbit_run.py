"""Versioned T1 numerical Run replay and mutation behavior."""

import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_t1_core_orbit_run import (  # noqa: E402
    AUDIT, FIXTURE, input_payload, replay_run, verify_policy_denials,
)


def _run_path() -> Path:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    return ROOT / audit["run_path"]


def test_versioned_numerical_run_replays_after_relocation(tmp_path: Path) -> None:
    source = _run_path()
    moved = tmp_path / source.name
    shutil.copytree(source, moved)
    assert replay_run(moved) == replay_run(source)
    assert len(replay_run(moved)["checks"]) == 8


def test_event_chain_tamper_fails_replay(tmp_path: Path) -> None:
    source = _run_path()
    moved = tmp_path / source.name
    shutil.copytree(source, moved)
    event_path = moved / "events.jsonl"
    events = event_path.read_text(encoding="utf-8").splitlines()
    changed = json.loads(events[2])
    changed["payload"]["calls_used"] = 2
    events[2] = json.dumps(changed)
    event_path.write_text("\n".join(events) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        replay_run(moved)


def test_policy_rejects_undeclared_provider_and_path() -> None:
    assert verify_policy_denials(input_payload(), FIXTURE) == {
        "wrong_provider_rejected": True,
        "out_of_scope_path_rejected": True,
    }
