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
	$(PY) scripts/ingest.py

status:
	$(PY) -m fabric.cli status

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .

# usage: make mcp NAME=fullenrich
mcp:
	$(PY) -m fabric.mcp.serve $(NAME)
