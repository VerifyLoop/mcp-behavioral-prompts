"""Anti-leak moderator.

The tutor is trusted-but-bounded: even when prompted carefully, an LLM may
slip and reveal the final answer or copy multiple consecutive steps from the
verified solution. The moderator is a deterministic post-processor that
inspects every TutorTurn before it leaves the orchestrator.

Defenses, ordered by recall:
1. Numeric leak: any number in the message that, after normalisation,
   evaluates to the verified `final_answer_numeric` within tolerance. Catches
   plain digits ("10"), scientific notation ("1e1"), spaced digits ("1 0"),
   thousands-separator forms ("1,000.0"), and prefix-LaTeX wrapping
   ("\\mathbf{10}").
2. Number-word leak: the digits of `final_answer_numeric` spelled out in EN
   or IT ("ten", "dieci", "one zero", "uno zero").
3. String leak: the canonical `final_answer` substring (case-insensitive).
4. Step-copy leak: more than `MODERATOR_MAX_CONSECUTIVE_STEPS` consecutive
   solution-step LaTeX fragments quoted in order.

On a hit the message is rewritten to a generic Socratic fallback that
references the first unproven step. The action list is preserved.

Performance: step fingerprints are computed once via `LeakModerator.precompute_fingerprints`
when the solution is solved — `review` then runs in O(len(message)) per check.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ..shared.schemas import SolvedProblem, TutorTurn
from ..shared.settings import TutorSettings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class LeakReport:
    """Why the moderator decided a message was unsafe."""

    leaked: bool
    reasons: list[str]
    redacted_message: str | None = None
    matched_steps: list[int] | None = field(default_factory=list)


# ---------------------------------------------------------------------------
# Number-word lexicon (English + Italian).
#
# Only digits 0..20 + a handful of decades and multipliers. The point is to
# catch the common verbal forms — a determined attacker could still write
# "sette per quattordici diviso uno", but at that point the student has done
# more arithmetic than just reading the answer.
# ---------------------------------------------------------------------------

_NUMBER_WORDS: dict[str, int] = {
    # English
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
    # Italian
    "zero_it": 0,  # placeholder; not used — "zero" same word
    "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10,
    "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
    "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19, "venti": 20,
    "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60,
    "settanta": 70, "ottanta": 80, "novanta": 90, "cento": 100, "mille": 1000,
}


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _strip_latex_decorators(s: str) -> str:
    """Strip LaTeX wrapping that could hide a number from substring search.

    "\\mathbf{10}" -> "mathbf 10"  (then numeric regex still finds "10")
    "$\\boxed{10}$" -> " boxed 10 "
    """
    s = s.replace("\\", " ")
    s = re.sub(r"[{}$]", " ", s)
    return s


# Matches integers, decimals, scientific notation, and thousands-separated forms.
# Lookbehind rejects letter- AND digit-prefixed labels so "v10" and the "0"
# inside "10" aren't extracted as separate numbers. We try thousands grouping
# first (strict: exactly-3-digit groups after the leading 1-3 digits) and fall
# back to a plain numeric form.
_NUM_RE = re.compile(
    r"""
    (?<![A-Za-z0-9])(?:
        -?\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?(?:[eE][+-]?\d+)?
        |
        -?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?
    )
    """,
    re.VERBOSE,
)

# Adversarial single-digit spacing: "1 0", "1 2 3". Composes into one number.
_SPACED_DIGIT_RE = re.compile(r"(?<![A-Za-z0-9])(?:\d\s+){1,}\d(?![A-Za-z0-9])")
_WORD_RE = re.compile(r"[a-zA-Z]+")


def _extract_numbers(msg: str) -> list[float]:
    """Pull every plausible numeric encoding out of `msg`.

    Order: spaced-digit composites first (so "1 0" becomes 10 before the
    plain regex grabs 1 and 0 separately), then thousands/scientific.
    """
    nums: list[float] = []
    consumed: list[tuple[int, int]] = []

    import contextlib

    for m in _SPACED_DIGIT_RE.finditer(msg):
        joined = m.group(0).replace(" ", "")
        with contextlib.suppress(ValueError):
            nums.append(float(joined))
            consumed.append((m.start(), m.end()))

    def overlaps(a_start: int, a_end: int) -> bool:
        return any(not (a_end <= cs or ce <= a_start) for cs, ce in consumed)

    for m in _NUM_RE.finditer(msg):
        if overlaps(m.start(), m.end()):
            continue
        token = m.group(0).replace(",", "").replace(" ", "")
        with contextlib.suppress(ValueError):
            nums.append(float(token))
    return nums


def _word_numbers(msg: str) -> list[int]:
    """Resolve EN/IT number-words and simple compositions like 'one zero'."""
    tokens = [w.lower() for w in _WORD_RE.findall(msg)]
    out: list[int] = []
    for tok in tokens:
        if tok in _NUMBER_WORDS:
            out.append(_NUMBER_WORDS[tok])

    # Composite: pairs of single-digit words concatenate ("one zero" -> 10).
    # We accept up to 4 consecutive single-digit words (covers up to 9999).
    i = 0
    while i < len(tokens):
        if tokens[i] in _NUMBER_WORDS and _NUMBER_WORDS[tokens[i]] < 10:
            run: list[int] = []
            j = i
            while j < len(tokens) and tokens[j] in _NUMBER_WORDS and _NUMBER_WORDS[tokens[j]] < 10:
                run.append(_NUMBER_WORDS[tokens[j]])
                j += 1
            if len(run) >= 2:
                composed = int("".join(str(d) for d in run))
                out.append(composed)
            i = j
        else:
            i += 1
    return out


class LeakModerator:
    """Inspect a TutorTurn and decide whether it leaks the solution."""

    def __init__(self, settings: TutorSettings | None = None) -> None:
        self._settings = settings or get_settings()

    # ---- precomputation hook ------------------------------------------------

    @staticmethod
    def precompute_fingerprints(solved: SolvedProblem) -> list[tuple[int, str]]:
        """Return [(step_n, fingerprint)] for the step-copy detector.

        Cheap to call; the orchestrator may cache the result alongside the
        SolvedProblem to avoid re-doing it on every review.
        """
        out = []
        for step in solved.steps:
            fp = LeakModerator._step_fingerprint(step.latex)
            if fp:
                out.append((step.n, fp))
        return out

    # ---- main entry point --------------------------------------------------

    def review(
        self,
        turn: TutorTurn,
        solved: SolvedProblem,
        fingerprints: list[tuple[int, str]] | None = None,
    ) -> LeakReport:
        reasons: list[str] = []
        matched: list[int] = []
        raw_msg = turn.student_facing_message
        cleaned = _normalise(_strip_latex_decorators(raw_msg))

        if self._numeric_leak(cleaned, solved):
            reasons.append("numeric final_answer present in message")

        if self._word_number_leak(cleaned, solved):
            reasons.append("final_answer spelled out as words")

        if self._string_leak(cleaned, solved):
            reasons.append("string final_answer present in message")

        fps = fingerprints if fingerprints is not None else self.precompute_fingerprints(solved)
        consecutive = self._consecutive_step_match(cleaned, fps, matched)
        if consecutive > self._settings.MODERATOR_MAX_CONSECUTIVE_STEPS:
            reasons.append(
                f"{consecutive} consecutive solution steps appear in message "
                f"(limit {self._settings.MODERATOR_MAX_CONSECUTIVE_STEPS})"
            )

        leaked = bool(reasons)
        redacted = self._redact(solved) if leaked else None
        if leaked:
            logger.warning("moderator blocked leak: %s", reasons)
        return LeakReport(
            leaked=leaked,
            reasons=reasons,
            redacted_message=redacted,
            matched_steps=matched,
        )

    # ---- detection helpers --------------------------------------------------

    def _numeric_leak(self, msg_norm: str, solved: SolvedProblem) -> bool:
        if solved.final_answer_numeric is None:
            return False
        target = solved.final_answer_numeric
        tol = self._settings.MODERATOR_NUMERIC_TOLERANCE
        return any(self._matches(val, target, tol) for val in _extract_numbers(msg_norm))

    def _word_number_leak(self, msg_norm: str, solved: SolvedProblem) -> bool:
        if solved.final_answer_numeric is None:
            return False
        target = solved.final_answer_numeric
        tol = self._settings.MODERATOR_NUMERIC_TOLERANCE
        return any(self._matches(float(v), target, tol) for v in _word_numbers(msg_norm))

    @staticmethod
    def _matches(val: float, target: float, tol: float) -> bool:
        if target == 0:
            return abs(val) <= tol
        if abs(val - target) <= tol:
            return True
        return abs((val - target) / target) <= tol

    def _string_leak(self, msg_norm: str, solved: SolvedProblem) -> bool:
        fa = _normalise(solved.final_answer)
        if not fa or len(fa) < 2:
            return False
        return fa in msg_norm

    def _consecutive_step_match(
        self,
        msg_norm: str,
        fingerprints: list[tuple[int, str]],
        matched_out: list[int],
    ) -> int:
        run = 0
        best = 0
        for step_n, fp in fingerprints:
            if fp in msg_norm:
                run += 1
                best = max(best, run)
                matched_out.append(step_n)
            else:
                run = 0
        return best

    @staticmethod
    def _step_fingerprint(latex: str) -> str:
        s = _strip_latex_decorators(latex)
        s = _normalise(s)
        # Single-character fingerprints would false-positive trivially.
        return s if len(s) >= 3 else ""

    def _redact(self, solved: SolvedProblem) -> str:
        target_step = next(
            (s.n for s in solved.steps if s.kind in ("setup", "concept", "derivation")),
            1,
        )
        return (
            f"Let's slow down and look at step {target_step} together. "
            "What does each symbol there represent, and what relationship between "
            "them did you use? Try to articulate it in one sentence before we "
            "move on."
        )
