"""Deterministic numerical baselines for the Hohmann benchmark."""

from __future__ import annotations

from math import pi, sqrt
from pydantic import BaseModel, ConfigDict, Field


class HohmannResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solver_id: str = "hohmann-analytic-v1"
    r1_km: float = Field(gt=0)
    r2_km: float = Field(gt=0)
    mu_km3_s2: float = Field(gt=0)
    transfer_semimajor_axis_km: float
    earth_departure_dv_km_s: float
    mars_arrival_dv_km_s: float
    total_heliocentric_dv_km_s: float
    time_of_flight_s: float
    time_of_flight_days: float


def hohmann_baseline(r1_km: float, r2_km: float, mu_km3_s2: float) -> HohmannResult:
    if r1_km <= 0 or r2_km <= 0 or mu_km3_s2 <= 0:
        raise ValueError("r1_km, r2_km, and mu_km3_s2 must be positive")
    transfer_a = 0.5 * (r1_km + r2_km)
    v1 = sqrt(mu_km3_s2 / r1_km)
    v2 = sqrt(mu_km3_s2 / r2_km)
    transfer_v1 = sqrt(mu_km3_s2 * (2.0 / r1_km - 1.0 / transfer_a))
    transfer_v2 = sqrt(mu_km3_s2 * (2.0 / r2_km - 1.0 / transfer_a))
    dv1 = transfer_v1 - v1
    dv2 = v2 - transfer_v2
    tof_s = pi * sqrt(transfer_a**3 / mu_km3_s2)
    return HohmannResult(
        r1_km=r1_km,
        r2_km=r2_km,
        mu_km3_s2=mu_km3_s2,
        transfer_semimajor_axis_km=transfer_a,
        earth_departure_dv_km_s=dv1,
        mars_arrival_dv_km_s=dv2,
        total_heliocentric_dv_km_s=dv1 + dv2,
        time_of_flight_s=tof_s,
        time_of_flight_days=tof_s / 86400.0,
    )
