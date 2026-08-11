.PHONY: test test-cov lint format typecheck security healthcheck sync generate-short dashboard clean lock all

test:
	pytest -q

test-cov:
	pytest -q --cov --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format . && ruff check --fix .

typecheck:
	mypy utils/ scripts/ upload_youtube.py generate_pata_jazz_short.py generate_site.py

security:
	bandit -r utils/ scripts/ *.py -ll -q && pip-audit -r requirements.lock

healthcheck:
	python scripts/healthcheck.py

sync:
	python scripts/sync_animal_broll.py && python scripts/sync_jazz_music.py

generate-short:
	python generate_pata_jazz_short.py

dashboard:
	python scripts/generate_dashboard.py

lock:
	pip-compile --strip-extras --output-file=requirements.lock pyproject.toml requirements-dev.txt

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

all: lint test typecheck
