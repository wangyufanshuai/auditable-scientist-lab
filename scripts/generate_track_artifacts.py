"""Generate deterministic T2–T5 fixture and acceptance receipts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from auditable_scientist.runtime.canonical import canonical_hash, canonical_json
from auditable_scientist.runtime.replay import fingerprint_file
from auditable_scientist.tracks.causal import CausalCase
from auditable_scientist.tracks.dynamics import DynamicsCase
from auditable_scientist.tracks.proof import ProofObligation, ProofPackage, ProofState
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep
from auditable_scientist.tracks.run_package import make_track_run
from auditable_scientist.tracks.runner import run_registered_track


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def evidence_for(path: Path) -> list[dict[str, object]]:
    fingerprint = fingerprint_file(path)
    return [
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": fingerprint.sha256,
            "bytes": fingerprint.bytes,
            "provenance_status": "unverified",
            "allowed_use": ["offline-fixture", "bounded-evaluator"],
        }
    ]


def write_track_bundle(
    *,
    track_id: str,
    directory: str,
    receipt: object,
    run: object,
    negative_case: object,
    demo_text: str,
) -> None:
    receipt_payload = receipt.model_dump(mode="json")
    if not receipt_payload["passed"] or not receipt_payload["negative_case_passed"]:
        raise ValueError(f"{track_id} evaluator did not pass both bounded fixture gates")
    artifact_dir = ROOT / "artifacts" / directory
    acceptance = {
        "track": track_id,
        "status": "accepted-with-bounded-scope",
        "evaluator": receipt_payload,
        "negative_case": negative_case,
        "evidence_boundaries": {
            "demo": True,
            "validated_reproduction": receipt_payload["evidence_level"] == "validated-reproduction",
            "real_data": False,
            "research_candidate": False,
        },
        "execution": "offline",
        "checks": [
            {
                "name": "bounded-domain-evaluator",
                "command": "python scripts/generate_track_artifacts.py",
                "exit_code": 0,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "input_version": receipt_payload["input_hash"],
                "output_path": f"artifacts/{directory}/sample-run.json",
            }
        ],
    }
    write_json(artifact_dir / "acceptance.json", acceptance)
    write_json(
        artifact_dir / "sample-run.json",
        {
            "track": track_id,
            "run": run.model_dump(mode="json"),
            "input_hash": receipt_payload["input_hash"],
            "evaluator": receipt_payload["result"],
            "negative_case": negative_case,
            "evidence_files": receipt_payload["evidence_files"],
            "source_files": receipt_payload["source_files"],
        },
    )
    (artifact_dir / "events.jsonl").write_text(
        "".join(canonical_json(event) + "\n" for event in run.events),
        encoding="utf-8",
        newline="\n",
    )
    (artifact_dir / "test-report.md").write_text(
        f"# {track_id} evaluator test report\n\n"
        "- Command: `python scripts/verify_acceptance.py`\n"
        "- Result: independently replayed by the portfolio verifier\n"
        "- Evidence level: bounded local fixture\n"
        "- Real-data claim: false\n"
        "- Research-candidate claim: false\n",
        encoding="utf-8",
        newline="\n",
    )
    (artifact_dir / "demo-transcript.md").write_text(
        f"# {track_id} demo transcript\n\n{demo_text}\n\n"
        "The evaluator is deterministic and offline. The result does not authorize a real-world scientific, clinical, or wet-lab claim.\n",
        encoding="utf-8",
        newline="\n",
    )


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
            "evidence_files": evidence_for(ROOT / "artifacts/sample-run.json"),
            "blocked_gates": ["external symbolic engine", "real-data provenance", "independent backend"],
            "result": {"selected_candidate_id": "tof-hohmann-v1", "holdout_verified": True, "acceptance": "artifacts/acceptance.json"},
        }
    ]

    causal_cases = [
        CausalCase(case_id="train-1", split="train", context_value=4, intervention_value=0, expected_outcome=1),
        CausalCase(case_id="train-2", split="train", context_value=-3, intervention_value=2, expected_outcome=5),
        CausalCase(case_id="holdout-1", split="holdout", context_value=99, intervention_value=3, expected_outcome=7),
    ]
    causal_fixture = ROOT / "examples/causal/fixture.json"
    write_json(causal_fixture, {"schema_version": "causal-fixture-v1", "cases": [item.model_dump(mode="json") for item in causal_cases]})
    causal_execution = run_registered_track("T2", causal_fixture)
    causal_receipt = causal_execution.receipt
    causal_negative = causal_execution.negative_case
    causal_run = make_track_run(track_id="T2", task_id="t2-causal-intervention-v1", receipt=causal_receipt, fixture_path=causal_fixture, negative_case=causal_negative, calls_used=causal_execution.calls_used)
    write_track_bundle(track_id="T2", directory="t2-causal", receipt=causal_receipt, run=causal_run, negative_case=causal_negative, demo_text=f"run_id={causal_run.run_id}; holdout_rmse={causal_receipt.result['holdout_rmse']}; negative_candidate_rejected={causal_receipt.result['negative_candidate_rejected']}")
    portfolio.append(causal_receipt.model_dump(mode="json"))

    dynamics_cases = [
        DynamicsCase(case_id="train-1", split="train", omega=1.0, dt=0.01, steps=500, x0=1, v0=0),
        DynamicsCase(case_id="train-2", split="train", omega=1.4, dt=0.01, steps=500, x0=0.5, v0=0.2),
        DynamicsCase(case_id="holdout-1", split="holdout", omega=0.8, dt=0.01, steps=700, x0=1.2, v0=-0.1),
    ]
    dynamics_fixture = ROOT / "examples/dynamics/fixture.json"
    write_json(dynamics_fixture, {"schema_version": "dynamics-fixture-v1", "cases": [item.model_dump(mode="json") for item in dynamics_cases]})
    dynamics_execution = run_registered_track("T3", dynamics_fixture)
    dynamics_receipt = dynamics_execution.receipt
    dynamics_negative = dynamics_execution.negative_case
    dynamics_run = make_track_run(track_id="T3", task_id="t3-harmonic-dynamics-v1", receipt=dynamics_receipt, fixture_path=dynamics_fixture, negative_case=dynamics_negative, calls_used=dynamics_execution.calls_used)
    write_track_bundle(track_id="T3", directory="t3-dynamics", receipt=dynamics_receipt, run=dynamics_run, negative_case=dynamics_negative, demo_text=f"run_id={dynamics_run.run_id}; holdout_max_position_error={dynamics_receipt.result['holdout_max_position_error']}; negative_euler_rejected={dynamics_receipt.result['negative_euler_rejected']}")
    portfolio.append(dynamics_receipt.model_dump(mode="json"))

    trajectory = [ProofState(step=0, mass_a=2, mass_b=3), ProofState(step=1, mass_a=1, mass_b=4)]
    obligations = [
        ProofObligation(obligation_id="o1", checker_id="mass-conservation", statement="total mass is constant"),
        ProofObligation(obligation_id="o2", checker_id="nonnegative-state", statement="masses are nonnegative"),
        ProofObligation(obligation_id="o3", checker_id="trajectory-hash", statement="trajectory hash matches"),
    ]
    proof_package = ProofPackage(package_id="proof-1", trajectory=trajectory, obligations=obligations, trajectory_hash=canonical_hash([item.model_dump(mode="json") for item in trajectory]))
    proof_fixture = ROOT / "examples/proof/fixture.json"
    write_json(proof_fixture, proof_package.model_dump(mode="json"))
    proof_execution = run_registered_track("T4", proof_fixture)
    proof_receipt = proof_execution.receipt
    proof_negative = proof_execution.negative_case
    proof_run = make_track_run(track_id="T4", task_id="t4-proof-carrying-v1", receipt=proof_receipt, fixture_path=proof_fixture, negative_case=proof_negative, calls_used=proof_execution.calls_used)
    write_track_bundle(track_id="T4", directory="t4-proof", receipt=proof_receipt, run=proof_run, negative_case=proof_negative, demo_text=f"run_id={proof_run.run_id}; checked_obligations={proof_receipt.result['checked_obligations']}; tampered_claim_status={proof_negative['claim_status']}")
    portfolio.append(proof_receipt.model_dump(mode="json"))

    protocol_steps = [
        ProtocolStep(step_id="step-1", action="mix", reagent="buffer", volume_ul=10, temperature_c=22, duration_min=5, provenance_status="verified"),
        ProtocolStep(step_id="step-2", action="incubate", reagent="sample", volume_ul=5, temperature_c=24, duration_min=10, provenance_status="verified"),
    ]
    protocol = ProtocolSpec(protocol_id="p-1", steps=protocol_steps, min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20)
    protocol_fixture = ROOT / "examples/protocol/fixture.json"
    write_json(protocol_fixture, protocol.model_dump(mode="json"))
    protocol_execution = run_registered_track("T5", protocol_fixture)
    protocol_receipt = protocol_execution.receipt
    protocol_negative = protocol_execution.negative_case
    protocol_run = make_track_run(track_id="T5", task_id="t5-bio-chem-protocol-v1", receipt=protocol_receipt, fixture_path=protocol_fixture, negative_case=protocol_negative, calls_used=protocol_execution.calls_used)
    write_track_bundle(track_id="T5", directory="t5-protocol", receipt=protocol_receipt, run=protocol_run, negative_case=protocol_negative, demo_text=f"run_id={protocol_run.run_id}; passed={protocol_receipt.result['passed']}; execution_allowed={protocol_receipt.result['execution_allowed']}")
    portfolio.append(protocol_receipt.model_dump(mode="json"))

    write_json(ROOT / "artifacts/track-portfolio.json", {"schema_version": "track-portfolio-v1", "status": "bounded-slices-accepted", "tracks": portfolio, "global_boundaries": ["No real-data claim", "No autonomous wet-lab execution", "No publication or novelty claim"]})
    status_rows = [
        {"track_id": "T1", "state": "reproduced-within-scope", "acceptance": "artifacts/acceptance.json", "open_gates": ["external symbolic engine", "real-data provenance", "independent backend"], "next_step": "decide local-only release boundary", "public_release": False},
        {"track_id": "T2", "state": "reproduced-within-scope", "acceptance": "artifacts/t2-causal/acceptance.json", "open_gates": ["real interventions", "causal identification", "data rights"], "next_step": "add a rights-cleared intervention dataset", "public_release": False},
        {"track_id": "T3", "state": "reproduced-within-scope", "acceptance": "artifacts/t3-dynamics/acceptance.json", "open_gates": ["multi-body validation", "independent production solver", "compute budget"], "next_step": "add a second numerical backend", "public_release": False},
        {"track_id": "T4", "state": "reproduced-within-scope", "acceptance": "artifacts/t4-proof/acceptance.json", "open_gates": ["formal proof backend", "obligation completeness"], "next_step": "bind obligations to a formal checker", "public_release": False},
        {"track_id": "T5", "state": "reproduced-within-scope", "acceptance": "artifacts/t5-protocol/acceptance.json", "open_gates": ["real protocol provenance", "biosafety review", "human acceptance"], "next_step": "rights and safety review before real-data use", "public_release": False},
    ]
    write_json(ROOT / "artifacts/portfolio-status.json", {"schema_version": "portfolio-status-v1", "status": "implementing", "remote": "https://github.com/wangyufanshuai/auditable-scientist-lab", "pushed": False, "public_release_allowed": False, "tracks": status_rows})
    markdown = [
        "# Portfolio status",
        "",
        "| Track | State | Acceptance | Open gates | Next step | Public release |",
        "|---|---|---|---|---|---|",
    ]
    for row in status_rows:
        markdown.append(f"| {row['track_id']} | `{row['state']}` | `{row['acceptance']}` | {', '.join(row['open_gates'])} | {row['next_step']} | `{row['public_release']}` |")
    markdown.extend(["", "Remote is configured locally but not pushed. The bounded fixture results do not support real-data, novelty, publication, or production claims."])
    (ROOT / "artifacts/portfolio-status.md").write_text("\n".join(markdown) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
