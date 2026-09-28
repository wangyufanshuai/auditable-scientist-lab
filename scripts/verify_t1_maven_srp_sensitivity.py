"""Recompute the predeclared conditional MAVEN solar-pressure response grid."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from fetch_maven_cruise import DEFAULT_PATH as MAVEN, fingerprint as fingerprint_maven
from auditable_scientist.adapters.naif_de440s import _fingerprint as fingerprint_de440s
from auditable_scientist.adapters.naif_mars_center import fingerprint_mar099s
from verify_t1_maven_planetary_force import gm_values, norm, third_body_acceleration


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T1_MAVEN_SRP_SENSITIVITY_PROTOCOL.json"
PROTOCOL_SHA256 = "68352f9158755dca98baeffe51bd08c65112c2542548ff503ec7a62bdae5e470"
PREREGISTRATION_COMMIT = "199ecc4"
PRIOR_PROTOCOL = ROOT / "docs/T1_MAVEN_PLANETARY_FORCE_PROTOCOL.json"
PRIOR_SNAPSHOT = ROOT / "artifacts/t1-maven-planetary-force-snapshot.json"
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"
GM_KERNEL = ROOT / "data/naif/gm_de440.tpc"
NAVIGATION_PDF = ROOT / "data/references/jesick_2016_maven_navigation_overview.pdf"
NASA_HTML = ROOT / "data/references/maven_srp/nasa_solar_irradiance_science.html"
IAU_PDF = ROOT / "data/references/maven_srp/iau_2012_b2.pdf"
SNAPSHOT = ROOT / "artifacts/t1-maven-srp-sensitivity-snapshot.json"
AUDIT = ROOT / "artifacts/t1-maven-srp-sensitivity-audit.json"
SOURCE_FILES = (Path(__file__).resolve(), PROTOCOL,
                ROOT / "docs/T1_MAVEN_SRP_SENSITIVITY_PROTOCOL.md",
                ROOT / "scripts/verify_t1_maven_planetary_force.py", PRIOR_PROTOCOL,
                ROOT / "requirements-t1-mars-center-win-py312.txt")


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": _hash(path),
            "bytes": path.stat().st_size}


def _config() -> tuple[dict, dict, dict]:
    if _hash(PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("precommitted MAVEN SRP protocol changed")
    config = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if (config.get("schema_version") != "t1-maven-srp-sensitivity-protocol-v1"
            or config.get("scientific_boundaries", {}).get("claim_status") != "unverified"
            or config.get("scientific_boundaries", {}).get("mission_validation") is not False
            or config.get("interpretation", {}).get("no_parameter_fit_to_nav_endpoint") is not True):
        raise ValueError("MAVEN SRP protocol boundary differs")
    sources = config["source_contract"]
    for path, key in ((NAVIGATION_PDF, "maven_navigation_pdf_sha256"),
                      (NASA_HTML, "nasa_solar_irradiance_html_sha256"),
                      (IAU_PDF, "iau_2012_au_pdf_sha256")):
        if _hash(path) != sources[key]:
            raise ValueError(f"MAVEN SRP source bytes differ: {path.name}")
    baseline = config["baseline"]
    if (_hash(PRIOR_PROTOCOL) != baseline["prior_protocol_sha256"]
            or _hash(PRIOR_SNAPSHOT) != baseline["prior_snapshot_sha256"]):
        raise ValueError("MAVEN SRP baseline source differs")
    prior_protocol = json.loads(PRIOR_PROTOCOL.read_text(encoding="utf-8"))
    prior_snapshot = json.loads(PRIOR_SNAPSHOT.read_text(encoding="utf-8"))
    if ([row["initial_et_tdb_seconds"] for row in prior_snapshot["arcs"]] !=
            baseline["initial_et_tdb_seconds"]
            or prior_snapshot["protocol_sha256"] != baseline["prior_protocol_sha256"]):
        raise ValueError("MAVEN SRP baseline arc contract differs")
    model = config["model"]
    if (model["solar_irradiance_at_1au_w_m2"] != 1361.0
            or model["astronomical_unit_km"] != 149597870.7
            or model["speed_of_light_m_s"] != 299792458.0
            or model["effective_area_over_mass_m2_per_kg"] != [0.0, 0.001, 0.01, 0.1]
            or model["step_seconds"] != [600.0, 300.0]):
        raise ValueError("MAVEN SRP force or scenario contract differs")
    return config, prior_protocol, prior_snapshot


def srp_acceleration(position: tuple[float, float, float],
                     effective_area_over_mass: float, model: dict) -> tuple[float, float, float]:
    radius = norm(position)
    if (radius <= 0 or not all(isfinite(x) for x in position)
            or not isfinite(effective_area_over_mass) or effective_area_over_mass < 0):
        raise ValueError("finite nonsingular position and nonnegative effective area/mass required")
    pressure_n_m2 = (model["solar_irradiance_at_1au_w_m2"] /
                     model["speed_of_light_m_s"] *
                     (model["astronomical_unit_km"] / radius)**2)
    acceleration_km_s2 = pressure_n_m2 * effective_area_over_mass / 1000.0
    return tuple(acceleration_km_s2 * x / radius for x in position)


def rk4_step(state: tuple[float, ...], et: float, dt: float,
             gm: dict[int, float], position_at: object,
             effective_area_over_mass: float, model: dict) -> tuple[float, ...]:
    if len(state) != 6 or not all(isfinite(x) for x in state) or dt <= 0:
        raise ValueError("finite six-component state and positive step required")

    def derivative(sample: tuple[float, ...], time: float) -> tuple[float, ...]:
        r = sample[:3]
        radius = norm(r)
        if radius <= 0:
            raise ValueError("solar singularity")
        a = [-gm[10] * x / radius**3 for x in r]
        for body in (3, 4):
            tide = third_body_acceleration(r, position_at(body, time), gm[body])
            a = [x+y for x, y in zip(a, tide, strict=True)]
        srp = srp_acceleration(r, effective_area_over_mass, model)
        a = [x+y for x, y in zip(a, srp, strict=True)]
        return (*sample[3:], *a)

    k1 = derivative(state, et)
    k2 = derivative(tuple(x+dt*k/2 for x, k in zip(state, k1, strict=True)), et+dt/2)
    k3 = derivative(tuple(x+dt*k/2 for x, k in zip(state, k2, strict=True)), et+dt/2)
    k4 = derivative(tuple(x+dt*k for x, k in zip(state, k3, strict=True)), et+dt)
    result = tuple(x+dt*(a+2*b+2*c+d)/6 for x, a, b, c, d in
                   zip(state, k1, k2, k3, k4, strict=True))
    if not all(isfinite(x) for x in result):
        raise ValueError("nonfinite integrated state")
    return result


def evaluate() -> dict:
    import spiceypy as spice
    from importlib.metadata import version

    config, prior_protocol, prior_snapshot = _config()
    paths = tuple(path.resolve(strict=True) for path in (DE440S, MAR099S, MAVEN, GM_KERNEL))
    if len(set(paths)) != 4 or tuple(path.name for path in paths) != (
            "de440s.bsp", "mar099s.bsp", "maven_cru_rec_131118_140923_v1.bsp",
            "gm_de440.tpc"):
        raise ValueError("four distinct named NAIF sources required")
    hashes = {"de440s": fingerprint_de440s(DE440S)["sha256"],
              "mar099s": fingerprint_mar099s(MAR099S)["sha256"],
              "maven_cruise": fingerprint_maven(MAVEN)["sha256"],
              "gm_kernel": _hash(GM_KERNEL)}
    if hashes != {"de440s": prior_protocol["source_contract"]["de440s_sha256"],
                  "mar099s": prior_protocol["source_contract"]["mar099s_sha256"],
                  "maven_cruise": prior_protocol["source_contract"]["maven_cruise_sha256"],
                  "gm_kernel": prior_protocol["source_contract"]["gm_kernel_sha256"]}:
        raise ValueError("MAVEN SRP NAIF source hash differs")
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
        step_total = 0

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

        rows = []
        model = config["model"]
        for prior in prior_snapshot["arcs"]:
            et = prior["initial_et_tdb_seconds"]
            initial = tuple(prior["initial_nav_sun_state_km_kms"])
            nav = tuple(float(x) for x in spice.spkezr("-202", et, "J2000", "NONE", "SUN")[0])
            if initial != nav:
                raise ValueError("MAVEN SRP initial state differs from pinned NAV SPK")
            by_step = {}
            for step in model["step_seconds"]:
                cases = {}
                count = config["baseline"]["horizon_seconds"] / step
                if not count.is_integer() or not 0 < count <= 100_000:
                    raise ValueError("bounded exact step count required")
                for coefficient in model["effective_area_over_mass_m2_per_kg"]:
                    state = initial
                    for i in range(int(count)):
                        step_total += 1
                        if step_total > config["compute_budget"]["maximum_rk4_steps_total"]:
                            raise ValueError("RK4 step budget exceeded")
                        state = rk4_step(state, et+i*step, step, gm, position_at,
                                         coefficient, model)
                    cases[str(coefficient)] = list(state)
                by_step[str(step)] = cases
            coarse = by_step[str(model["step_seconds"][0])]
            fine = by_step[str(model["step_seconds"][1])]
            baseline_coarse = coarse["0.0"]
            baseline_fine = fine["0.0"]
            zero_position_difference = norm([a-b for a, b in zip(
                baseline_coarse[:3], prior["planetary_force_endpoint_state_km_kms"][:3], strict=True)])
            zero_velocity_difference = norm([a-b for a, b in zip(
                baseline_coarse[3:], prior["planetary_force_endpoint_state_km_kms"][3:], strict=True)])
            cases = []
            for coefficient in model["effective_area_over_mass_m2_per_kg"]:
                key = str(coefficient)
                response = [a-b for a, b in zip(coarse[key], baseline_coarse, strict=True)]
                fine_response = [a-b for a, b in zip(fine[key], baseline_fine, strict=True)]
                cases.append({"effective_area_over_mass_m2_per_kg": coefficient,
                              "endpoint_state_km_kms": coarse[key],
                              "refined_endpoint_state_km_kms": fine[key],
                              "response_position_km": response[:3],
                              "response_velocity_km_s": response[3:],
                              "response_position_norm_km": norm(response[:3]),
                              "response_refinement_difference_km": norm([
                                  a-b for a, b in zip(response[:3], fine_response[:3], strict=True)])})
            rows.append({"initial_et_tdb_seconds": et,
                         "zero_coefficient_position_difference_from_prior_km": zero_position_difference,
                         "zero_coefficient_velocity_difference_from_prior_km_s": zero_velocity_difference,
                         "cases": cases})
        gates = config["engineering_gates"]
        checks = {
            "source_and_baseline_bound": True,
            "zero_coefficient_reproduces_prior": all(
                row["zero_coefficient_position_difference_from_prior_km"] <=
                gates["zero_coefficient_position_difference_km_max"] and
                row["zero_coefficient_velocity_difference_from_prior_km_s"] <=
                gates["zero_coefficient_velocity_difference_km_s_max"] for row in rows),
            "all_cases_reported": len(rows) == 2 and all(
                [case["effective_area_over_mass_m2_per_kg"] for case in row["cases"]] ==
                model["effective_area_over_mass_m2_per_kg"] for row in rows),
            "monotonic_radial_response_scale": all(
                next_case["response_position_norm_km"] + gates["monotonic_response_tolerance_km"] >=
                case["response_position_norm_km"]
                for row in rows for case, next_case in zip(row["cases"], row["cases"][1:])),
            "step_refinement": all(
                case["response_refinement_difference_km"] <=
                gates["refinement_response_difference_km_max"]
                for row in rows for case in row["cases"]),
            "finite_states_and_responses": all(
                isfinite(x) for row in rows for case in row["cases"]
                for x in (*case["endpoint_state_km_kms"],
                          *case["refined_endpoint_state_km_kms"],
                          *case["response_position_km"],
                          *case["response_velocity_km_s"],
                          case["response_position_norm_km"],
                          case["response_refinement_difference_km"])),
            "compute_budget": step_total <= config["compute_budget"]["maximum_rk4_steps_total"]
                              and query_count <= config["compute_budget"]["maximum_spice_position_queries"],
        }
        result = {"schema_version": "t1-maven-srp-sensitivity-snapshot-v1",
                  "protocol_sha256": PROTOCOL_SHA256,
                  "preregistration_commit": PREREGISTRATION_COMMIT,
                  "source_sha256": {**hashes,
                                    "nasa_solar_irradiance": _hash(NASA_HTML),
                                    "iau_2012_au": _hash(IAU_PDF),
                                    "maven_navigation_pdf": _hash(NAVIGATION_PDF)},
                  "prior_snapshot_sha256": config["baseline"]["prior_snapshot_sha256"],
                  "reader": {"package": "spiceypy", "version": version("spiceypy"),
                             "toolkit": spice.tkvrsn("TOOLKIT")},
                  "model": model, "engineering_gates": gates,
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
    return {"schema_version": "t1-maven-srp-sensitivity-audit-v1",
            "status": "passed-conditional-srp-sensitivity-only" if all(snapshot["checks"].values())
                      else "failed-conditional-srp-sensitivity",
            "protocol_sha256": PROTOCOL_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "source_files": [_source(path) for path in SOURCE_FILES],
            "snapshot_sha256": sha256(_json_bytes(snapshot)).hexdigest(),
            "source_sha256": snapshot["source_sha256"],
            "observed_budget": snapshot["observed_budget"],
            "checks": snapshot["checks"],
            "boundaries": {"conditional_response_scale": True,
                           "mission_srp_model_validated": False,
                           "statistical_uncertainty_interval": False,
                           "independent_observables": False,
                           "scientific_holdout": False,
                           "mission_validation": False,
                           "claim_status": "unverified"}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    snapshot = evaluate()
    audit = build_audit(snapshot)
    if args.write:
        payload = _json_bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != payload:
            raise ValueError("refusing to overwrite different MAVEN SRP snapshot")
        SNAPSHOT.write_bytes(payload)
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n",
                         encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != _json_bytes(snapshot):
            raise ValueError("saved MAVEN SRP snapshot differs from recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if (not isinstance(timestamp, str)
                or datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo is None
                or saved != audit):
            raise ValueError("saved MAVEN SRP audit differs from recomputation")
    print(json.dumps({"status": audit["status"], "checks": snapshot["checks"],
                      "observed_budget": snapshot["observed_budget"],
                      "arcs": [{"start_et": row["initial_et_tdb_seconds"],
                                "response_m": [case["response_position_norm_km"]*1000
                                               for case in row["cases"]]}
                               for row in snapshot["arcs"]]}, indent=2))
    if audit["status"].startswith("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
