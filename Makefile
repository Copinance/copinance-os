.PHONY: help venv setup install install-dev test test-unit test-integration coverage lint format type-check clean clean-venv run docs

# Detect Python version and virtual environment
PYTHON := python3
VENV := venv
VENV_BIN := $(VENV)/bin

# Use venv tools if venv exists, otherwise use system tools
ifeq ($(wildcard $(VENV_BIN)/pip),)
	PIP := pip
	PYTHON_CMD := $(PYTHON)
	PRE_COMMIT := pre-commit
	PYTEST := pytest
	BLACK := black
	RUFF := ruff
	MYPY := mypy
else
	PIP := $(VENV_BIN)/pip
	PYTHON_CMD := $(VENV_BIN)/python
	PRE_COMMIT := $(VENV_BIN)/pre-commit
	PYTEST := $(VENV_BIN)/pytest
	BLACK := $(VENV_BIN)/black
	RUFF := $(VENV_BIN)/ruff
	MYPY := $(VENV_BIN)/mypy
endif

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

venv: ## Create a Python virtual environment
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created at $(VENV)"
	@echo ""
	@echo "Activate it with:"
	@echo "  source $(VENV_BIN)/activate"
	@echo ""
	@echo "Or on Windows:"
	@echo "  $(VENV_BIN)\\activate"

setup: venv ## Set up development environment (create venv and install dev dependencies)
	@echo "Installing development dependencies..."
	$(VENV_BIN)/pip install -e ".[dev]"
	$(VENV_BIN)/pre-commit install
	$(VENV_BIN)/pre-commit install --hook-type pre-push
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "Activate the virtual environment with:"
	@echo "  source $(VENV_BIN)/activate"
	@echo ""
	@echo "To build documentation, see docs/README.md"

install: ## Install package in production mode
	@if [ -d "$(VENV)" ]; then \
		$(VENV_BIN)/pip install -e .; \
	else \
		$(PIP) install -e .; \
	fi

install-dev: ## Install package in development mode with all dependencies
	@if [ -d "$(VENV)" ]; then \
		$(VENV_BIN)/pip install -e ".[dev]"; \
		$(VENV_BIN)/pre-commit install; \
	else \
		$(PIP) install -e ".[dev]"; \
		$(PRE_COMMIT) install; \
	fi

test: ## Run all tests
	$(PYTEST)

test-unit: ## Run unit tests only
	$(PYTEST) -m unit

test-integration: ## Run integration tests only
	$(PYTEST) -m integration

coverage: ## Run tests with coverage report
	$(PYTEST) --cov=copinance --cov-report=html --cov-report=term-missing

lint: ## Run linting checks
	$(RUFF) check src/ tests/ .pre-commit-hooks/

format: ## Format code with black
	$(BLACK) src/ tests/ .pre-commit-hooks/

format-check: ## Check code formatting without making changes
	$(BLACK) --check src/ tests/ .pre-commit-hooks/

type-check: ## Run type checking with mypy
	$(MYPY) src/

quality: lint type-check format-check ## Run all quality checks

fix: format ## Fix code formatting and auto-fixable linting issues
	$(RUFF) check src/ tests/ --fix

clean: ## Clean up generated files (keeps venv)
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-venv: ## Remove virtual environment
	rm -rf $(VENV)
	@echo "Virtual environment removed"

cli: ## Show CLI help
	copinance --help

docs: ## Build documentation with Nextra
	@echo "Building documentation with Nextra..."
	@cd docs && npm install && npm run build
	@echo "Documentation built in docs/out/"

docs-serve: ## Serve documentation locally with Nextra
	@echo "Starting Nextra development server..."
	@cd docs && npm install && npm run dev

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

check: quality test ## Run all checks (quality + tests)

version: ## Show package version
	@$(PYTHON_CMD) -c "from copinance import __version__; print(__version__)"
