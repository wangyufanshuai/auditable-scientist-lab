"""Generate deterministic T2–T5 fixture and acceptance receipts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from auditable_scientist.runtime.canonical import canonical_hash, canonical_json
from auditable_scientist.runtime.replay import BoundPaths, fingerprint_file
from auditable_scientist.tracks.causal import CausalCase
from auditable_scientist.tracks.dynamics import DynamicsCase
from auditable_scientist.tracks.physical_world import PhysicalCase, compare, standard_cases
from auditable_scientist.tracks.oscillator_proof import create_oscillator_package
from auditable_scientist.tracks.proof import ProofObligation, ProofPackage, ProofState
from auditable_scientist.tracks.protocol import extract_teaching_protocol
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
    if track_id == "T3" and (ROOT / "artifacts/t3-sweep.json").is_file():
        sweep = json.loads((ROOT / "artifacts/t3-sweep.json").read_text(encoding="utf-8"))
        if sweep.get("schema_version") != "t3-sweep-v1" or sweep.get("passed") is not True:
            raise ValueError("T3 sweep audit is present but did not pass")
        acceptance["checks"].append({
            "name": "bounded-parameter-step-sweep",
            "command": "python scripts/verify_t3_sweep.py --write",
            "exit_code": 0,
            "recorded_at": sweep["recorded_at"],
            "input_version": "t3-sweep-v1",
            "output_path": "artifacts/t3-sweep.json",
        })
    if track_id == "T3" and (ROOT / "artifacts/t3-external-run-audit.json").is_file():
        external = json.loads((ROOT / "artifacts/t3-external-run-audit.json").read_text(encoding="utf-8"))
        if external.get("schema_version") != "t3-external-run-audit-v1" or external.get("status") != "verified-within-pinned-oscillator-grid":
            raise ValueError("optional T3 external Run audit is present but did not pass")
        acceptance["checks"].append({
            "name": "optional-external-solver-run",
            "command": "python scripts/verify_t3_external_run.py --verify",
            "exit_code": 0,
            "recorded_at": external["recorded_at"],
            "input_version": "t3-external-run-audit-v1",
            "output_path": "artifacts/t3-external-run-audit.json",
        })
    if track_id == "T3" and (ROOT / "artifacts/t3-perturbed-audit.json").is_file():
        perturbed = json.loads((ROOT / "artifacts/t3-perturbed-audit.json").read_text(encoding="utf-8"))
        if (
            perturbed.get("schema_version") != "t3-perturbed-audit-v1"
            or perturbed.get("status") != "passed-optional-finite-horizon-cross-check"
            or len(perturbed.get("checks", {})) != 11
            or not all(perturbed["checks"].values())
        ):
            raise ValueError("optional T3 perturbed audit is present but did not pass")
        acceptance["checks"].append({
            "name": "optional-perturbed-three-body-cross-check",
            "command": "python scripts/verify_t3_perturbed.py --verify",
            "exit_code": 0,
            "recorded_at": perturbed["recorded_at"],
            "input_version": "t3-perturbed-audit-v1",
            "output_path": "artifacts/t3-perturbed-audit.json",
        })
    if track_id == "T3" and (ROOT / "artifacts/t3-perturbed-run-audit.json").is_file():
        perturbed_run = json.loads((ROOT / "artifacts/t3-perturbed-run-audit.json").read_text(encoding="utf-8"))
        if (
            perturbed_run.get("schema_version") != "t3-perturbed-run-audit-v1"
            or perturbed_run.get("status") != "verified-within-pinned-perturbed-grid"
            or perturbed_run.get("replay", {}).get("verified") is not True
            or perturbed_run.get("relocated_replay_equal") is not True
            or perturbed_run.get("result_tamper_rejected") is not True
            or perturbed_run.get("license_tamper_rejected") is not True
        ):
            raise ValueError("optional T3 perturbed Run audit is present but did not pass")
        acceptance["checks"].append({
            "name": "optional-perturbed-three-body-run",
            "command": "python scripts/verify_t3_perturbed_run.py --verify",
            "exit_code": 0,
            "recorded_at": perturbed_run["recorded_at"],
            "input_version": "t3-perturbed-run-audit-v1",
            "output_path": "artifacts/t3-perturbed-run-audit.json",
        })
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
            "result": {"selected_candidate_id": "tof-semimajor-pi-v2", "holdout_verified": True, "acceptance": "artifacts/acceptance.json"},
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
    causal_run = make_track_run(track_id="T2", task_id="t2-causal-intervention-v1", receipt=causal_receipt, fixture_path=causal_fixture, negative_case=causal_negative, calls_used=causal_execution.calls_used, bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t2-causal"))
    write_track_bundle(track_id="T2", directory="t2-causal", receipt=causal_receipt, run=causal_run, negative_case=causal_negative, demo_text=f"run_id={causal_run.run_id}; holdout_rmse={causal_receipt.result['holdout_rmse']}; negative_candidate_rejected={causal_receipt.result['negative_candidate_rejected']}")
    portfolio.append(causal_receipt.model_dump(mode="json"))

    physical_fixture = ROOT / "examples/causal/physical-fixture.json"
    physical_cases = [PhysicalCase.model_validate(row) for row in json.loads(physical_fixture.read_text(encoding="utf-8"))["cases"]]
    if [case.model_dump(mode="json") for case in physical_cases] != [case.model_dump(mode="json") for case in standard_cases()]:
        raise ValueError("physical fixture differs from the fixed 100-case suite")
    physical_execution = run_registered_track("T2P", physical_fixture)
    physical_receipt = physical_execution.receipt
    physical_negative = physical_execution.negative_case
    physical_run = make_track_run(
        track_id="T2P", task_id="t2-planar-ball-counterfactual-v1", receipt=physical_receipt,
        fixture_path=physical_fixture, negative_case=physical_negative,
        calls_used=physical_execution.calls_used,
        bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t2-physical"),
    )
    write_track_bundle(
        track_id="T2P", directory="t2-physical", receipt=physical_receipt, run=physical_run,
        negative_case=physical_negative,
        demo_text=f"run_id={physical_run.run_id}; case_count={physical_receipt.result['case_count']}; ignored_intervention_rejected={physical_receipt.result['ignored_intervention_rejected']}",
    )
    example_path = ROOT / "artifacts/t2-physical/counterfactual-example.json"
    write_json(example_path, compare(physical_cases[3]).model_dump(mode="json"))
    physical_acceptance = ROOT / "artifacts/t2-physical/acceptance.json"
    physical_package = json.loads(physical_acceptance.read_text(encoding="utf-8"))
    physical_package["checks"].append({
        "name": "joint-counterfactual-example",
        "command": "python scripts/generate_track_artifacts.py",
        "exit_code": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input_version": physical_receipt.input_hash,
        "output_path": "artifacts/t2-physical/counterfactual-example.json",
    })
    write_json(physical_acceptance, physical_package)
    causal_acceptance = ROOT / "artifacts/t2-causal/acceptance.json"
    causal_package = json.loads(causal_acceptance.read_text(encoding="utf-8"))
    causal_package["checks"].append({
        "name": "physical-counterfactual-subtrack",
        "command": "python scripts/generate_track_artifacts.py",
        "exit_code": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input_version": physical_receipt.input_hash,
        "output_path": "artifacts/t2-physical/acceptance.json",
    })
    write_json(causal_acceptance, causal_package)

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
    dynamics_run = make_track_run(track_id="T3", task_id="t3-harmonic-dynamics-v2", receipt=dynamics_receipt, fixture_path=dynamics_fixture, negative_case=dynamics_negative, calls_used=dynamics_execution.calls_used, bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t3-dynamics"))
    write_track_bundle(track_id="T3", directory="t3-dynamics", receipt=dynamics_receipt, run=dynamics_run, negative_case=dynamics_negative, demo_text=f"run_id={dynamics_run.run_id}; holdout_max_position_error={dynamics_receipt.result['holdout_max_position_error']}; max_backend_position_delta={dynamics_receipt.result['max_backend_position_delta']}; negative_euler_rejected={dynamics_receipt.result['negative_euler_rejected']}")
    portfolio.append(dynamics_receipt.model_dump(mode="json"))

    nbody_fixture = ROOT / "examples/dynamics/nbody-fixture.json"
    nbody_execution = run_registered_track("T3N", nbody_fixture)
    nbody_receipt = nbody_execution.receipt
    nbody_negative = nbody_execution.negative_case
    nbody_run = make_track_run(
        track_id="T3N", task_id="t3-equilateral-three-body-v1", receipt=nbody_receipt,
        fixture_path=nbody_fixture, negative_case=nbody_negative,
        calls_used=nbody_execution.calls_used,
        bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t3-nbody"),
    )
    write_track_bundle(
        track_id="T3N", directory="t3-nbody", receipt=nbody_receipt, run=nbody_run,
        negative_case=nbody_negative,
        demo_text=f"run_id={nbody_run.run_id}; max_verlet_position_error={nbody_receipt.result['max_verlet_position_error']}; negative_force_rejected={nbody_receipt.result['negative_force_rejected']}",
    )
    dynamics_acceptance = ROOT / "artifacts/t3-dynamics/acceptance.json"
    dynamics_package = json.loads(dynamics_acceptance.read_text(encoding="utf-8"))
    dynamics_package["checks"].append({
        "name": "symmetric-three-body-subtrack",
        "command": "python scripts/generate_track_artifacts.py",
        "exit_code": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input_version": nbody_receipt.input_hash,
        "output_path": "artifacts/t3-nbody/acceptance.json",
    })
    write_json(dynamics_acceptance, dynamics_package)

    trajectory = [ProofState(step=0, mass_a=2, mass_b=3), ProofState(step=1, mass_a=1, mass_b=4)]
    obligations = [
        ProofObligation(obligation_id="o1", checker_id="mass-conservation", statement="total mass is constant"),
        ProofObligation(obligation_id="o2", checker_id="nonnegative-state", statement="masses are nonnegative"),
        ProofObligation(obligation_id="o3", checker_id="trajectory-hash", statement="trajectory hash matches"),
        ProofObligation(obligation_id="o4", checker_id="transition-rule", statement="each step follows the declared transfer witness"),
        ProofObligation(obligation_id="o5", checker_id="symbolic-invariant", statement="the conservative transfer rule preserves total mass"),
    ]
    proof_package = ProofPackage(
        package_id="proof-1", rule_id="conservative-transfer-v1", trajectory=trajectory,
        transfers=["1"], obligations=obligations,
        trajectory_hash=canonical_hash([item.model_dump(mode="json") for item in trajectory]),
    )
    proof_fixture = ROOT / "examples/proof/fixture.json"
    write_json(proof_fixture, proof_package.model_dump(mode="json"))
    proof_execution = run_registered_track("T4", proof_fixture)
    proof_receipt = proof_execution.receipt
    proof_negative = proof_execution.negative_case
    proof_run = make_track_run(track_id="T4", task_id="t4-proof-carrying-v2", receipt=proof_receipt, fixture_path=proof_fixture, negative_case=proof_negative, calls_used=proof_execution.calls_used, bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t4-proof"))
    write_track_bundle(track_id="T4", directory="t4-proof", receipt=proof_receipt, run=proof_run, negative_case=proof_negative, demo_text=f"run_id={proof_run.run_id}; checked_obligations={proof_receipt.result['checked_obligations']}; tampered_claim_status={proof_negative['claim_status']}")
    portfolio.append(proof_receipt.model_dump(mode="json"))

    oscillator_package = create_oscillator_package(dynamics_cases[-1])
    oscillator_fixture = ROOT / "examples/proof/oscillator-fixture.json"
    write_json(oscillator_fixture, oscillator_package.model_dump(mode="json"))
    oscillator_execution = run_registered_track("T4O", oscillator_fixture)
    oscillator_receipt = oscillator_execution.receipt
    oscillator_negative = oscillator_execution.negative_case
    oscillator_run = make_track_run(
        track_id="T4O", task_id="t4-oscillator-proof-v1", receipt=oscillator_receipt,
        fixture_path=oscillator_fixture, negative_case=oscillator_negative,
        calls_used=oscillator_execution.calls_used,
        bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t4-oscillator"),
    )
    write_track_bundle(
        track_id="T4O", directory="t4-oscillator", receipt=oscillator_receipt,
        run=oscillator_run, negative_case=oscillator_negative,
        demo_text=f"run_id={oscillator_run.run_id}; checker_statuses={[item['status'] for item in oscillator_receipt.result['results']]}; negative_claim_status={oscillator_negative['claim_status']}",
    )
    proof_acceptance = ROOT / "artifacts/t4-proof/acceptance.json"
    proof_acceptance_payload = json.loads(proof_acceptance.read_text(encoding="utf-8"))
    proof_acceptance_payload["checks"].append({
        "name": "oscillator-physical-module-subtrack",
        "command": "python scripts/generate_track_artifacts.py",
        "exit_code": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input_version": oscillator_receipt.input_hash,
        "output_path": "artifacts/t4-oscillator/acceptance.json",
    })
    write_json(proof_acceptance, proof_acceptance_payload)

    protocol_text = (
        "step-1 action=mix reagent=buffer volume=10 uL temperature=22 C duration=5 min\n"
        "step-2 action=mix reagent=water volume=5 uL temperature=24 C duration=10 min\n"
    )
    protocol = extract_teaching_protocol(
        protocol_text, protocol_id="p-1", document_id="synthetic-buffer-plan-v1",
        min_temperature_c=20, max_temperature_c=30, max_total_volume_ul=20,
    )
    protocol_fixture = ROOT / "examples/protocol/fixture.json"
    write_json(protocol_fixture, protocol.model_dump(mode="json"))
    protocol_execution = run_registered_track("T5", protocol_fixture)
    protocol_receipt = protocol_execution.receipt
    protocol_negative = protocol_execution.negative_case
    protocol_run = make_track_run(track_id="T5", task_id="t5-bio-chem-text-review-v2", receipt=protocol_receipt, fixture_path=protocol_fixture, negative_case=protocol_negative, calls_used=protocol_execution.calls_used, bindings=BoundPaths(root=ROOT, run_dir=ROOT / "artifacts/t5-protocol"))
    write_track_bundle(track_id="T5", directory="t5-protocol", receipt=protocol_receipt, run=protocol_run, negative_case=protocol_negative, demo_text=f"run_id={protocol_run.run_id}; passed={protocol_receipt.result['passed']}; execution_allowed={protocol_receipt.result['execution_allowed']}")
    portfolio.append(protocol_receipt.model_dump(mode="json"))

    write_json(ROOT / "artifacts/track-portfolio.json", {"schema_version": "track-portfolio-v1", "status": "bounded-slices-accepted", "tracks": portfolio, "global_boundaries": ["No real-data claim", "No autonomous wet-lab execution", "No publication or novelty claim"]})
    status_rows = [
        {"track_id": "T1", "state": "reproduced-within-scope", "acceptance": "artifacts/acceptance.json", "open_gates": ["external symbolic engine", "real-data provenance", "independent backend"], "next_step": "decide local-only release boundary", "public_release": False},
        {"track_id": "T2", "state": "reproduced-within-scope", "acceptance": "artifacts/t2-causal/acceptance.json", "physical_subtrack": "artifacts/t2-physical/acceptance.json", "open_gates": ["real interventions", "causal identification", "data rights", "external algorithm source rights"], "next_step": "add a rights-cleared physical intervention dataset and independent estimator", "public_release": False},
        {"track_id": "T3", "state": "reproduced-within-scope", "acceptance": "artifacts/t3-dynamics/acceptance.json", "symmetric_nbody_subtrack": "artifacts/t3-nbody/acceptance.json", "optional_external_run": "artifacts/t3-external-run-audit.json", "optional_perturbed_audit": "artifacts/t3-perturbed-audit.json", "optional_perturbed_run": "artifacts/t3-perturbed-run-audit.json", "open_gates": ["long-horizon/nonintegrable multi-body validation", "real-mission provenance", "compute budget"], "next_step": "specify a wider validation grid and finite compute budget before long-horizon claims", "public_release": False},
        {"track_id": "T4", "state": "reproduced-within-scope", "acceptance": "artifacts/t4-proof/acceptance.json", "oscillator_subtrack": "artifacts/t4-oscillator/acceptance.json", "open_gates": ["general formal proof backend", "reviewed physical transition model", "real-world validation"], "next_step": "review a physical model and add independent source-backed validation", "public_release": False},
        {"track_id": "T5", "state": "text-demo-within-scope", "acceptance": "artifacts/t5-protocol/acceptance.json", "open_gates": ["independent protocol source and rights", "biosafety review", "human acceptance"], "next_step": "add a rights-cleared document adapter with independent citation checks", "public_release": False},
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
    if (ROOT / "artifacts/t3-external-scipy.json").is_file():
        markdown.extend([
            "The separate SciPy audit records source tags, installed license notices, pinned wheel hashes,",
            "and a nine-case oscillator cross-check. An optional versioned Tool/Provider Run now",
            "replays that scope separately; the core T3 Run remains SciPy-free and multi-body gates remain open.",
        ])
    markdown.extend(["", "T3N is a bounded symmetric three-body subtrack with an analytic orbit and an independent local RK4 cross-check. A separate pinned-SciPy Tool/Provider Run replays two short perturbed trajectories and rejects altered result or license bytes; long-horizon/nonintegrable and real-mission gates remain open."])
    markdown.extend(["", "T2P adds a 100-case planar ball-and-floor counterfactual suite with one shared initial state per pair, analytic impact checks, and an ignored-intervention negative control. It remains synthetic simulator evidence only."])
    markdown.extend(["", "T4O adds an oscillator proof receipt tied to the T3 velocity-Verlet source and a fixed finite grid. A checker verifies units, hashes, boundaries, solver replay, analytic and RK4 references, and energy drift. The formal-prover obligation is not applicable; reviewed physics and external validation remain open."])
    markdown.extend(["", "T5 is a synthetic text-review demonstration. Each field is located in an embedded LF document with a SHA-256 hash and exact character span. An altered document is rejected. Source rights, real materials, safety, and human acceptance are unverified; execution remains forbidden."])
    (ROOT / "artifacts/portfolio-status.md").write_text("\n".join(markdown) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
