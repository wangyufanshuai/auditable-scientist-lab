"""Source and structure gates for an optional real projectile dataset."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

from openpyxl import load_workbook
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_t2_projectile_source import (  # noqa: E402
    AUDIT, CONTRACT, LOCAL, _check_observation_rows, evaluate,
)
from sync_optional_acceptance import _t2_projectile_receipt  # noqa: E402


def _rows() -> list[tuple]:
    path = LOCAL / "pedadd2c5supp1.xlsx"
    if not path.is_file():
        pytest.skip("optional source workbook is unavailable")
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        return list(book.active.values)[1:]
    finally:
        book.close()


def test_projectile_source_inventory_has_real_data_but_no_validated_claim() -> None:
    saved = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert _t2_projectile_receipt(verify_dynamic=False)["status"] == saved["status"]
    assert saved["measured_inventory"]["sample_count"] == 179
    assert saved["measured_inventory"]["trial_count"] == 30
    assert saved["article"]["paper_reported_experiments"] == 82
    assert len(saved["measured_inventory"]["observed_declared_speed_above_paper_bound_trials"]) == 15
    assert saved["boundaries"]["complete_reported_experiment_set"] is False
    assert saved["boundaries"]["causal_effect_identified"] is False
    assert saved["boundaries"]["physical_model_validated"] is False
    assert saved["boundaries"]["claim_status"] == "unverified"
    if not (LOCAL / "pedadd2c5supp1.xlsx").is_file():
        pytest.skip("optional source files are unavailable")
    recorded_at = saved.pop("recorded_at")
    assert recorded_at
    assert evaluate() == saved


@pytest.mark.parametrize("mutation", [
    "missing_row", "nonfinite", "duplicate_time", "changed_trial_input",
])
def test_projectile_measurement_structure_rejects_corruption(mutation: str) -> None:
    rows = deepcopy(_rows())
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if mutation == "missing_row":
        rows.pop()
    elif mutation == "nonfinite":
        rows[0] = (*rows[0][:2], float("nan"), *rows[0][3:])
    elif mutation == "duplicate_time":
        rows[1] = (rows[1][0], rows[0][1], *rows[1][2:])
    else:
        rows[1] = (*rows[1][:4], rows[1][4] + 1, rows[1][5])
    with pytest.raises(ValueError):
        _check_observation_rows(rows, contract)


@pytest.mark.parametrize("mutation", [
    "missing_trial", "claimed_model_validation", "claimed_supplement_rights",
    "changed_workbook_hash", "missing_negative_control", "changed_verifier_hash",
])
def test_projectile_acceptance_projection_rejects_mutated_receipt(mutation: str) -> None:
    audit = deepcopy(json.loads(AUDIT.read_text(encoding="utf-8")))
    if mutation == "missing_trial":
        audit["measured_inventory"]["trials"].pop()
    elif mutation == "claimed_model_validation":
        audit["boundaries"]["physical_model_validated"] = True
    elif mutation == "claimed_supplement_rights":
        audit["boundaries"]["supplement_rights_reviewed"] = True
    elif mutation == "changed_workbook_hash":
        audit["local_file_fingerprints"][1]["sha256"] = "0" * 64
    elif mutation == "missing_negative_control":
        audit["negative_controls"]["missing_sample_rejected"] = False
    else:
        audit["source_files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        _t2_projectile_receipt(audit, verify_dynamic=False)
