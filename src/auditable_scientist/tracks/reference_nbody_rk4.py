"""Independent fixed-step RK4 reference for the planar three-body benchmark."""

from __future__ import annotations

from math import hypot


def rk4_three_body(
    positions: list[tuple[float, float]],
    velocities: list[tuple[float, float]],
    masses: list[float],
    gravitational_constant: float,
    dt: float,
    steps: int,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Integrate a twelve-component Cartesian state without using the Verlet RHS."""

    if len(positions) != 3 or len(velocities) != 3 or len(masses) != 3:
        raise ValueError("RK4 reference requires exactly three bodies")
    state = [component for point in positions for component in point]
    state.extend(component for velocity in velocities for component in velocity)

    def derivative(values: list[float]) -> list[float]:
        result = values[6:]
        for i in range(3):
            acceleration_x = 0.0
            acceleration_y = 0.0
            for j in range(3):
                if i == j:
                    continue
                dx = values[2 * j] - values[2 * i]
                dy = values[2 * j + 1] - values[2 * i + 1]
                radius = hypot(dx, dy)
                if radius <= 0.0:
                    raise ValueError("RK4 reference encountered a collision")
                scale = gravitational_constant * masses[j] / (radius * radius * radius)
                acceleration_x += scale * dx
                acceleration_y += scale * dy
            result.extend((acceleration_x, acceleration_y))
        return result

    for _ in range(steps):
        k1 = derivative(state)
        k2 = derivative([value + 0.5 * dt * slope for value, slope in zip(state, k1)])
        k3 = derivative([value + 0.5 * dt * slope for value, slope in zip(state, k2)])
        k4 = derivative([value + dt * slope for value, slope in zip(state, k3)])
        state = [
            value + dt * (a + 2 * b + 2 * c + d) / 6
            for value, a, b, c, d in zip(state, k1, k2, k3, k4)
        ]
    return (
        [(state[2 * i], state[2 * i + 1]) for i in range(3)],
        [(state[6 + 2 * i], state[7 + 2 * i]) for i in range(3)],
    )
