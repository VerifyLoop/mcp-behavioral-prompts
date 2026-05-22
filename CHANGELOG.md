# Changelog

All notable changes to the Brainer STEM Tutor stack live here. Format: Keep
a Changelog; semver applies to the `brainer_stem_tutor` package.

## [Unreleased] — 2026-05-22

### Added

- **Anti-leak hardening (Phase A)**: bypass-resistant numeric parser
  catching scientific notation, thousands separators, single-digit
  spacing, LaTeX-wrapped numbers, and EN/IT number-words (incl.
  composite "one zero" / "uno zero" → 10).
- **Spotlighting** (Hines et al. 2024): `spotlight.datamark` wraps every
  student turn in a sentinel so the LLM treats user input as data, not
  instructions. `GeminiTutorLLM` applies it by default.
- **Solver correctness (Phase B)**: complex-only roots, multi-variable
  under-specified solutions, and sympy timeouts now mark verifications
  as failed (was: silently passing at confidence > 0.5). Cross-platform
  `run_with_timeout` (SIGALRM + threaded fallback) on every sympy call.
- **Policy boundary fix (Phase C)**: `target_step` cannot escape past
  `total_steps` when a student finishes; new "all steps completed"
  branch returns confirm_and_advance with a dedicated reason.
- **Real-benchmark loaders (Phase E)**: `load_gsm8k_jsonl`,
  `load_math_jsonl`, with canonical `#### N` and `\boxed{...}` extractors
  (last-boxed, nested-brace aware). `score_math` uses sympy equivalence
  with timeout; `score_gsm8k` uses relative-tolerance numeric match.
- **Calibration metrics** (small-N): Brier Skill Score against the
  climatology baseline, 5-quantile reliability bins, percentile
  bootstrap CI.
- **Gemini-native vision schema (Phase F)**: `BBox.from_gemini_box_2d`
  and `to_gemini_box_2d` convert the official `[y_min, x_min, y_max,
  x_max]` 0-1000 integer format. `VisionAgent` accepts both Gemini-native
  (`box_2d` + `page_meta`) and internal (`bbox` + `page_width`) payload
  shapes at the boundary.
- **Real-LLM adapter scaffolding (Phase G)**: `GeminiSolverLLM`,
  `GeminiTutorLLM`, `GeminiVisionLLM` shaped to the existing Protocols
  with a duck-typed `GenerativeClient`. `build_adk_solver_agent_stub`
  shows the 2026 `McpToolset(connection_params=StdioConnectionParams(...))`
  pattern and raises a clear ImportError when ADK is missing.
- **Cache LRU tests**: `SolvedCache` and `VisionCache` eviction at
  `max_entries`, recency refresh on overwrite, granularity isolation.
- **Tooling (Phase H)**: ruff + mypy clean across 47 source files,
  pytest-cov gate at 85% (current: 90%), CI workflow runs lint + types
  + tests across Python 3.10/3.11/3.12 + eval gates.

### Fixed

- `cache or SolvedCache()` discarded an empty user-supplied cache
  because `__len__` made it falsy. Now uses `is None`.
- `LeakReport.matched_steps` was typed `list[int]` with a default of
  `None`; now `Optional[list[int]]` with no `type: ignore`.
- `SolverAgent.solve` validates `subject` against the schema literal at
  the boundary; unknown subjects coerce to `"other"`.

## [0.1.0] — 2026-05-21

### Added

- Initial release of `brainer_stem_tutor` package: shared schemas,
  solver agent with sympy/pint verification, socratic tutor with
  anti-leak moderator, vision pipeline, orchestrator + FastAPI shim,
  eval harness with 5 simulated student personas, static HTML demo,
  MCP-prompt republishing.
- 232 tests, 90% coverage, 0 leaks across 75 adversarial-persona turns.
