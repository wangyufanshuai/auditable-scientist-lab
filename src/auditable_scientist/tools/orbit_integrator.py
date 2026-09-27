"""Bounded, dependency-free two-body propagation for an outward transfer.

The vis-viva departure speed is an input to this numerical check.  The
integrator independently finds the first apoapsis; it does not derive the
transfer orbit or model a dated planetary encounter.
"""

from __future__ import annotations

from math import hypot, isfinite, pi, sqrt


State = tuple[float, float, float, float]


def _derivative(state: State, gravity_sign: int) -> State:
    x, y, vx, vy = state
    radius = hypot(x, y)
    if radius < 1e-9 or not isfinite(radius):
        raise ValueError("two-body trajectory left the finite noncollision domain")
    factor = -gravity_sign / radius**3
    return vx, vy, factor * x, factor * y


def _rk4(state: State, dt: float, gravity_sign: int) -> State:
    k1 = _derivative(state, gravity_sign)
    k2 = _derivative(tuple(state[i] + dt * k1[i] / 2 for i in range(4)), gravity_sign)
    k3 = _derivative(tuple(state[i] + dt * k2[i] / 2 for i in range(4)), gravity_sign)
    k4 = _derivative(tuple(state[i] + dt * k3[i] for i in range(4)), gravity_sign)
    result = tuple(state[i] + dt * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) / 6 for i in range(4))
    if not all(isfinite(value) for value in result):
        raise ValueError("two-body propagation produced a nonfinite state")
    return result  # type: ignore[return-value]


def _radial_dot(state: State) -> float:
    x, y, vx, vy = state
    return x * vx + y * vy


def _invariants(state: State) -> tuple[float, float]:
    x, y, vx, vy = state
    return (vx * vx + vy * vy) / 2 - 1 / hypot(x, y), x * vy - y * vx


def propagate_to_apoapsis(
    r1_km: float, r2_km: float, mu_km3_s2: float, *,
    steps: int = 4096, gravity_sign: int = 1,
) -> dict[str, float | int | bool | list[float]]:
    """Find the first positive-time outward-to-inward radial crossing.

    Coordinates use length ``r1`` and time ``sqrt(r1**3 / mu)``. ``steps``
    bounds the entire four-period search window, including a no-event run.
    """
    if (not all(isfinite(value) for value in (r1_km, r2_km, mu_km3_s2))
            or not 0 < r1_km < r2_km or mu_km3_s2 <= 0
            or type(steps) is not int or not 256 <= steps <= 65536
            or type(gravity_sign) is not int or gravity_sign not in (-1, 1)):
        raise ValueError("finite outward-transfer inputs, bounded steps, and signed gravity are required")
    ratio = r2_km / r1_km
    time_scale = sqrt(r1_km / mu_km3_s2) * r1_km
    if not isfinite(ratio) or ratio > 100 or not isfinite(time_scale) or time_scale <= 0:
        raise ValueError("two-body scales exceed the bounded propagation domain")
    a = (1 + ratio) / 2
    speed = sqrt(2 - 1 / a)
    state: State = (1.0, 0.0, 0.0, speed)
    initial_energy, initial_momentum = _invariants(state)
    max_energy_drift = 0.0
    max_momentum_drift = 0.0
    dt = 4 * pi * sqrt(a**3) / steps
    elapsed = 0.0
    previous_radial = 0.0

    for index in range(1, steps + 1):
        next_state = _rk4(state, dt, gravity_sign)
        next_radial = _radial_dot(next_state)
        energy, momentum = _invariants(next_state)
        max_energy_drift = max(max_energy_drift, abs(energy - initial_energy) / abs(initial_energy))
        max_momentum_drift = max(max_momentum_drift, abs(momentum - initial_momentum) / initial_momentum)
        if previous_radial > 0 and next_radial <= 0:
            left, right = 0.0, dt
            # Reintegrate from the bracketing state, so event time is not
            # supplied by the analytic half-period or linear interpolation.
            for _ in range(40):
                middle = (left + right) / 2
                middle_state = _rk4(state, middle, gravity_sign)
                if _radial_dot(middle_state) > 0:
                    left = middle
                else:
                    right = middle
            event_offset = (left + right) / 2
            event_state = _rk4(state, event_offset, gravity_sign)
            energy, momentum = _invariants(event_state)
            max_energy_drift = max(max_energy_drift, abs(energy - initial_energy) / abs(initial_energy))
            max_momentum_drift = max(max_momentum_drift, abs(momentum - initial_momentum) / initial_momentum)
            return {
                "event_detected": True,
                "steps_executed": index,
                "event_time_s": (elapsed + event_offset) * time_scale,
                "event_state": list(event_state),
                "relative_energy_drift": max_energy_drift,
                "relative_angular_momentum_drift": max_momentum_drift,
            }
        state = next_state
        previous_radial = next_radial
        elapsed = index * dt
    return {"event_detected": False, "steps_executed": steps}
