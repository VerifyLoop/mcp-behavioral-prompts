.PHONY: install test eval demo clean lint serve-frontend mcp

PY := PYTHONPATH=src python

install:
	poetry install || pip install pydantic 'pydantic-settings>=2.3' sympy pint pytest 'pytest-asyncio>=0.23' colorlog fastapi uvicorn

test:
	$(PY) -m pytest -q

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

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache
