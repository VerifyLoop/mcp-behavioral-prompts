"""Answer extractors + equivalence scorers for GSM8K and MATH."""
from __future__ import annotations

from brainer_stem_tutor.eval.scorers import (
    extract_boxed_answer,
    extract_gsm8k_answer,
    score_gsm8k,
    score_math,
)


class TestGSM8KExtraction:
    def test_simple(self) -> None:
        text = "Step 1...\nStep 2...\n#### 42"
        assert extract_gsm8k_answer(text) == "42"

    def test_with_commas(self) -> None:
        text = "We get the result.\n#### 1,234"
        assert extract_gsm8k_answer(text) == "1234"

    def test_decimal(self) -> None:
        text = "Solution.\n#### 3.14"
        assert extract_gsm8k_answer(text) == "3.14"

    def test_negative(self) -> None:
        text = "#### -5"
        assert extract_gsm8k_answer(text) == "-5"

    def test_missing_tail(self) -> None:
        text = "I think the answer is 42."
        assert extract_gsm8k_answer(text) is None


class TestBoxedExtraction:
    def test_simple_boxed(self) -> None:
        assert extract_boxed_answer("Therefore $\\boxed{42}$.") == "42"

    def test_last_boxed_wins(self) -> None:
        text = "First guess $\\boxed{3}$ but actually $\\boxed{42}$."
        assert extract_boxed_answer(text) == "42"

    def test_nested_braces_in_boxed(self) -> None:
        text = "Final answer: $\\boxed{\\frac{1}{2}}$"
        assert extract_boxed_answer(text) == "\\frac{1}{2}"

    def test_unbalanced_braces_returns_none(self) -> None:
        # Audit: never silently misparse — return None on bad input.
        assert extract_boxed_answer("\\boxed{42") is None

    def test_no_boxed(self) -> None:
        assert extract_boxed_answer("the answer is 42") is None


class TestGSM8KScorer:
    def test_exact(self) -> None:
        r = score_gsm8k("42", "42")
        assert r.correct and r.method == "numeric"

    def test_close_decimal(self) -> None:
        r = score_gsm8k("3.14159", "3.14160", tol=1e-3)
        assert r.correct

    def test_wrong(self) -> None:
        r = score_gsm8k("42", "43")
        assert not r.correct

    def test_non_numeric(self) -> None:
        r = score_gsm8k("forty two", "42")
        assert not r.correct and r.method == "skipped"


class TestMathScorer:
    def test_numeric_match(self) -> None:
        r = score_math("42", "42")
        assert r.correct and r.method == "numeric"

    def test_sympy_equivalence(self) -> None:
        r = score_math("(x+1)**2", "x**2 + 2*x + 1")
        assert r.correct and r.method == "sympy"

    def test_sympy_inequivalence(self) -> None:
        r = score_math("x + 1", "x + 2")
        assert not r.correct and r.method == "sympy"

    def test_fraction(self) -> None:
        r = score_math("1/2", "0.5")
        assert r.correct  # numeric path

    def test_string_fallback_on_unparseable(self) -> None:
        # Symbols sympy can't parse fall back to normalised string match.
        r = score_math("hello world", "hello world")
        assert r.correct and r.method == "string"

    def test_sympy_timeout_safe(self) -> None:
        # Force a timeout via budget=0 — should not raise.
        r = score_math("(x+1)**100", "x**100", timeout=1e-9)
        assert not r.correct
        assert r.method in ("skipped", "sympy")
