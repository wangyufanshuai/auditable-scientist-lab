"""The T3 convergence sweep is executable from the installed package API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auditable_scientist.tracks.convergence import build_receipt, verify_saved_receipt


ROOT = Path(__file__).resolve().parents[1]


def test_package_convergence_receipt_has_bounded_pass() -> None:
    receipt = build_receipt()
    assert receipt["schema_version"] == "t3-sweep-v1"
    assert receipt["summary"]["case_count"] == 27
    assert receipt["passed"] is True
    assert all(receipt["checks"].values())
    assert receipt["boundaries"] == {
        "fixture_reproduction": True,
        "real_mission_validation": False,
        "multi_body_validation": False,
        "external_solver_validation": False,
    }
    assert {item["path"] for item in receipt["source_files"]} == {
        "src/auditable_scientist/tracks/convergence.py",
        "src/auditable_scientist/tracks/dynamics.py",
        "src/auditable_scientist/tracks/reference_rk4.py",
    }


def test_saved_convergence_receipt_rejects_mutation(tmp_path: Path) -> None:
    source = ROOT / "artifacts/t3-sweep.json"
    saved = json.loads(source.read_text(encoding="utf-8"))
    saved["summary"]["case_count"] = 28
    mutated = tmp_path / "t3-sweep.json"
    mutated.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(ValueError, match="T3 sweep audit differs"):
        verify_saved_receipt(mutated)
