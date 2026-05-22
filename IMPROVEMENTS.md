# Brainer STEM Tutor — Improvement TODO (driven by audit + research)

Generated from a parallel audit (`Explore` agent) and a research pass on Gemini /
ADK / MATH-GSM8K / prompt injection / Brier calibration. Each item references a
finding so the rationale is auditable.

## Phase A — Safety hardening (HIGHEST PRIORITY)

The moderator is what makes this product safe. The audit found concrete bypasses;
the research recommends a layered defense (spotlighting + structured output +
output-side classifier — Hines et al. 2024, Microsoft MSRC 2025).

- [ ] **A1**. Strengthen `LeakModerator._numeric_leak`:
  - extend regex to match scientific notation: `r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"`
  - detect "spaced digits" — collapse runs of `\d ` into a single number before scanning
  - apply step-fingerprint normalisation (strip backslashes/braces) BEFORE numeric search, not after — currently inconsistent
- [ ] **A2**. Detect **number words** in EN and IT (and the digits-spelled-out form).
  - lexicon-based for single digits and common multi-digit ("ten", "dieci", "twenty", "venti", ...)
  - "one zero" / "uno zero" -> compose to "10"
- [ ] **A3**. Add **spotlighting** to `TutorAgent`: wrap the student message in a
  datamarker (sentinel char between words) when handing it to the LLM, and
  document it in `TUTOR_SYSTEM_PROMPT`. The mock LLM doesn't use it but a real
  Gemini-backed impl will — and the schema needs to exist now.
- [ ] **A4**. Cache step fingerprints on `SolvedProblem` construction so the
  moderator does O(steps) work once per problem, not per review.

## Phase B — Solver verification correctness

- [ ] **B1**. Mark verifications `passed=False` when `sympy.solve` returns
  complex/imaginary roots and the problem asked for reals (no `I` in expected
  domain). Update `MockSolverLLM._draft_equation`.
- [ ] **B2**. Reject multi-variable solutions: if the returned roots contain
  free symbols (`y` when solving for `x`), mark `passed=False, notes="under-specified"`.
- [ ] **B3**. Wrap every `sympy.*` call in `sympy_cas.py` with a small
  timeout helper (signal.alarm on POSIX, threading on Windows) and treat
  timeout as `ok=False` rather than silently raising and being swallowed.

## Phase C — Bug fixes

- [ ] **C1**. `FollowPolicy.decide`: off-by-one at boundary
  `last_correct_step == total_steps`. Currently `min(s+1, max(total,1))` can return `s+1`
  even past the last step. Add explicit test for this case.
- [ ] **C2**. Stop using `# type: ignore` on `matched_steps`; make it
  `Optional[list[int]]`.
- [ ] **C3**. Validate `subject` literal at the SolverAgent boundary so an
  ill-formed Draft can't slip through.

## Phase D — Test coverage gaps

- [ ] **D1**. Property-based tests (`hypothesis`) for the moderator: generate
  random "innocent" messages and adversarial templates, assert no false
  positives on innocent and no leak on adversarial.
- [ ] **D2**. `SolvedCache` LRU eviction at `max_entries` boundary: verify the
  oldest entry is evicted, not arbitrary.
- [ ] **D3**. `VisionCache` independent tests: granularity collision, LRU
  ordering, put-on-existing-key updates recency.
- [ ] **D4**. `SolvedProblem`/`TutorAction`/`VisionResult` explicit invariant
  tests for: empty verifications rejected, `correct_idx` out-of-range, duplicate
  element ids.
- [ ] **D5**. Boundary `FollowPolicy` test for the C1 fix.

## Phase E — Real-benchmark integration

- [ ] **E1**. Add `MATHLoader` and `GSM8KLoader` that read JSONL files
  with the canonical fields (`question`/`answer` for GSM8K, `problem`/`solution`
  for MATH).
- [ ] **E2**. Implement `BoxedAnswerExtractor` (extracts `\boxed{...}` from MATH
  solutions) and `GSM8KAnswerExtractor` (extracts the number after `####`).
- [ ] **E3**. Add `SympyEquivalenceScorer` that compares two candidate answers
  with `sympy.simplify(a - b) == 0` plus numeric fallback — matches the
  Minerva/math_verify recipe.
- [ ] **E4**. Brier **Skill Score** + quantile-bin reliability table + bootstrap
  95% CI for small N (research §5).

## Phase F — Vision schema for Gemini compatibility

- [ ] **F1**. Add `box_2d: list[int]` ([y_min, x_min, y_max, x_max] in 0-1000) as
  the canonical Gemini-native format on `VisionElement`. Keep `BBox(x,y,w,h)` as
  a derived view. Converters in both directions with tests.
- [ ] **F2**. Update `VISION_SYSTEM_PROMPT` to spec the Gemini-native format.

## Phase G — Real LLM adapter scaffolding

- [ ] **G1**. `GeminiSolverLLM(SolverProtocol)` skeleton: accepts an injected
  `client` (so tests can pass a fake), uses `response_schema` for structured
  output. No API key here — class compiles, raises `NotImplementedError` if
  client is None at runtime.
- [ ] **G2**. `ADKSolverAdapter` showing the 2026 `McpToolset(connection_params=StdioConnectionParams(...))` pattern (research §2).

## Phase H — Tooling & DX

- [ ] **H1**. `pyproject.toml`: add `ruff` and `mypy` config.
- [ ] **H2**. Run `ruff --fix` and ensure clean. Run `mypy src/brainer_stem_tutor` and fix what's reasonable.
- [ ] **H3**. `pytest-cov` config + coverage gate (`--cov-fail-under=85`).
- [ ] **H4**. Update CI workflow to run lint + types + coverage.
- [ ] **H5**. Architecture mermaid diagram in README.
- [ ] **H6**. `CHANGELOG.md`.
- [ ] **H7**. Configure brainer logging via `LoggingSetup` (separate handler from mcp_prompts_server).

## Phase I — Operational

- [ ] **I1**. Session replay: `Session.replay()` walks recorded turns and
  re-runs them through the moderator — useful for regression tests on prompt
  changes.
- [ ] **I2**. `HintQualityJudge` stub with the same `Protocol` shape as a real
  LLM-judge would have (so it's swappable). Mock uses simple heuristics.
- [ ] **I3**. Concurrent-session test (5 sessions in parallel via threading).
- [ ] **I4**. Performance benchmark for the moderator (microbenchmark via
  pytest-benchmark or just `time.perf_counter`).
