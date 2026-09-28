"""Recompute a predeclared MAVEN short-arc planetary-tide diagnostic."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from fetch_maven_cruise import DEFAULT_PATH as MAVEN, fingerprint as fingerprint_maven
from auditable_scientist.adapters.naif_de440s import _fingerprint as fingerprint_de440s
from auditable_scientist.adapters.naif_mars_center import fingerprint_mar099s


ROOT = Path(__file__).resolve().parents[1]
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"
GM_KERNEL = ROOT / "data/naif/gm_de440.tpc"
PROTOCOL = ROOT / "docs/T1_MAVEN_PLANETARY_FORCE_PROTOCOL.json"
PROTOCOL_SHA256 = "15095d28e9f74896edbd41b3edb1ef9e5eb82d469a29d1a6a70fd3ec3528a394"
PREREGISTRATION_COMMIT = "4b98a57"
BASELINE = ROOT / "artifacts/t1-maven-preflight-snapshot.json"
SNAPSHOT = ROOT / "artifacts/t1-maven-planetary-force-snapshot.json"
AUDIT = ROOT / "artifacts/t1-maven-planetary-force-audit.json"
SOURCE_FILES = (Path(__file__).resolve(), PROTOCOL,
                ROOT / "docs/T1_MAVEN_PLANETARY_FORCE_PROTOCOL.md",
                ROOT / "scripts/fetch_maven_cruise.py",
                ROOT / "src/auditable_scientist/adapters/naif_de440s.py",
                ROOT / "src/auditable_scientist/adapters/naif_mars_center.py")


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def norm(vector: tuple[float, ...] | list[float]) -> float:
    return math.sqrt(sum(component * component for component in vector))


def source(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def protocol() -> dict:
    data = PROTOCOL.read_bytes()
    if sha256(data).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("precommitted planetary-force protocol changed")
    config = json.loads(data)
    if (config.get("schema_version") != "t1-maven-planetary-force-protocol-v1"
            or config.get("scientific_boundaries", {}).get("claim_status") != "unverified"
            or config.get("scientific_boundaries", {}).get("mission_validation") is not False):
        raise ValueError("planetary-force protocol boundary differs")
    return config


def gm_values(path: Path, config: dict) -> dict[int, float]:
    data = path.read_bytes()
    if sha256(data).hexdigest() != config["source_contract"]["gm_kernel_sha256"]:
        raise ValueError("GM kernel differs from pinned NAIF bytes")
    content = data.decode("ascii")
    result = {}
    for body in (3, 4, 10):
        matches = re.findall(rf"^\s*BODY{body}_GM\s*=\s*\(\s*([\d.EeDd+-]+)\s*\)",
                             content, flags=re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f"GM kernel must contain one BODY{body}_GM")
        value = float(matches[0].replace("D", "E"))
        if not math.isfinite(value) or value <= 0:
            raise ValueError("positive finite GM required")
        result[body] = value
    expected = {10: config["model"]["sun_gm_km3_s2"],
                **{row["naif_id"]: row["gm_km3_s2"] for row in config["model"]["perturbers"]}}
    if result != expected:
        raise ValueError("protocol GM values differ from pinned NAIF kernel")
    return result


def third_body_acceleration(position: tuple[float, ...], planet: tuple[float, ...],
                            gm: float, indirect_sign: int = -1) -> tuple[float, ...]:
    if len(position) != 3 or len(planet) != 3 or not all(
            math.isfinite(v) for v in (*position, *planet, gm)) or gm <= 0:
        raise ValueError("finite position and positive GM required")
    if indirect_sign not in (-1, 1):
        raise ValueError("invalid indirect-term sign")
    delta = tuple(p-r for p, r in zip(planet, position, strict=True))
    distance = norm(delta)
    planet_distance = norm(planet)
    if distance <= 0 or planet_distance <= 0:
        raise ValueError("third-body singularity")
    return tuple(gm * (d / distance**3 + indirect_sign * p / planet_distance**3)
                 for d, p in zip(delta, planet, strict=True))


def rk4_step(state: tuple[float, ...], et: float, dt: float, gm: dict[int, float],
             position_at: object) -> tuple[float, ...]:
    if len(state) != 6 or not all(math.isfinite(x) for x in state) or dt <= 0:
        raise ValueError("finite six-component state and positive step required")

    def derivative(sample: tuple[float, ...], time: float) -> tuple[float, ...]:
        r = sample[:3]
        radius = norm(r)
        if radius <= 0:
            raise ValueError("solar singularity")
        a = [-gm[10] * x / radius**3 for x in r]
        for body in (3, 4):
            planet = position_at(body, time)
            tide = third_body_acceleration(r, planet, gm[body])
            a = [x+y for x, y in zip(a, tide, strict=True)]
        return (*sample[3:], *a)

    k1 = derivative(state, et)
    k2 = derivative(tuple(x+dt*k/2 for x, k in zip(state, k1, strict=True)), et+dt/2)
    k3 = derivative(tuple(x+dt*k/2 for x, k in zip(state, k2, strict=True)), et+dt/2)
    k4 = derivative(tuple(x+dt*k for x, k in zip(state, k3, strict=True)), et+dt)
    result = tuple(x+dt*(a+2*b+2*c+d)/6 for x, a, b, c, d in
                   zip(state, k1, k2, k3, k4, strict=True))
    if not all(math.isfinite(x) for x in result):
        raise ValueError("nonfinite integrated state")
    return result


def propagate(state: tuple[float, ...], start_et: float, horizon: float, dt: float,
              gm: dict[int, float], position_at: object) -> tuple[float, ...]:
    steps = horizon / dt
    if not math.isfinite(steps) or not steps.is_integer() or not 0 < steps <= 100_000:
        raise ValueError("bounded exact number of steps required")
    result = state
    for i in range(int(steps)):
        result = rk4_step(result, start_et+i*dt, dt, gm, position_at)
    return result


def evaluate(de440s: Path = DE440S, mar099s: Path = MAR099S,
             maven: Path = MAVEN, gm_kernel: Path = GM_KERNEL) -> dict:
    import spiceypy as spice
    from importlib.metadata import version

    config = protocol()
    paths = tuple(path.resolve(strict=True) for path in (de440s, mar099s, maven, gm_kernel))
    if len(set(paths)) != 4 or tuple(path.name for path in paths) != (
            "de440s.bsp", "mar099s.bsp", "maven_cru_rec_131118_140923_v1.bsp",
            "gm_de440.tpc"):
        raise ValueError("four distinct named NAIF sources required")
    de440s, mar099s, maven, gm_kernel = paths
    hashes = {"de440s": fingerprint_de440s(de440s)["sha256"],
              "mar099s": fingerprint_mar099s(mar099s)["sha256"],
              "maven_cruise": fingerprint_maven(maven)["sha256"],
              "gm_kernel": sha256(gm_kernel.read_bytes()).hexdigest()}
    if hashes != {"de440s": config["source_contract"]["de440s_sha256"],
                  "mar099s": config["source_contract"]["mar099s_sha256"],
                  "maven_cruise": config["source_contract"]["maven_cruise_sha256"],
                  "gm_kernel": config["source_contract"]["gm_kernel_sha256"]}:
        raise ValueError("NAIF source hash mismatch")
    gm = gm_values(gm_kernel, config)
    prior = json.loads(BASELINE.read_text(encoding="utf-8"))
    if (prior.get("protocol_sha256") !=
            "a37b11b983a9ea0765682d4457c8eed9b378566262fa3adc478d7d60ef9e5a47"
            or len(prior.get("arcs", [])) != 2):
        raise ValueError("Sun-only comparison source differs")
    if spice.ktotal("SPK") != 0:
        raise ValueError("empty SPK pool required")
    for path in (maven, mar099s, de440s):
        spice.furnsh(str(path))
    try:
        if spice.ktotal("SPK") != 3:
            raise ValueError("expected three pinned SPKs")
        position_cache = {}

        def position_at(body: int, et: float) -> tuple[float, ...]:
            key = (body, et)
            if key not in position_cache:
                values, _ = spice.spkpos(str(body), et, "J2000", "NONE", "SUN")
                result = tuple(float(x) for x in values)
                if len(result) != 3 or not all(math.isfinite(x) for x in result):
                    raise ValueError("nonfinite planetary state")
                position_cache[key] = result
            return position_cache[key]

        arcs = []
        settings = config["arc_contract"]
        gates = config["engineering_gates"]
        for start_et, previous in zip(settings["initial_et_tdb_seconds"], prior["arcs"], strict=True):
            stop_et = start_et + settings["horizon_seconds"]
            if (previous["initial_et_tdb_seconds"] != start_et
                    or previous["endpoint_et_tdb_seconds"] != stop_et):
                raise ValueError("preflight arc epoch differs")
            for et in (start_et, stop_et):
                _, descriptor, _ = spice.spksfs(-202, et, 80)
                if spice.spkuds(descriptor)[1] != settings["segment_center_id_required"]:
                    raise ValueError("MAVEN arc is not direct Sun-centered")
            initial = tuple(float(x) for x in spice.spkezr("-202", start_et, "J2000", "NONE", "SUN")[0])
            endpoint = tuple(float(x) for x in spice.spkezr("-202", stop_et, "J2000", "NONE", "SUN")[0])
            if (list(initial) != previous["initial_nav_sun_state_km_kms"]
                    or list(endpoint) != previous["held_nav_endpoint_sun_state_km_kms"]):
                raise ValueError("NAV states differ from bound Sun-only preflight")
            predicted = propagate(initial, start_et, settings["horizon_seconds"],
                                  config["model"]["step_seconds"], gm, position_at)
            refined = propagate(initial, start_et, settings["horizon_seconds"],
                                config["model"]["refinement_step_seconds"], gm, position_at)
            position_error = norm([a-b for a, b in zip(predicted[:3], endpoint[:3], strict=True)])
            velocity_error = norm([a-b for a, b in zip(predicted[3:], endpoint[3:], strict=True)])
            refinement_error = norm([a-b for a, b in zip(predicted[:3], refined[:3], strict=True)])
            baseline_error = previous["position_error_km"]
            passed = (math.isfinite(position_error) and math.isfinite(velocity_error)
                      and refinement_error <= gates["refinement_position_difference_km_max"]
                      and position_error <= gates["endpoint_error_limit_km"])
            arcs.append({"initial_et_tdb_seconds": start_et,
                         "endpoint_et_tdb_seconds": stop_et,
                         "initial_nav_sun_state_km_kms": list(initial),
                         "held_nav_endpoint_sun_state_km_kms": list(endpoint),
                         "planetary_force_endpoint_state_km_kms": list(predicted),
                         "position_error_km": position_error,
                         "velocity_error_km_s": velocity_error,
                         "refinement_position_difference_km": refinement_error,
                         "sun_only_position_error_km": baseline_error,
                         "position_error_delta_from_sun_only_km": position_error-baseline_error,
                         "engineering_gates_passed": passed})
        probe = (100_000_000.0, -20_000_000.0, 5_000_000.0)
        identity = all(third_body_acceleration((0.0, 0.0, 0.0), probe, gm[body]) ==
                       (0.0, 0.0, 0.0) for body in (3, 4))
        wrong_sign = any(norm(third_body_acceleration((0.0, 0.0, 0.0), probe,
                                                     gm[body], indirect_sign=1)) > 0
                         for body in (3, 4))
        if not identity or not wrong_sign:
            raise ValueError("indirect-term negative control failed")
        result = {"schema_version": "t1-maven-planetary-force-snapshot-v1",
                  "protocol_sha256": PROTOCOL_SHA256,
                  "preregistration_commit": PREREGISTRATION_COMMIT,
                  "source_sha256": hashes,
                  "baseline_snapshot_sha256": sha256(BASELINE.read_bytes()).hexdigest(),
                  "reader": {"package": "spiceypy", "version": version("spiceypy"),
                             "toolkit": spice.tkvrsn("TOOLKIT")},
                  "coordinate_contract": config["coordinate_contract"],
                  "model": config["model"], "engineering_gates": gates,
                  "indirect_term_identity_at_sun": identity,
                  "wrong_indirect_sign_rejected": wrong_sign,
                  "arcs": arcs,
                  "engineering_gates_passed": all(row["engineering_gates_passed"] for row in arcs),
                  "claim_status": "unverified",
                  "scientific_boundaries": config["scientific_boundaries"]}
    finally:
        for path in (de440s, mar099s, maven):
            spice.unload(str(path))
    if spice.ktotal("SPK") != 0:
        raise ValueError("SPK pool not emptied")
    return result


def build_audit(snapshot: dict) -> dict:
    return {"schema_version": "t1-maven-planetary-force-audit-v1",
            "status": "passed-engineering-diagnostic-only" if snapshot["engineering_gates_passed"]
                      else "failed-engineering-diagnostic",
            "protocol_sha256": PROTOCOL_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "source_files": [source(path) for path in SOURCE_FILES],
            "snapshot_sha256": sha256(json_bytes(snapshot)).hexdigest(),
            "arc_count": len(snapshot["arcs"]),
            "engineering_gates_passed": snapshot["engineering_gates_passed"],
            "boundaries": {"real_mission_reconstructed_states": True,
                           "planetary_tide_model": True,
                           "maneuver_model": False, "independent_observables": False,
                           "scientific_holdout": False, "mission_validation": False}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    snapshot = evaluate()
    audit = build_audit(snapshot)
    if args.write:
        contents = json_bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != contents:
            raise ValueError("refusing to overwrite a different planetary-force snapshot")
        SNAPSHOT.write_bytes(contents)
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != json_bytes(snapshot):
            raise ValueError("saved planetary-force snapshot differs from recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if (not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None
                or saved != audit):
            raise ValueError("saved planetary-force audit differs from recomputation")
    print(json.dumps({"status": audit["status"], "arcs": [
        {"start_et": arc["initial_et_tdb_seconds"],
         "position_error_km": arc["position_error_km"],
         "delta_from_sun_only_km": arc["position_error_delta_from_sun_only_km"],
         "passed": arc["engineering_gates_passed"]} for arc in snapshot["arcs"]],
        "snapshot_sha256": audit["snapshot_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
