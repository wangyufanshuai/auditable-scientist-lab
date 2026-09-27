"""Audit selected reconstructed MAVEN states as mission-source geometry only."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import tempfile

from fetch_maven_cruise import (
    DEFAULT_PATH as MAVEN, LABEL_URL, PRODUCT_LIDVID, URL as MAVEN_URL,
    fingerprint as fingerprint_maven,
)
from auditable_scientist.adapters.naif_de440s import _fingerprint as fingerprint_de440s
from auditable_scientist.adapters.naif_mars_center import fingerprint_mar099s


ROOT = Path(__file__).resolve().parents[1]
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"
SNAPSHOT = ROOT / "artifacts/t1-maven-source-snapshot.json"
AUDIT = ROOT / "artifacts/t1-maven-source-audit.json"
SOURCE_FILES = (
    ROOT / "scripts/fetch_maven_cruise.py", Path(__file__).resolve(),
    ROOT / "src/auditable_scientist/adapters/naif_de440s.py",
    ROOT / "src/auditable_scientist/adapters/naif_mars_center.py",
    ROOT / "docs/T1_MAVEN_MISSION_SOURCE.md",
    ROOT / "requirements-t1-mars-center-win-py312.txt",
)
SAMPLE_ET_TDB_SECONDS = (446_904_000.0, 464_616_000.0, 464_702_400.0)


def _bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _source(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def read_states(de440s: Path, mar099s: Path, maven: Path) -> dict:
    import spiceypy as spice
    from importlib.metadata import version

    de440s = de440s.resolve(strict=True)
    mar099s = mar099s.resolve(strict=True)
    maven = maven.resolve(strict=True)
    if len({de440s, mar099s, maven}) != 3:
        raise ValueError("mission source audit requires three distinct kernels")
    if tuple(path.name for path in (de440s, mar099s, maven)) != (
            "de440s.bsp", "mar099s.bsp", "maven_cru_rec_131118_140923_v1.bsp"):
        raise ValueError("mission source audit requires the named kernels")
    sources = {
        "de440s": fingerprint_de440s(de440s),
        "mar099s": fingerprint_mar099s(mar099s),
        "maven_cruise": fingerprint_maven(maven),
    }
    if spice.ktotal("SPK") != 0:
        raise ValueError("mission source audit requires an empty SPK pool")
    # MAVEN SPK includes planetary segments. The two later kernels own the
    # planetary chain, while body -202 remains the archived NAV solution.
    for path in (maven, mar099s, de440s):
        spice.furnsh(str(path))
    try:
        if spice.ktotal("SPK") != 3 or -202 not in set(spice.spkobj(str(maven))):
            raise ValueError("MAVEN mission source or kernel pool differs")
        coverage = spice.spkcov(str(maven), -202)
        if spice.wncard(coverage) != 1:
            raise ValueError("MAVEN -202 coverage is not one interval")
        start, stop = spice.wnfetd(coverage, 0)
        if not start < SAMPLE_ET_TDB_SECONDS[0] < SAMPLE_ET_TDB_SECONDS[-1] < stop:
            raise ValueError("fixed samples fall outside MAVEN coverage")

        def state(target: str, et: float, observer: str) -> list[float]:
            raw, _ = spice.spkezr(target, et, "J2000", "NONE", observer)
            result = [float(value) for value in raw]
            if len(result) != 6 or not all(math.isfinite(value) for value in result):
                raise ValueError("incomplete or nonfinite mission state")
            return result

        samples = []
        for et in SAMPLE_ET_TDB_SECONDS:
            _, descriptor, segment = spice.spksfs(-202, et, 80)
            body, center, frame, segment_type, first, last, _, _ = spice.spkuds(descriptor)
            if (body != -202 or center not in (10, 4) or frame != 1 or segment_type != 1
                    or not first <= et <= last):
                raise ValueError("MAVEN segment center/frame/type differs from contract")
            spacecraft = state("-202", et, "SUN")
            mars = state("MARS", et, "SUN")
            relative = state("-202", et, "MARS")
            difference = [a - b for a, b in zip(spacecraft, mars, strict=True)]
            chain_position_error_m = _norm([a-b for a, b in zip(relative[:3], difference[:3], strict=True)]) * 1000
            chain_velocity_error_m_s = _norm([a-b for a, b in zip(relative[3:], difference[3:], strict=True)]) * 1000
            if chain_position_error_m > 0.001 or chain_velocity_error_m_s > 1e-6:
                raise ValueError("mission state chain differs from explicit subtraction")
            samples.append({
                "et_tdb_seconds_past_j2000": et,
                "jd_tdb": 2_451_545.0 + et / 86_400.0,
                "maven_segment_center_id": center,
                "maven_segment_id": segment,
                "maven_sun_state_km_kms": spacecraft,
                "mars_center_sun_state_km_kms": mars,
                "maven_mars_center_state_km_kms": relative,
                "mars_center_distance_km": _norm(relative[:3]),
                "mars_center_relative_speed_km_s": _norm(relative[3:]),
                "chain_position_error_m": chain_position_error_m,
                "chain_velocity_error_m_s": chain_velocity_error_m_s,
            })
        if [row["maven_segment_center_id"] for row in samples] != [10, 4, 4]:
            raise ValueError("sampled mission segment transition differs")
        result = {
            "schema_version": "t1-maven-source-snapshot-v1",
            "mission_product": {"url": MAVEN_URL, "label_url": LABEL_URL,
                                "lidvid": PRODUCT_LIDVID, **sources["maven_cruise"]},
            "sources": {"de440s": sources["de440s"], "mar099s": sources["mar099s"]},
            "reader": {"package": "spiceypy", "version": version("spiceypy"),
                       "toolkit": spice.tkvrsn("TOOLKIT")},
            "coordinate_contract": {"frame": "J2000", "aberration": "NONE",
                                    "time_scale": "TDB", "time_origin": "J2000 JD 2451545.0",
                                    "state_units": ["km", "km/s"],
                                    "kernel_load_order": ["maven_cruise", "mar099s", "de440s"]},
            "spacecraft_id": -202,
            "spacecraft_coverage_et_tdb_seconds": [start, stop],
            "samples": samples,
            "sampling_status": "exploratory-selected-after-source-inspection; not a holdout",
            "claim_status": "unverified",
            "meaning": "archived reconstructed-spacecraft and Mars-center geometry only",
        }
    finally:
        for path in (de440s, mar099s, maven):
            spice.unload(str(path))
    if spice.ktotal("SPK") != 0 or sources != {
            "de440s": fingerprint_de440s(de440s),
            "mar099s": fingerprint_mar099s(mar099s),
            "maven_cruise": fingerprint_maven(maven)}:
        raise ValueError("source bytes or SPK pool changed during mission source audit")
    return result


def build_audit(snapshot: dict, de440s: Path, mar099s: Path, maven: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="scientist-maven-negative-") as temporary:
        bad = Path(temporary) / maven.name
        bad.write_bytes(b"forged mission kernel")
        try:
            read_states(de440s, mar099s, bad)
        except ValueError:
            wrong_kernel_rejected = True
        else:
            wrong_kernel_rejected = False
    checks = {
        "pds_label_md5_and_size_matched": snapshot["mission_product"]["md5"] ==
            "8d7c55ef3bb935ad487c529f5be5343d" and snapshot["mission_product"]["bytes"] == 4_797_440,
        "pinned_sha256_matched": snapshot["mission_product"]["sha256"] ==
            "07c76dfc2a1f66a54b4dd74105b2a5a70d72192813abee3659a74d4d21988dc5",
        "three_declared_samples": len(snapshot["samples"]) == 3,
        "center_transition_observed": [row["maven_segment_center_id"] for row in snapshot["samples"]] == [10, 4, 4],
        "mars_approach_observed": snapshot["samples"][0]["mars_center_distance_km"] > 100_000_000
            and all(row["mars_center_distance_km"] < 100_000 for row in snapshot["samples"][1:]),
        "direct_chain_consistent": all(row["chain_position_error_m"] < 0.001 for row in snapshot["samples"]),
        "mission_claim_unverified": snapshot["claim_status"] == "unverified",
        "wrong_kernel_rejected": wrong_kernel_rejected,
    }
    return {
        "schema_version": "t1-maven-source-audit-v1",
        "status": "verified-source-tracked-reconstructed-mission-geometry-only" if all(checks.values()) else "failed",
        "source_files": [_source(path) for path in SOURCE_FILES],
        "snapshot_sha256": sha256(_bytes(snapshot)).hexdigest(),
        "kernel_local_paths": {"de440s": de440s.relative_to(ROOT).as_posix(),
                               "mar099s": mar099s.relative_to(ROOT).as_posix(),
                               "maven_cruise": maven.relative_to(ROOT).as_posix()},
        "checks": checks,
        "source_rights": {"rules_url": "https://naif.jpl.nasa.gov/naif/rules.html",
                          "citation_url": "https://naif.jpl.nasa.gov/naif/credit.html",
                          "product_label_url": LABEL_URL,
                          "unmodified_kernel_redistributed": False},
        "boundaries": {"archived_spacecraft_states_available": True,
                       "independent_planetary_ephemeris": False,
                       "independent_spacecraft_propagation": False,
                       "mission_validation": False,
                       "scientific_holdout": False,
                       "publication_ready": False},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    paths = (DE440S.resolve(strict=True), MAR099S.resolve(strict=True), MAVEN.resolve(strict=True))
    if any(not path.is_relative_to(ROOT) for path in paths):
        raise ValueError("mission source audit requires local pinned kernels")
    snapshot = read_states(*paths)
    audit = build_audit(snapshot, *paths)
    if audit["status"] != "verified-source-tracked-reconstructed-mission-geometry-only":
        raise ValueError(f"MAVEN source audit failed: {audit['checks']}")
    if args.write:
        contents = _bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != contents:
            raise ValueError("refusing to overwrite a different MAVEN source snapshot")
        SNAPSHOT.write_bytes(contents)
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != _bytes(snapshot):
            raise ValueError("saved MAVEN state differs from offline recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if (not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None
                or saved != audit):
            raise ValueError("saved MAVEN source audit differs from recomputation")
    print(json.dumps({"status": audit["status"], "checks": audit["checks"],
                      "snapshot_sha256": audit["snapshot_sha256"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
