"""Keep catalog facts separate from a verified MAVEN maneuver history."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import verify_acceptance


@pytest.mark.parametrize("mutation", [
    "source", "row_count", "arc_event", "invented_desat",
    "context_id", "time_window", "claim_promotion",
])
def test_static_acceptance_rejects_ops_catalog_tampering(mutation: str) -> None:
    audit = verify_acceptance.load("artifacts/t1-maven-ops-event-search-audit.json")
    assert verify_acceptance.verify_optional_t1_maven_ops_events(
        audit, verify_dynamic=False)["dynamic_verified_here"] is False
    altered = deepcopy(audit)
    if mutation == "source":
        altered["source_files"][-1]["sha256"] = "0"*64
    elif mutation == "row_count":
        altered["records_checked"] -= 1
    elif mutation == "arc_event":
        altered["arcs"][1]["all_arc_events"] = 1
    elif mutation == "invented_desat":
        altered["arcs"][0]["keyword_arc_hits"] = [altered["arcs"][0]["keyword_context_hits"][0]]
    elif mutation == "context_id":
        altered["arcs"][0]["keyword_context_hits"][0]["id"] = "forged"
    elif mutation == "time_window":
        altered["arcs"][0]["start_utc"] = "2014-04-29T00:00:00Z"
    else:
        altered["boundaries"]["claim_status"] = "validated"
    with pytest.raises(ValueError, match="MAVEN operations-event"):
        verify_acceptance.verify_optional_t1_maven_ops_events(altered, verify_dynamic=False)
