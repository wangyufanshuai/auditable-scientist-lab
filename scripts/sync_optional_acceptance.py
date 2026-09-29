"""Reattach bounded optional receipts after the pinned base-track generator.

The base generator is included in seven committed Run source manifests. Keeping
this independent projection avoids invalidating those historical Run receipts.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STATUS_CONTRACT = ROOT / "docs/PORTFOLIO_STATUS_CONTRACT.json"
STATUS_NARRATIVE = ROOT / "docs/PORTFOLIO_STATUS_NARRATIVE.md"
T2_PROJECTILE_CONTRACT_SHA256 = "7f0591720ee87672004be5421e989a3d63bd89a8b385d22748e456701294467d"
T2_PROJECTILE_AUDIT_SHA256 = "ea58eabc93dadd0e90f39df8497e8e87c822df1bec25d6271a7296cfa0a9ebdf"
T2_PROJECTILE_PROTOCOL_SHA256 = "b9fa970bee858bbd66fc27c1a41e56559a76d0c961d4ed71096564fac5c35400"
T5_CROSS_READER_CONTRACT_SHA256 = "d8398495281ecd31f4ec6e25253055a5752e7a02ebb9a5d42e4b51a8d602108a"
T5_CROSS_READER_AUDIT_SHA256 = "894b7101574873eb4ebb181c8204f74c5b12943991515c7bbc5beed6f188cc6d"

OPTIONAL = (
    ("t2-causal", "context-sensitivity-negative-control", "t2-causal-sensitivity-audit.json",
     "t2-causal-sensitivity-audit-v1", "verified-synthetic-context-sensitivity-only",
     "python scripts/verify_t2_causal_sensitivity.py --verify", None,
     ("real_intervention_data", "causal_identification", "source_rights_reviewed",
      "research_candidate", "publication_ready"), ("negative_case_rejected",)),
    ("t2-physical", "independent-endpoint-estimator", "t2-independent-endpoint-audit.json",
     "t2-independent-endpoint-audit-v1", "verified-synthetic-endpoints-only",
     "python scripts/verify_t2_independent_endpoint.py --verify", None,
     ("real_intervention_data", "observational_causal_identification", "physical_model_validated",
      "source_rights_reviewed", "publication_ready"), ()),
    ("t2-physical", "independent-endpoint-run", "t2-independent-run-audit.json",
     "t2-independent-run-audit-v1", "verified-synthetic-endpoint-run-only",
     "python scripts/verify_t2_independent_run.py --verify", "run_id",
     ("real_intervention_data", "observational_causal_identification", "physical_model_validated",
      "source_rights_reviewed", "publication_ready"),
     ("relocated_replay_equal", "result_tamper_rejected", "snapshot_tamper_rejected")),
    ("t3-dynamics", "optional-expanded-horizon-grid", "t3-horizon-grid-audit.json",
     "t3-horizon-grid-audit-v1", "verified-finite-0.75-period-and-stress-rejection",
     "python scripts/verify_t3_horizon_grid.py --verify", None,
     ("chaotic_long_horizon_validated", "general_nbody_validated", "real_ephemerides",
      "mission_validation", "publication_ready", "one_period_stress_cases_admitted"), ()),
    ("t3-dynamics", "optional-published-figure-eight", "t3-figure-eight-audit.json",
     "t3-figure-eight-audit-v1", "passed-finite-published-figure-eight-numerics-only",
     '& "$env:TEMP\\auditable-scientist-figure8-20260927\\Scripts\\python.exe" scripts/verify_t3_figure_eight.py --verify',
     "protocol_sha256", (), ()),
    ("t3-dynamics", "optional-pythagorean-close-encounter", "t3-pythagorean-audit.json",
     "t3-pythagorean-audit-v1", "passed-bounded-close-encounter-numerics-only",
     '& "$env:TEMP\\auditable-scientist-figure8-20260927\\Scripts\\python.exe" scripts/verify_t3_pythagorean.py --verify',
     "protocol_sha256", (), ()),
    ("t4-proof", "exact-linear-invariant-subtrack", "t4-linear-formal-audit.json",
     "t4-linear-formal-audit-v1", "verified-exact-linear-class-only",
     "python scripts/verify_t4_linear_formal.py --verify", "input_sha256",
     ("general_formal_backend", "physical_model_validated", "real_data", "publication_ready"), ()),
    ("t4-proof", "exact-linear-invariant-run", "t4-linear-run-audit.json",
     "t4-linear-run-audit-v1", "verified-exact-linear-class-only",
     "python scripts/verify_t4_linear_run.py --verify", "run_id",
     ("general_formal_backend", "physical_model_validated", "real_data", "publication_ready"),
     ("relocated_replay_equal", "result_tamper_rejected", "snapshot_tamper_rejected")),
    ("t4-proof", "exact-verlet-discrete-invariant", "t4-verlet-invariant-audit.json",
     "t4-verlet-invariant-audit-v1", "verified-exact-verlet-discrete-invariant-only",
     "python scripts/verify_t4_verlet_invariant.py --verify", "protocol_sha256",
     ("floating_implementation_proved", "physical_model_validated", "general_formal_backend",
      "nonlinear_dynamics_proved", "real_data", "publication_ready"), ()),
    ("t4-proof", "floating-implementation-conformance", "t4-floating-conformance-audit.json",
     "t4-floating-conformance-audit-v1", "verified-finite-floating-output-conformance-only",
     "python scripts/verify_t4_floating_conformance.py --verify", "t4_parent_input_hash",
     ("floating_implementation_proved", "physical_model_validated", "general_formal_backend",
      "real_data", "publication_ready"), ("positive_cases_passed", "negative_controls_rejected")),
    ("t5-protocol", "optional-t5-pbs-source-run", "t5-pbs-source-run-audit.json",
     "t5-pbs-source-run-audit-v1", "verified-read-only-source-inventory-only",
     "python scripts/verify_t5_pbs_source_run.py --verify", "run_id",
     ("independent_procedure_validation", "biosafety_review_complete", "human_acceptance",
      "execution_allowed"),
     ("relocated_replay_equal", "result_tamper_rejected", "snapshot_tamper_rejected")),
)

REPORT_NOTES = {
    "t2-causal": (
        "The optional [context-sensitivity negative control](../t2-causal-sensitivity-audit.json) "
        "keeps the declared synthetic outcome dependent on `do(intervention_value)` only "
        "and rejects a fixed candidate that leaks `context_value` on holdout. This is a "
        "semantic control for the fixture, not causal identification, exchangeability, "
        "real intervention evidence, source-rights review, or a research-candidate claim.\n"
    ),
    "t2-physical": (
        "An optional impact-to-impact endpoint estimator independently recomputes 124\n"
        "synthetic factual and intervened horizontal outcomes, including 24 varied\n"
        "holdout states. The 84-case holdout effect RMSE is approximately 8.7e-16 m;\n"
        "an ignored-intervention estimator has approximately 0.266 m RMSE. This checks\n"
        "only the declared simulator and does not establish real causal identification.\n\n"
        "The optional `python scripts/verify_t2_independent_run.py --verify` checks a\n"
        "shared Tool/Policy/Provider Run with both fixture snapshots, source and environment\n"
        "fingerprints, one tool call, moved replay, mutation controls, and policy denials.\n"
        "Its real-world Claim remains `unverified`.\n"
    ),
    "t3-dynamics": (
        "The optional expanded [finite-horizon audit](../t3-horizon-grid-audit.json) "
        "admits two preflight-selected 0.75-period synthetic trajectories under a "
        "12,000 DOP853-call and 35,000 fixed-step budget. Both one-period stress "
        "cases cross the $0.5a$ close-approach threshold and are excluded from "
        "accuracy claims. Pinned SciPy `python scripts/verify_t3_horizon_grid.py --verify` "
        "recomputes the numerical receipt; core acceptance checks saved source bytes, "
        "scope, budget, and gates without importing SciPy. The inherited fixture "
        "holdout label is not untouched scientific validation.\n"
    ),
    "t4-proof": (
        "The optional exact linear-invariant audit proves two declared rational linear\n"
        "identities for all states and controls, and rejects a leaky negative control.\n"
        "`python scripts/verify_t4_linear_formal.py --verify` and the independent\n"
        "`python scripts/check_t4_linear_certificate.py` both passed. Twelve targeted\n"
        "tests cover a new matrix and malformed or forged certificates. This is a\n"
        "mathematical statement about declared matrices, not physical-model validation.\n\n"
        "The separate `python scripts/verify_t4_linear_run.py --verify` binds the exact\n"
        "certificate to one policy-guarded Tool/Provider Run. Replay checks its input,\n"
        "source, environment, seed, event chain, and output; relocation and tamper controls\n"
        "pass. The Run's physical Claim remains `unverified`.\n\n"
        "The optional [finite floating conformance audit](../t4-floating-conformance-audit.json)\n"
        "compares T3 velocity-Verlet outputs with an independent exact-rational\n"
        "map over three finite cases and rejects explicit Euler plus a perturbed update.\n"
        "It records a numerical error envelope, not a formal proof of floating execution;\n"
        "physical-model, real-data, and publication gates remain open.\n"
    ),
}
REPORT_MARKERS = {
    "t2-causal": "The optional [context-sensitivity negative control]",
    "t2-physical": "An optional impact-to-impact endpoint estimator",
    "t3-dynamics": "The optional expanded [finite-horizon audit]",
    "t4-proof": "The optional exact linear-invariant audit",
}
VERLET_REPORT_NOTE = (
    "The optional [exact Verlet invariant audit](../t4-verlet-invariant-audit.json) "
    "rechecks one rational velocity-Verlet matrix with an exact quadratic invariant "
    "and rejects explicit Euler. It proves only this declared discrete map; floating "
    "execution, physical validation, nonlinear dynamics, and real-data gates remain open.\n"
)
FLOATING_REPORT_NOTE = (
    "The optional [finite floating conformance audit](../t4-floating-conformance-audit.json) "
    "compares final position and maximum energy drift in three finite velocity-Verlet "
    "cases with an independent exact rational map, and rejects explicit Euler plus a "
    "perturbed update. It records a numerical "
    "error envelope; it does not prove arbitrary floating execution or validate the physical "
    "model, real data, or publication readiness.\n"
)
PYTHAGOREAN_REPORT_NOTE = (
    "The optional [Pythagorean close-encounter audit](../t3-pythagorean-audit.json) "
    "compares a published 3–4–5 three-body state and one authored perturbation "
    "with pinned DOP853 and independently implemented adaptive RK4. Both stop at "
    "the predeclared 0.001 pair-separation guard near t=15.8299. All 12 finite "
    "engineering checks pass within budget; no post-guard orbit, Lyapunov "
    "estimate, untouched scientific holdout, or mission validation is claimed. "
    "Pinned SciPy `python scripts/verify_t3_pythagorean.py --verify` recomputes "
    "the receipt; core acceptance checks saved arithmetic and scope.\n"
)
PROJECTILE_REPORT_NOTE = (
    "The optional [real projectile source inventory](../t2-projectile-source-audit.json) "
    "pins a 2025 article PDF and two supplementary workbooks without redistributing "
    "them. The measured workbook contains 179 samples from 30 trials, while the "
    "article reports 82 experiments. Fifteen trial IDs have a declared `v0` above "
    "the article's stated launcher range; the column's meaning is unresolved. "
    "Supplement reuse rights, coverage, physical-model comparison, trial-level "
    "holdout, and causal identification remain open. Official supplement rights "
    "language is reviewed, but raw-XLSX redistribution remains unconfirmed. The [blocked model protocol] "
    "(../docs/T2_PROJECTILE_MODEL_PROTOCOL.md) freezes a whole-trial split but "
    "permits no fit until those source gates close. The Claim is `unverified`.\n"
)


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _render_json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _receipt_row(spec: tuple) -> dict:
    directory, name, filename, schema, status, command, input_key, blocked, required = spec
    audit = _load(f"artifacts/{filename}")
    if (
        audit.get("schema_version") != schema or audit.get("status") != status
        or any(audit.get("boundaries", {}).get(key) is not False for key in blocked)
        or any(audit.get(key) is not True for key in required)
    ):
        raise ValueError(f"optional audit is missing or exceeds its boundary: {filename}")
    if filename == "t3-horizon-grid-audit.json" and (
        audit.get("boundaries", {}).get("smooth_synthetic_0_75_period_grid") is not True
        or set(audit.get("checks", {})) != {
            "two_smooth_source_configurations", "fine_verlet_position", "fine_verlet_velocity",
            "rk4_position", "verlet_convergence", "energy_drift", "angular_momentum_drift",
            "center_of_mass_drift", "smooth_separation", "stress_excluded", "compute_budget",
        }
        or not all(value is True for value in audit["checks"].values())
    ):
        raise ValueError("T3 horizon grid cannot enter acceptance")
    if filename == "t2-causal-sensitivity-audit.json":
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_t2_causal_sensitivity.py"), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=30,
        )
        if process.returncode != 0 or json.loads(process.stdout).get("status") != status:
            raise ValueError(f"T2 context sensitivity dynamic check failed: {process.stderr.strip()}")
    if filename == "t4-verlet-invariant-audit.json":
        protocol_path = ROOT / "docs/T4_VERLET_INVARIANT_PROTOCOL.json"
        solver_path = ROOT / "src/auditable_scientist/tracks/dynamics.py"
        expected_boundaries = {
            "exact_discrete_invariant_class": True,
            "floating_implementation_proved": False,
            "physical_model_validated": False,
            "general_formal_backend": False,
            "nonlinear_dynamics_proved": False,
            "real_data": False,
            "publication_ready": False,
            "claim_status": "unverified",
        }
        source_files = audit.get("source_files", [])
        if (
            audit.get("protocol_sha256") != hashlib.sha256(protocol_path.read_bytes()).hexdigest()
            or audit.get("boundaries") != expected_boundaries
            or audit.get("positive_certificate", {}).get("residual_matrix") != [["0", "0"], ["0", "0"]]
            or audit.get("negative_control", {}).get("rejected") is not True
            or {item.get("path") for item in source_files} != {
                "docs/T4_VERLET_INVARIANT_PROTOCOL.json",
                "src/auditable_scientist/tracks/dynamics.py",
            }
            or next((item.get("sha256") for item in source_files
                     if item.get("path") == "src/auditable_scientist/tracks/dynamics.py"), None)
            != hashlib.sha256(solver_path.read_bytes()).hexdigest()
        ):
            raise ValueError("T4 Verlet invariant audit cannot enter acceptance")
    if filename == "t4-floating-conformance-audit.json":
        protocol_path = ROOT / "docs/T4_FLOATING_CONFORMANCE_PROTOCOL.json"
        solver_path = ROOT / "src/auditable_scientist/tracks/dynamics.py"
        checker_path = ROOT / "scripts/verify_t4_floating_conformance.py"
        expected_boundaries = {
            "finite_horizon_output_conformance": True,
            "finite_error_envelope": True,
            "floating_implementation_proved": False,
            "exact_rational_reference": True,
            "physical_model_validated": False,
            "general_formal_backend": False,
            "real_data": False,
            "publication_ready": False,
            "claim_status": "unverified",
        }
        source_files = audit.get("source_files", [])
        expected_sources = {
            "docs/T4_FLOATING_CONFORMANCE_PROTOCOL.json": protocol_path,
            "src/auditable_scientist/tracks/dynamics.py": solver_path,
            "scripts/verify_t4_floating_conformance.py": checker_path,
        }
        if (
            audit.get("protocol_sha256") != hashlib.sha256(protocol_path.read_bytes()).hexdigest()
            or audit.get("boundaries") != expected_boundaries
            or audit.get("positive_cases_passed") is not True
            or audit.get("negative_controls_rejected") is not True
            or set(item.get("path") for item in source_files) != set(expected_sources)
            or any(item.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
                   or item.get("bytes") != path.stat().st_size
                   for item in source_files for path in [expected_sources[item.get("path")]])
        ):
            raise ValueError("T4 floating conformance audit cannot enter acceptance")
        process = subprocess.run(
            [sys.executable, str(checker_path), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=30,
        )
        if process.returncode != 0 or json.loads(process.stdout).get("status") != status:
            raise ValueError(f"T4 floating conformance dynamic check failed: {process.stderr.strip()}")
    if filename == "t3-figure-eight-audit.json" and (
        audit.get("scientific_boundaries", {}).get("claim_status") != "unverified"
        or audit.get("scientific_boundaries", {}).get("untouched_scientific_holdout") is not False
        or audit.get("scientific_boundaries", {}).get("chaotic_regime_validated") is not False
        or audit.get("scientific_boundaries", {}).get("real_mission_validated") is not False
        or audit.get("protocol_sha256") !=
        "7828754b52af988780a5e4679b017ff5c20d1aa490cc9720d250b1e719643a3d"
        or set(audit.get("checks", {})) != {
            "finite_three_case_inventory", "endpoint_position", "endpoint_velocity",
            "refinement", "energy", "angular_momentum", "center_of_mass",
            "separation", "one_period_closure", "negative_repulsive_force",
            "compute_budget",
        }
        or not all(value is True for value in audit["checks"].values())
    ):
        raise ValueError("T3 figure-eight audit cannot enter acceptance")
    if filename == "t3-pythagorean-audit.json" and (
        audit.get("scientific_boundaries", {}).get("claim_status") != "unverified"
        or audit.get("scientific_boundaries", {}).get("untouched_scientific_holdout") is not False
        or audit.get("scientific_boundaries", {}).get("chaotic_regime_validated") is not False
        or audit.get("scientific_boundaries", {}).get("real_mission_validated") is not False
        or audit.get("protocol_sha256") !=
        "f9848ae9fb01565f51d3560688a6e5cc30cfd09a274dba2d165bfa309de29927"
        or set(audit.get("checks", {})) != {
            "initial_state", "finite_pre_event_comparison", "external_energy",
            "independent_energy", "angular_momentum", "center_of_mass",
            "terminal_close_approach", "event_pair_match", "event_time_agreement",
            "historical_event_window", "negative_wrong_force", "compute_budget",
        }
        or not all(value is True for value in audit["checks"].values())
    ):
        raise ValueError("T3 Pythagorean audit cannot enter acceptance")
    recorded_at = audit.get("recorded_at")
    if not isinstance(recorded_at, str):
        raise ValueError(f"optional audit has no timestamp: {filename}")
    timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"optional audit timestamp is naive: {filename}")
    input_version = audit.get(input_key) if input_key else schema
    if not isinstance(input_version, str) or not input_version:
        raise ValueError(f"optional audit has no input version: {filename}")
    return {
        "name": name, "command": command, "exit_code": 0,
        "recorded_at": recorded_at, "input_version": input_version,
        "output_path": f"artifacts/{filename}",
    }


def _insert_or_replace(checks: list[dict], row: dict) -> None:
    matches = [index for index, check in enumerate(checks) if check.get("name") == row["name"]]
    if len(matches) > 1:
        raise ValueError(f"duplicate acceptance row: {row['name']}")
    if matches:
        checks[matches[0]] = row
    else:
        checks.append(row)


def _status_markdown(contract: dict) -> str:
    rows = [
        "# Portfolio status", "",
        "| Track | State | Acceptance | Open gates | Next step | Public release |",
        "|---|---|---|---|---|---|",
    ]
    for item in contract["tracks"]:
        rows.append(
            f"| {item['track_id']} | `{item['state']}` | `{item['acceptance']}` | "
            f"{', '.join(item['open_gates'])} | {item['next_step']} | `{item['public_release']}` |"
        )
    narrative = STATUS_NARRATIVE.read_text(encoding="utf-8")
    if "The [expanded finite-horizon audit]" not in narrative or "Claim stays `unverified`" not in narrative:
        raise ValueError("portfolio narrative omits a bounded evidence boundary")
    return "\n".join(rows) + "\n\n" + narrative


def _t5_cross_reader_receipt(audit: dict | None = None,
                             *, verify_dynamic: bool = True) -> dict:
    """Check the saved cross-reader inventory, then rerun when both readers exist."""

    audit_path = ROOT / "artifacts/t5-pbs-cross-reader-audit.json"
    contract_path = ROOT / "docs/T5_PBS_CROSS_READER_CONTRACT.json"
    if (hashlib.sha256(audit_path.read_bytes()).hexdigest() != T5_CROSS_READER_AUDIT_SHA256
            or hashlib.sha256(contract_path.read_bytes()).hexdigest() !=
            T5_CROSS_READER_CONTRACT_SHA256):
        raise ValueError("T5 cross-reader receipt or contract bytes differ")
    audit = audit if audit is not None else _load("artifacts/t5-pbs-cross-reader-audit.json")
    contract = _load("docs/T5_PBS_CROSS_READER_CONTRACT.json")
    source = _load("docs/T5_PBS_SOURCE_CONTRACT.json")
    expected_boundaries = {
        "cross_reader_text_coverage": True, "source_pdf_redistributed": False,
        "complete_semantic_omission_review": False,
        "independent_procedure_validation": False,
        "biosafety_review_complete": False, "human_acceptance": False,
        "execution_allowed": False, "claim_status": "unverified",
    }
    expected_controls = {
        "safety_heading_omission_rejected": True,
        "numbered_step_omission_rejected": True,
        "non_anchor_text_omission_rejected": True,
    }
    expected_sources = {
        "scripts/verify_t5_pbs_cross_reader.py",
        "docs/T5_PBS_CROSS_READER_CONTRACT.json",
        "docs/T5_PBS_SOURCE_CONTRACT.json",
        "scripts/verify_t5_pbs_source.py",
    }
    if (contract.get("schema_version") != "t5-pbs-cross-reader-contract-v1"
            or audit.get("schema_version") != "t5-pbs-cross-reader-audit-v1"
            or audit.get("status") != "verified-three-page-cross-reader-text-coverage-only"
            or audit.get("source_pdf_sha256") != contract.get("source_pdf_sha256")
            or contract.get("source_pdf_sha256") !=
            "184b4d211aa8c1a2fcde0eb06a2fd8ae57727c28f1a2b41e5fbfd94b5f8c1271"
            or contract.get("source_contract_sha256") !=
            hashlib.sha256((ROOT / "docs/T5_PBS_SOURCE_CONTRACT.json").read_bytes()).hexdigest()
            or audit.get("source_contract_sha256") != contract["source_contract_sha256"]
            or audit.get("cross_reader_contract_sha256") != T5_CROSS_READER_CONTRACT_SHA256
            or audit.get("boundaries") != expected_boundaries
            or contract.get("boundaries") != expected_boundaries
            or audit.get("negative_controls") != expected_controls
            or audit.get("numbered_steps") != [1, 2, 3, 4, 5, 6]
            or audit.get("extractors") != {
                "pypdf_version": "6.15.0", "pdftotext_version": "26.02.0",
                "pdftotext_executable_sha256":
                "c7392e92727abbb54c07662268eef7348e4edd1cd741c264e20f76e757c0b467",
                "pdftotext_binary_redistributed": False,
                "pdftotext_binary_distribution_license_reviewed": False,
            }
            or len(audit.get("pages", [])) != 3
            or len(audit.get("anchors", [])) != 11
            or len(audit.get("sections", [])) != 4
            or {row.get("path") for row in audit.get("source_files", [])} != expected_sources
            or len(audit.get("source_files", [])) != len(expected_sources)):
        raise ValueError("T5 cross-reader source, coverage, or boundary differs")
    for index, row in enumerate(audit["pages"]):
        hashes = row.get("line_sha256", [])
        if (row.get("page") != index + 1
                or row.get("poppler_text_sha256") != contract["poppler_page_text_sha256"][index]
                or row.get("pypdf_text_sha256") != contract["pypdf_page_text_sha256"][index]
                or len(hashes) != row.get("line_count")
                or any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes)
                or row.get("shared_fraction", 0) < 0.94):
            raise ValueError("T5 cross-reader page or ordered-line inventory differs")
    if ([(row.get("key"), row.get("page")) for row in audit["anchors"]] !=
            [(row["key"], row["page"]) for row in source["anchors"]]
            or [(row.get("key"), row.get("page")) for row in audit["sections"]] !=
            [(row["key"], row["page"]) for row in contract["section_markers"]]):
        raise ValueError("T5 independent citation or section inventory differs")
    for row in audit["source_files"]:
        path = ROOT / row["path"]
        if (hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256")
                or path.stat().st_size != row.get("bytes")):
            raise ValueError(f"T5 cross-reader verifier source differs: {row['path']}")
    timestamp = audit.get("recorded_at")
    if (not isinstance(timestamp, str)
            or datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("T5 cross-reader timestamp differs")
    dynamic = False
    local_executable = shutil.which("pdftotext")
    matching_extractor = (
        local_executable is not None and
        hashlib.sha256(Path(local_executable).read_bytes()).hexdigest() ==
        contract["poppler"]["local_executable_sha256"]
    )
    if (verify_dynamic and (ROOT / "data/references/t5_pbs/protocols_io_p4rdqv6.pdf").is_file()
            and matching_extractor and importlib.util.find_spec("pypdf") is not None):
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_t5_pbs_cross_reader.py"), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=40,
        )
        if (process.returncode != 0
                or json.loads(process.stdout).get("status") != audit["status"]):
            raise ValueError(f"T5 cross-reader dynamic check failed: {process.stderr.strip()}")
        dynamic = True
    verifier_source = next(row for row in audit["source_files"]
                           if row["path"] == "scripts/verify_t5_pbs_cross_reader.py")
    return {"status": audit["status"], "recorded_at": timestamp,
            "verifier_sha256": verifier_source["sha256"],
            "dynamic_verified_here": dynamic}


def _t2_projectile_receipt(audit: dict | None = None,
                           *, verify_dynamic: bool = True) -> dict:
    """Pin the source inventory and recompute it when all local readers exist."""

    audit_path = ROOT / "artifacts/t2-projectile-source-audit.json"
    contract_path = ROOT / "docs/T2_PROJECTILE_SOURCE_CONTRACT.json"
    if (hashlib.sha256(audit_path.read_bytes()).hexdigest() != T2_PROJECTILE_AUDIT_SHA256
            or hashlib.sha256(contract_path.read_bytes()).hexdigest() !=
            T2_PROJECTILE_CONTRACT_SHA256):
        raise ValueError("T2 projectile receipt or contract bytes differ")
    audit = audit if audit is not None else _load("artifacts/t2-projectile-source-audit.json")
    contract = _load("docs/T2_PROJECTILE_SOURCE_CONTRACT.json")
    expected_boundaries = {
        "source_tracked_real_measurements": True,
        "complete_reported_experiment_set": False,
        "supplement_rights_reviewed": True,
        "velocity_column_semantics_reviewed": False,
        "physical_model_validated": False,
        "causal_effect_identified": False,
        "scientific_holdout": False,
        "research_candidate": False,
        "publication_ready": False,
        "claim_status": "unverified",
    }
    inventory = audit.get("measured_inventory", {})
    source_files = audit.get("source_files", [])
    expected_sources = {
        "scripts/verify_t2_projectile_source.py",
        "docs/T2_PROJECTILE_SOURCE_CONTRACT.json",
    }
    fingerprints = audit.get("local_file_fingerprints", [])
    if (contract.get("schema_version") != "t2-projectile-source-contract-v1"
            or audit.get("schema_version") != "t2-projectile-source-audit-v1"
            or audit.get("status") != "verified-30-trial-real-source-inventory-only"
            or audit.get("contract_sha256") != T2_PROJECTILE_CONTRACT_SHA256
            or audit.get("article") != contract.get("article")
            or audit.get("reader") != contract.get("reader")
            or audit.get("rights_review") != contract.get("rights_review")
            or contract.get("article", {}).get("doi") != "10.1088/1361-6552/add2c5"
            or contract["article"].get("paper_reported_experiments") != 82
            or audit.get("boundaries") != expected_boundaries
            or contract.get("boundaries") != expected_boundaries
            or inventory.get("sample_count") != 179
            or inventory.get("trial_count") != 30
            or [row.get("trial_id") for row in inventory.get("trials", [])] != list(range(2, 32))
            or len(inventory.get("observed_declared_speed_above_paper_bound_trials", [])) != 15
            or audit.get("numerical_spreadsheet") != {
                "formula_cells": 3507, "admitted_as_observations": False,
            }
            or audit.get("negative_controls") != {
                "missing_sample_rejected": True,
                "nonfinite_measurement_rejected": True,
                "duplicate_time_rejected": True,
                "changed_within_trial_input_rejected": True,
            }
            or len(audit.get("article_page_text_sha256", [])) != 19
            or any(not re.fullmatch(r"[a-f0-9]{64}", value)
                   for value in audit["article_page_text_sha256"])
            or {row.get("path") for row in source_files} != expected_sources
            or len(source_files) != len(expected_sources)
            or {row.get("role") for row in fingerprints} != set(contract.get("files", {}))
            or len(fingerprints) != 3):
        raise ValueError("T2 projectile source inventory or scientific boundary differs")
    for row in fingerprints:
        expected = contract["files"][row["role"]]
        if (row.get("filename") != expected["local_name"]
                or row.get("sha256") != expected["sha256"]
                or row.get("bytes") != expected["bytes"]
                or row.get("redistributed") is not False):
            raise ValueError("T2 projectile source fingerprint or redistribution differs")
    for row in source_files:
        path = ROOT / row["path"]
        if (hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256")
                or path.stat().st_size != row.get("bytes")):
            raise ValueError(f"T2 projectile verifier source differs: {row['path']}")
    timestamp = audit.get("recorded_at")
    if not isinstance(timestamp, str):
        raise ValueError("T2 projectile timestamp is missing")
    stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("T2 projectile timestamp is naive")
    local = ROOT / "data/references/t2_projectile_wadsworth_2025"
    dynamic = False
    if (verify_dynamic
            and all((local / item["local_name"]).is_file()
                    for item in contract["files"].values())
            and importlib.util.find_spec("openpyxl") is not None
            and importlib.util.find_spec("pypdf") is not None):
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_t2_projectile_source.py"), "--verify"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=60,
        )
        if (process.returncode != 0
                or json.loads(process.stdout).get("status") != audit["status"]):
            raise ValueError(f"T2 projectile dynamic check failed: {process.stderr.strip()}")
        dynamic = True
    verifier = next(row for row in source_files
                    if row["path"] == "scripts/verify_t2_projectile_source.py")
    return {"status": audit["status"], "recorded_at": timestamp,
            "verifier_sha256": verifier["sha256"],
            "dynamic_verified_here": dynamic}


def _t2_projectile_protocol() -> dict:
    """Check the frozen design without treating it as a model result."""

    path = ROOT / "docs/T2_PROJECTILE_MODEL_PROTOCOL.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != T2_PROJECTILE_PROTOCOL_SHA256:
        raise ValueError("T2 projectile model protocol bytes differ")
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t2_projectile_model_protocol.py")],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    if process.returncode != 0:
        raise ValueError(f"T2 projectile model protocol check failed: {process.stderr.strip()}")
    result = json.loads(process.stdout)
    if (result.get("status") != "verified-blocked-protocol-only"
            or result.get("fit_permitted") is not False):
        raise ValueError("T2 projectile model protocol exceeds its blocked scope")
    return result


def desired_outputs() -> dict[Path, str]:
    """Build all outputs in memory before writing any file."""

    bundles = {
        directory: _load(f"artifacts/{directory}/acceptance.json")
        for directory in ("t2-causal", "t2-physical", "t3-dynamics", "t4-proof", "t5-protocol")
    }
    rows = [_receipt_row(spec) for spec in OPTIONAL]
    for spec, row in zip(OPTIONAL, rows):
        _insert_or_replace(bundles[spec[0]]["checks"], row)
    root = _load("artifacts/acceptance.json")
    desat = _load("artifacts/t1-maven-desat-sensitivity-audit.json")
    expected_desat_checks = {
        "source_and_baseline_bound", "all_24_scenarios", "split_no_impulse",
        "orthonormal_basis", "opposite_sign_oddness", "step_refinement",
        "finite_responses", "compute_budget",
    }
    if (desat.get("schema_version") != "t1-maven-desat-sensitivity-audit-v1"
            or desat.get("status") != "passed-conditional-impulse-sensitivity-only"
            or desat.get("protocol_sha256") !=
            "cc6d520386505f73a2850d3dcee7dc8d3ba08f2e0901e924360c56eb3c78237d"
            or set(desat.get("checks", {})) != expected_desat_checks
            or not all(value is True for value in desat["checks"].values())
            or desat.get("boundaries") != {
                "conditional_response_scale": True, "actual_desat_in_arcs": False,
                "statistical_uncertainty_interval": False, "independent_observables": False,
                "scientific_holdout": False, "mission_validation": False}):
        raise ValueError("T1 MAVEN desat audit cannot enter acceptance")
    desat_sources = [item for item in desat.get("source_files", [])
                     if item.get("path") == "scripts/verify_t1_maven_desat_sensitivity.py"]
    recorded_at = desat.get("recorded_at")
    if (len(desat_sources) != 1 or not isinstance(recorded_at, str)
            or datetime.fromisoformat(recorded_at.replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("T1 MAVEN desat source or timestamp differs")
    _insert_or_replace(root["checks"], {
        "name": "optional-t1-maven-desat-sensitivity",
        "command": "python scripts/verify_t1_maven_desat_sensitivity.py --verify",
        "exit_code": 0, "recorded_at": recorded_at,
        "input_version": desat_sources[0]["sha256"],
        "output_path": "artifacts/t1-maven-desat-sensitivity-audit.json",
    })
    srp = _load("artifacts/t1-maven-srp-sensitivity-audit.json")
    srp_sources = [item for item in srp.get("source_files", [])
                   if item.get("path") == "scripts/verify_t1_maven_srp_sensitivity.py"]
    srp_timestamp = srp.get("recorded_at")
    srp_checks = {
        "source_and_baseline_bound", "zero_coefficient_reproduces_prior",
        "all_cases_reported", "monotonic_radial_response_scale", "step_refinement",
        "finite_states_and_responses", "compute_budget",
    }
    if (srp.get("schema_version") != "t1-maven-srp-sensitivity-audit-v1"
            or srp.get("status") != "passed-conditional-srp-sensitivity-only"
            or srp.get("protocol_sha256") !=
            "68352f9158755dca98baeffe51bd08c65112c2542548ff503ec7a62bdae5e470"
            or set(srp.get("checks", {})) != srp_checks
            or not all(value is True for value in srp["checks"].values())
            or srp.get("boundaries", {}).get("claim_status") != "unverified"
            or srp["boundaries"].get("mission_validation") is not False
            or len(srp_sources) != 1 or not isinstance(srp_timestamp, str)
            or datetime.fromisoformat(srp_timestamp.replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("T1 MAVEN SRP audit cannot enter acceptance")
    _insert_or_replace(root["checks"], {
        "name": "optional-t1-maven-srp-sensitivity",
        "command": "python scripts/verify_t1_maven_srp_sensitivity.py --verify",
        "exit_code": 0, "recorded_at": srp_timestamp,
        "input_version": srp_sources[0]["sha256"],
        "output_path": "artifacts/t1-maven-srp-sensitivity-audit.json",
    })
    ops = _load("artifacts/t1-maven-ops-event-search-audit.json")
    ops_sources = [item for item in ops.get("source_files", [])
                   if item.get("path") == "scripts/verify_t1_maven_ops_events.py"]
    ops_timestamp = ops.get("recorded_at")
    if (ops.get("schema_version") != "t1-maven-ops-event-search-audit-v1"
            or ops.get("status") != "catalog-inspected-not-mission-validation"
            or ops.get("protocol_sha256") !=
            "07f7dcc05063d1102835fc1d8549bb776b8c2b6f1ee3dce12f31060e919aee33"
            or ops.get("records_checked") != 185321
            or len(ops_sources) != 1
            or not isinstance(ops_timestamp, str)
            or datetime.fromisoformat(ops_timestamp.replace("Z", "+00:00")).tzinfo is None
            or ops.get("boundaries") != {
                "catalog_scope_only": True, "event_list_complete_for_desats": False,
                "impulse_vectors_admitted": False, "independent_observables": False,
                "scientific_holdout": False, "mission_validation": False,
                "claim_status": "unverified"}
            or [item.get("all_arc_events") for item in ops.get("arcs", [])] != [2, 0]
            or any(item.get("keyword_arc_hits") != [] for item in ops["arcs"])):
        raise ValueError("T1 MAVEN operations-event audit cannot enter acceptance")
    _insert_or_replace(root["checks"], {
        "name": "optional-t1-maven-ops-event-search",
        "command": "python scripts/verify_t1_maven_ops_events.py --verify",
        "exit_code": 0, "recorded_at": ops_timestamp,
        "input_version": ops_sources[0]["sha256"],
        "output_path": "artifacts/t1-maven-ops-event-search-audit.json",
    })
    sff = _load("artifacts/t1-maven-sff-exploratory-audit.json")
    sff_timestamp = sff.get("recorded_at")
    if (sff.get("schema_version") != "t1-maven-sff-exploratory-audit-v1"
            or sff.get("status") != "verified-local-source-inventory-only"
            or sff.get("inventory_sha256") !=
            "abbff6aa64720986a920b0bc9cdb8d9283d6b3b8877bce8b9afcd7b15feae6d0"
            or len(sff.get("files", [])) != 9
            or len(sff.get("same_records_except_production_time", [])) != 4
            or sff.get("boundaries", {}).get("claim_status") != "unverified"
            or sff["boundaries"].get("values_admitted_to_dynamics_model") is not False
            or sff["boundaries"].get("mission_validation") is not False
            or not isinstance(sff_timestamp, str)
            or datetime.fromisoformat(sff_timestamp.replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("T1 MAVEN SFF inventory cannot enter acceptance")
    _insert_or_replace(root["checks"], {
        "name": "optional-t1-maven-sff-exploratory-inventory",
        "command": "python scripts/verify_t1_maven_sff_inventory.py --verify",
        "exit_code": 0, "recorded_at": sff_timestamp,
        "input_version": hashlib.sha256((ROOT / "scripts/verify_t1_maven_sff_inventory.py").read_bytes()).hexdigest(),
        "output_path": "artifacts/t1-maven-sff-exploratory-audit.json",
    })
    _insert_or_replace(root["checks"], {
        **next(row for row in rows if row["name"] == "optional-expanded-horizon-grid"),
        "name": "optional-t3-expanded-horizon-grid",
        "command": '& "$env:TEMP\\auditable-scientist-scipy-20260927\\Scripts\\python.exe" scripts/verify_t3_horizon_grid.py --verify',
    })
    _insert_or_replace(root["checks"], {
        **next(row for row in rows if row["name"] == "optional-published-figure-eight"),
        "name": "optional-t3-published-figure-eight",
    })
    _insert_or_replace(root["checks"], {
        **next(row for row in rows if row["name"] == "optional-pythagorean-close-encounter"),
        "name": "optional-t3-pythagorean-close-encounter",
    })
    projectile = _t2_projectile_receipt()
    _t2_projectile_protocol()
    _insert_or_replace(root["checks"], {
        "name": "optional-t2-projectile-real-source-inventory",
        "command": "python scripts/verify_t2_projectile_source.py --verify",
        "exit_code": 0, "recorded_at": projectile["recorded_at"],
        "input_version": projectile["verifier_sha256"],
        "output_path": "artifacts/t2-projectile-source-audit.json",
    })
    sensitivity = _load("artifacts/t2-causal-sensitivity-audit.json")
    sensitivity_timestamp = sensitivity.get("recorded_at")
    if (sensitivity.get("schema_version") != "t2-causal-sensitivity-audit-v1"
            or sensitivity.get("status") != "verified-synthetic-context-sensitivity-only"
            or sensitivity.get("negative_case_rejected") is not True
            or not isinstance(sensitivity_timestamp, str)
            or datetime.fromisoformat(sensitivity_timestamp.replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("T2 context sensitivity audit cannot enter acceptance")
    _insert_or_replace(root["checks"], {
        "name": "optional-t2-causal-context-sensitivity",
        "command": "python scripts/verify_t2_causal_sensitivity.py --verify",
        "exit_code": 0, "recorded_at": sensitivity_timestamp,
        "input_version": sensitivity["schema_version"],
        "output_path": "artifacts/t2-causal-sensitivity-audit.json",
    })
    pbs = _load("artifacts/t5-pbs-source-audit.json")
    pbs_timestamp = pbs.get("recorded_at")
    pbs_sources = [item for item in pbs.get("source_files", [])
                   if item.get("path") == "scripts/verify_t5_pbs_source.py"]
    if (pbs.get("schema_version") != "t5-pbs-source-audit-v1"
            or pbs.get("status") != "verified-source-document-and-review-flags-only"
            or pbs.get("source_pdf_sha256") !=
            "184b4d211aa8c1a2fcde0eb06a2fd8ae57727c28f1a2b41e5fbfd94b5f8c1271"
            or pbs.get("boundaries", {}).get("execution_allowed") is not False
            or pbs["boundaries"].get("claim_status") != "unverified"
            or len(pbs.get("step_inventory", [])) != 6
            or len(pbs_sources) != 1 or not isinstance(pbs_timestamp, str)
            or datetime.fromisoformat(pbs_timestamp.replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("T5 PBS source audit cannot enter acceptance")
    _insert_or_replace(root["checks"], {
        "name": "optional-t5-pbs-real-source-inventory",
        "command": "python scripts/verify_t5_pbs_source.py --verify",
        "exit_code": 0, "recorded_at": pbs_timestamp,
        "input_version": pbs_sources[0]["sha256"],
        "output_path": "artifacts/t5-pbs-source-audit.json",
    })
    _insert_or_replace(root["checks"], next(
        row for row in rows if row["name"] == "optional-t5-pbs-source-run"))
    cross_reader = _t5_cross_reader_receipt()
    _insert_or_replace(root["checks"], {
        "name": "optional-t5-pbs-cross-reader-text-coverage",
        "command": "python scripts/verify_t5_pbs_cross_reader.py --verify",
        "exit_code": 0, "recorded_at": cross_reader["recorded_at"],
        "input_version": cross_reader["verifier_sha256"],
        "output_path": "artifacts/t5-pbs-cross-reader-audit.json",
    })
    status = json.loads(STATUS_CONTRACT.read_text(encoding="utf-8"))
    required_gates = {
        "T1": {"external symbolic engine", "mission-domain force and maneuver comparison", "preregistered mission holdout and uncertainty review"},
        "T2": {"real interventions", "causal identification", "data rights", "external algorithm source rights"},
        "T3": {"long-horizon/nonintegrable multi-body validation", "real-mission provenance", "long-horizon compute budget"},
        "T4": {"general formal proof backend", "reviewed physical transition model", "real-world validation"},
        "T5": {"independent protocol source and rights", "biosafety review", "human acceptance"},
    }
    if (
        status.get("schema_version") != "portfolio-status-v1"
        or status.get("public_release_allowed") is not False
        or status.get("pushed") is not False
        or [item.get("track_id") for item in status.get("tracks", [])] != ["T1", "T2", "T3", "T4", "T5"]
        or status["tracks"][0].get("optional_desat_sensitivity_audit") !=
        "artifacts/t1-maven-desat-sensitivity-audit.json"
        or status["tracks"][0].get("optional_srp_sensitivity_audit") !=
        "artifacts/t1-maven-srp-sensitivity-audit.json"
        or status["tracks"][0].get("optional_ops_event_search_audit") !=
        "artifacts/t1-maven-ops-event-search-audit.json"
        or status["tracks"][0].get("optional_sff_exploratory_audit") !=
        "artifacts/t1-maven-sff-exploratory-audit.json"
        or status["tracks"][1].get("optional_projectile_source_audit") !=
        "artifacts/t2-projectile-source-audit.json"
        or status["tracks"][1].get("optional_projectile_model_protocol") !=
        "docs/T2_PROJECTILE_MODEL_PROTOCOL.json"
        or status["tracks"][4].get("optional_pbs_source_audit") !=
        "artifacts/t5-pbs-source-audit.json"
        or status["tracks"][4].get("optional_pbs_cross_reader_audit") !=
        "artifacts/t5-pbs-cross-reader-audit.json"
        or status["tracks"][4].get("optional_pbs_source_run") !=
        "artifacts/t5-pbs-source-run-audit.json"
        or status["tracks"][2].get("optional_horizon_grid_audit") != "artifacts/t3-horizon-grid-audit.json"
        or status["tracks"][2].get("optional_figure_eight_audit") != "artifacts/t3-figure-eight-audit.json"
        or status["tracks"][2].get("optional_pythagorean_audit") != "artifacts/t3-pythagorean-audit.json"
        or status["tracks"][3].get("optional_verlet_invariant_audit") != "artifacts/t4-verlet-invariant-audit.json"
        or any(item.get("public_release") is not False for item in status["tracks"])
        or any(item.get("state") != ("text-demo-within-scope" if item["track_id"] == "T5" else "reproduced-within-scope") for item in status["tracks"])
        or any(not required_gates[item["track_id"]] <= set(item.get("open_gates", [])) for item in status["tracks"])
    ):
        raise ValueError("portfolio status contract exceeds the bounded release state")
    outputs = {
        ROOT / f"artifacts/{directory}/acceptance.json": _render_json(payload)
        for directory, payload in bundles.items()
    }
    outputs[ROOT / "artifacts/acceptance.json"] = _render_json(root)
    outputs[ROOT / "artifacts/portfolio-status.json"] = _render_json(status)
    outputs[ROOT / "artifacts/portfolio-status.md"] = _status_markdown(status)
    for directory, note in REPORT_NOTES.items():
        path = ROOT / f"artifacts/{directory}/test-report.md"
        report = path.read_text(encoding="utf-8")
        if REPORT_MARKERS[directory] not in report:
            report = report.rstrip("\n") + "\n\n" + note
        outputs[path] = report
    t3_report = ROOT / "artifacts/t3-dynamics/test-report.md"
    if "The optional [Pythagorean close-encounter audit]" not in outputs[t3_report]:
        outputs[t3_report] = outputs[t3_report].rstrip("\n") + "\n\n" + PYTHAGOREAN_REPORT_NOTE
    t4_report = ROOT / "artifacts/t4-proof/test-report.md"
    if "The optional [exact Verlet invariant audit]" not in outputs[t4_report]:
        outputs[t4_report] = outputs[t4_report].rstrip("\n") + "\n\n" + VERLET_REPORT_NOTE
    if "The optional [finite floating conformance audit]" not in outputs[t4_report]:
        outputs[t4_report] = outputs[t4_report].rstrip("\n") + "\n\n" + FLOATING_REPORT_NOTE
    t2_causal_report = ROOT / "artifacts/t2-causal/test-report.md"
    if "The optional [context-sensitivity negative control]" not in outputs[t2_causal_report]:
        outputs[t2_causal_report] = outputs[t2_causal_report].rstrip("\n") + "\n\n" + REPORT_NOTES["t2-causal"]
    t2_report = ROOT / "artifacts/t2-physical/test-report.md"
    if "The optional [real projectile source inventory]" not in outputs[t2_report]:
        outputs[t2_report] = outputs[t2_report].rstrip("\n") + "\n\n" + PROJECTILE_REPORT_NOTE
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    outputs = desired_outputs()
    for path, expected in outputs.items():
        current = path.read_text(encoding="utf-8")
        equivalent = current == expected
        if path.suffix == ".json" and not equivalent:
            equivalent = json.loads(current) == json.loads(expected)
        if args.write and not equivalent:
            path.write_text(expected, encoding="utf-8", newline="\n")
        elif args.verify and not equivalent:
            raise SystemExit(f"optional acceptance projection differs: {path.relative_to(ROOT)}")
    print(json.dumps({"status": "verified-bounded-optional-acceptance-projection",
                      "output_count": len(outputs)}, sort_keys=True))


if __name__ == "__main__":
    main()
