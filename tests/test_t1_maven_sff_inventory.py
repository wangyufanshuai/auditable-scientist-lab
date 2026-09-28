"""Reject promotion or alteration of exploratory MAVEN small-forces evidence."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import verify_acceptance


@pytest.mark.parametrize("mutation", [
    "source_hash", "raw_time", "duplicate_pair", "force_promotion", "claim_promotion",
])
def test_sff_inventory_rejects_tampering(mutation: str) -> None:
    audit = verify_acceptance.load("artifacts/t1-maven-sff-exploratory-audit.json")
    assert verify_acceptance.verify_optional_t1_maven_sff_inventory(
        audit, verify_dynamic=False)["dynamic_verified_here"] is False
    altered = deepcopy(audit)
    if mutation == "source_hash":
        altered["files"][0]["sha256"] = "0"*64
    elif mutation == "raw_time":
        altered["files"][5]["last_raw_end"] = "2014-06-29 04:04:48.522"
    elif mutation == "duplicate_pair":
        altered["same_records_except_production_time"].pop()
    elif mutation == "force_promotion":
        altered["boundaries"]["values_admitted_to_dynamics_model"] = True
    else:
        altered["boundaries"]["claim_status"] = "validated"
    with pytest.raises(ValueError, match="MAVEN SFF"):
        verify_acceptance.verify_optional_t1_maven_sff_inventory(
            altered, verify_dynamic=False)
