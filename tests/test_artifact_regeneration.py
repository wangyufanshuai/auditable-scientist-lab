"""Regenerating base bundles must retain verified optional evidence rows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import sync_optional_acceptance


ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_ROWS = {
    "t2-physical": {"independent-endpoint-estimator", "independent-endpoint-run"},
    "t3-dynamics": {"optional-expanded-horizon-grid"},
    "t4-proof": {"exact-linear-invariant-subtrack", "exact-linear-invariant-run"},
}


def test_regeneration_preserves_optional_receipts_and_acceptance(tmp_path: Path) -> None:
    copied = tmp_path / "repo"
    shutil.copytree(
        ROOT, copied,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc", "*.pyo"),
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(copied / "src")
    generated = subprocess.run(
        [sys.executable, "scripts/generate_track_artifacts.py"], cwd=copied,
        env=environment, capture_output=True, text=True, check=False, timeout=60,
    )
    assert generated.returncode == 0, generated.stderr
    synchronized = subprocess.run(
        [sys.executable, "scripts/sync_optional_acceptance.py", "--write"], cwd=copied,
        env=environment, capture_output=True, text=True, check=False, timeout=30,
    )
    assert synchronized.returncode == 0, synchronized.stderr
    for directory, expected in OPTIONAL_ROWS.items():
        acceptance = json.loads((copied / "artifacts" / directory / "acceptance.json").read_text(encoding="utf-8"))
        assert expected <= {row["name"] for row in acceptance["checks"]}
    status = json.loads((copied / "artifacts/portfolio-status.json").read_text(encoding="utf-8"))
    current_status = json.loads((ROOT / "artifacts/portfolio-status.json").read_text(encoding="utf-8"))
    assert status == current_status
    verified = subprocess.run(
        [sys.executable, "scripts/verify_acceptance.py"], cwd=copied,
        env=environment, capture_output=True, text=True, check=False, timeout=60,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "verified"


def test_optional_receipt_rejects_boundary_overclaim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit = json.loads((ROOT / "artifacts/t3-horizon-grid-audit.json").read_text(encoding="utf-8"))
    audit["boundaries"]["mission_validation"] = True
    destination = tmp_path / "artifacts/t3-horizon-grid-audit.json"
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(audit), encoding="utf-8")
    monkeypatch.setattr(sync_optional_acceptance, "ROOT", tmp_path)
    spec = next(item for item in sync_optional_acceptance.OPTIONAL if item[1] == "optional-expanded-horizon-grid")
    with pytest.raises(ValueError, match="exceeds its boundary"):
        sync_optional_acceptance._receipt_row(spec)


def test_status_contract_cannot_drop_real_data_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contract = json.loads(sync_optional_acceptance.STATUS_CONTRACT.read_text(encoding="utf-8"))
    contract["tracks"][0]["open_gates"].remove("real-data provenance")
    changed = tmp_path / "status.json"
    changed.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(sync_optional_acceptance, "STATUS_CONTRACT", changed)
    with pytest.raises(ValueError, match="exceeds the bounded release state"):
        sync_optional_acceptance.desired_outputs()
