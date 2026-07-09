.PHONY: setup seed ingest test lint clean

PYTHON ?= python

setup:
	$(PYTHON) -m pip install -e ".[dev]"

seed:
	$(PYTHON) scripts/seed.py

ingest:
	$(PYTHON) scripts/ingest.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

clean:
	rm -f acr.db
