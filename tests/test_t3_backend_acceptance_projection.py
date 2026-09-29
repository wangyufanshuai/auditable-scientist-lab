"""Fail-closed tests for the T3 backend contract acceptance projection."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_optional_acceptance import _t3_backend_contract_receipt  # noqa: E402


def test_t3_backend_contract_projection_is_bounded() -> None:
    audit = json.loads((ROOT / "artifacts/t3-backend-contract-audit.json").read_text(encoding="utf-8"))
    receipt = _t3_backend_contract_receipt(audit)
    assert receipt["verifier_sha256"]
    assert audit["audit_count"] == 3
    assert audit["boundaries"]["scientific_claim_verified"] is False


@pytest.mark.parametrize("mutation", ["status", "audit_count", "claim"])
def test_t3_backend_contract_projection_rejects_overclaim(mutation: str) -> None:
    audit = deepcopy(json.loads((ROOT / "artifacts/t3-backend-contract-audit.json").read_text(encoding="utf-8")))
    if mutation == "status":
        audit["status"] = "verified-general-nbody"
    elif mutation == "audit_count":
        audit["audit_count"] = 2
    else:
        audit["boundaries"]["scientific_claim_verified"] = True
    with pytest.raises(ValueError):
        _t3_backend_contract_receipt(audit)
