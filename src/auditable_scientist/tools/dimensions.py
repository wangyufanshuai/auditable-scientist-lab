"""Small exact dimension algebra for the first physics vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any

import sympy as sp


@dataclass(frozen=True)
class UnitDimension:
    length: Fraction = Fraction(0)
    mass: Fraction = Fraction(0)
    time: Fraction = Fraction(0)

    def __mul__(self, other: "UnitDimension") -> "UnitDimension":
        return UnitDimension(self.length + other.length, self.mass + other.mass, self.time + other.time)

    def __truediv__(self, other: "UnitDimension") -> "UnitDimension":
        return UnitDimension(self.length - other.length, self.mass - other.mass, self.time - other.time)

    def power(self, exponent: Fraction) -> "UnitDimension":
        return UnitDimension(self.length * exponent, self.mass * exponent, self.time * exponent)

    def label(self) -> str:
        parts = []
        for symbol, value in (("L", self.length), ("M", self.mass), ("T", self.time)):
            if value:
                parts.append(f"{symbol}^{value}")
        return "1" if not parts else " ".join(parts)


DIMENSIONLESS = UnitDimension()
BASE_UNITS = {
    "1": DIMENSIONLESS,
    "dimensionless": DIMENSIONLESS,
    "m": UnitDimension(length=Fraction(1)),
    "km": UnitDimension(length=Fraction(1)),
    "cm": UnitDimension(length=Fraction(1)),
    "kg": UnitDimension(mass=Fraction(1)),
    "g": UnitDimension(mass=Fraction(1)),
    "s": UnitDimension(time=Fraction(1)),
    "sec": UnitDimension(time=Fraction(1)),
    "day": UnitDimension(time=Fraction(1)),
    "days": UnitDimension(time=Fraction(1)),
}
UNIT_TOKEN = re.compile(r"(?P<name>[A-Za-z]+)(?:\^(?P<exponent>-?\d+(?:/\d+)?))?")


class DimensionError(ValueError):
    pass


@dataclass(frozen=True)
class DimensionCheckResult:
    status: str
    expression: str
    inferred_unit: str | None
    expected_unit: str | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "expression": self.expression,
            "inferred_unit": self.inferred_unit,
            "expected_unit": self.expected_unit,
            "message": self.message,
        }


def parse_unit(unit: str) -> UnitDimension:
    normalized = unit.strip().replace(" ", "")
    if normalized in BASE_UNITS:
        return BASE_UNITS[normalized]
    if not normalized:
        raise DimensionError("unit cannot be empty")
    result = DIMENSIONLESS
    numerator, *denominators = normalized.split("/")
    for product in (numerator,):
        for token in _unit_product_tokens(product):
            result = result * _parse_unit_factor(token)
    for denominator in denominators:
        for token in _unit_product_tokens(denominator):
            result = result / _parse_unit_factor(token)
    return result


def _unit_product_tokens(product: str) -> list[str]:
    """Parse a unit product while keeping names such as ``km`` intact."""
    tokens: list[str] = []
    position = 0
    for match in re.finditer(r"[A-Za-z]+(?:\^-?\d+(?:/\d+)?)?", product):
        if match.start() != position and product[position:match.start()] != "*":
            raise DimensionError(f"invalid unit expression: {product}")
        tokens.append(match.group(0))
        position = match.end()
    if position != len(product) or not tokens:
        raise DimensionError(f"invalid unit expression: {product}")
    return tokens


def _parse_unit_factor(token: str) -> UnitDimension:
    match = UNIT_TOKEN.fullmatch(token)
    if not match or match.group("name") not in BASE_UNITS:
        raise DimensionError(f"unknown unit token: {token}")
    exponent_text = match.group("exponent") or "1"
    exponent = Fraction(exponent_text) if "/" in exponent_text else Fraction(int(exponent_text))
    return BASE_UNITS[match.group("name")].power(exponent)


def check_expression_dimensions(
    expression: str,
    variable_units: dict[str, str],
    expected_unit: str | None = None,
) -> DimensionCheckResult:
    try:
        normalized = expression.replace("^", "**")
        symbols = {name: sp.Symbol(name) for name in variable_units}
        parsed = sp.sympify(normalized, locals=symbols)
        dimensions = {name: parse_unit(unit) for name, unit in variable_units.items()}
        inferred = _dimension_of(parsed, dimensions)
        expected = parse_unit(expected_unit) if expected_unit is not None else None
        if expected is not None and inferred != expected:
            return DimensionCheckResult(
                "invalid",
                expression,
                inferred.label(),
                expected.label(),
                "inferred dimension does not match expected unit",
            )
        return DimensionCheckResult(
            "valid", expression, inferred.label(), expected.label() if expected else None, "dimension check passed"
        )
    except (DimensionError, TypeError, ValueError, sp.SympifyError) as exc:
        return DimensionCheckResult("invalid", expression, None, expected_unit, str(exc))


def _dimension_of(node: sp.Expr, dimensions: dict[str, UnitDimension]) -> UnitDimension:
    if node.is_Number or node in (sp.pi, sp.E):
        return DIMENSIONLESS
    if node.is_Symbol:
        if str(node) not in dimensions:
            raise DimensionError(f"missing unit for symbol: {node}")
        return dimensions[str(node)]
    if node.is_Add:
        children = [_dimension_of(item, dimensions) for item in node.args]
        if any(item != children[0] for item in children[1:]):
            raise DimensionError("additive terms have incompatible dimensions")
        return children[0]
    if node.is_Mul:
        result = DIMENSIONLESS
        for item in node.args:
            result = result * _dimension_of(item, dimensions)
        return result
    if node.is_Pow:
        base, exponent = node.args
        if not exponent.is_Rational:
            raise DimensionError("power exponent must be numeric")
        return _dimension_of(base, dimensions).power(Fraction(int(exponent.p), int(exponent.q)))
    if node.func == sp.sqrt and len(node.args) == 1:
        return _dimension_of(node.args[0], dimensions).power(Fraction(1, 2))
    raise DimensionError(f"unsupported expression node: {node.func}")
