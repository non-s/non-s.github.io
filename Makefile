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
	mypy generate_liquid_wire_video.py upload_youtube.py scripts/healthcheck.py scripts/remaster_procedural_audio.py scripts/run_liquid_wire_live.py scripts/generate_site.py utils/channel_config.py utils/content_funnel.py utils/liquid_wire_composer.py utils/liquid_wire_quality.py utils/liquid_wire_timeline.py utils/paths.py utils/playlist_manager.py utils/youtube_oauth.py

security:
	bandit -r generate_liquid_wire_video.py upload_youtube.py scripts/healthcheck.py scripts/remaster_procedural_audio.py scripts/run_liquid_wire_live.py scripts/generate_site.py utils/channel_config.py utils/content_funnel.py utils/liquid_wire_composer.py utils/liquid_wire_quality.py utils/liquid_wire_timeline.py utils/paths.py utils/playlist_manager.py utils/youtube_oauth.py -ll -q && pip-audit -r requirements.txt

healthcheck:
	python scripts/healthcheck.py

generate-short:
	python generate_liquid_wire_video.py --preset short

dashboard:
	python scripts/generate_dashboard.py

lock:
	pip-compile --strip-extras --output-file=requirements.lock pyproject.toml

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

all: lint test typecheck
