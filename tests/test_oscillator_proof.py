"""Adversarial checks for the bounded proof-carrying oscillator adapter."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.tracks.dynamics import DynamicsCase
from auditable_scientist.tracks.oscillator_proof import (
    OscillatorProofPackage, create_oscillator_package, verify_oscillator_package,
)


def package() -> OscillatorProofPackage:
    case = DynamicsCase(case_id="holdout-1", split="holdout", omega=0.8, dt=0.01, steps=700, x0=1.2, v0=-0.1)
    return create_oscillator_package(case)


def statuses(item: OscillatorProofPackage) -> dict[str, str]:
    return {result.checker_id: result.status for result in verify_oscillator_package(item).results}


def test_oscillator_receipt_is_bounded_and_forged_output_hash_is_rejected() -> None:
    original = package()
    verified = verify_oscillator_package(original)
    assert verified.passed and verified.claim_status == "bounded-verified"
    assert statuses(original)["formal-prover"] == "not_applicable"
    assert all(status == "passed" for checker, status in statuses(original).items() if checker != "formal-prover")

    forged_output = original.output.model_copy(update={"final_x": original.output.final_x + 0.1})
    forged = original.model_copy(update={
        "output": forged_output,
        "output_hash": canonical_hash(forged_output.model_dump(mode="json")),
    })
    assert statuses(forged)["output-hash"] == "passed"
    assert statuses(forged)["solver-replay"] == "failed"
    assert verify_oscillator_package(forged).claim_status == "blocked"


def test_oscillator_receipt_rejects_source_units_boundary_and_missing_obligation() -> None:
    original = package()
    assert statuses(original.model_copy(update={"source_sha256": "0" * 64}))["source-hash"] == "failed"
    assert statuses(original.model_copy(update={"units": {**original.units, "position": "km"}}))["units"] == "failed"
    altered_output = original.output.model_copy(update={"initial_x": original.output.initial_x + 1})
    altered = original.model_copy(update={"output": altered_output, "output_hash": canonical_hash(altered_output.model_dump(mode="json"))})
    assert statuses(altered)["initial-boundary"] == "failed"

    missing = original.model_copy(update={"obligations": [item for item in original.obligations if item.checker_id != "energy-drift"]})
    assert statuses(missing)["energy-drift"] == "inconclusive"
    assert not verify_oscillator_package(missing).passed
    repeated = original.model_copy(update={"obligations": [*original.obligations, original.obligations[0]]})
    assert statuses(repeated)[original.obligations[0].checker_id] == "failed"


def test_oscillator_reference_is_independent_and_input_is_bounded(monkeypatch) -> None:
    original = package()
    monkeypatch.setattr("auditable_scientist.tracks.oscillator_proof.rk4_oscillator", lambda *args: (100.0, 0.0, 0.0))
    assert statuses(original)["rk4-reference"] == "failed"
    invalid = original.model_dump(mode="json")
    invalid["case"]["steps"] = 1001
    with pytest.raises(ValidationError, match="finite grid"):
        OscillatorProofPackage.model_validate(invalid)
