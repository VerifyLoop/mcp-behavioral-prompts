# Contributing

## Setup

```bash
poetry install
# or, without poetry:
pip install pydantic 'pydantic-settings>=2.3' sympy pint pytest \
  'pytest-asyncio>=0.23' pytest-cov ruff mypy colorlog fastapi httpx
```

## Before opening a PR

Every commit must keep all four gates green:

```bash
make check
# expands to: ruff + mypy + pytest with 85% coverage gate + eval CI gates
```

Individual targets:

```bash
make lint       # ruff
make types      # mypy
make test       # pytest -q
make test-cov   # with coverage gate
make eval-ci    # solver accuracy + tutor leak_rate gates on smoke dataset
make demo       # writes snapshot.json for the static frontend
```

## Coding conventions

- **No emojis** in source, tests, commit messages, or PR descriptions.
- **One thing per commit** with a descriptive message — never amend
  previous commits unless explicitly asked.
- **Default to no comments.** Only add one when the *why* is non-obvious
  (a workaround, an invariant the reader couldn't infer, a constraint
  from an external system).
- **Match scope.** Bug fix doesn't need surrounding cleanup; one-shot
  operation doesn't need a helper.
- **Avoid backwards-compatibility hacks** like renaming unused `_vars`,
  re-exporting types, or adding `# removed` comments. Delete cleanly.
- **Boundary validation only.** Don't add error handling for scenarios
  that can't happen — trust internal code and framework guarantees.

## Repository invariants

These hold across every commit (CI enforces them):

1. `SolvedProblem` requires at least one `VerificationRecord`.
2. `LeakModerator` blocks any tutor message containing the verified
   `final_answer` in any encoding (digits, scientific, thousands-grouped,
   spaced, LaTeX-wrapped, English number-words, Italian number-words).
3. Step-copy leak limit is configurable; tested at 2.
4. Coverage gate: 85%. Current: 90%+.
5. Ruff and mypy must be clean.
6. Eval gates: `solver accuracy >= 0.8`, `tutor leak_rate == 0`.

## Adding a new dataset

1. Drop a JSONL file under `eval/datasets/` (or register a builtin in
   `loaders.py`).
2. If the schema differs from `EvalProblem`, add a loader in
   `eval/datasets/hf_loaders.py`.
3. If answer extraction needs special handling, add a scorer in
   `eval/scorers.py`.
4. Run `make eval-ci`.

## Adding a new tutor strategy

1. Extend the `Strategy` Literal in `tutor/policy.py`.
2. Add the decision branch in `FollowPolicy.decide`.
3. Add the message template in `MockTutorLLM._message_for`.
4. Add a unit test under `tests/tutor/test_policy_boundaries.py`.
5. Update `TUTOR_SYSTEM_PROMPT` so a real Gemini-backed tutor knows
   how to handle the strategy.

## Adding a new moderator rule

Critical path — go through a code review with a sanity check using
`replay_session` over a held-out corpus of historic turns to ensure
no regressions on benign messages.
