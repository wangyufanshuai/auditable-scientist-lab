"""The T5 source-availability receipt fails closed when the PDF is local or altered."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import verify_t5_source_availability


def test_clean_checkout_receipt_is_blocked_and_pinned() -> None:
    result = verify_t5_source_availability.verify_saved()
    assert result["status"] == "blocked-local-source-not-redistributed"
    assert result["availability"]["local_pdf_exists"] is False
    assert result["checks"]["dynamic_pdf_replay_blocked"] is True
    assert result["expected_source"]["doi"] == "10.17504/protocols.io.p4rdqv6"
    assert result["boundaries"] == {
        "source_inventory_only": True,
        "local_dynamic_replay_available": False,
        "source_pdf_redistributed": False,
        "execution_allowed": False,
        "independent_procedure_validation": False,
        "biosafety_review_complete": False,
        "human_acceptance": False,
        "claim_status": "unverified",
    }


def test_local_pdf_presence_is_not_silently_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local_pdf = tmp_path / "protocols_io_p4rdqv6.pdf"
    local_pdf.write_bytes(b"not the redistributed source")
    monkeypatch.setattr(verify_t5_source_availability, "PDF", local_pdf)
    with pytest.raises(ValueError, match="present locally"):
        verify_t5_source_availability.evaluate()


@pytest.mark.parametrize("mutation", ["status", "hash", "promotion", "availability"])
def test_saved_receipt_rejects_tampering(mutation: str) -> None:
    saved = json.loads(verify_t5_source_availability.AUDIT.read_text(encoding="utf-8"))
    changed = deepcopy(saved)
    if mutation == "status":
        changed["status"] = "verified-source-document"
    elif mutation == "hash":
        changed["expected_source"]["pdf_sha256"] = "0" * 64
    elif mutation == "promotion":
        changed["boundaries"]["claim_status"] = "validated"
    else:
        changed["availability"]["local_dynamic_replay_available"] = True
    with pytest.raises(ValueError, match="receipt differs"):
        verify_t5_source_availability.verify_saved(changed)
