"""Independent algebra and fail-closed receipt tests for the bounded T4 class."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.check_t4_linear_certificate import AUDIT, check_audit, exact, expected_certificate


def test_exact_checker_accepts_a_new_conservative_matrix() -> None:
    system = {
        "system_id": "averaging-with-transfer",
        "state_names": ["left", "right"],
        "control_names": ["transfer"],
        "transition_matrix": [["1/2", "1/2"], ["1/2", "1/2"]],
        "control_matrix": [["-1"], ["1"]],
        "invariant_coefficients": ["1", "1"],
        "sample_state": ["2", "4"],
        "sample_control": ["1"],
    }
    certificate = expected_certificate(system)
    assert certificate["universal_conservation_proved"] is True
    assert certificate["residual_state_coefficients"] == ["0", "0"]
    assert certificate["residual_control_coefficients"] == ["0"]
    assert certificate["sample_next_state"] == ["2", "4"]
    assert certificate["sample_invariant_delta"] == "0"


@pytest.mark.parametrize("value", ["0/1", "2/4", "+1", "01", "1.0", "1/0"])
def test_noncanonical_rationals_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        exact(value)


@pytest.mark.parametrize("mutation", ["forged_coefficient", "forged_proof", "real_data", "source_hash", "negative_control"])
def test_audit_rejects_mutation(mutation: str) -> None:
    audit = deepcopy(json.loads(AUDIT.read_text(encoding="utf-8")))
    if mutation == "forged_coefficient":
        audit["certificates"][0]["residual_state_coefficients"][0] = "1"
    elif mutation == "forged_proof":
        audit["certificates"][2]["universal_conservation_proved"] = True
    elif mutation == "real_data":
        audit["boundaries"]["real_data"] = True
    elif mutation == "source_hash":
        audit["source_files"][0]["sha256"] = "0" * 64
    else:
        audit["certificates"][2]["sample_invariant_delta"] = "0"
    with pytest.raises(ValueError):
        check_audit(audit)
