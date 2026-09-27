"""Recompute the predeclared conditional MAVEN desaturation response grid."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isclose, isfinite, sqrt
from pathlib import Path

from fetch_maven_cruise import DEFAULT_PATH as MAVEN, fingerprint as fingerprint_maven
from auditable_scientist.adapters.naif_de440s import _fingerprint as fingerprint_de440s
from auditable_scientist.adapters.naif_mars_center import fingerprint_mar099s
from verify_t1_maven_planetary_force import gm_values, propagate


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T1_MAVEN_DESAT_SENSITIVITY_PROTOCOL.json"
PROTOCOL_SHA256 = "cc6d520386505f73a2850d3dcee7dc8d3ba08f2e0901e924360c56eb3c78237d"
PREREGISTRATION_COMMIT = "25a4e20"
PDF = ROOT / "data/references/jesick_2016_maven_navigation_overview.pdf"
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"
GM_KERNEL = ROOT / "data/naif/gm_de440.tpc"
PRIOR_PROTOCOL = ROOT / "docs/T1_MAVEN_PLANETARY_FORCE_PROTOCOL.json"
PRIOR_SNAPSHOT = ROOT / "artifacts/t1-maven-planetary-force-snapshot.json"
SNAPSHOT = ROOT / "artifacts/t1-maven-desat-sensitivity-snapshot.json"
AUDIT = ROOT / "artifacts/t1-maven-desat-sensitivity-audit.json"
SOURCE_FILES = (Path(__file__).resolve(), PROTOCOL,
                ROOT / "docs/T1_MAVEN_DESAT_SENSITIVITY_PROTOCOL.md",
                ROOT / "scripts/verify_t1_maven_planetary_force.py", PRIOR_PROTOCOL,
                ROOT / "requirements-t1-mars-center-win-py312.txt")


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()


def _source(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def _norm(values: tuple[float, ...] | list[float]) -> float:
    return sqrt(sum(v*v for v in values))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x*y for x, y in zip(a, b, strict=True))


def _cross(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, float, float]:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _basis(state: tuple[float, ...]) -> dict[str, tuple[float, float, float]]:
    r, v = state[:3], state[3:]
    rnorm = _norm(r)
    h = _cross(r, v)
    hnorm = _norm(h)
    if min(rnorm, hnorm) <= 0 or not all(isfinite(x) for x in state):
        raise ValueError("nonfinite or singular orbital frame")
    radial = tuple(x/rnorm for x in r)
    normal = tuple(x/hnorm for x in h)
    transverse = _cross(normal, radial)
    return {"radial": radial, "transverse": transverse, "normal": normal}


def _basis_error(basis: dict[str, tuple[float, float, float]]) -> float:
    axes = list(basis.values())
    return max([abs(_norm(axis)-1) for axis in axes] + [
        abs(_dot(axes[i], axes[j])) for i in range(3) for j in range(i+1, 3)])


def _config() -> tuple[dict, dict, dict]:
    if sha256(PROTOCOL.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("precommitted MAVEN desat protocol bytes differ")
    config = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if (config.get("schema_version") != "t1-maven-desat-sensitivity-protocol-v1"
            or config.get("scientific_boundaries", {}).get("claim_status") != "unverified"
            or config.get("scenario", {}).get("paper_average_is_upper_bound") is not False):
        raise ValueError("MAVEN desat boundary differs")
    if sha256(PDF.read_bytes()).hexdigest() != config["source"]["local_pdf_sha256"]:
        raise ValueError("author-hosted MAVEN navigation PDF differs")
    if sha256(PRIOR_PROTOCOL.read_bytes()).hexdigest() != config["baseline"]["prior_protocol_sha256"]:
        raise ValueError("prior MAVEN force protocol differs")
    if sha256(PRIOR_SNAPSHOT.read_bytes()).hexdigest() != config["baseline"]["prior_snapshot_sha256"]:
        raise ValueError("prior MAVEN force snapshot differs")
    previous_protocol = json.loads(PRIOR_PROTOCOL.read_text(encoding="utf-8"))
    previous = json.loads(PRIOR_SNAPSHOT.read_text(encoding="utf-8"))
    if (previous.get("protocol_sha256") != config["baseline"]["prior_protocol_sha256"]
            or [row["initial_et_tdb_seconds"] for row in previous["arcs"]] !=
            config["baseline"]["initial_et_tdb_seconds"]
            or not isclose(config["scenario"]["impulse_magnitude_km_s"],
                           config["scenario"]["impulse_magnitude_mm_s"]*1e-6,
                           rel_tol=1e-15)):
        raise ValueError("MAVEN desat baseline or units differ")
    return config, previous_protocol, previous


def evaluate() -> dict:
    import spiceypy as spice
    from importlib.metadata import version

    config, prior_protocol, previous = _config()
    paths = tuple(path.resolve(strict=True) for path in (DE440S, MAR099S, MAVEN, GM_KERNEL))
    if len(set(paths)) != 4 or tuple(path.name for path in paths) != (
            "de440s.bsp", "mar099s.bsp", "maven_cru_rec_131118_140923_v1.bsp",
            "gm_de440.tpc"):
        raise ValueError("four distinct named NAIF sources required")
    hashes = {"de440s": fingerprint_de440s(DE440S)["sha256"],
              "mar099s": fingerprint_mar099s(MAR099S)["sha256"],
              "maven_cruise": fingerprint_maven(MAVEN)["sha256"],
              "gm_kernel": sha256(GM_KERNEL.read_bytes()).hexdigest()}
    if hashes != {"de440s": prior_protocol["source_contract"]["de440s_sha256"],
                  "mar099s": prior_protocol["source_contract"]["mar099s_sha256"],
                  "maven_cruise": prior_protocol["source_contract"]["maven_cruise_sha256"],
                  "gm_kernel": prior_protocol["source_contract"]["gm_kernel_sha256"]}:
        raise ValueError("MAVEN desat NAIF source hash differs")
    gm = gm_values(GM_KERNEL, prior_protocol)
    if spice.ktotal("SPK") != 0:
        raise ValueError("empty SPK pool required")
    for path in (MAVEN, MAR099S, DE440S):
        spice.furnsh(str(path))
    try:
        if spice.ktotal("SPK") != 3:
            raise ValueError("expected three pinned SPKs")
        position_cache: dict[tuple[int, float], tuple[float, ...]] = {}
        query_count = 0

        def position_at(body: int, et: float) -> tuple[float, ...]:
            nonlocal query_count
            key = (body, et)
            if key not in position_cache:
                query_count += 1
                if query_count > config["compute_budget"]["maximum_spice_position_queries"]:
                    raise ValueError("SPICE query budget exceeded")
                values, _ = spice.spkpos(str(body), et, "J2000", "NONE", "SUN")
                position_cache[key] = tuple(float(x) for x in values)
                if not all(isfinite(x) for x in position_cache[key]):
                    raise ValueError("nonfinite planetary state")
            return position_cache[key]

        step_total = 0

        def integrate(state: tuple[float, ...], et: float, duration: float,
                      step: float) -> tuple[float, ...]:
            nonlocal step_total
            n = duration/step
            if not n.is_integer() or n < 0:
                raise ValueError("desat segment requires exact nonnegative step count")
            step_total += int(n)
            if step_total > config["compute_budget"]["maximum_rk4_steps_total"]:
                raise ValueError("desat RK4 step budget exceeded")
            return state if n == 0 else propagate(state, et, duration, step, gm, position_at)

        rows = []
        horizon = config["baseline"]["horizon_seconds"]
        magnitude = config["scenario"]["impulse_magnitude_km_s"]
        for prior in previous["arcs"]:
            et = prior["initial_et_tdb_seconds"]
            initial = tuple(float(x) for x in prior["initial_nav_sun_state_km_kms"])
            nav = tuple(float(x) for x in spice.spkezr("-202", et, "J2000", "NONE", "SUN")[0])
            if initial != nav:
                raise ValueError("MAVEN desat NAV initial state differs from pinned SPK")
            by_step = {}
            for step in config["numerics"]["step_seconds"]:
                baseline = integrate(initial, et, horizon, step)
                if step == prior_protocol["model"]["step_seconds"] and list(baseline) != prior[
                        "planetary_force_endpoint_state_km_kms"]:
                    raise ValueError("MAVEN desat baseline differs from earlier force result")
                cases = {}
                for fraction in config["scenario"]["injection_time_fractions"]:
                    prefix_duration = horizon*fraction
                    prefix = integrate(initial, et, prefix_duration, step)
                    injection_et = et+prefix_duration
                    remaining = horizon-prefix_duration
                    no_impulse = integrate(prefix, injection_et, remaining, step)
                    frame = _basis(prefix)
                    controls = {"position_split_error_km": _norm(tuple(a-b for a, b in
                                zip(no_impulse[:3], baseline[:3], strict=True))),
                                "velocity_split_error_km_s": _norm(tuple(a-b for a, b in
                                zip(no_impulse[3:], baseline[3:], strict=True))),
                                "basis_error": _basis_error(frame)}
                    for axis in config["scenario"]["axes"]:
                        for sign in config["scenario"]["signs"]:
                            kick = tuple(sign*magnitude*x for x in frame[axis])
                            kicked = (*prefix[:3], *(prefix[3+i]+kick[i] for i in range(3)))
                            endpoint = integrate(kicked, injection_et, remaining, step)
                            response = tuple(a-b for a, b in zip(endpoint, baseline, strict=True))
                            if not all(isfinite(x) for x in (*endpoint, *response)):
                                raise ValueError("nonfinite desat response")
                            cases[f"{fraction}:{axis}:{sign}"] = {
                                "injection_state_km_kms": list(prefix),
                                "impulse_vector_km_s": list(kick),
                                "endpoint_state_km_kms": list(endpoint),
                                "response_position_km": list(response[:3]),
                                "response_velocity_km_s": list(response[3:]),
                                "response_position_norm_km": _norm(response[:3]),
                            }
                    cases[f"{fraction}:control"] = controls
                by_step[str(step)] = {"baseline_endpoint_state_km_kms": list(baseline),
                                      "cases": cases}
            scenarios = []
            coarse = by_step[str(config["numerics"]["step_seconds"][0])]["cases"]
            fine = by_step[str(config["numerics"]["step_seconds"][1])]["cases"]
            for fraction in config["scenario"]["injection_time_fractions"]:
                for axis in config["scenario"]["axes"]:
                    plus_key = f"{fraction}:{axis}:1"
                    minus_key = f"{fraction}:{axis}:-1"
                    plus, minus = coarse[plus_key], coarse[minus_key]
                    plus_fine, minus_fine = fine[plus_key], fine[minus_key]
                    scenarios.append({
                        "injection_time_fraction": fraction, "axis": axis,
                        "positive_response_position_km": plus["response_position_km"],
                        "negative_response_position_km": minus["response_position_km"],
                        "positive_response_norm_km": plus["response_position_norm_km"],
                        "negative_response_norm_km": minus["response_position_norm_km"],
                        "positive_response_refinement_difference_km": _norm(tuple(a-b for a, b in
                            zip(plus["response_position_km"], plus_fine["response_position_km"], strict=True))),
                        "negative_response_refinement_difference_km": _norm(tuple(a-b for a, b in
                            zip(minus["response_position_km"], minus_fine["response_position_km"], strict=True))),
                        "opposite_sign_position_oddness_km": _norm(tuple(a+b for a, b in
                            zip(plus["response_position_km"], minus["response_position_km"], strict=True))),
                    })
            rows.append({"initial_et_tdb_seconds": et,
                         "prior_nav_position_residual_km": prior["position_error_km"],
                         "step_data": by_step, "scenario_pairs": scenarios})
        gates = config["engineering_gates"]
        checks = {
            "source_and_baseline_bound": True,
            "all_24_scenarios": len(rows) == 2 and all(len(row["scenario_pairs"]) == 6
                                               for row in rows),
            "split_no_impulse": all(
                row["step_data"][str(step)]["cases"][f"{fraction}:control"]["position_split_error_km"] <=
                gates["split_no_impulse_position_difference_km_max"]
                and row["step_data"][str(step)]["cases"][f"{fraction}:control"]["velocity_split_error_km_s"] <=
                gates["split_no_impulse_velocity_difference_km_s_max"]
                for row in rows for step in config["numerics"]["step_seconds"]
                for fraction in config["scenario"]["injection_time_fractions"]),
            "orthonormal_basis": all(
                row["step_data"][str(step)]["cases"][f"{fraction}:control"]["basis_error"] <=
                gates["basis_norm_and_dot_tolerance"]
                for row in rows for step in config["numerics"]["step_seconds"]
                for fraction in config["scenario"]["injection_time_fractions"]),
            "opposite_sign_oddness": all(pair["opposite_sign_position_oddness_km"] <=
                                         gates["opposite_sign_position_oddness_km_max"]
                                         for row in rows for pair in row["scenario_pairs"]),
            "step_refinement": all(max(pair["positive_response_refinement_difference_km"],
                                       pair["negative_response_refinement_difference_km"]) <=
                                   gates["impulse_response_refinement_difference_km_max"]
                                   for row in rows for pair in row["scenario_pairs"]),
            "finite_responses": all(isfinite(x) for row in rows for pair in row["scenario_pairs"]
                                    for x in (pair["positive_response_norm_km"],
                                              pair["negative_response_norm_km"])),
            "compute_budget": step_total <= config["compute_budget"]["maximum_rk4_steps_total"]
                              and query_count <= config["compute_budget"]["maximum_spice_position_queries"],
        }
        result = {"schema_version": "t1-maven-desat-sensitivity-snapshot-v1",
                  "protocol_sha256": PROTOCOL_SHA256,
                  "preregistration_commit": PREREGISTRATION_COMMIT,
                  "source_pdf_sha256": config["source"]["local_pdf_sha256"],
                  "source_sha256": hashes,
                  "prior_snapshot_sha256": config["baseline"]["prior_snapshot_sha256"],
                  "reader": {"package": "spiceypy", "version": version("spiceypy"),
                             "toolkit": spice.tkvrsn("TOOLKIT")},
                  "scenario_contract": config["scenario"],
                  "numerics": config["numerics"],
                  "engineering_gates": gates,
                  "observed_budget": {"rk4_steps_total": step_total,
                                      "spice_position_queries": query_count},
                  "arcs": rows, "checks": checks,
                  "scientific_boundaries": config["scientific_boundaries"]}
    finally:
        for path in (DE440S, MAR099S, MAVEN):
            spice.unload(str(path))
    if spice.ktotal("SPK") != 0:
        raise ValueError("SPK pool not emptied")
    return result


def build_audit(snapshot: dict) -> dict:
    return {"schema_version": "t1-maven-desat-sensitivity-audit-v1",
            "status": "passed-conditional-impulse-sensitivity-only" if all(snapshot["checks"].values())
                      else "failed-conditional-impulse-sensitivity",
            "protocol_sha256": PROTOCOL_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "source_files": [_source(path) for path in SOURCE_FILES],
            "snapshot_sha256": sha256(_json_bytes(snapshot)).hexdigest(),
            "source_pdf_sha256": snapshot["source_pdf_sha256"],
            "observed_budget": snapshot["observed_budget"],
            "checks": snapshot["checks"],
            "boundaries": {"conditional_response_scale": True,
                           "actual_desat_in_arcs": False,
                           "statistical_uncertainty_interval": False,
                           "independent_observables": False,
                           "scientific_holdout": False,
                           "mission_validation": False}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    snapshot = evaluate()
    audit = build_audit(snapshot)
    if args.write:
        data = _json_bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != data:
            raise ValueError("refusing to overwrite different MAVEN desat snapshot")
        SNAPSHOT.write_bytes(data)
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n",
                         encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != _json_bytes(snapshot):
            raise ValueError("saved MAVEN desat snapshot differs from recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if not timestamp or datetime.fromisoformat(timestamp).tzinfo is None or saved != audit:
            raise ValueError("saved MAVEN desat audit differs from recomputation")
    print(json.dumps({"status": audit["status"], "checks": snapshot["checks"],
                      "observed_budget": snapshot["observed_budget"],
                      "arcs": [{"start_et": row["initial_et_tdb_seconds"],
                                "prior_nav_residual_km": row["prior_nav_position_residual_km"],
                                "max_response_km": max(max(p["positive_response_norm_km"],
                                                           p["negative_response_norm_km"])
                                                       for p in row["scenario_pairs"])}
                               for row in snapshot["arcs"]]}, indent=2))
    if audit["status"].startswith("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
