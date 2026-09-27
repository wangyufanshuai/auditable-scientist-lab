from __future__ import annotations

from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.tracks.causal import CausalCase, evaluate_causal_fixture
from auditable_scientist.tracks.dynamics import DynamicsCase, evaluate_dynamics_fixture
from auditable_scientist.tracks.proof import ProofObligation, ProofPackage, ProofState, verify_proof_package
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep, verify_protocol


def test_t2_causal_intervention_and_negative_control() -> None:
    cases = [
        CausalCase(case_id="train-1", split="train", context_value=4, intervention_value=0, expected_outcome=1),
        CausalCase(case_id="train-2", split="train", context_value=-3, intervention_value=2, expected_outcome=5),
        CausalCase(case_id="holdout-1", split="holdout", context_value=99, intervention_value=3, expected_outcome=7),
    ]
    evaluation, receipt = evaluate_causal_fixture(cases)
    assert evaluation.passed is True
    assert evaluation.negative_candidate_rejected is True
    assert receipt.negative_case_passed is True
    assert receipt.evidence_level == "validated-reproduction"


def test_t3_dynamics_reproduction_and_euler_negative_case(monkeypatch) -> None:
    cases = [
        DynamicsCase(case_id="train-1", split="train", omega=1.0, dt=0.01, steps=500, x0=1, v0=0),
        DynamicsCase(case_id="train-2", split="train", omega=1.4, dt=0.01, steps=500, x0=0.5, v0=0.2),
        DynamicsCase(case_id="holdout-1", split="holdout", omega=0.8, dt=0.01, steps=700, x0=1.2, v0=-0.1),
    ]
    evaluation, receipt = evaluate_dynamics_fixture(cases)
    assert evaluation.passed is True
    assert evaluation.reference_solver_id == "fixed-step-rk4-v1"
    assert evaluation.backend_agreement_passed is True
    assert evaluation.max_reference_position_error < 1e-5
    assert evaluation.negative_euler_rejected is True
    assert receipt.negative_case_passed is True
    monkeypatch.setattr("auditable_scientist.tracks.dynamics.rk4_oscillator", lambda *args: (100.0, 0.0, 0.0))
    failed, failed_receipt = evaluate_dynamics_fixture(cases)
    assert failed.backend_agreement_passed is False
    assert failed.passed is False
    assert failed_receipt.evidence_level == "demo"


def test_t4_proof_obligations_block_tampered_trajectory() -> None:
    trajectory = [ProofState(step=0, mass_a=2, mass_b=3), ProofState(step=1, mass_a=1, mass_b=4)]
    obligations = [
        ProofObligation(obligation_id="o1", checker_id="mass-conservation", statement="total mass is constant"),
        ProofObligation(obligation_id="o2", checker_id="nonnegative-state", statement="masses are nonnegative"),
        ProofObligation(obligation_id="o3", checker_id="trajectory-hash", statement="trajectory hash matches"),
    ]
    package = ProofPackage(
        package_id="proof-1",
        trajectory=trajectory,
        obligations=obligations,
        trajectory_hash=canonical_hash([item.model_dump(mode="json") for item in trajectory]),
    )
    result = verify_proof_package(package)
    assert result.passed is True
    tampered = package.model_copy(update={"trajectory": [*trajectory, ProofState(step=2, mass_a=0, mass_b=4)]})
    failed = verify_proof_package(tampered)
    assert failed.passed is False
    assert failed.claim_status == "blocked"


def test_t5_protocol_constraints_pass_without_execution_and_fail_bad_provenance() -> None:
    steps = [
        ProtocolStep(step_id="step-1", action="mix", reagent="buffer", volume_ul=10, temperature_c=22, duration_min=5, provenance_status="verified"),
        ProtocolStep(step_id="step-2", action="incubate", reagent="sample", volume_ul=5, temperature_c=24, duration_min=10, provenance_status="verified"),
    ]
    protocol = ProtocolSpec(protocol_id="p-1", steps=steps, min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20)
    result = verify_protocol(protocol)
    assert result.passed is True
    assert result.execution_allowed is False
    bad = protocol.model_copy(update={"steps": [steps[0].model_copy(update={"provenance_status": "blocked"}), steps[1]]})
    failed = verify_protocol(bad)
    assert failed.passed is False
    assert "provenance:step-1" in failed.failures
