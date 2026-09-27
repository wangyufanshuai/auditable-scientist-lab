"""T2 planar ball counterfactuals in a declared event-driven collision model."""

from __future__ import annotations

from math import hypot, isfinite, sqrt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import TrackReceipt, make_track_receipt


class BallParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mass_kg: float = Field(ge=0.1, le=10)
    friction: float = Field(ge=0, le=0.8)
    restitution: float = Field(ge=0.2, le=0.9)
    gravity_m_s2: float = Field(ge=1, le=20)


class WorldState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_m: float = Field(ge=-100, le=100)
    y_m: float = Field(ge=0.1, le=5)
    vx_m_s: float = Field(ge=-5, le=5)
    vy_m_s: float = Field(ge=-5, le=5)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impulse_x_kg_m_s: float = Field(ge=0.1, le=10)


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_type: Literal["single", "joint", "policy"]
    parameter_updates: dict[Literal["mass_kg", "friction", "restitution", "gravity_m_s2"], float] = Field(default_factory=dict)
    impulse_x_kg_m_s: float | None = None

    @model_validator(mode="after")
    def check_shape(self) -> Intervention:
        count = len(self.parameter_updates)
        if self.query_type == "single" and (count != 1 or self.impulse_x_kg_m_s is not None):
            raise ValueError("single intervention requires exactly one parameter update")
        if self.query_type == "joint" and (count < 2 or self.impulse_x_kg_m_s is not None):
            raise ValueError("joint intervention requires at least two parameter updates")
        if self.query_type == "policy" and (count or self.impulse_x_kg_m_s is None):
            raise ValueError("policy counterfactual requires only a new impulse")
        if not all(isfinite(value) for value in self.parameter_updates.values()):
            raise ValueError("intervention values must be finite")
        if self.impulse_x_kg_m_s is not None and not 0.1 <= self.impulse_x_kg_m_s <= 10:
            raise ValueError("counterfactual impulse is out of domain")
        return self


class PhysicalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    split: Literal["train", "holdout"]
    parameters: BallParameters
    initial_state: WorldState
    action: Action
    intervention: Intervention
    horizon_s: float = Field(ge=0.5, le=3)
    sample_dt_s: float = Field(ge=0.01, le=0.1)

    @model_validator(mode="after")
    def check_domain(self) -> PhysicalCase:
        count = self.horizon_s / self.sample_dt_s
        if not isfinite(count) or abs(count - round(count)) > 1e-9:
            raise ValueError("sample interval must exactly divide the horizon")
        if round(count) > 300:
            raise ValueError("too many trajectory samples")
        if self.intervention.parameter_updates:
            updated = {**self.parameters.model_dump(), **self.intervention.parameter_updates}
            BallParameters.model_validate(updated)
        return self


class Trajectory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    states: list[dict[str, float]]
    impact_count: int
    max_free_flight_energy_residual: float
    max_impact_energy_gain: float
    first_impact_time_s: float
    first_rebound_apex_m: float
    first_post_impact_vx_m_s: float


class Counterfactual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    common_initial_state: WorldState
    intervention: Intervention
    factual: Trajectory
    counterfactual: Trajectory
    final_x_effect_m: float
    rebound_apex_effect_m: float
    model_uncertainty: str = "not-quantified-outside-declared-simulator"


class PhysicalEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "planar-ball-counterfactual-v1"
    simulator_id: str = "analytic-flight-event-collision-v1"
    case_count: int
    train_count: int
    holdout_count: int
    query_counts: dict[str, int]
    max_free_flight_energy_residual: float
    max_impact_energy_gain: float
    max_noop_trajectory_delta: float
    max_first_impact_time_error: float
    max_first_rebound_apex_error: float
    ignored_intervention_holdout_rmse: float
    direction_passed: bool
    ignored_intervention_rejected: bool
    passed: bool
    notes: list[str]


def _energy(state: dict[str, float], parameters: BallParameters) -> float:
    return parameters.mass_kg * (
        0.5 * (state["vx_m_s"] ** 2 + state["vy_m_s"] ** 2)
        + parameters.gravity_m_s2 * state["y_m"]
    )


def _flight(state: dict[str, float], duration: float, gravity: float) -> dict[str, float]:
    return {
        "x_m": state["x_m"] + state["vx_m_s"] * duration,
        "y_m": state["y_m"] + state["vy_m_s"] * duration - 0.5 * gravity * duration**2,
        "vx_m_s": state["vx_m_s"],
        "vy_m_s": state["vy_m_s"] - gravity * duration,
    }


def _advance(
    state: dict[str, float], duration: float, parameters: BallParameters, elapsed: float,
) -> tuple[dict[str, float], list[tuple[float, float, float, float]], float, float]:
    impacts: list[tuple[float, float, float, float]] = []
    max_flight_residual = max_impact_gain = 0.0
    remaining = duration
    for _ in range(100):
        if remaining <= 1e-12:
            break
        if state["y_m"] <= 1e-12 and abs(state["vy_m_s"]) <= 1e-8:
            state = {**state, "x_m": state["x_m"] + state["vx_m_s"] * remaining, "y_m": 0.0, "vy_m_s": 0.0}
            remaining = 0.0
            break
        velocity = state["vy_m_s"]
        altitude = max(state["y_m"], 0.0)
        root = sqrt(velocity * velocity + 2 * parameters.gravity_m_s2 * altitude)
        impact_time = (velocity + root) / parameters.gravity_m_s2
        if impact_time <= 1e-12 and velocity < 0:
            impact_time = 0.0
        if impact_time >= remaining - 1e-12:
            future = _flight(state, remaining, parameters.gravity_m_s2)
            if future["y_m"] < 0 and future["y_m"] > -1e-10:
                future["y_m"] = 0.0
            max_flight_residual = max(max_flight_residual, abs(_energy(future, parameters) - _energy(state, parameters)))
            state = future
            remaining = 0.0
            break
        before = _flight(state, impact_time, parameters.gravity_m_s2)
        before["y_m"] = 0.0
        max_flight_residual = max(max_flight_residual, abs(_energy(before, parameters) - _energy(state, parameters)))
        after = {
            **before,
            "vx_m_s": (1 - parameters.friction) * before["vx_m_s"],
            "vy_m_s": -parameters.restitution * before["vy_m_s"],
        }
        if after["vy_m_s"] < 1e-8:
            after["vy_m_s"] = 0.0
        max_impact_gain = max(max_impact_gain, _energy(after, parameters) - _energy(before, parameters))
        elapsed += impact_time
        impacts.append((elapsed, before["vy_m_s"], after["vy_m_s"], after["vx_m_s"]))
        state = after
        remaining -= impact_time
    else:
        raise ValueError("collision event cap exceeded")
    if remaining > 1e-12:
        raise ValueError("collision integration left unresolved time")
    if not all(isfinite(value) for value in state.values()) or state["y_m"] < -1e-10:
        raise ValueError("collision simulation diverged")
    return state, impacts, max_flight_residual, max_impact_gain


def simulate(case: PhysicalCase, *, parameters: BallParameters | None = None, action: Action | None = None) -> Trajectory:
    parameters = parameters or case.parameters
    action = action or case.action
    state = case.initial_state.model_dump(mode="json")
    state["vx_m_s"] += action.impulse_x_kg_m_s / parameters.mass_kg
    start_velocity = state["vy_m_s"]
    discriminant = start_velocity**2 + 2 * parameters.gravity_m_s2 * state["y_m"]
    first_impact = (start_velocity + sqrt(discriminant)) / parameters.gravity_m_s2
    first_apex = parameters.restitution**2 * discriminant / (2 * parameters.gravity_m_s2)
    states = [{"t_s": 0.0, **state}]
    impacts: list[tuple[float, float, float, float]] = []
    max_flight = max_gain = 0.0
    count = round(case.horizon_s / case.sample_dt_s)
    for step in range(count):
        state, step_impacts, residual, gain = _advance(state, case.sample_dt_s, parameters, step * case.sample_dt_s)
        impacts.extend(step_impacts)
        max_flight = max(max_flight, residual)
        max_gain = max(max_gain, gain)
        states.append({"t_s": (step + 1) * case.sample_dt_s, **state})
    return Trajectory(
        states=states, impact_count=len(impacts),
        max_free_flight_energy_residual=max_flight,
        max_impact_energy_gain=max_gain,
        first_impact_time_s=first_impact,
        first_rebound_apex_m=first_apex,
        first_post_impact_vx_m_s=impacts[0][3] if impacts else 0.0,
    )


def compare(case: PhysicalCase) -> Counterfactual:
    factual = simulate(case)
    updated = BallParameters.model_validate({**case.parameters.model_dump(), **case.intervention.parameter_updates})
    action = case.action if case.intervention.impulse_x_kg_m_s is None else Action(impulse_x_kg_m_s=case.intervention.impulse_x_kg_m_s)
    counterfactual = simulate(case, parameters=updated, action=action)
    return Counterfactual(
        case_id=case.case_id, common_initial_state=case.initial_state,
        intervention=case.intervention, factual=factual, counterfactual=counterfactual,
        final_x_effect_m=counterfactual.states[-1]["x_m"] - factual.states[-1]["x_m"],
        rebound_apex_effect_m=counterfactual.first_rebound_apex_m - factual.first_rebound_apex_m,
    )


def standard_cases() -> list[PhysicalCase]:
    cases: list[PhysicalCase] = []
    for index in range(100):
        parameters = BallParameters(
            mass_kg=1 + (index % 5) * 0.2,
            friction=0.1 + (index % 4) * 0.1,
            restitution=0.4 + (index % 3) * 0.1,
            gravity_m_s2=9.81,
        )
        kind = index % 5
        if kind == 0:
            intervention = Intervention(query_type="single", parameter_updates={"mass_kg": parameters.mass_kg * 1.25})
        elif kind == 1:
            intervention = Intervention(query_type="single", parameter_updates={"friction": parameters.friction + 0.1})
        elif kind == 2:
            intervention = Intervention(query_type="single", parameter_updates={"restitution": parameters.restitution + 0.1})
        elif kind == 3:
            intervention = Intervention(query_type="joint", parameter_updates={"friction": parameters.friction + 0.1, "restitution": parameters.restitution + 0.1})
        else:
            intervention = Intervention(query_type="policy", impulse_x_kg_m_s=2.5)
        cases.append(PhysicalCase(
            case_id=f"ball-{index:03d}", split="train" if index < 40 else "holdout",
            parameters=parameters, initial_state=WorldState(x_m=0, y_m=1, vx_m_s=0, vy_m_s=0),
            action=Action(impulse_x_kg_m_s=2), intervention=intervention,
            horizon_s=1.5, sample_dt_s=0.05,
        ))
    return cases


def evaluate_physical_fixture(cases: list[PhysicalCase]) -> tuple[PhysicalEvaluation, TrackReceipt]:
    if len(cases) < 100 or not {"train", "holdout"}.issubset({case.split for case in cases}):
        raise ValueError("physical fixture requires at least 100 train/holdout cases")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("physical case IDs must be unique")
    max_residual = max_gain = max_noop = max_impact_error = max_apex_error = 0.0
    holdout_effects: list[float] = []
    directions: list[bool] = []
    query_counts = {"single": 0, "joint": 0, "policy": 0}
    for case in cases:
        result = compare(case)
        query_counts[case.intervention.query_type] += 1
        noop = simulate(case, parameters=case.parameters, action=case.action)
        max_noop = max(max_noop, max(
            hypot(a["x_m"] - b["x_m"], a["y_m"] - b["y_m"])
            for a, b in zip(result.factual.states, noop.states)
        ))
        for trajectory, parameters in (
            (result.factual, case.parameters),
            (result.counterfactual, BallParameters.model_validate({**case.parameters.model_dump(), **case.intervention.parameter_updates})),
        ):
            max_residual = max(max_residual, trajectory.max_free_flight_energy_residual)
            max_gain = max(max_gain, trajectory.max_impact_energy_gain)
            expected_time = sqrt(2 * case.initial_state.y_m / parameters.gravity_m_s2)
            expected_apex = parameters.restitution**2 * case.initial_state.y_m
            max_impact_error = max(max_impact_error, abs(trajectory.first_impact_time_s - expected_time))
            max_apex_error = max(max_apex_error, abs(trajectory.first_rebound_apex_m - expected_apex))
            if trajectory.impact_count < 1:
                directions.append(False)
        updates = case.intervention.parameter_updates
        if "mass_kg" in updates:
            directions.append(result.final_x_effect_m < -1e-4)
        if "friction" in updates:
            directions.append(
                result.counterfactual.first_post_impact_vx_m_s
                < result.factual.first_post_impact_vx_m_s - 1e-4
            )
        if "restitution" in updates:
            directions.append(result.rebound_apex_effect_m > 1e-4)
        if case.intervention.query_type == "policy":
            directions.append(result.final_x_effect_m > 1e-4)
        if case.split == "holdout":
            effect = result.rebound_apex_effect_m if set(updates) == {"restitution"} else result.final_x_effect_m
            holdout_effects.append(effect)
    ignored_rmse = sqrt(sum(effect * effect for effect in holdout_effects) / len(holdout_effects))
    negative_rejected = ignored_rmse > 0.01
    passed = (
        all(directions)
        and max_residual <= 1e-10
        and max_gain <= 1e-10
        and max_noop == 0
        and max_impact_error <= 1e-12
        and max_apex_error <= 1e-12
        and negative_rejected
        and all(query_counts.values())
    )
    evaluation = PhysicalEvaluation(
        case_count=len(cases), train_count=sum(case.split == "train" for case in cases),
        holdout_count=sum(case.split == "holdout" for case in cases), query_counts=query_counts,
        max_free_flight_energy_residual=max_residual, max_impact_energy_gain=max_gain,
        max_noop_trajectory_delta=max_noop,
        max_first_impact_time_error=max_impact_error,
        max_first_rebound_apex_error=max_apex_error,
        ignored_intervention_holdout_rmse=ignored_rmse,
        direction_passed=all(directions), ignored_intervention_rejected=negative_rejected,
        passed=passed,
        notes=[
            "Exactly specified two-dimensional ballistic flight with floor collisions; horizontal friction acts only at impact.",
            "Factual and counterfactual share the same initial state; do(parameter=value) replaces a parameter, not an observational association.",
            "Deterministic simulator uncertainty is zero only within its equations; real-world model discrepancy is not quantified.",
        ],
    )
    receipt = make_track_receipt(
        track_id="T2P", evaluator_id=evaluation.evaluator_id,
        input_payload=[case.model_dump(mode="json") for case in cases],
        evidence_level="validated-reproduction" if passed else "demo",
        passed=passed, negative_case_passed=negative_rejected,
        result=evaluation.model_dump(mode="json"),
        blocked_gates=["real physical intervention data and causal identification", "external algorithm adapter license and revision", "out-of-domain model uncertainty"],
    )
    return evaluation, receipt
