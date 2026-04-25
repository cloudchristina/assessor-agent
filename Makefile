.PHONY: install lint type test test-unit test-integration fmt clean

install:
	uv pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src tests
	ruff format --check src tests

fmt:
	ruff check --fix src tests
	ruff format src tests

type:
	pyright

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

test: test-unit test-integration

clean:
	rm -rf .pytest_cache .ruff_cache .coverage build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
