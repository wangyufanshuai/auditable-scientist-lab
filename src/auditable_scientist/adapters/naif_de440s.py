"""Read-only, pinned DE440s state-vector adapter for dated T1 diagnostics."""

from __future__ import annotations

from hashlib import md5, sha256
import math
from pathlib import Path
from typing import Any


SOURCE_URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"
SOURCE_MD5 = "3917ee56769db332790c751e2168843d"
SOURCE_SHA256 = "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
GM_SUN_KM3_S2 = 132_712_440_041.279419  # DE440 technical comments, GMS.
DEPARTURE_JD_TDB = (2460584.5, 2461375.5)  # 2024-10-01 and 2026-12-01, TDB calendar dates.


def _fingerprint(path: Path) -> dict[str, Any]:
    sha = sha256()
    md = md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            sha.update(chunk)
            md.update(chunk)
            size += len(chunk)
    if sha.hexdigest() != SOURCE_SHA256 or md.hexdigest() != SOURCE_MD5 or size != 32_726_016:
        raise ValueError("DE440s kernel differs from the pinned NAIF source")
    return {"sha256": sha.hexdigest(), "md5": md.hexdigest(), "bytes": size}


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def compare_fixed_departures(kernel_path: Path) -> dict[str, Any]:
    """Compare two predeclared ideal transfers to DE440s Earth/Mars-barycenter states.

    This is a geometry diagnostic, not a mission trajectory or a scientific holdout.
    ``spiceypy`` is optional and imported only when this adapter is invoked.
    """

    import spiceypy as spice
    from importlib.metadata import version

    kernel = kernel_path.resolve(strict=True)
    fingerprint = _fingerprint(kernel)
    if spice.ktotal("SPK") != 0:
        raise ValueError("DE440s diagnostic requires an otherwise empty SPK kernel pool")
    spice.furnsh(str(kernel))
    try:
        if spice.ktotal("SPK") != 1:
            raise ValueError("DE440s diagnostic did not load exactly one SPK kernel")

        def state(body: str, jd_tdb: float) -> list[float]:
            et = (jd_tdb - 2_451_545.0) * 86_400.0
            values, _light_time = spice.spkezr(body, et, "J2000", "NONE", "SUN")
            result = [float(value) for value in values]
            if len(result) != 6 or not all(math.isfinite(value) for value in result):
                raise ValueError("DE440s returned a nonfinite or incomplete state")
            return result

        cases = []
        for departure_jd in DEPARTURE_JD_TDB:
            earth = state("EARTH", departure_jd)
            mars_departure = state("MARS BARYCENTER", departure_jd)
            earth_radius = _norm(earth[:3])
            mars_radius = _norm(mars_departure[:3])
            semi_major = (earth_radius + mars_radius) / 2.0
            tof_days = math.pi * math.sqrt(semi_major**3 / GM_SUN_KM3_S2) / 86_400.0
            arrival_jd = departure_jd + tof_days
            mars_arrival = state("MARS BARYCENTER", arrival_jd)
            predicted_apoapsis = [-value * mars_radius / earth_radius for value in earth[:3]]
            distance = _norm([observed - ideal for observed, ideal in
                              zip(mars_arrival[:3], predicted_apoapsis, strict=True)])
            cosine = _dot(earth[:3], mars_arrival[:3]) / (earth_radius * _norm(mars_arrival[:3]))
            angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
            cases.append({
                "departure_jd_tdb": departure_jd,
                "arrival_jd_tdb": arrival_jd,
                "ideal_tof_days": tof_days,
                "earth_departure_state_km_kms": earth,
                "mars_barycenter_departure_state_km_kms": mars_departure,
                "mars_barycenter_arrival_state_km_kms": mars_arrival,
                "ideal_arrival_position_km": predicted_apoapsis,
                "arrival_position_gap_km": distance,
                "departure_to_arrival_angle_deg": angle,
                "opposition_angle_gap_deg": 180.0 - angle,
            })
        if len(cases) != 2 or not all(0.0 <= row["arrival_position_gap_km"] < 600_000_000
                                      for row in cases):
            raise ValueError("DE440s fixed-date geometry is outside the declared diagnostic bounds")
        result = {
            "schema_version": "t1-de440s-fixed-date-geometry-v1",
            "source": {"url": SOURCE_URL, "kernel": "de440s.bsp", **fingerprint},
            "reader": {"package": "spiceypy", "version": version("spiceypy"),
                       "toolkit": spice.tkvrsn("TOOLKIT")},
            "coordinate_contract": {"center": "SUN", "frame": "J2000",
                                    "aberration": "NONE", "time_scale": "TDB",
                                    "time_argument": "Julian Date TDB; ET seconds from J2000",
                                    "state_units": ["km", "km/s"],
                                    "mars_target": "MARS BARYCENTER (4), not Mars center (499)"},
            "gm_sun_km3_s2": GM_SUN_KM3_S2,
            "cases": cases,
            "claim_status": "unverified",
            "evidence_level": "real-data",
            "meaning": "source-tracked ephemeris-model geometry diagnostic only",
        }
    finally:
        spice.unload(str(kernel))
    if spice.ktotal("SPK") != 0 or _fingerprint(kernel) != fingerprint:
        raise ValueError("DE440s kernel pool or source bytes changed during evaluation")
    return result
