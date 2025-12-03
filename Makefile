.PHONY: install dev test lint format type-check security clean build publish help sync lock

help:
	@echo "AgentSH Development Commands"
	@echo "============================"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install package in development mode"
	@echo "  make dev         Install with all development dependencies"
	@echo "  make sync        Sync dependencies from lock file"
	@echo "  make lock        Update lock file"
	@echo ""
	@echo "Testing:"
	@echo "  make test        Run all tests"
	@echo "  make test-unit   Run unit tests only"
	@echo "  make test-cov    Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        Run linters (ruff)"
	@echo "  make format      Auto-format code (black)"
	@echo "  make type-check  Run type checker (mypy)"
	@echo "  make security    Run security checks (bandit)"
	@echo "  make check       Run all checks (lint, type, security)"
	@echo ""
	@echo "Build:"
	@echo "  make build       Build distribution packages"
	@echo "  make clean       Remove build artifacts"
	@echo "  make publish     Publish to PyPI (requires credentials)"

# Installation with uv
install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev,all]"
	uv run pre-commit install || true

sync:
	uv sync

lock:
	uv lock

# Testing
test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-cov:
	uv run pytest tests/ --cov=src/agentsh --cov-report=term-missing --cov-report=html

# Code Quality
lint:
	uv run ruff check src tests

format:
	uv run black src tests
	uv run ruff check --fix src tests

type-check:
	uv run mypy src/agentsh --ignore-missing-imports

security:
	uv run bandit -r src/agentsh -ll

check: lint type-check security

# Build
build: clean
	uv build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .venv/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

publish: build
	uv publish

# Development helpers
run:
	uv run agentsh

config-show:
	uv run agentsh config show

status:
	uv run agentsh status
