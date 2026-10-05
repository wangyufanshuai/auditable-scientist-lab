"""Fail-closed tests for the T2 projectile source reconciliation receipt."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_t2_projectile_source_reconciliation import (  # noqa: E402
    AUDIT, evaluate, verify_saved,
)
from sync_optional_acceptance import _t2_projectile_reconciliation_receipt  # noqa: E402


def test_reconciliation_receipt_records_partial_coverage_and_blocked_claims() -> None:
    saved = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert saved["article"]["reported_experiment_count"] == 82
    assert saved["measured_workbook"]["trial_count"] == 30
    assert saved["measured_workbook"]["sample_count"] == 179
    assert saved["reconciliation"]["unaccounted_experiment_count"] == 52
    assert saved["measured_workbook"]["v0_role_status"] == "unresolved"
    assert saved["measured_workbook"]["metadata"]["metadata_role"] == "provenance-only"
    assert saved["reconciliation"]["duplicate_crosses_holdout_boundary"] is True
    assert saved["provenance"]["source_rights_cleared"] is False
    assert saved["boundaries"]["claim_status"] == "unverified"
    recorded_at = saved.pop("recorded_at")
    assert recorded_at
    assert evaluate() == saved


@pytest.mark.parametrize("mutation", [
    "coverage_spoof", "force_v0_resolved", "source_hash_tamper",
    "ignore_duplicate_split", "promote_rights",
])
def test_reconciliation_negative_controls_reject_overclaim(mutation: str) -> None:
    audit = deepcopy(json.loads(AUDIT.read_text(encoding="utf-8")))
    if mutation == "coverage_spoof":
        audit["reconciliation"]["coverage_status"] = "complete"
    elif mutation == "force_v0_resolved":
        audit["measured_workbook"]["v0_role_status"] = "resolved-measured"
    elif mutation == "source_hash_tamper":
        audit["input_hashes"]["source_audit_sha256"] = "0" * 64
    elif mutation == "ignore_duplicate_split":
        audit["reconciliation"]["duplicate_crosses_holdout_boundary"] = False
    else:
        audit["provenance"]["source_rights_cleared"] = True
    with pytest.raises(ValueError):
        verify_saved(audit)


@pytest.mark.parametrize("mutation", ["coverage_spoof", "source_hash_tamper", "rights_promotion"])
def test_reconciliation_is_required_in_acceptance_projection(mutation: str) -> None:
    audit = deepcopy(json.loads(AUDIT.read_text(encoding="utf-8")))
    if mutation == "coverage_spoof":
        audit["reconciliation"]["coverage_status"] = "complete"
    elif mutation == "source_hash_tamper":
        audit["input_hashes"]["source_audit_sha256"] = "0" * 64
    else:
        audit["provenance"]["source_rights_cleared"] = True
    with pytest.raises(ValueError):
        _t2_projectile_reconciliation_receipt(audit)
