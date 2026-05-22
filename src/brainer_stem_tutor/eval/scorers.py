"""Answer extractors and equivalence scorers for real benchmarks.

References:
- GSM8K (Cobbe et al. 2021): canonical answer follows "#### " in `answer`.
  Standard evaluation = regex extract + exact numeric match.
- MATH (Hendrycks et al. 2021): canonical answer is the last `\\boxed{...}`
  in `solution`. Standard evaluation = sympy equivalence on extracted
  expressions (Minerva recipe).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import sympy as sp

from ..solver.mcp_tools._timeout import run_with_timeout


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


_GSM8K_TAIL_RE = re.compile(r"####\s*(-?[\d,]+(?:\.\d+)?)")


def extract_gsm8k_answer(text: str) -> Optional[str]:
    """Pull the canonical GSM8K answer from a solution string.

    Returns the cleaned numeric string (no commas, leading + stripped) or
    None if no `#### ...` tail is present.
    """
    m = _GSM8K_TAIL_RE.search(text)
    if not m:
        return None
    return m.group(1).replace(",", "")


def extract_boxed_answer(text: str) -> Optional[str]:
    r"""Pull the LAST \\boxed{...} from a MATH-style solution.

    Handles nested braces so \\boxed{\\frac{1}{2}} returns "\\frac{1}{2}".
    Returns the inside of the last boxed, or None.
    """
    needle = r"\boxed{"
    last_index = text.rfind(needle)
    if last_index == -1:
        return None
    start = last_index + len(needle)
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


# ---------------------------------------------------------------------------
# Equivalence scorers
# ---------------------------------------------------------------------------


@dataclass
class ScoreResult:
    correct: bool
    method: str           # "numeric" | "sympy" | "string" | "skipped"
    notes: str = ""


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def score_gsm8k(predicted: str, gold: str, tol: float = 1e-3) -> ScoreResult:
    """GSM8K convention: numeric exact-match (modulo rounding)."""
    p = _to_float(predicted)
    g = _to_float(gold)
    if p is None or g is None:
        return ScoreResult(
            correct=False, method="skipped", notes="non-numeric extraction"
        )
    if g == 0:
        ok = abs(p) <= tol
    else:
        ok = abs(p - g) <= tol * max(1.0, abs(g))
    return ScoreResult(correct=ok, method="numeric")


def score_math(
    predicted: str, gold: str, timeout: float = 2.0
) -> ScoreResult:
    """MATH convention: sympy equivalence on extracted boxed expressions.

    Strategy:
    1. Try numeric float match first (cheapest).
    2. Try sympy `simplify(a - b) == 0` with a timeout.
    3. Fall back to normalised string equality (whitespace + lowercase).
    """
    p_num = _to_float(predicted)
    g_num = _to_float(gold)
    if p_num is not None and g_num is not None:
        if g_num == 0:
            return ScoreResult(correct=abs(p_num) <= 1e-9, method="numeric")
        return ScoreResult(
            correct=abs(p_num - g_num) <= 1e-6 * max(1.0, abs(g_num)),
            method="numeric",
        )

    try:
        p_expr = sp.sympify(predicted, evaluate=True)
        g_expr = sp.sympify(gold, evaluate=True)
    except (sp.SympifyError, SyntaxError, TypeError):
        norm_p = re.sub(r"\s+", "", predicted).lower()
        norm_g = re.sub(r"\s+", "", gold).lower()
        return ScoreResult(correct=norm_p == norm_g, method="string")

    try:
        diff = run_with_timeout(sp.simplify, args=(p_expr - g_expr,), seconds=timeout)
    except TimeoutError:
        return ScoreResult(correct=False, method="skipped", notes="sympy timeout")
    except Exception as exc:
        return ScoreResult(correct=False, method="skipped", notes=f"sympy error: {exc}")

    return ScoreResult(correct=bool(diff == 0), method="sympy")
