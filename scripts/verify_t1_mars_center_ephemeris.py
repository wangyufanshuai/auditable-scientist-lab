"""Audit two fixed-date Mars-center states without promoting a mission Claim."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from auditable_scientist.adapters.naif_mars_center import compare_fixed_departures_center


ROOT = Path(__file__).resolve().parents[1]
DE440S = ROOT / "data/naif/de440s.bsp"
MAR099S = ROOT / "data/naif/mar099s.bsp"
OLDER = ROOT / "artifacts/t1-de440s-ephemeris-snapshot.json"
SNAPSHOT = ROOT / "artifacts/t1-mars-center-ephemeris-snapshot.json"
AUDIT = ROOT / "artifacts/t1-mars-center-ephemeris-audit.json"
SOURCES = (
    Path(__file__).resolve(), ROOT / "scripts/fetch_mar099s.py",
    ROOT / "src/auditable_scientist/adapters/naif_mars_center.py",
    ROOT / "src/auditable_scientist/adapters/naif_de440s.py",
    ROOT / "docs/T1_MARS_CENTER_EPHEMERIS.md",
    ROOT / "requirements-t1-mars-center-win-py312.txt",
    OLDER,
)


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _source(path: Path) -> dict[str, str | int]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def build_audit(de440s: Path, mar099s: Path, snapshot: dict) -> dict:
    older = json.loads(OLDER.read_text(encoding="utf-8"))
    cases = snapshot["cases"]
    old_cases = older["cases"]
    with tempfile.TemporaryDirectory(prefix="scientist-mars-center-negative-") as temporary:
        fake = Path(temporary) / "mar099s.bsp"
        fake.write_bytes(b"not a NAIF kernel")
        try:
            compare_fixed_departures_center(de440s, fake)
        except ValueError:
            wrong_kernel_rejected = True
        else:
            wrong_kernel_rejected = False
    checks = {
        "official_md5_matched": snapshot["sources"]["mar099s"]["md5"] ==
            "fd7302dfbaa0c63ce85b1e98923ee6a1",
        "pinned_sha256_matched": snapshot["sources"]["mar099s"]["sha256"] ==
            "997dc93ba640e476da7a494d2237dcdeb145e528db37be8ccee588c615e4e1ff",
        "de440s_source_preserved": snapshot["sources"]["de440s"] == older["source"],
        "fixed_departure_dates": [row["departure_jd_tdb"] for row in cases] ==
            [2460584.5, 2461375.5],
        "planetary_states_preserved": len(cases) == len(old_cases) == 2 and all(
            case["earth_departure_state_km_kms"] == old["earth_departure_state_km_kms"]
            and case["mars_barycenter_departure_state_km_kms"] ==
            old["mars_barycenter_departure_state_km_kms"]
            for case, old in zip(cases, old_cases, strict=True)
        ),
        "mars_499_coverage": snapshot["mars_499_coverage_et_seconds"] ==
            [-157809600.0, 1577880000.0],
        "center_offset_bounded": all(0 <= row["center_barycenter_separation_m"] < 1
                                     for row in cases),
        "spice_chain_consistent": all(row["spice_chain_position_error_m"] < 0.01
                                      for row in cases),
        "mission_claim_unverified": snapshot["claim_status"] == "unverified",
        "wrong_kernel_rejected": wrong_kernel_rejected,
    }
    return {
        "schema_version": "t1-mars-center-ephemeris-audit-v1",
        "status": "verified-source-tracked-center-geometry-only" if all(checks.values()) else "failed",
        "kernel_sources": snapshot["sources"],
        "kernel_local_paths": {"de440s": de440s.relative_to(ROOT).as_posix(),
                               "mar099s": mar099s.relative_to(ROOT).as_posix()},
        "source_rights": {
            "rules_url": "https://naif.jpl.nasa.gov/naif/rules.html",
            "satellite_guide_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/AAREADME_Satellite_SPKs",
            "checksum_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/aa_checksums.txt",
            "use": "NAIF kernels may be downloaded and used by anyone, subject to NAIF rules",
            "redistribution": "permitted only for unmodified NAIF-distributed kernels",
            "kernels_redistributed_in_repository": False,
            "applies_to_unrelated_sources": False,
        },
        "snapshot_sha256": sha256(_json_bytes(snapshot)).hexdigest(),
        "source_files": [_source(path) for path in SOURCES],
        "checks": checks,
        "boundaries": {
            "mars_center_state_available": True,
            "source_tracked_ephemeris_geometry": True,
            "independent_planetary_ephemeris": False,
            "spacecraft_trajectory_propagated": False,
            "mission_trajectory_validated": False,
            "scientific_holdout": False,
            "publication_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--de440s", type=Path, default=DE440S)
    parser.add_argument("--mar099s", type=Path, default=MAR099S)
    args = parser.parse_args()
    de440s = args.de440s.resolve(strict=True)
    mar099s = args.mar099s.resolve(strict=True)
    if (not de440s.is_relative_to(ROOT) or not mar099s.is_relative_to(ROOT)
            or de440s.name != "de440s.bsp" or mar099s.name != "mar099s.bsp"):
        raise ValueError("Mars-center audit requires named local kernels under this project")
    snapshot = compare_fixed_departures_center(de440s, mar099s)
    result = build_audit(de440s, mar099s, snapshot)
    if result["status"] != "verified-source-tracked-center-geometry-only":
        raise ValueError(f"Mars-center geometry audit failed: {result['checks']}")
    if args.write:
        contents = _json_bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != contents:
            raise ValueError("refusing to overwrite a different Mars-center snapshot")
        SNAPSHOT.write_bytes(contents)
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != _json_bytes(snapshot):
            raise ValueError("saved Mars-center snapshot differs from offline recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if (not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None
                or saved != result):
            raise ValueError("Mars-center source audit differs from recomputation")
    print(json.dumps({"status": result["status"], "checks": result["checks"],
                      "snapshot_sha256": result["snapshot_sha256"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
