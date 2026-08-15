.PHONY: install test verify scan simulate adversarial docker-build docker-verify lint clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=agenticarb --cov-report=term-missing

verify:
	python -m agenticarb.cli verify

scan:
	python -m agenticarb.cli scan

simulate:
	python -m agenticarb.cli simulate --hours 168 --adversarial --verbose

adversarial:
	python -m agenticarb.cli adversarial --repeats 2

docker-build:
	docker compose build

docker-verify:
	docker compose run --rm agenticarb

lint:
	ruff check src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
