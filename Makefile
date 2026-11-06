PY := .venv/bin/python
YEAR ?= 2024

.PHONY: setup download run test lint charts check

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

download:
	$(PY) src/download.py --year $(YEAR)

run:
	$(PY) src/pipeline.py --raw-glob "data/raw/311_$(YEAR)-*.csv"

charts:
	$(PY) src/charts.py

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/sqlfluff lint sql

check: lint test
