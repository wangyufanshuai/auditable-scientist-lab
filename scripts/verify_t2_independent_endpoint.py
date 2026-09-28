"""Independently estimate T2P intervention endpoints by whole flight intervals."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path

from auditable_scientist.tracks.physical_world import (
    Action, BallParameters, Intervention, PhysicalCase, WorldState, compare, standard_cases,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_INPUT = ROOT / "examples/causal/physical-fixture.json"
VARIED_INPUT = ROOT / "artifacts/t2-independent-endpoint-input.json"
AUDIT = ROOT / "artifacts/t2-independent-endpoint-audit.json"
SOURCE_PATHS = [
    Path(__file__).resolve(),
    ROOT / "src/auditable_scientist/tracks/physical_world.py",
    ROOT / "docs/T2_PHYSICAL_METHOD.md",
    ROOT / "docs/T2_INDEPENDENT_ENDPOINT.md",
    BASE_INPUT,
    VARIED_INPUT,
]


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def expected_varied_input() -> dict:
    cases: list[dict] = []
    for index in range(24):
        parameters = BallParameters(
            mass_kg=0.8 + 0.1 * (index % 7),
            friction=0.05 + 0.04 * (index % 6),
            restitution=0.3 + 0.05 * (index % 7),
            gravity_m_s2=7.5 + 0.5 * (index % 8),
        )
        kind = index % 6
        if kind == 0:
            intervention = Intervention(query_type="single", parameter_updates={"mass_kg": parameters.mass_kg * 1.2})
        elif kind == 1:
            intervention = Intervention(query_type="single", parameter_updates={"friction": parameters.friction + 0.1})
        elif kind == 2:
            intervention = Intervention(query_type="single", parameter_updates={"restitution": parameters.restitution + 0.1})
        elif kind == 3:
            intervention = Intervention(query_type="single", parameter_updates={"gravity_m_s2": parameters.gravity_m_s2 * 1.1})
        elif kind == 4:
            intervention = Intervention(query_type="joint", parameter_updates={
                "friction": parameters.friction + 0.1, "restitution": parameters.restitution + 0.1,
            })
        else:
            intervention = Intervention(query_type="policy", impulse_x_kg_m_s=2.5)
        case = PhysicalCase(
            case_id=f"varied-{index:03d}", split="holdout", parameters=parameters,
            initial_state=WorldState(
                x_m=0.05 * (index % 4), y_m=0.6 + 0.1 * (index % 6),
                vx_m_s=-0.2 + 0.1 * (index % 5), vy_m_s=-0.25 + 0.1 * (index % 6),
            ),
            action=Action(impulse_x_kg_m_s=1.2 + 0.2 * (index % 7)),
            intervention=intervention,
            horizon_s=1.0 + 0.25 * (index % 5), sample_dt_s=0.05,
        )
        cases.append(case.model_dump(mode="json"))
    return {
        "schema_version": "t2-independent-endpoint-input-v1",
        "construction": "24 deterministic varied initial states and parameter interventions; no observed real-world data",
        "cases": cases,
    }


def endpoint_x(case: PhysicalCase, *, parameters: BallParameters, action: Action) -> float:
    """Compute final x by impact-to-impact intervals; never call the grid simulator."""
    gravity = parameters.gravity_m_s2
    remaining = case.horizon_s
    x = case.initial_state.x_m
    y = case.initial_state.y_m
    vx = case.initial_state.vx_m_s + action.impulse_x_kg_m_s / parameters.mass_kg
    vy = case.initial_state.vy_m_s
    for _ in range(100):
        if remaining <= 1e-12:
            return x
        if y <= 1e-12 and vy <= 1e-8:
            return x + vx * remaining
        to_impact = (vy + sqrt(vy * vy + 2 * gravity * max(y, 0.0))) / gravity
        if to_impact <= 1e-12 and vy < 0:
            to_impact = 0.0
        if to_impact >= remaining - 1e-12:
            return x + vx * remaining
        x += vx * to_impact
        remaining -= to_impact
        pre_impact_vy = vy - gravity * to_impact
        vx *= 1 - parameters.friction
        vy = -parameters.restitution * pre_impact_vy
        if vy < 1e-8:
            vy = 0.0
        y = 0.0
    raise ValueError("independent impact interval cap exceeded")


def estimate_effect(case: PhysicalCase) -> tuple[float, float, float]:
    """Return factual endpoint, intervened endpoint, and their synthetic contrast."""
    factual = endpoint_x(case, parameters=case.parameters, action=case.action)
    updated = BallParameters.model_validate({
        **case.parameters.model_dump(mode="json"), **case.intervention.parameter_updates,
    })
    changed_action = (
        case.action if case.intervention.impulse_x_kg_m_s is None
        else Action(impulse_x_kg_m_s=case.intervention.impulse_x_kg_m_s)
    )
    changed = endpoint_x(case, parameters=updated, action=changed_action)
    return factual, changed, changed - factual


def _load_cases() -> list[PhysicalCase]:
    base = json.loads(BASE_INPUT.read_text(encoding="utf-8"))
    varied = json.loads(VARIED_INPUT.read_text(encoding="utf-8"))
    if base.get("schema_version") != "physical-world-fixture-v1" or varied != expected_varied_input():
        raise ValueError("T2 independent endpoint input inventory differs")
    cases = [PhysicalCase.model_validate(item) for item in (*base["cases"], *varied["cases"])]
    standard = [case.model_dump(mode="json") for case in standard_cases()]
    if ([case.model_dump(mode="json") for case in cases[:100]] != standard
            or len(cases) != 124 or len({case.case_id for case in cases}) != 124
            or sum(case.split == "train" for case in cases) != 40
            or sum(case.split == "holdout" for case in cases) != 84):
        raise ValueError("T2 endpoint train or holdout inventory differs")
    return cases


def build_audit() -> dict:
    cases = _load_cases()
    rows = []
    squared = {"train": [], "holdout": []}
    negative_squared: list[float] = []
    maximum_factual = maximum_counterfactual = maximum_effect = 0.0
    for case in cases:
        factual, changed, effect = estimate_effect(case)
        reference = compare(case)
        factual_error = abs(factual - reference.factual.states[-1]["x_m"])
        counterfactual_error = abs(changed - reference.counterfactual.states[-1]["x_m"])
        effect_error = abs(effect - reference.final_x_effect_m)
        maximum_factual = max(maximum_factual, factual_error)
        maximum_counterfactual = max(maximum_counterfactual, counterfactual_error)
        maximum_effect = max(maximum_effect, effect_error)
        squared[case.split].append(effect_error * effect_error)
        if case.split == "holdout":
            negative_squared.append(reference.final_x_effect_m ** 2)
        rows.append({
            "case_id": case.case_id, "split": case.split,
            "estimated_factual_x_m": factual,
            "estimated_counterfactual_x_m": changed,
            "estimated_effect_m": effect,
            "reference_effect_m": reference.final_x_effect_m,
            "effect_error_m": effect_error,
        })
    train_rmse = sqrt(sum(squared["train"]) / len(squared["train"]))
    holdout_rmse = sqrt(sum(squared["holdout"]) / len(squared["holdout"]))
    ignored_intervention_rmse = sqrt(sum(negative_squared) / len(negative_squared))
    gates = {
        "factual_endpoint_max_1e-8_m": maximum_factual <= 1e-8,
        "counterfactual_endpoint_max_1e-8_m": maximum_counterfactual <= 1e-8,
        "effect_max_1e-8_m": maximum_effect <= 1e-8,
        "holdout_effect_rmse_1e-8_m": holdout_rmse <= 1e-8,
        "ignored_intervention_rejected": ignored_intervention_rmse > 0.01,
    }
    if not all(gates.values()):
        raise ValueError(f"T2 independent endpoint gate failed: {gates}")
    return {
        "schema_version": "t2-independent-endpoint-audit-v1",
        "status": "verified-synthetic-endpoints-only",
        "method": "whole-flight impact recurrence independent of the sample-grid simulator",
        "case_count": len(cases), "train_count": len(squared["train"]),
        "holdout_count": len(squared["holdout"]),
        "metrics": {
            "max_factual_endpoint_error_m": maximum_factual,
            "max_counterfactual_endpoint_error_m": maximum_counterfactual,
            "max_effect_error_m": maximum_effect,
            "train_effect_rmse_m": train_rmse,
            "holdout_effect_rmse_m": holdout_rmse,
            "ignored_intervention_holdout_rmse_m": ignored_intervention_rmse,
        },
        "gates": gates, "rows": rows,
        "source_files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path), "bytes": path.stat().st_size}
            for path in SOURCE_PATHS
        ],
        "boundaries": {
            "synthetic_simulator_endpoints": True,
            "independent_event_interval_implementation": True,
            "observational_causal_identification": False,
            "real_intervention_data": False,
            "physical_model_validated": False,
            "source_rights_reviewed": False,
            "research_candidate": False,
            "publication_ready": False,
        },
    }


def verify_saved(saved: dict, current: dict) -> None:
    timestamp = saved.get("recorded_at")
    if not isinstance(timestamp, str):
        raise ValueError("T2 independent endpoint audit has no timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("T2 independent endpoint audit timestamp differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("T2 independent endpoint audit timestamp is naive")
    if {key: value for key, value in saved.items() if key != "recorded_at"} != current:
        raise ValueError("T2 independent endpoint audit differs from current computation")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write and not VARIED_INPUT.exists():
        VARIED_INPUT.write_text(json.dumps(expected_varied_input(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    current = build_audit()
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        verify_saved(saved, current)
    print(json.dumps({"status": current["status"], "case_count": current["case_count"], "gates": current["gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()
