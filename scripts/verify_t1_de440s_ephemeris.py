"""Audit two predeclared DE440s dates without promoting a mission Claim."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from auditable_scientist.adapters.naif_de440s import compare_fixed_departures


ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "data/naif/de440s.bsp"
SNAPSHOT = ROOT / "artifacts/t1-de440s-ephemeris-snapshot.json"
AUDIT = ROOT / "artifacts/t1-de440s-ephemeris-audit.json"
SOURCES = (
    Path(__file__).resolve(), ROOT / "scripts/fetch_de440s.py",
    ROOT / "src/auditable_scientist/adapters/naif_de440s.py",
    ROOT / "docs/T1_DE440S_EPHEMERIS.md",
    ROOT / "requirements-t1-de440s-win-py312.txt",
)


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _source(path: Path) -> dict[str, str | int]:
    contents = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(contents).hexdigest(), "bytes": len(contents)}


def build_audit(kernel: Path, snapshot: dict) -> dict:
    if snapshot.get("schema_version") != "t1-de440s-fixed-date-geometry-v1":
        raise ValueError("DE440s snapshot schema differs")
    with tempfile.TemporaryDirectory(prefix="scientist-de440s-negative-") as temporary:
        fake = Path(temporary) / "de440s.bsp"
        fake.write_bytes(b"not a NAIF kernel")
        try:
            compare_fixed_departures(fake)
        except ValueError:
            wrong_kernel_rejected = True
        else:
            wrong_kernel_rejected = False
    cases = snapshot["cases"]
    checks = {
        "official_md5_matched": snapshot["source"]["md5"] == "3917ee56769db332790c751e2168843d",
        "pinned_sha256_matched": snapshot["source"]["sha256"] == "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2",
        "fixed_departure_dates": [row["departure_jd_tdb"] for row in cases] == [2460584.5, 2461375.5],
        "finite_dated_geometry": len(cases) == 2 and all(
            0 < row["ideal_tof_days"] < 400 and
            0 <= row["arrival_position_gap_km"] < 600_000_000 and
            0 <= row["opposition_angle_gap_deg"] <= 180 for row in cases
        ),
        "reader_and_frame_explicit": snapshot["reader"]["version"] == "8.1.0"
        and snapshot["reader"]["toolkit"] == "CSPICE_N0067"
        and snapshot["coordinate_contract"]["frame"] == "J2000"
        and snapshot["coordinate_contract"]["time_scale"] == "TDB"
        and snapshot["coordinate_contract"]["mars_target"].startswith("MARS BARYCENTER"),
        "mission_claim_unverified": snapshot["claim_status"] == "unverified",
        "wrong_kernel_rejected": wrong_kernel_rejected,
    }
    return {
        "schema_version": "t1-de440s-ephemeris-audit-v1",
        "status": "verified-source-tracked-geometry-only" if all(checks.values()) else "failed",
        "kernel_source": snapshot["source"],
        "kernel_local_path": kernel.relative_to(ROOT).as_posix(),
        "source_rights": {
            "rules_url": "https://naif.jpl.nasa.gov/naif/rules.html",
            "checksum_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/aa_checksums.txt",
            "use": "NAIF kernels may be downloaded and used by anyone, subject to NAIF rules",
            "redistribution": "permitted only for unmodified NAIF-distributed kernels",
            "kernel_redistributed_in_repository": False,
            "applies_to_unrelated_sources": False,
        },
        "snapshot_sha256": sha256(_json_bytes(snapshot)).hexdigest(),
        "source_files": [_source(path) for path in SOURCES],
        "checks": checks,
        "boundaries": {
            "external_ephemeris_model_used": True,
            "real_ephemeris_source_tracked": True,
            "mars_center_state_available": False,
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
    parser.add_argument("--kernel", type=Path, default=KERNEL)
    arguments = parser.parse_args()
    kernel = arguments.kernel.resolve(strict=True)
    if not kernel.is_relative_to(ROOT) or kernel.name != "de440s.bsp":
        raise ValueError("DE440s audit requires a local named kernel under the project root")
    snapshot = compare_fixed_departures(kernel)
    result = build_audit(kernel, snapshot)
    if result["status"] != "verified-source-tracked-geometry-only":
        raise ValueError(f"DE440s geometry audit failed: {result['checks']}")
    if arguments.write:
        contents = _json_bytes(snapshot)
        if SNAPSHOT.exists() and SNAPSHOT.read_bytes() != contents:
            raise ValueError("refusing to overwrite a different DE440s snapshot")
        SNAPSHOT.write_bytes(contents)
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        if SNAPSHOT.read_bytes() != _json_bytes(snapshot):
            raise ValueError("saved DE440s snapshot differs from offline recomputation")
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if (not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None
                or saved != result):
            raise ValueError("DE440s source audit differs from recomputation")
    print(json.dumps({"status": result["status"], "checks": result["checks"],
                      "snapshot_sha256": result["snapshot_sha256"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
