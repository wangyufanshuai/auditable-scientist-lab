"""Compare a predeclared Sun-only RK4 trajectory with archived MAVEN NAV states."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

from fetch_maven_cruise import DEFAULT_PATH as MAVEN, fingerprint as fingerprint_maven
from auditable_scientist.adapters.naif_de440s import _fingerprint as fingerprint_de440s
from auditable_scientist.adapters.naif_mars_center import fingerprint_mar099s


ROOT = Path(__file__).resolve().parents[1]
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"
PROTOCOL = ROOT / "docs/T1_MAVEN_PROPAGATION_PREFLIGHT.json"
PROTOCOL_SHA256 = "a37b11b983a9ea0765682d4457c8eed9b378566262fa3adc478d7d60ef9e5a47"
PREREGISTRATION_COMMIT = "27cc842553d3ff888df092883ff9f50225e92aae"
SNAPSHOT = ROOT / "artifacts/t1-maven-preflight-snapshot.json"
AUDIT = ROOT / "artifacts/t1-maven-preflight-audit.json"
SOURCE_FILES = (
    Path(__file__).resolve(), ROOT / "scripts/fetch_maven_cruise.py", PROTOCOL,
    ROOT / "docs/T1_MAVEN_PROPAGATION_PREFLIGHT.md",
    ROOT / "src/auditable_scientist/adapters/naif_de440s.py",
    ROOT / "src/auditable_scientist/adapters/naif_mars_center.py",
    ROOT / "requirements-t1-mars-center-win-py312.txt",
)


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _source(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def _norm(values: list[float] | tuple[float, ...]) -> float:
    return math.sqrt(sum(value * value for value in values))


def derivative(state: tuple[float, ...], mu: float, gravity_sign: int = 1) -> tuple[float, ...]:
    if len(state) != 6 or not all(math.isfinite(value) for value in state):
        raise ValueError("finite six-component state required")
    if not math.isfinite(mu) or mu <= 0 or gravity_sign not in (-1, 1):
        raise ValueError("positive finite GM and declared gravity sign required")
    radius = _norm(state[:3])
    if radius <= 0:
        raise ValueError("nonzero heliocentric radius required")
    factor = -gravity_sign * mu / radius ** 3
    return (state[3], state[4], state[5],
            factor * state[0], factor * state[1], factor * state[2])


def rk4_step(state: tuple[float, ...], mu: float, dt: float,
             gravity_sign: int = 1) -> tuple[float, ...]:
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("positive finite time step required")
    k1 = derivative(state, mu, gravity_sign)
    k2 = derivative(tuple(x + dt * k / 2 for x, k in zip(state, k1, strict=True)),
                    mu, gravity_sign)
    k3 = derivative(tuple(x + dt * k / 2 for x, k in zip(state, k2, strict=True)),
                    mu, gravity_sign)
    k4 = derivative(tuple(x + dt * k for x, k in zip(state, k3, strict=True)),
                    mu, gravity_sign)
    result = tuple(x + dt * (a + 2*b + 2*c + d) / 6
                   for x, a, b, c, d in zip(state, k1, k2, k3, k4, strict=True))
    if not all(math.isfinite(value) for value in result):
        raise ValueError("nonfinite RK4 result")
    return result


def propagate(state: tuple[float, ...], mu: float, horizon: float, step: float,
              gravity_sign: int = 1) -> tuple[float, ...]:
    steps = horizon / step
    if (not math.isfinite(steps) or not steps.is_integer() or steps <= 0
            or steps > 100_000):
        raise ValueError("horizon must be a bounded exact number of steps")
    result = state
    for _ in range(int(steps)):
        result = rk4_step(result, mu, step, gravity_sign)
    return result


def specific_energy(state: tuple[float, ...], mu: float) -> float:
    return 0.5 * sum(value * value for value in state[3:]) - mu / _norm(state[:3])


def _protocol() -> dict:
    data = PROTOCOL.read_bytes()
    if sha256(data).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("precommitted MAVEN protocol bytes changed")
    config = json.loads(data)
    if (config.get("schema_version") != "t1-maven-sun-only-preflight-v1"
            or config.get("status") != "predeclared-engineering-comparison-not-scientific-validation"
            or config.get("scientific_boundaries", {}).get("claim_status") != "unverified"):
        raise ValueError("MAVEN preflight protocol or boundary differs")
    return config


def evaluate(de440s: Path, mar099s: Path, maven: Path) -> dict:
    import spiceypy as spice
    from importlib.metadata import version

    config = _protocol()
    de440s = de440s.resolve(strict=True)
    mar099s = mar099s.resolve(strict=True)
    maven = maven.resolve(strict=True)
    if len({de440s, mar099s, maven}) != 3 or tuple(path.name for path in (de440s, mar099s, maven)) != (
            "de440s.bsp", "mar099s.bsp", "maven_cru_rec_131118_140923_v1.bsp"):
        raise ValueError("preflight requires three distinct pinned kernels")
    source_hashes = {"de440s": fingerprint_de440s(de440s),
                     "mar099s": fingerprint_mar099s(mar099s),
                     "maven_cruise": fingerprint_maven(maven)}
    if spice.ktotal("SPK") != 0:
        raise ValueError("preflight requires an empty SPK pool")
    for path in (maven, mar099s, de440s):
        spice.furnsh(str(path))
    try:
        if spice.ktotal("SPK") != 3 or -202 not in set(spice.spkobj(str(maven))):
            raise ValueError("spacecraft source or pool differs")
        coverage = spice.spkcov(str(maven), -202)
        if spice.wncard(coverage) != 1:
            raise ValueError("MAVEN spacecraft coverage differs")
        coverage_start, coverage_end = spice.wnfetd(coverage, 0)
        times = config["time_contract"]
        mu = config["model"]["mu_sun_km3_s2"]
        step = config["model"]["step_seconds"]
        refined_step = config["model"]["refinement_step_seconds"]
        horizon = times["horizon_seconds"]
        gates = config["engineering_gates"]
        arcs = []
        for start_et in times["initial_et_seconds"]:
            stop_et = start_et + horizon
            if not coverage_start < start_et < stop_et < coverage_end:
                raise ValueError("predeclared arc falls outside NAV coverage")
            # The NAV kernel supplies initial and held endpoint states only.
            initial = tuple(float(value) for value in spice.spkezr("-202", start_et, "J2000", "NONE", "SUN")[0])
            nav_endpoint = tuple(float(value) for value in spice.spkezr("-202", stop_et, "J2000", "NONE", "SUN")[0])
            if not all(math.isfinite(value) for value in (*initial, *nav_endpoint)):
                raise ValueError("nonfinite NAV state")
            _, start_descriptor, _ = spice.spksfs(-202, start_et, 80)
            _, stop_descriptor, _ = spice.spksfs(-202, stop_et, 80)
            start_center = spice.spkuds(start_descriptor)[1]
            stop_center = spice.spkuds(stop_descriptor)[1]
            if start_center != 10 or stop_center != 10:
                raise ValueError("preflight arcs must use direct Sun-centered MAVEN segments")
            predicted = propagate(initial, mu, horizon, step)
            refined = propagate(initial, mu, horizon, refined_step)
            repulsive = propagate(initial, mu, horizon, step, gravity_sign=-1)
            position_error = _norm([a-b for a, b in zip(predicted[:3], nav_endpoint[:3], strict=True)])
            velocity_error = _norm([a-b for a, b in zip(predicted[3:], nav_endpoint[3:], strict=True)])
            refinement_error = _norm([a-b for a, b in zip(predicted[:3], refined[:3], strict=True)])
            repulsive_error = _norm([a-b for a, b in zip(repulsive[:3], nav_endpoint[:3], strict=True)])
            initial_energy = specific_energy(initial, mu)
            energy_drift = abs(specific_energy(predicted, mu) - initial_energy) / max(abs(initial_energy), 1.0)
            passed = (position_error <= gates["endpoint_position_error_km_max"]
                      and velocity_error <= gates["endpoint_velocity_error_km_s_max"]
                      and refinement_error <= gates["refinement_position_difference_km_max"]
                      and energy_drift <= gates["relative_two_body_energy_drift_max"]
                      and repulsive_error > gates["endpoint_position_error_km_max"])
            arcs.append({
                "initial_et_tdb_seconds": start_et, "endpoint_et_tdb_seconds": stop_et,
                "start_segment_center_id": start_center, "endpoint_segment_center_id": stop_center,
                "initial_nav_sun_state_km_kms": list(initial),
                "held_nav_endpoint_sun_state_km_kms": list(nav_endpoint),
                "sun_only_rk4_endpoint_state_km_kms": list(predicted),
                "position_error_km": position_error, "velocity_error_km_s": velocity_error,
                "refinement_position_difference_km": refinement_error,
                "relative_two_body_energy_drift": energy_drift,
                "wrong_sign_position_error_km": repulsive_error,
                "engineering_gates_passed": passed,
            })
        result = {
            "schema_version": "t1-maven-sun-only-preflight-snapshot-v1",
            "protocol_sha256": PROTOCOL_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "source_hashes": source_hashes,
            "reader": {"package": "spiceypy", "version": version("spiceypy"),
                       "toolkit": spice.tkvrsn("TOOLKIT")},
            "coordinate_contract": config["coordinate_contract"],
            "model": config["model"], "engineering_gates": gates,
            "spacecraft_coverage_et_tdb_seconds": [coverage_start, coverage_end],
            "arcs": arcs,
            "engineering_preflight_passed": all(arc["engineering_gates_passed"] for arc in arcs),
            "claim_status": "unverified",
            "scientific_boundaries": {"mission_validation": False, "full_force_model": False,
                                      "maneuver_reconstruction": False,
                                      "untouched_scientific_holdout": False},
        }
    finally:
        for path in (de440s, mar099s, maven):
            spice.unload(str(path))
    # These two NAV arcs should need no planetary bridge: the mission SPK
    # alone must reproduce the states used above, byte for byte.
    if spice.ktotal("SPK") != 0:
        raise ValueError("SPK pool was not emptied before mission-only check")
    spice.furnsh(str(maven))
    try:
        mission_only_equal = all(
            list(spice.spkezr("-202", arc["initial_et_tdb_seconds"], "J2000", "NONE", "SUN")[0]) ==
            arc["initial_nav_sun_state_km_kms"]
            and list(spice.spkezr("-202", arc["endpoint_et_tdb_seconds"], "J2000", "NONE", "SUN")[0]) ==
            arc["held_nav_endpoint_sun_state_km_kms"]
            for arc in result["arcs"]
        )
    finally:
        spice.unload(str(maven))
    if not mission_only_equal:
        raise ValueError("planetary kernels altered a direct Sun-centered MAVEN state")
    result["mission_only_states_equal"] = True
    if spice.ktotal("SPK") != 0 or source_hashes != {
            "de440s": fingerprint_de440s(de440s),
            "mar099s": fingerprint_mar099s(mar099s),
            "maven_cruise": fingerprint_maven(maven)}:
        raise ValueError("source bytes or kernel pool changed during preflight")
    return result


def build_audit(snapshot: dict) -> dict:
    return {
        "schema_version": "t1-maven-sun-only-preflight-audit-v1",
        "status": "passed-engineering-preflight-only" if snapshot["engineering_preflight_passed"]
                  else "failed-engineering-preflight",
        "protocol_sha256": PROTOCOL_SHA256,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "source_files": [_source(path) for path in SOURCE_FILES],
        "snapshot_sha256": sha256(_json_bytes(snapshot)).hexdigest(),
        "arc_count": len(snapshot["arcs"]),
        "engineering_preflight_passed": snapshot["engineering_preflight_passed"],
        "mission_only_states_equal": snapshot["mission_only_states_equal"],
        "boundaries": {"real_mission_source": True, "independent_sun_only_propagation": True,
                       "full_force_model": False, "mission_validation": False,
                       "scientific_holdout": False, "publication_ready": False},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    snapshot = evaluate(DE440S, MAR099S, MAVEN)
    audit = build_audit(snapshot)
    if args.write:
        contents = _json_bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != contents:
            raise ValueError("refusing to overwrite a different preflight snapshot")
        SNAPSHOT.write_bytes(contents)
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != _json_bytes(snapshot):
            raise ValueError("saved preflight states differ from recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if (not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None
                or saved != audit):
            raise ValueError("saved preflight audit differs from recomputation")
    print(json.dumps({"status": audit["status"], "arcs": [
        {"start_et": arc["initial_et_tdb_seconds"], "position_error_km": arc["position_error_km"],
         "velocity_error_km_s": arc["velocity_error_km_s"], "passed": arc["engineering_gates_passed"]}
        for arc in snapshot["arcs"]], "snapshot_sha256": audit["snapshot_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
