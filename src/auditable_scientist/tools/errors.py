"""Deterministic error statistics and holdout promotion gate."""

from __future__ import annotations

from math import sqrt
from pydantic import BaseModel, ConfigDict, Field


class ErrorStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1)
    mae: float = Field(ge=0)
    rmse: float = Field(ge=0)
    max_abs_error: float = Field(ge=0)
    residuals: list[float]


class HoldoutGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    threshold: float = Field(ge=0)
    train: ErrorStatistics
    holdout: ErrorStatistics
    reason: str


def compute_error_statistics(y_true: list[float], y_pred: list[float]) -> ErrorStatistics:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if not y_true:
        raise ValueError("at least one observation is required")
    residuals = [float(pred - truth) for truth, pred in zip(y_true, y_pred)]
    absolute = [abs(value) for value in residuals]
    return ErrorStatistics(
        count=len(residuals),
        mae=sum(absolute) / len(absolute),
        rmse=sqrt(sum(value * value for value in residuals) / len(residuals)),
        max_abs_error=max(absolute),
        residuals=residuals,
    )


def holdout_gate(
    train_true: list[float],
    train_pred: list[float],
    holdout_true: list[float],
    holdout_pred: list[float],
    *,
    max_holdout_rmse: float,
) -> HoldoutGateResult:
    if max_holdout_rmse < 0:
        raise ValueError("max_holdout_rmse must be non-negative")
    train = compute_error_statistics(train_true, train_pred)
    holdout = compute_error_statistics(holdout_true, holdout_pred)
    passed = holdout.rmse <= max_holdout_rmse
    reason = "holdout RMSE is within threshold" if passed else "holdout RMSE exceeds threshold"
    return HoldoutGateResult(
        passed=passed,
        threshold=max_holdout_rmse,
        train=train,
        holdout=holdout,
        reason=reason,
    )
