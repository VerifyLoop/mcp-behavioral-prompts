# MCP Behavioral Prompts + Brainer STEM Tutor

This repo hosts two packages under `src/`:

1. **`mcp_prompts_server`** — the original FastMCP server that exposes a set
   of behavioural prompts (project analyst, socratic consultant, code
   reviewer, software architect) as MCP primitives.
2. **`brainer_stem_tutor`** — the Brainer STEM tutoring stack: a verified
   solver, a socratic tutor with an anti-leak moderator, a vision pipeline
   for student notes, an orchestrator that glues them together, and an
   evaluation harness that lets us iterate on prompts with measurable
   metrics.

The MCP server also republishes the STEM stack's system prompts (solver,
tutor, vision) as MCP prompts so other agents can adopt them.

## Why this exists

Brainer wants an app that doesn't solve a STEM problem **for** the student
but accompanies them socratically to discover the solution. The trick: the
system already **knows** the verified answer — so the tutor can guide
without inventing and without giving away the answer even under
prompt-injection attempts.

The stack is structured so that the **safety** (anti-leak), the **control**
(follow policy), and the **intelligence** (LLM) are independent layers that
can be swapped without rewriting each other.

## Quickstart

```bash
poetry install
# or, for fast iteration without poetry:
pip install pydantic 'pydantic-settings>=2.3' sympy pint pytest 'pytest-asyncio>=0.23' mcp[cli] colorlog

# run the original MCP server
poetry run python -m mcp_prompts_server.server

# run all tests (122 of them)
pytest -q

# run the eval harness
PYTHONPATH=src python -m brainer_stem_tutor.eval.cli --dataset smoke --tutor

# run the end-to-end demo (writes a snapshot the static frontend can render)
PYTHONPATH=src python -m brainer_stem_tutor.demo \
  --snapshot src/brainer_stem_tutor/demo_frontend/snapshot.json

# then serve the static frontend
cd src/brainer_stem_tutor/demo_frontend && python -m http.server 8000
# open http://localhost:8000
```

## Package layout

```
src/brainer_stem_tutor/
├── shared/         # pydantic schemas + settings (the cross-layer contract)
├── solver/         # SolverAgent + sympy/pint MCP tools + cache + prompt
├── tutor/          # TutorAgent + LeakModerator + FollowPolicy + prompt
├── vision/         # VisionAgent + LiveDetector + VisionCache + prompt
├── orchestrator/   # SessionStore + SignalComputer + Orchestrator
├── eval/           # datasets + metrics + runners + simulated student + CLI
├── demo_frontend/  # static HTML overlay that renders snapshot.json
└── demo.py         # end-to-end CLI demo
```

## Key invariants

- **A SolvedProblem must include at least one VerificationRecord.** The
  solver refuses to close otherwise.
- **The LeakModerator inspects every tutor turn** and rewrites it when it
  spots the verified `final_answer` (numeric within tolerance, or string
  substring), or when more than 2 consecutive solution steps are quoted.
  Tested against three adversarial tutor LLMs (leaky-compliant,
  jailbreak-susceptible, step-copier) — all are caught.
- **FollowPolicy is pure-Python.** No LLM decides its own intervention
  style; signals → strategy is a deterministic table.

## Evaluation baseline (mock stack)

```
solver (C0_mock): n=5  acc=1.00  acc_verified=1.00  brier=0.006  conf=0.94
tutor  (C0_mock): n=75 leak_rate=0.000  (across 5 personas inc. extractor + shortcut)
```

Replace `MockSolverLLM` / `MockTutorLLM` / `MockVisionLLM` with the real
Gemini / GPT / DeepSeek implementations and the same harness measures the
delta.

## Roadmap

See `/.claude/plans/allora-devi-fare-un-dynamic-reddy.md` (project spec).
The Python backend, MCP tools, evaluation harness and static demo frontend
are complete. The Next.js full frontend (App Router + WebSocket streaming)
and the real Gemini-backed LLM adapters are the next phases.

## Repo conventions

- Develop on the feature branch indicated in the task; pushes go there.
- Tests live under `tests/`, one folder per layer. `conftest.py` at root
  inserts `src/` into `sys.path` so you can `pytest -q` without a poetry
  install.
- No emojis in code or commit messages.
