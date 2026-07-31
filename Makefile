.PHONY: test lint validate-demo run-demo validate-release run-public-dev summarize-public-dev sanitize-public-results

test:
	uv run pytest

lint:
	uv run ruff check .

validate-demo:
	uv run medphys-bench validate tasks/dev/physics_units_001/task.yaml

run-demo:
	uv run medphys-bench demo tasks/dev/physics_units_001/task.yaml

validate-release:
	uv run medphys-bench validate-release releases/public_dev_2026_07_31.yaml

run-public-dev:
	uv run medphys-bench run-release releases/public_dev_2026_07_31.yaml --adapter ollama --model qwen3.5:4b --results-dir runs

summarize-public-dev:
	uv run medphys-bench summarize releases/public_dev_2026_07_31.yaml --results-dir results/releases --output results/releases/public-dev-2026-07-31/leaderboard.json
	cp results/releases/public-dev-2026-07-31/leaderboard.json web/public/data/leaderboard.json

sanitize-public-results:
	uv run python scripts/sanitize_public_results.py results/releases/public-dev-2026-07-31

web:
	cd web && npm run build
