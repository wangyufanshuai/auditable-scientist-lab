"""Bounded, offline Hohmann grammar enumeration with independent baseline checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import pi, sqrt
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.canonical import canonical_hash
from ..tools.dimensions import check_expression_dimensions
from ..tools.errors import HoldoutGateResult, holdout_gate
from ..tools.numerical import HohmannResult, hohmann_baseline


GRAMMAR_VERSION = "hohmann-radius-factor-grammar-v2"


class HohmannCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    split: Literal["train", "holdout"]
    r1_km: float = Field(gt=0)
    r2_km: float = Field(gt=0)
    mu_km3_s2: float = Field(gt=0)
    target_tof_days: float = Field(gt=0)


class HohmannConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "hohmann-config-v1"
    task_id: str = "hohmann-time-of-flight-v1"
    dataset_path: str = Field(min_length=1)
    target: Literal["time_of_flight_days"] = "time_of_flight_days"
    max_holdout_rmse: float = Field(ge=0, default=1e-8)
    source_revision: str = "local-working-tree"


class CandidateEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    expression: str
    source: str
    complexity: int = Field(ge=1)
    dimensional_status: Literal["valid", "invalid"]
    train_predictions: list[float]
    holdout_predictions: list[float]
    train_rmse: float = Field(ge=0)
    holdout_rmse: float = Field(ge=0)
    train_residuals: list[float]
    holdout_residuals: list[float]
    failed_candidate_count: int = Field(ge=0)


class HohmannExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str = "hohmann-mars-transfer-v1"
    grammar_version: str = GRAMMAR_VERSION
    target: str
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_set_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_order: list[str]
    candidates: list[CandidateEvaluation]
    selected_candidate_id: str
    gate: HoldoutGateResult
    baseline: list[HohmannResult]


@dataclass(frozen=True)
class _CandidateSpec:
    candidate_id: str
    expression: str
    complexity: int
    evaluator: Callable[[HohmannCase], float]


@dataclass(frozen=True)
class _RadiusNode:
    node_id: str
    expression: str
    complexity: int
    evaluator: Callable[[HohmannCase], float]


def bounded_candidate_specs() -> list[_CandidateSpec]:
    """Enumerate a fixed ten-expression grammar; no candidate calls the baseline."""

    radii = [
        _RadiusNode("semimajor", "(r1+r2)/2", 3, lambda case: (case.r1_km + case.r2_km) / 2),
        _RadiusNode("sum", "r1+r2", 2, lambda case: case.r1_km + case.r2_km),
        _RadiusNode("inner", "r1", 1, lambda case: case.r1_km),
        _RadiusNode("outer", "r2", 1, lambda case: case.r2_km),
        _RadiusNode("geometric", "sqrt(r1*r2)", 3, lambda case: sqrt(case.r1_km * case.r2_km)),
    ]
    factors = [("pi", "pi*", pi, 1), ("unit", "", 1.0, 0)]
    specifications: list[_CandidateSpec] = []
    for radius in radii:
        for factor_id, prefix, factor, factor_cost in factors:
            specifications.append(_CandidateSpec(
                candidate_id=f"tof-{radius.node_id}-{factor_id}-v2",
                expression=f"{prefix}sqrt(({radius.expression})^3/mu)/86400",
                complexity=radius.complexity + factor_cost + 2,
                evaluator=lambda case, r=radius.evaluator, f=factor: f * sqrt(r(case) ** 3 / case.mu_km3_s2) / 86400.0,
            ))
    return specifications


def load_hohmann_dataset(path: str | Path) -> list[HohmannCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != "hohmann-dataset-v1":
        raise ValueError("unsupported Hohmann dataset schema")
    cases = [HohmannCase.model_validate(item) for item in raw.get("cases", [])]
    if not cases or not any(item.split == "train" for item in cases) or not any(item.split == "holdout" for item in cases):
        raise ValueError("dataset must contain non-empty train and holdout splits")
    if len({item.case_id for item in cases}) != len(cases):
        raise ValueError("dataset case_id values must be unique")
    return cases


def load_hohmann_config(path: str | Path) -> HohmannConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return HohmannConfig.model_validate(raw)


def _dimension_status(spec: _CandidateSpec) -> str:
    result = check_expression_dimensions(
        spec.expression.replace("/86400", ""),
        {"r1": "km", "r2": "km", "mu": "km^3/s^2"},
        expected_unit="s",
    )
    return "valid" if result.status == "valid" else "invalid"


def run_hohmann_experiment(config: HohmannConfig, cases: list[HohmannCase]) -> HohmannExperiment:
    train = [case for case in cases if case.split == "train"]
    holdout = [case for case in cases if case.split == "holdout"]
    specs = bounded_candidate_specs()
    candidate_order = [item.candidate_id for item in specs]
    candidate_set_hash = canonical_hash({
        "grammar_version": GRAMMAR_VERSION,
        "candidates": [{"candidate_id": item.candidate_id, "expression": item.expression, "complexity": item.complexity} for item in specs],
    })
    evaluations: list[CandidateEvaluation] = []
    failed_count = 0
    for spec in specs:
        dimensional_status = _dimension_status(spec)
        if dimensional_status == "invalid":
            failed_count += 1
            evaluations.append(
                CandidateEvaluation(
                    candidate_id=spec.candidate_id,
                    expression=spec.expression,
                    source="internal-bounded-generator",
                    complexity=spec.complexity,
                    dimensional_status="invalid",
                    train_predictions=[],
                    holdout_predictions=[],
                    train_rmse=float("inf"),
                    holdout_rmse=float("inf"),
                    train_residuals=[],
                    holdout_residuals=[],
                    failed_candidate_count=failed_count,
                )
            )
            continue
        train_predictions = [spec.evaluator(case) for case in train]
        holdout_predictions = [spec.evaluator(case) for case in holdout]
        gate = holdout_gate(
            [case.target_tof_days for case in train],
            train_predictions,
            [case.target_tof_days for case in holdout],
            holdout_predictions,
            max_holdout_rmse=float("inf"),
        )
        evaluations.append(
            CandidateEvaluation(
                candidate_id=spec.candidate_id,
                expression=spec.expression,
                source="internal-bounded-generator",
                complexity=spec.complexity,
                dimensional_status=dimensional_status,
                train_predictions=train_predictions,
                holdout_predictions=holdout_predictions,
                train_rmse=gate.train.rmse,
                holdout_rmse=gate.holdout.rmse,
                train_residuals=gate.train.residuals,
                holdout_residuals=gate.holdout.residuals,
                failed_candidate_count=failed_count,
            )
        )
    valid = [item for item in evaluations if item.dimensional_status == "valid"]
    if not valid:
        raise ValueError("candidate generator produced no dimensionally valid candidates")
    selected = min(valid, key=lambda item: (item.train_rmse, item.complexity, item.candidate_id))
    selected_gate = holdout_gate(
        [case.target_tof_days for case in train],
        selected.train_predictions,
        [case.target_tof_days for case in holdout],
        selected.holdout_predictions,
        max_holdout_rmse=config.max_holdout_rmse,
    )
    baseline = [hohmann_baseline(case.r1_km, case.r2_km, case.mu_km3_s2) for case in cases]
    return HohmannExperiment(
        grammar_version=GRAMMAR_VERSION,
        target=config.target,
        dataset_hash=canonical_hash([case.model_dump(mode="json") for case in cases]),
        candidate_set_hash=candidate_set_hash,
        candidate_order=candidate_order,
        candidates=evaluations,
        selected_candidate_id=selected.candidate_id,
        gate=selected_gate,
        baseline=baseline,
    )
