"""Real document intake is source-bound and never grants protocol authority."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts import verify_acceptance, verify_t5_pbs_source


def test_pinned_real_source_recomputes_and_stays_nonexecutable() -> None:
    result = verify_t5_pbs_source.evaluate()
    assert result["status"] == "verified-source-document-and-review-flags-only"
    assert len(result["anchors"]) == 11
    assert len(result["step_inventory"]) == 6
    assert result["boundaries"]["execution_allowed"] is False
    assert result["boundaries"]["human_acceptance"] is False
    assert verify_acceptance.verify_optional_t5_pbs_source()["dynamic_verified_here"] is True


@pytest.mark.parametrize("mutation", [
    "source_hash", "license", "citation_location", "step_digest",
    "missing_step", "execution", "claim_promotion",
])
def test_saved_source_inventory_rejects_tampering(mutation: str) -> None:
    audit = deepcopy(verify_acceptance.load("artifacts/t5-pbs-source-audit.json"))
    if mutation == "source_hash":
        audit["source_pdf_sha256"] = "0"*64
    elif mutation == "license":
        audit["source"]["license_declaration"] = "unknown"
    elif mutation == "citation_location":
        audit["anchors"][0]["start"] += 1
    elif mutation == "step_digest":
        audit["step_inventory"][0]["text_sha256"] = "0"*64
    elif mutation == "missing_step":
        audit["step_inventory"].pop()
    elif mutation == "execution":
        audit["boundaries"]["execution_allowed"] = True
    else:
        audit["boundaries"]["claim_status"] = "validated"
    with pytest.raises(ValueError, match="T5 PBS"):
        verify_acceptance.verify_optional_t5_pbs_source(
            audit, verify_dynamic=False)


def test_modified_pdf_bytes_fail_before_text_extraction(tmp_path: Path) -> None:
    payload = verify_t5_pbs_source.PDF.read_bytes()
    modified = tmp_path / "modified.pdf"
    modified.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
    with pytest.raises(ValueError, match="pinned bytes"):
        verify_t5_pbs_source.evaluate(modified)
