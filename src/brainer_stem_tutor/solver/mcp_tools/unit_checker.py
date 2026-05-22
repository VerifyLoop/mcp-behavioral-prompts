"""Dimensional analysis backed by pint.

Used by the solver to catch the most common physics blunder: getting a number
right but with the wrong units, or producing an answer whose units don't
match the question.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pint

_UREG = pint.UnitRegistry()


@dataclass
class UnitCheckResult:
    ok: bool
    output: str
    notes: Optional[str] = None


def normalise_unit(unit: str) -> UnitCheckResult:
    """Normalise a unit string to its SI base representation.

    Returns the base unit string (e.g. 'kg * m / s ** 2' for Newton) so the
    solver can compare unit strings safely instead of using lexical equality.
    """
    try:
        q = _UREG.parse_expression(unit)
        base = q.to_base_units()
        return UnitCheckResult(
            ok=True,
            output=str(base.units),
            notes=f"magnitude={base.magnitude}",
        )
    except Exception as exc:
        return UnitCheckResult(ok=False, output="", notes=f"parse failed: {exc}")


def check_dimensions(expected: str, actual: str) -> UnitCheckResult:
    """Return ok=True if `expected` and `actual` are dimensionally equivalent."""
    try:
        e = _UREG.parse_expression(expected)
        a = _UREG.parse_expression(actual)
    except Exception as exc:
        return UnitCheckResult(ok=False, output="false", notes=f"parse: {exc}")
    try:
        ratio = (a / e).to_base_units()
        if ratio.dimensionless:
            return UnitCheckResult(
                ok=True,
                output="true",
                notes=f"ratio magnitude={ratio.magnitude}",
            )
        return UnitCheckResult(
            ok=False,
            output="false",
            notes=f"residual dimension={ratio.dimensionality}",
        )
    except Exception as exc:
        return UnitCheckResult(ok=False, output="false", notes=f"compare: {exc}")
