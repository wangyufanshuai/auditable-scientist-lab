from __future__ import annotations

from datetime import datetime, timezone
import shutil

import pytest

from auditable_scientist.runtime import BoundPaths, EventLog, EventLogError, ReplayManifest, ReplayMismatch, canonical_hash


def test_canonical_hash_ignores_mapping_order() -> None:
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


def test_event_log_appends_and_verifies_hash_chain(tmp_path) -> None:
    log = EventLog(tmp_path / "events.jsonl")
    first = log.append(
        "input",
        {"question": "Hohmann"},
        event_id="event-0",
        occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
    second = log.append(
        "result",
        {"rmse": 0.0},
        event_id="event-1",
        occurred_at=datetime(2026, 9, 20, 0, 0, 1, tzinfo=timezone.utc),
    )
    assert first.prev_event_hash == "genesis"
    assert second.prev_event_hash == first.payload_hash
    assert [item.seq for item in log.verify()] == [0, 1]


def test_event_log_rejects_payload_tampering(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.append("input", {"question": "Hohmann"}, event_id="event-0")
    text = path.read_text(encoding="utf-8").replace("Hohmann", "tampered")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(EventLogError, match="payload hash mismatch"):
        log.verify()
    with pytest.raises(EventLogError):
        log.append("blocked", {"reason": "log was already tampered"})


def test_replay_manifest_verifies_and_detects_source_input_and_output_changes(tmp_path) -> None:
    source = tmp_path / "source.py"
    evidence = tmp_path / "holdout.json"
    source.write_text("return 1\n", encoding="utf-8")
    evidence.write_text('{"rmse": 0.0}\n', encoding="utf-8")
    input_payload = {"r1": 1.0, "r2": 1.5, "mu": 2.0}
    manifest = ReplayManifest.create(
        input_payload=input_payload,
        code_revision="snapshot-1",
        environment={"python": "3.12.3"},
        seed=17,
        source_paths=[source],
        evidence_paths=[evidence],
        candidate_order=["c2", "c1"],
        computational_output={"tof": 4.2},
    )
    manifest_path = manifest.write(tmp_path / "replay.json")
    loaded = ReplayManifest.load(manifest_path)
    receipt = loaded.verify(
        input_payload=input_payload,
        code_revision="snapshot-1",
        environment={"python": "3.12.3"},
        seed=17,
        source_paths=[source],
        evidence_paths=[evidence],
        candidate_order=["c2", "c1"],
        computational_output={"tof": 4.2},
    )
    assert receipt.verified is True
    assert set(receipt.checks) == {
        "input_hash",
        "code_revision",
        "environment",
        "seed",
        "source_files",
        "evidence_files",
        "candidate_order",
        "computational_output",
    }
    source.write_text("return 999\n", encoding="utf-8")
    with pytest.raises(ReplayMismatch, match="source file snapshot changed"):
        loaded.verify(source_paths=[source])
    with pytest.raises(ReplayMismatch, match="input hash changed"):
        loaded.verify(input_payload={"r1": 2.0})
    with pytest.raises(ReplayMismatch, match="computational output changed"):
        loaded.verify(computational_output={"tof": 999.0})
    with pytest.raises(ReplayMismatch, match="code revision changed"):
        loaded.verify(code_revision="snapshot-2")
    with pytest.raises(ReplayMismatch, match="runtime environment changed"):
        loaded.verify(environment={"python": "other"})
    with pytest.raises(ReplayMismatch, match="random seed changed"):
        loaded.verify(seed=18)


def test_bound_manifest_replays_after_relocation_and_rejects_escaping_references(tmp_path) -> None:
    original = tmp_path / "original"
    relocated = tmp_path / "relocated"
    (original / "runs").mkdir(parents=True)
    (original / "src").mkdir()
    source = original / "src/evaluator.py"
    evidence = original / "runs/fixture.json"
    source.write_bytes(b"return 1\n")
    evidence.write_bytes(b'{"case":1}\n')
    bindings = BoundPaths(root=original, run_dir=original / "runs")
    manifest = ReplayManifest.create(
        input_payload={"case": 1}, code_revision="local", environment={"python": "test"},
        seed=17, source_paths=[source], evidence_paths=[evidence],
        computational_output={"passed": True}, bindings=bindings,
    )
    assert manifest.schema_version == "replay-manifest-v2"
    assert [item.path for item in manifest.source_files] == ["root://src/evaluator.py"]
    assert [item.path for item in manifest.evidence_files] == ["run://fixture.json"]
    manifest.write(original / "runs/replay-manifest.json")
    shutil.copytree(original, relocated)
    moved = BoundPaths(root=relocated, run_dir=relocated / "runs")
    loaded = ReplayManifest.load(relocated / "runs/replay-manifest.json")
    assert loaded.verify(
        source_paths=[moved.resolve(item.path) for item in loaded.source_files],
        evidence_paths=[moved.resolve(item.path) for item in loaded.evidence_files],
        bindings=moved,
    ).verified
    for bad in ("run://../src/evaluator.py", "root://C:/Windows/file", "run://..\\fixture.json", "file:///outside", "run:///fixture.json"):
        with pytest.raises(ReplayMismatch):
            moved.resolve(bad)
    (relocated / "runs/fixture.json").write_bytes(b'{"case":2}\n')
    with pytest.raises(ReplayMismatch, match="evidence file snapshot changed"):
        loaded.verify(evidence_paths=[relocated / "runs/fixture.json"], bindings=moved)
