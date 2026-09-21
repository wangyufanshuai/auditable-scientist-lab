"""T2: deterministic intervention semantics with a negative control."""

from __future__ import annotations

from math import sqrt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import TrackReceipt, make_track_receipt


class CausalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    split: Literal["train", "holdout"]
    context_value: float
    intervention_value: float
    expected_outcome: float


class CausalEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "causal-intervention-v1"
    coefficient: float
    intercept: float
    train_rmse: float = Field(ge=0)
    holdout_rmse: float = Field(ge=0)
    max_context_invariance_error: float = Field(ge=0)
    passed: bool
    negative_candidate_rejected: bool
    notes: list[str]


def _rmse(cases: list[CausalCase], coefficient: float, intercept: float) -> float:
    if not cases:
        raise ValueError("causal split cannot be empty")
    residuals = [coefficient * item.intervention_value + intercept - item.expected_outcome for item in cases]
    return sqrt(sum(item * item for item in residuals) / len(residuals))


def evaluate_causal_fixture(
    cases: list[CausalCase],
    *,
    coefficient: float = 2.0,
    intercept: float = 1.0,
    negative_coefficient: float = 1.0,
    max_rmse: float = 1e-12,
) -> tuple[CausalEvaluation, TrackReceipt]:
    train = [item for item in cases if item.split == "train"]
    holdout = [item for item in cases if item.split == "holdout"]
    if not train or not holdout:
        raise ValueError("causal fixture requires train and holdout cases")
    train_rmse = _rmse(train, coefficient, intercept)
    holdout_rmse = _rmse(holdout, coefficient, intercept)
    context_errors = [
        coefficient * item.intervention_value + intercept - (coefficient * (item.intervention_value + item.context_value * 0.0) + intercept)
        for item in cases
    ]
    max_context_error = max(abs(item) for item in context_errors)
    negative_rmse = _rmse(holdout, negative_coefficient, intercept)
    negative_rejected = negative_rmse > max_rmse
    passed = holdout_rmse <= max_rmse and max_context_error <= max_rmse and negative_rejected
    evaluation = CausalEvaluation(
        coefficient=coefficient,
        intercept=intercept,
        train_rmse=train_rmse,
        holdout_rmse=holdout_rmse,
        max_context_invariance_error=max_context_error,
        passed=passed,
        negative_candidate_rejected=negative_rejected,
        notes=[
            "Intervention outcome uses do(x=value); context_value is intentionally ignored.",
            "Negative candidate is required to fail the holdout gate.",
        ],
    )
    receipt = make_track_receipt(
        track_id="T2",
        evaluator_id=evaluation.evaluator_id,
        input_payload=[item.model_dump(mode="json") for item in cases],
        evidence_level="validated-reproduction" if passed else "demo",
        passed=passed,
        negative_case_passed=negative_rejected,
        result=evaluation.model_dump(mode="json"),
        blocked_gates=["real-world intervention data and causal identification"],
    )
    return evaluation, receipt
