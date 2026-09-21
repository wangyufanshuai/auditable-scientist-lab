"""Deterministic scientific tools used by the audit layer."""

from .dimensions import DimensionCheckResult, check_expression_dimensions, parse_unit
from .errors import ErrorStatistics, HoldoutGateResult, compute_error_statistics, holdout_gate
from .numerical import HohmannResult, hohmann_baseline

__all__ = [
    "DimensionCheckResult",
    "ErrorStatistics",
    "HohmannResult",
    "HoldoutGateResult",
    "check_expression_dimensions",
    "compute_error_statistics",
    "hohmann_baseline",
    "holdout_gate",
    "parse_unit",
]
