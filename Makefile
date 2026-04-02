.PHONY: help venv setup install install-dev test test-unit test-integration coverage lint format format-check type-check quality clean clean-cache clean-cache-data clean-venv clean-docs cli docs docs-serve pre-commit check version zip-config

ESC := \033
RESET := $(ESC)[0m
BOLD := $(ESC)[1m
BLUE := $(ESC)[34m
GREEN := $(ESC)[32m
YELLOW := $(ESC)[33m
CYAN := $(ESC)[36m

SETUP_TARGETS := venv setup install install-dev
QUALITY_TARGETS := lint format format-check type-check quality pre-commit
TEST_TARGETS := test test-unit test-integration coverage check
DOCS_TARGETS := docs docs-serve
UTILITY_TARGETS := cli version zip-config
CLEAN_TARGETS := clean clean-cache clean-cache-data clean-venv clean-docs

# Detect Python version and virtual environment
PYTHON := python3
VENV := .venv
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
	@printf "$(BOLD)Usage:$(RESET) make [target]\n\n"
	@printf "$(BOLD)Available targets:$(RESET)\n\n"
	@print_group() { \
		title="$$1"; \
		shift; \
		printf "$(BOLD)%s$(RESET)\n" "$$title"; \
		for target in "$$@"; do \
			desc=$$(awk -F':.*?## ' -v target="$$target" '$$1 == target { print $$2 }' $(MAKEFILE_LIST)); \
			printf "  $(CYAN)%-20s$(RESET) %s\n" "$$target" "$$desc"; \
		done; \
		printf "\n"; \
	}; \
	print_group "Setup" $(SETUP_TARGETS); \
	print_group "Quality" $(QUALITY_TARGETS); \
	print_group "Testing" $(TEST_TARGETS); \
	print_group "Docs" $(DOCS_TARGETS); \
	print_group "Utilities" $(UTILITY_TARGETS); \
	print_group "Cleanup" $(CLEAN_TARGETS)

venv: ## Create a Python virtual environment; then run: . .venv/bin/activate
	@printf "$(BLUE)Creating virtual environment...$(RESET)\n"
	$(PYTHON) -m venv $(VENV)
	@printf "$(GREEN)Virtual environment created at $(VENV)$(RESET)\n\n"
	@printf "$(BOLD)Enable it in your shell (copy-paste):$(RESET)\n"
	@printf "  $(CYAN). $(VENV_BIN)/activate$(RESET)\n\n"
	@printf "$(BOLD)Or from any directory:$(RESET)\n"
	@printf "  $(CYAN)cd $(CURDIR) && . $(VENV_BIN)/activate$(RESET)\n\n"
	@printf "$(BOLD)On Windows:$(RESET)\n"
	@printf "  $(CYAN)$(VENV_BIN)\\\\activate$(RESET)\n"
	@$(VENV_BIN)/python --version

setup: venv ## Set up development environment (create venv and install dev dependencies)
	@printf "$(BLUE)Installing development dependencies...$(RESET)\n"
	$(VENV_BIN)/pip install -e ".[dev]"
	$(VENV_BIN)/pre-commit install
	$(VENV_BIN)/pre-commit install --hook-type pre-push
	@printf "\n$(GREEN)Setup complete!$(RESET)\n\n"
	@printf "$(BOLD)Activate the virtual environment with:$(RESET)\n"
	@printf "  $(CYAN)source $(VENV_BIN)/activate$(RESET)\n\n"
	@printf "$(YELLOW)To build documentation, see docs/README.md$(RESET)\n"

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
	$(PYTEST) --cov=copinance_os --cov-report=html --cov-report=term-missing
	@echo "" && echo "Coverage report: file://$(CURDIR)/htmlcov/index.html"

test-unit: ## Run unit tests only
	$(PYTEST) -m unit --cov=copinance_os --cov-report=html --cov-report=term-missing
	@echo "" && echo "Coverage report: file://$(CURDIR)/htmlcov/index.html"

test-integration: ## Run integration tests only
	$(PYTEST) -m integration --cov=copinance_os --cov-report=html --cov-report=term-missing
	@echo "" && echo "Coverage report: file://$(CURDIR)/htmlcov/index.html"

coverage: ## Run tests with coverage report
	$(PYTEST) --cov=copinance_os --cov-report=html --cov-report=term-missing
	@echo "" && echo "Coverage report: file://$(CURDIR)/htmlcov/index.html"

lint: ## Run linting checks
	@if [ -d "$(VENV)" ] && [ ! -x "$(VENV_BIN)/ruff" ]; then \
		printf "$(YELLOW)Dev tools not installed in $(VENV).$(RESET)\n"; \
		printf "Run: $(CYAN)make setup$(RESET)\n"; \
		exit 1; \
	fi
	$(RUFF) check src/ tests/ .pre-commit-hooks/ --fix

format: ## Format code with black
	@if [ -d "$(VENV)" ] && [ ! -x "$(VENV_BIN)/black" ]; then \
		printf "$(YELLOW)Dev tools not installed in $(VENV).$(RESET)\n"; \
		printf "Run: $(CYAN)make setup$(RESET)\n"; \
		exit 1; \
	fi
	$(BLACK) src/ tests/ .pre-commit-hooks/

format-check: ## Check code formatting without making changes
	@if [ -d "$(VENV)" ] && [ ! -x "$(VENV_BIN)/black" ]; then \
		printf "$(YELLOW)Dev tools not installed in $(VENV).$(RESET)\n"; \
		printf "Run: $(CYAN)make setup$(RESET)\n"; \
		exit 1; \
	fi
	$(BLACK) --check src/ tests/ .pre-commit-hooks/

type-check: ## Run type checking with mypy
	@if [ -d "$(VENV)" ] && [ ! -x "$(VENV_BIN)/mypy" ]; then \
		printf "$(YELLOW)Dev tools not installed in $(VENV).$(RESET)\n"; \
		printf "Run: $(CYAN)make setup$(RESET)\n"; \
		exit 1; \
	fi
	$(MYPY) src/

quality: format lint type-check format-check ## Run all quality checks

clean: clean-cache ## Clean up generated files (keeps venv)
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf htmlcov/
	find . -type d -name "*.egg-info" -exec rm -rf {} +

clean-cache: ## Remove Python and tool cache files
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-cache-data: ## Remove local CLI cached data
	rm -rf "$${COPINANCEOS_STORAGE_PATH:-.copinance}"

clean-venv: ## Remove virtual environment
	rm -rf $(VENV)
	@printf "$(YELLOW)Virtual environment removed$(RESET)\n"

cli: ## Show CLI help
	copinance --help

docs: ## Build documentation with Nextra
	@printf "$(BLUE)Building documentation with Nextra...$(RESET)\n"
	@cd docs && npm install && npm run build
	@printf "$(GREEN)Documentation built in docs/out/$(RESET)\n"

docs-serve: ## Serve documentation locally with Nextra
	@printf "$(BLUE)Starting Nextra development server...$(RESET)\n"
	@cd docs && npm install && npm run dev

clean-docs: ## Remove generated docs build files and dependencies
	rm -rf docs/.next
	rm -rf docs/out
	rm -rf docs/node_modules
	@printf "$(YELLOW)Documentation build artifacts removed$(RESET)\n"

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

check: format quality test ## Run all checks (quality + tests)

version: ## Show package version
	@$(PYTHON_CMD) -c "from copinance import __version__; print(__version__)"

zip-config: ## Zip .claude, .cursor, and CLAUDE.md into timestamped archive
	@test -d .claude || (printf "$(YELLOW)Missing .claude/$(RESET)\n"; exit 1)
	@test -d .cursor || (printf "$(YELLOW)Missing .cursor/$(RESET)\n"; exit 1)
	@test -f CLAUDE.md || (printf "$(YELLOW)Missing CLAUDE.md$(RESET)\n"; exit 1)
	@out="copinance-os-claude-cursor-$$(date +%Y%m%d-%H%M%S).zip"; \
	zip -r "$$out" .claude .cursor CLAUDE.md -x "*.DS_Store" && \
	printf "$(GREEN)Created:$(RESET) %s/%s\n" "$(CURDIR)" "$$out"
