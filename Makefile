# ACR Connection Fabric. Works on a fresh clone with an empty .env (mock mode).
PY ?= .venv/Scripts/python.exe
PIP ?= .venv/Scripts/pip.exe

.PHONY: setup seed ingest status test mcp lint

setup:
	python -m venv .venv || py -3 -m venv .venv
	$(PIP) install -e ".[dev]"

seed:
	$(PY) scripts/seed.py

ingest:
	$(PY) scripts/ingest.py --analyze

status:
	$(PY) -m fabric.cli status

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .

# usage: make mcp NAME=fullenrich
mcp:
	$(PY) -m fabric.mcp.serve $(NAME)

# one-command demo on fixtures: seed, ingest, content analysis, full agent run
demo:
	$(PY) scripts/seed.py
	$(PY) scripts/ingest.py --analyze
	$(PY) -m fabric.cli demo
