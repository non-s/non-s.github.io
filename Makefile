.PHONY: test test-cov lint format typecheck security healthcheck generate-short dashboard clean lock all

test:
	pytest -q

test-cov:
	pytest -q --cov --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format . && ruff check --fix .

typecheck:
	mypy generate_liquid_wire_video.py upload_youtube.py scripts/ utils/

security:
	bandit -r generate_liquid_wire_video.py upload_youtube.py scripts/ utils/ -ll -q && pip-audit -r requirements.txt

healthcheck:
	python scripts/healthcheck.py

generate-short:
	python generate_liquid_wire_video.py --preset short

dashboard:
	python scripts/generate_dashboard.py

lock:
	pip-compile --strip-extras --output-file=requirements.lock pyproject.toml

clean:
ifeq ($(OS),Windows_NT)
	powershell -NoProfile -Command "Get-ChildItem -Path . -Recurse -Force -Directory -Filter __pycache__ | Remove-Item -Recurse -Force; Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .pytest_cache,.ruff_cache,.mypy_cache,.coverage,htmlcov"
else
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
endif

all: lint test typecheck security
