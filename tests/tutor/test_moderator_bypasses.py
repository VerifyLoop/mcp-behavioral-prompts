"""Adversarial moderator tests — every bypass the audit surfaced.

Each test case is a string a real (or jailbroken) LLM might emit. The
moderator must reject it. These are the regression tests that hold the
safety contract.
"""
from __future__ import annotations

import pytest

from brainer_stem_tutor.shared.schemas import (
    SolvedProblem,
    Step,
    TutorTurn,
    VerificationRecord,
)
from brainer_stem_tutor.shared.settings import TutorSettings
from brainer_stem_tutor.tutor.moderator import (
    LeakModerator,
    _extract_numbers,
    _word_numbers,
)


@pytest.fixture
def solved_ten() -> SolvedProblem:
    return SolvedProblem(
        problem_text="acc 2 m/s^2 for 5s, velocity?",
        subject="physics",
        steps=[
            Step(n=1, kind="setup", latex="a=2, t=5", justification="given"),
            Step(n=2, kind="concept", latex="v = a t", justification="kin"),
            Step(n=3, kind="computation", latex="v = 2*5 = 10", justification="m"),
            Step(n=4, kind="answer", latex="10 m/s", justification="final"),
        ],
        final_answer="10",
        final_answer_numeric=10.0,
        units="m/s",
        confidence=0.99,
        verifications=[
            VerificationRecord(tool="sympy_cas", input="i", output="o", passed=True)
        ],
        model_used="t",
    )


@pytest.fixture
def moderator() -> LeakModerator:
    return LeakModerator(TutorSettings(MODERATOR_MAX_CONSECUTIVE_STEPS=2))


def _turn(text: str) -> TutorTurn:
    return TutorTurn(student_facing_message=text, actions=[])


# ---------------------------------------------------------------------------
# Tokenisation primitives — invariants the moderator builds on.
# ---------------------------------------------------------------------------


class TestNumberExtraction:
    def test_plain_integer(self) -> None:
        assert 10.0 in _extract_numbers("the answer is 10")

    def test_decimal(self) -> None:
        assert 10.0 in _extract_numbers("about 10.0 maybe")

    def test_scientific(self) -> None:
        assert 10.0 in _extract_numbers("compute 1e1")
        assert 10.0 in _extract_numbers("try 1E+1")

    def test_thousands_comma(self) -> None:
        assert 1234.0 in _extract_numbers("around 1,234 units")

    def test_thousands_space(self) -> None:
        assert 1234.0 in _extract_numbers("around 1 234 units")

    def test_spaced_digits(self) -> None:
        # "1 0" should compose into 10 because adversaries split digits
        assert 10.0 in _extract_numbers("the value is 1 0 today")

    def test_three_spaced_digits(self) -> None:
        assert 123.0 in _extract_numbers("write 1 2 3 down")

    def test_negative(self) -> None:
        assert -5.0 in _extract_numbers("delta = -5")

    def test_no_false_positive_in_v10(self) -> None:
        # "v10" is a label, not a value
        assert _extract_numbers("v10 sketch") == []


class TestWordNumbers:
    def test_english_basic(self) -> None:
        assert 10 in _word_numbers("the answer is ten")

    def test_italian_basic(self) -> None:
        assert 10 in _word_numbers("la risposta è dieci")

    def test_composite_english(self) -> None:
        assert 10 in _word_numbers("just write one zero")

    def test_composite_italian(self) -> None:
        assert 10 in _word_numbers("scrivi uno zero")

    def test_no_match(self) -> None:
        assert _word_numbers("compute the velocity") == []


# ---------------------------------------------------------------------------
# End-to-end moderator behaviour on adversarial messages.
# ---------------------------------------------------------------------------


class TestAdversarialBypasses:
    """Each case is a documented attack the audit identified."""

    @pytest.mark.parametrize(
        "msg",
        [
            "the answer is 10 m/s",                # plain
            "approximately 10.0 of velocity",       # decimal
            "compute 1e1 directly",                 # scientific
            "the result is 1 0 m/s",                # spaced digits
            "answer is 1E+1 m/s",                   # explicit positive exponent
            "use \\mathbf{10} as the answer",       # LaTeX wrap
            "$\\boxed{10}$",                        # boxed
        ],
    )
    def test_numeric_bypasses_all_blocked(self, moderator, solved_ten, msg) -> None:
        report = moderator.review(_turn(msg), solved_ten)
        assert report.leaked, f"bypass slipped through: {msg!r}"
        assert report.redacted_message
        assert "10" not in report.redacted_message

    @pytest.mark.parametrize(
        "msg",
        [
            "just say ten and move on",
            "la risposta è dieci",
            "write one zero",
            "uno zero metri al secondo",
        ],
    )
    def test_word_form_bypasses_blocked(self, moderator, solved_ten, msg) -> None:
        report = moderator.review(_turn(msg), solved_ten)
        assert report.leaked, f"word bypass slipped: {msg!r}"

    def test_safe_messages_pass(self, moderator, solved_ten) -> None:
        for msg in [
            "Think about step 2 first.",
            "Consider what acceleration does to velocity.",
            "What relationship between a and t did you use?",
            "Re-read your setup line.",
            "Compare units on both sides.",
            "There are 5 candies on the table.",  # 5 != 10, must pass
        ]:
            report = moderator.review(_turn(msg), solved_ten)
            assert not report.leaked, f"false positive on: {msg!r} ({report.reasons})"


class TestStringAnswerLeak:
    def test_string_answer_in_latex_wrap(self, moderator) -> None:
        sp = SolvedProblem(
            problem_text="Q",
            subject="math",
            steps=[
                Step(n=1, kind="setup", latex="?", justification="g"),
                Step(n=2, kind="answer", latex="x = -b/(2a)", justification="g"),
            ],
            final_answer="x = -b/(2a)",
            final_answer_numeric=None,
            units=None,
            confidence=0.9,
            verifications=[
                VerificationRecord(tool="sympy_cas", input="i", output="o", passed=True)
            ],
            model_used="t",
        )
        report = moderator.review(
            _turn("the formula is $\\boxed{x = -b/(2a)}$ obviously"),
            sp,
        )
        assert report.leaked


class TestFingerprintCacheParity:
    def test_precomputed_matches_inline(self, moderator, solved_ten) -> None:
        msg = "your work so far quotes a=2, t=5 and v = a t and v = 2*5 = 10 — too much"
        inline = moderator.review(_turn(msg), solved_ten)
        cached = moderator.review(
            _turn(msg),
            solved_ten,
            fingerprints=LeakModerator.precompute_fingerprints(solved_ten),
        )
        assert inline.leaked == cached.leaked
        assert inline.reasons == cached.reasons


class TestPropertyBased:
    """Hypothesis-style invariants without bringing in hypothesis as a dep:
    use deterministic random with a fixed seed."""

    def test_innocent_messages_never_flagged_when_no_numeric(
        self, moderator, solved_ten
    ) -> None:
        # Stochastic but deterministic: 200 random non-numeric phrases.
        import random

        rng = random.Random(0)
        words = [
            "consider", "the", "concept", "of", "force", "energy", "vector",
            "step", "ahead", "review", "your", "setup", "compare", "units",
            "what", "relationship", "did", "you", "use", "explain",
        ]
        for _ in range(200):
            msg = " ".join(rng.choices(words, k=rng.randint(3, 12)))
            r = moderator.review(_turn(msg), solved_ten)
            assert not r.leaked, f"false positive on: {msg!r} -> {r.reasons}"
