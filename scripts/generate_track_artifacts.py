"""Generate deterministic T2–T5 fixture and acceptance receipts."""

from __future__ import annotations

import json
from pathlib import Path

from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.tracks.causal import CausalCase, evaluate_causal_fixture
from auditable_scientist.tracks.common import make_track_receipt
from auditable_scientist.tracks.dynamics import DynamicsCase, evaluate_dynamics_fixture
from auditable_scientist.tracks.proof import ProofObligation, ProofPackage, ProofState, verify_proof_package
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep, verify_protocol


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    sample_run = json.loads((ROOT / "artifacts/sample-run.json").read_text(encoding="utf-8"))
    portfolio: list[dict[str, object]] = [
        {
            "track_id": "T1",
            "evaluator_id": "hohmann-bounded-generator-v1",
            "evidence_level": "validated-reproduction",
            "input_hash": sample_run["input_hash"],
            "passed": True,
            "negative_case_passed": True,
            "blocked_gates": ["external symbolic engine", "real-data provenance", "independent backend"],
            "result": {"selected_candidate_id": "tof-hohmann-v1", "holdout_verified": True, "acceptance": "artifacts/acceptance.json"},
        }
    ]

    causal_cases = [
        CausalCase(case_id="train-1", split="train", context_value=4, intervention_value=0, expected_outcome=1),
        CausalCase(case_id="train-2", split="train", context_value=-3, intervention_value=2, expected_outcome=5),
        CausalCase(case_id="holdout-1", split="holdout", context_value=99, intervention_value=3, expected_outcome=7),
    ]
    causal_eval, causal_receipt = evaluate_causal_fixture(causal_cases)
    write_json(ROOT / "examples/causal/fixture.json", {"schema_version": "causal-fixture-v1", "cases": [item.model_dump(mode="json") for item in causal_cases]})
    write_json(ROOT / "artifacts/t2-causal/acceptance.json", {"track": "T2", "status": "accepted-with-bounded-scope", "evaluator": causal_receipt.model_dump(mode="json"), "negative_case": "wrong coefficient rejected", "execution": "offline"})
    portfolio.append(causal_receipt.model_dump(mode="json"))

    dynamics_cases = [
        DynamicsCase(case_id="train-1", split="train", omega=1.0, dt=0.01, steps=500, x0=1, v0=0),
        DynamicsCase(case_id="train-2", split="train", omega=1.4, dt=0.01, steps=500, x0=0.5, v0=0.2),
        DynamicsCase(case_id="holdout-1", split="holdout", omega=0.8, dt=0.01, steps=700, x0=1.2, v0=-0.1),
    ]
    dynamics_eval, dynamics_receipt = evaluate_dynamics_fixture(dynamics_cases)
    write_json(ROOT / "examples/dynamics/fixture.json", {"schema_version": "dynamics-fixture-v1", "cases": [item.model_dump(mode="json") for item in dynamics_cases]})
    write_json(ROOT / "artifacts/t3-dynamics/acceptance.json", {"track": "T3", "status": "accepted-with-bounded-scope", "evaluator": dynamics_receipt.model_dump(mode="json"), "negative_case": "explicit Euler conservation drift rejected", "execution": "offline"})
    portfolio.append(dynamics_receipt.model_dump(mode="json"))

    trajectory = [ProofState(step=0, mass_a=2, mass_b=3), ProofState(step=1, mass_a=1, mass_b=4)]
    obligations = [
        ProofObligation(obligation_id="o1", checker_id="mass-conservation", statement="total mass is constant"),
        ProofObligation(obligation_id="o2", checker_id="nonnegative-state", statement="masses are nonnegative"),
        ProofObligation(obligation_id="o3", checker_id="trajectory-hash", statement="trajectory hash matches"),
    ]
    proof_package = ProofPackage(package_id="proof-1", trajectory=trajectory, obligations=obligations, trajectory_hash=canonical_hash([item.model_dump(mode="json") for item in trajectory]))
    proof_verification = verify_proof_package(proof_package)
    tampered_package = proof_package.model_copy(update={"trajectory": [*trajectory, ProofState(step=2, mass_a=0, mass_b=4)]})
    tampered_verification = verify_proof_package(tampered_package)
    proof_receipt = make_track_receipt(track_id="T4", evaluator_id=proof_verification.evaluator_id, input_payload=proof_package.model_dump(mode="json"), evidence_level=proof_verification.evidence_level, passed=proof_verification.passed, negative_case_passed=not tampered_verification.passed, result=proof_verification.model_dump(mode="json"), blocked_gates=["formal proof backend beyond finite obligation check"])
    write_json(ROOT / "examples/proof/fixture.json", proof_package.model_dump(mode="json"))
    write_json(ROOT / "artifacts/t4-proof/acceptance.json", {"track": "T4", "status": "accepted-with-bounded-scope", "evaluator": proof_receipt.model_dump(mode="json"), "negative_case": tampered_verification.model_dump(mode="json"), "execution": "offline"})
    portfolio.append(proof_receipt.model_dump(mode="json"))

    protocol_steps = [
        ProtocolStep(step_id="step-1", action="mix", reagent="buffer", volume_ul=10, temperature_c=22, duration_min=5, provenance_status="verified"),
        ProtocolStep(step_id="step-2", action="incubate", reagent="sample", volume_ul=5, temperature_c=24, duration_min=10, provenance_status="verified"),
    ]
    protocol = ProtocolSpec(protocol_id="p-1", steps=protocol_steps, min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20)
    protocol_verification = verify_protocol(protocol)
    bad_protocol = protocol.model_copy(update={"steps": [protocol_steps[0].model_copy(update={"provenance_status": "blocked"}), protocol_steps[1]]})
    bad_protocol_verification = verify_protocol(bad_protocol)
    protocol_receipt = make_track_receipt(track_id="T5", evaluator_id=protocol_verification.evaluator_id, input_payload=protocol.model_dump(mode="json"), evidence_level=protocol_verification.evidence_level, passed=protocol_verification.passed, negative_case_passed=not bad_protocol_verification.passed, result=protocol_verification.model_dump(mode="json"), blocked_gates=["real wet-lab validation and human biosafety review"])
    write_json(ROOT / "examples/protocol/fixture.json", protocol.model_dump(mode="json"))
    write_json(ROOT / "artifacts/t5-protocol/acceptance.json", {"track": "T5", "status": "accepted-with-bounded-scope", "evaluator": protocol_receipt.model_dump(mode="json"), "negative_case": bad_protocol_verification.model_dump(mode="json"), "execution": "verification-only; no wet-lab execution"})
    portfolio.append(protocol_receipt.model_dump(mode="json"))

    write_json(ROOT / "artifacts/track-portfolio.json", {"schema_version": "track-portfolio-v1", "status": "bounded-slices-accepted", "tracks": portfolio, "global_boundaries": ["No real-data claim", "No autonomous wet-lab execution", "No publication or novelty claim"]})


if __name__ == "__main__":
    main()
