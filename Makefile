PY := .venv/bin/python
YEAR ?= 2024

.PHONY: setup download reference run test lint charts site audit check

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

download:
	$(PY) src/download.py --year $(YEAR)

reference:          # small ZIP-level reference table (committed); only needed if data/reference is missing
	$(PY) src/download_reference.py

run:
	$(PY) src/pipeline.py --raw-glob "data/raw/311_$(YEAR)-*.csv"

charts:
	$(PY) src/charts.py

site:               # build docs/index.html, the one-page decision write-up, from outputs/tables
	$(PY) src/build_site.py

audit:
	$(PY) scripts/audit_headlines.py

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/sqlfluff lint sql

check: lint test
