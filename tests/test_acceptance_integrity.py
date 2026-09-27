"""Mutation checks for the saved cross-file acceptance contract."""

import copy
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import ValidationError as SchemaValidationError

from scripts.verify_acceptance import verify_track_bundle


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("mutation", ["boundary", "sample-result", "event-log", "source-hash"])
def test_track_bundle_rejects_cross_file_tampering(tmp_path: Path, mutation: str) -> None:
    original = ROOT / "artifacts/t2-causal"
    bundle = tmp_path / "t2-causal"
    bundle.mkdir()
    for name in ("acceptance.json", "test-report.md", "demo-transcript.md", "sample-run.json", "events.jsonl"):
        shutil.copy2(original / name, bundle / name)
    portfolio = json.loads((ROOT / "artifacts/track-portfolio.json").read_text(encoding="utf-8"))
    receipt = copy.deepcopy(next(item for item in portfolio["tracks"] if item["track_id"] == "T2"))
    verify_track_bundle("T2", receipt, bundle)
    if mutation == "boundary":
        path = bundle / "acceptance.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["evidence_boundaries"]["real_data"] = True
        path.write_text(json.dumps(data), encoding="utf-8")
    elif mutation == "sample-result":
        path = bundle / "sample-run.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["evaluator"]["coefficient"] = 999
        path.write_text(json.dumps(data), encoding="utf-8")
    elif mutation == "event-log":
        path = bundle / "events.jsonl"
        path.write_text(path.read_text(encoding="utf-8").replace("evaluator.completed", "evaluator.changed", 1), encoding="utf-8")
    else:
        receipt["source_files"][0]["sha256"] = "0" * 64
    with pytest.raises((ValueError, SchemaValidationError)):
        verify_track_bundle("T2", receipt, bundle)
