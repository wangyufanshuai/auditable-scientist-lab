"""Independent fixed-step RK4 reference for the bounded harmonic oscillator.

The method follows the classical four-slope RK4 update in Peter Young,
"Comparison of methods for integrating the simple harmonic oscillator",
Physics 115/242, equations (9a)-(9e):
https://bpb-us-e1.wpmucdn.com/sites.ucsc.edu/dist/7/1905/files/2025/03/ode_solve.pdf

This is an original implementation of a standard formula, not copied source
code or an external solver dependency. The source is a method reference only;
its redistribution rights and applicability beyond this oscillator are not
established by the local fixture.
"""

from __future__ import annotations


def rk4_oscillator(x0: float, v0: float, omega: float, dt: float, steps: int) -> tuple[float, float, float]:
    """Return final (position, velocity, maximum absolute energy drift)."""

    x, v = x0, v0
    omega_squared = omega * omega
    initial_energy = 0.5 * (v0 * v0 + omega_squared * x0 * x0)
    max_drift = 0.0
    for _ in range(steps):
        k1x, k1v = v, -omega_squared * x
        k2x = v + 0.5 * dt * k1v
        k2v = -omega_squared * (x + 0.5 * dt * k1x)
        k3x = v + 0.5 * dt * k2v
        k3v = -omega_squared * (x + 0.5 * dt * k2x)
        k4x = v + dt * k3v
        k4v = -omega_squared * (x + dt * k3x)
        x += dt * (k1x + 2 * k2x + 2 * k3x + k4x) / 6
        v += dt * (k1v + 2 * k2v + 2 * k3v + k4v) / 6
        current_energy = 0.5 * (v * v + omega_squared * x * x)
        max_drift = max(max_drift, abs(current_energy - initial_energy))
    return x, v, max_drift
