"""Reattach bounded optional receipts after the pinned base-track generator.

The base generator is included in seven committed Run source manifests. Keeping
this independent projection avoids invalidating those historical Run receipts.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_CONTRACT = ROOT / "docs/PORTFOLIO_STATUS_CONTRACT.json"
STATUS_NARRATIVE = ROOT / "docs/PORTFOLIO_STATUS_NARRATIVE.md"

OPTIONAL = (
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
)

REPORT_NOTES = {
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
        "pass. The Run's physical Claim remains `unverified`.\n"
    ),
}
REPORT_MARKERS = {
    "t2-physical": "An optional impact-to-impact endpoint estimator",
    "t3-dynamics": "The optional expanded [finite-horizon audit]",
    "t4-proof": "The optional exact linear-invariant audit",
}
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


def desired_outputs() -> dict[Path, str]:
    """Build all outputs in memory before writing any file."""

    bundles = {
        directory: _load(f"artifacts/{directory}/acceptance.json")
        for directory in ("t2-physical", "t3-dynamics", "t4-proof")
    }
    rows = [_receipt_row(spec) for spec in OPTIONAL]
    for spec, row in zip(OPTIONAL, rows):
        _insert_or_replace(bundles[spec[0]]["checks"], row)
    root = _load("artifacts/acceptance.json")
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
        or status["tracks"][2].get("optional_horizon_grid_audit") != "artifacts/t3-horizon-grid-audit.json"
        or status["tracks"][2].get("optional_figure_eight_audit") != "artifacts/t3-figure-eight-audit.json"
        or status["tracks"][2].get("optional_pythagorean_audit") != "artifacts/t3-pythagorean-audit.json"
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
