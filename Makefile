.PHONY: install test test-cov lint types check eval eval-ci demo clean serve-frontend mcp all

PY := PYTHONPATH=src python

install:
	poetry install || pip install pydantic 'pydantic-settings>=2.3' sympy pint pytest \
		'pytest-asyncio>=0.23' pytest-cov ruff mypy colorlog fastapi httpx uvicorn

test:
	$(PY) -m pytest -q

test-cov:
	$(PY) -m pytest --cov --cov-report=term-missing --cov-fail-under=85

lint:
	ruff check src/brainer_stem_tutor tests

types:
	mypy src/brainer_stem_tutor

check: lint types test-cov eval-ci

eval:
	$(PY) -m brainer_stem_tutor.eval.cli --dataset smoke --tutor

eval-ci:
	$(PY) -m brainer_stem_tutor.eval.cli --dataset smoke --tutor --ci

demo:
	$(PY) -m brainer_stem_tutor.demo --snapshot src/brainer_stem_tutor/demo_frontend/snapshot.json

serve-frontend: demo
	cd src/brainer_stem_tutor/demo_frontend && python -m http.server 8000

mcp:
	$(PY) -m mcp_prompts_server.server

all: check

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage
