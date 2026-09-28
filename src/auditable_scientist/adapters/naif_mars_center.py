"""Read-only NAIF MAR099s offset combined with pinned DE440s planetary states."""

from __future__ import annotations

from hashlib import md5, sha256
import math
from pathlib import Path
from typing import Any

from .naif_de440s import (
    DEPARTURE_JD_TDB, GM_SUN_KM3_S2, _fingerprint as fingerprint_de440s,
    _norm,
)


SOURCE_URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/mar099s.bsp"
SOURCE_MD5 = "fd7302dfbaa0c63ce85b1e98923ee6a1"
SOURCE_SHA256 = "997dc93ba640e476da7a494d2237dcdeb145e528db37be8ccee588c615e4e1ff"
SOURCE_BYTES = 67_594_240


def fingerprint_mar099s(path: Path) -> dict[str, Any]:
    sha = sha256()
    md = md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > SOURCE_BYTES:
                raise ValueError("MAR099s kernel exceeds the pinned byte count")
            sha.update(chunk)
            md.update(chunk)
    if (size != SOURCE_BYTES or sha.hexdigest() != SOURCE_SHA256
            or md.hexdigest() != SOURCE_MD5):
        raise ValueError("MAR099s kernel differs from the pinned NAIF source")
    return {"sha256": sha.hexdigest(), "md5": md.hexdigest(), "bytes": size}


def compare_fixed_departures_center(de440s_path: Path, mar099s_path: Path) -> dict[str, Any]:
    """Compare ideal transfer geometry to the Mars mass center at fixed dates.

    This checks a center correction to an ephemeris-model diagnostic. It does
    not propagate a spacecraft or validate an encounter.
    """

    import spiceypy as spice
    from importlib.metadata import version

    de440s = de440s_path.resolve(strict=True)
    mar099s = mar099s_path.resolve(strict=True)
    if de440s == mar099s or de440s.name != "de440s.bsp" or mar099s.name != "mar099s.bsp":
        raise ValueError("DE440s and MAR099s must be distinct named kernels")
    de_fingerprint = fingerprint_de440s(de440s)
    mar_fingerprint = fingerprint_mar099s(mar099s)
    if spice.ktotal("SPK") != 0:
        raise ValueError("Mars-center diagnostic requires an otherwise empty SPK pool")
    # MAR099s is loaded first. DE440s therefore owns overlapping planetary
    # segments, while MAR099s supplies body 499 relative to barycenter 4.
    spice.furnsh(str(mar099s))
    spice.furnsh(str(de440s))
    try:
        if spice.ktotal("SPK") != 2 or 499 not in set(spice.spkobj(str(mar099s))):
            raise ValueError("Mars-center kernel inventory or pool differs")
        coverage = spice.spkcov(str(mar099s), 499)
        if spice.wncard(coverage) != 1:
            raise ValueError("MAR099s Mars-center coverage is not one declared interval")
        coverage_start, coverage_end = spice.wnfetd(coverage, 0)
        first_et = (DEPARTURE_JD_TDB[0] - 2_451_545.0) * 86_400.0
        last_et = (DEPARTURE_JD_TDB[-1] + 400 - 2_451_545.0) * 86_400.0
        if coverage_start >= first_et or coverage_end <= last_et:
            raise ValueError("MAR099s does not cover the fixed-date diagnostic window")

        def state(body: str, jd_tdb: float, center: str) -> list[float]:
            et = (jd_tdb - 2_451_545.0) * 86_400.0
            values, _light_time = spice.spkezr(body, et, "J2000", "NONE", center)
            result = [float(value) for value in values]
            if len(result) != 6 or not all(math.isfinite(value) for value in result):
                raise ValueError("NAIF returned an incomplete or nonfinite Mars-center state")
            return result

        cases = []
        for departure_jd in DEPARTURE_JD_TDB:
            earth = state("EARTH", departure_jd, "SUN")
            bary_departure = state("MARS BARYCENTER", departure_jd, "SUN")
            offset_departure = state("MARS", departure_jd, "MARS BARYCENTER")
            center_departure = [a + b for a, b in zip(bary_departure, offset_departure, strict=True)]
            earth_radius = _norm(earth[:3])
            bary_radius = _norm(bary_departure[:3])
            center_radius = _norm(center_departure[:3])
            center_tof_days = math.pi * math.sqrt(((earth_radius + center_radius) / 2.0) ** 3 /
                                                   GM_SUN_KM3_S2) / 86_400.0
            bary_tof_days = math.pi * math.sqrt(((earth_radius + bary_radius) / 2.0) ** 3 /
                                                 GM_SUN_KM3_S2) / 86_400.0
            arrival_jd = departure_jd + center_tof_days
            bary_arrival = state("MARS BARYCENTER", arrival_jd, "SUN")
            offset_arrival = state("MARS", arrival_jd, "MARS BARYCENTER")
            center_arrival = [a + b for a, b in zip(bary_arrival, offset_arrival, strict=True)]
            direct_center = state("MARS", arrival_jd, "SUN")
            chain_error = _norm([a - b for a, b in zip(center_arrival[:3], direct_center[:3], strict=True)])
            ideal_arrival = [-value * center_radius / earth_radius for value in earth[:3]]
            center_gap = _norm([a - b for a, b in zip(center_arrival[:3], ideal_arrival, strict=True)])
            bary_gap = _norm([a - b for a, b in zip(bary_arrival[:3], ideal_arrival, strict=True)])
            center_bary_separation = _norm(offset_arrival[:3])
            if (not 0 <= center_bary_separation < 1.0 or chain_error > 1e-5
                    or not 0 <= center_gap < 600_000_000):
                raise ValueError("Mars-center geometry exceeds its declared diagnostic bounds")
            cases.append({
                "departure_jd_tdb": departure_jd,
                "arrival_jd_tdb": arrival_jd,
                "earth_departure_state_km_kms": earth,
                "mars_barycenter_departure_state_km_kms": bary_departure,
                "mars_center_relative_departure_state_km_kms": offset_departure,
                "mars_center_departure_state_km_kms": center_departure,
                "mars_barycenter_arrival_state_km_kms": bary_arrival,
                "mars_center_relative_arrival_state_km_kms": offset_arrival,
                "mars_center_arrival_state_km_kms": center_arrival,
                "ideal_arrival_position_km": ideal_arrival,
                "ideal_tof_days": center_tof_days,
                "center_vs_barycenter_tof_seconds": (center_tof_days - bary_tof_days) * 86_400,
                "mars_center_arrival_gap_km": center_gap,
                "barycenter_gap_at_same_arrival_km": bary_gap,
                "center_vs_barycenter_gap_m": (center_gap - bary_gap) * 1000,
                "center_barycenter_separation_m": center_bary_separation * 1000,
                "spice_chain_position_error_m": chain_error * 1000,
            })
        result = {
            "schema_version": "t1-mars-center-fixed-date-geometry-v1",
            "sources": {
                "de440s": {"url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
                            "kernel": "de440s.bsp", **de_fingerprint},
                "mar099s": {"url": SOURCE_URL, "kernel": "mar099s.bsp", **mar_fingerprint},
            },
            "reader": {"package": "spiceypy", "version": version("spiceypy"),
                       "toolkit": spice.tkvrsn("TOOLKIT")},
            "coordinate_contract": {
                "frame": "J2000", "aberration": "NONE", "time_scale": "TDB",
                "state_units": ["km", "km/s"],
                "planetary_center": "SUN; DE440s loaded after MAR099s for overlapping segments",
                "mars_offset": "MARS (499) relative to MARS BARYCENTER (4) from MAR099s",
            },
            "gm_sun_km3_s2": GM_SUN_KM3_S2,
            "mars_499_coverage_et_seconds": [coverage_start, coverage_end],
            "cases": cases,
            "claim_status": "unverified",
            "evidence_level": "real-data",
            "meaning": "source-tracked Mars-center ephemeris-model geometry only",
        }
    finally:
        spice.unload(str(de440s))
        spice.unload(str(mar099s))
    if (spice.ktotal("SPK") != 0 or fingerprint_de440s(de440s) != de_fingerprint
            or fingerprint_mar099s(mar099s) != mar_fingerprint):
        raise ValueError("Mars-center kernel pool or source bytes changed during evaluation")
    return result
