.PHONY: test lint coverage docs docs-dev agent-test i18n-tools i18n-extract i18n-check i18n-compile

ACORN_VERSION = 8.18.0

test:
	pytest -q

lint:
	ruff check app.py core tests

coverage:
	pytest -q --cov=core --cov=app --cov-report=term-missing

docs:
	npm run docs:build

docs-dev:
	npm run docs:dev

agent-test:
	cd agent && go build ./... && go vet ./... && go test ./...

i18n-tools:
	npm install --prefix scripts/i18n --no-save --ignore-scripts --no-audit --no-fund acorn@$(ACORN_VERSION)

i18n-extract:
	python scripts/i18n/extract.py

i18n-check:
	python scripts/i18n/check.py --require-tools

i18n-compile:
	pybabel compile -d locale -D messages --statistics
