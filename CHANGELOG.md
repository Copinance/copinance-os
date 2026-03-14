# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Strategy

**Note:** This project is currently in active development with frequent architectural changes and improvements. As such, no package releases will be made until the project reaches a mature and stable state. All changes are tracked in the `[Unreleased]` section below. Once the project stabilizes, versioned releases will begin following Semantic Versioning.

## [Unreleased]

### Added

- `DefaultJobRunner` in `run_job.py`: default implementation of `JobRunner` that resolves a workflow executor for each job, builds profile context, and executes; consumers can replace with custom (e.g. queue-based) runners.
- Market instrument use cases: `GetInstrumentUseCase`, `SearchInstrumentsUseCase` (with `InstrumentSearchMode`: auto, symbol, general), plus use cases for market quote, historical data, and options chain.
- `market` CLI group with `search`, `quote`, `history`, and `options` subcommands for instrument lookup and market data (replaces stock-specific CLI).
- Market domain models: `MarketType`, `OptionSide`, `MarketDataPoint`, `OptionContract`, `OptionsChain` in `domain/models/market.py`.
- Persistence module (`infrastructure/persistence.py`): `PERSISTENCE_SCHEMA_VERSION = "v2"` and path helpers `get_persistence_root`, `get_data_dir`, `get_cache_dir`, `get_results_dir`, `get_state_dir` for versioned storage; cache, profile state, file storage, and workflow results use these paths.
- Unit and integration tests for market use cases, run job, market CLI, market search, and workflow instrument handling.

### Changed

- CLI now exposes `analyze` and `ask` commands instead of `research`; profile and workflow execution wired through default job runner and job model (consumers can replace the runner for custom orchestration).
- Job execution centralized in `DefaultJobRunner`; dedicated workflow use case removed.
- Stock-centric flows replaced by market/instrument-centric: instrument search and data access via `market` use cases and `market` CLI; `StockRepository` used as instrument cache where applicable.
- Cache manager, local file cache, profile current state, and file storage use persistence schema v2 and shared persistence path helpers.
- Static and agentic workflow implementations updated for instrument/market handling and job runner integration; analyze/ask/cache CLI and docs aligned accordingly.
- Updated developer guide, user guide, and tools documentation to describe workflow-based analysis and current CLI usage.
- Enhanced CONTRIBUTING.md with commit message template reference, pull request template guidance, and comprehensive "Adding New Tools" section.
- Rewrote MANIFESTO.md for improved clarity, structure, and messaging around the project's mission and vision.
- Updated README.md section headers to remove emoji formatting for consistency.
- Updated market regime detection documentation to include comprehensive guide for Market Regime Indicators Tool.
- Added `pandas-stubs` to dev dependencies so mypy can type-check pandas usage in market regime tools (fixes CI type-check failures).
- yfinance provider: type fixes for mypy (optional-import block, `datetime` conversion for `MarketDataPoint` timestamp, and `DataFrame` return type); added `pandas-stubs` to pre-commit mypy hook.

### Removed

- `research` CLI command and research subcommands (replaced by `analyze` and `ask`).
- Research use case, domain models, and research repository (superseded by job runner, Job model, and workflow executors).
- Stock use case and `stock` CLI (replaced by market use cases and `market` CLI with search, quote, history, options).
- Workflow use case (replaced by `DefaultJobRunner` in `run_job.py`).
- Dedicated tests for stock use case, workflow use case, stock CLI, stock search integration, and static workflow (superseded by market/run_job/workflow tests).
- `analyze` CLI command for running predefined analysis workflows (e.g. fundamentals, macro regime).
- `ask` CLI command for agentic analysis with custom questions and dynamic tool use.
- `Job` domain model and `JobRunner` port; profile context support for passing the current research profile into workflow execution.
- `LLMConfig` dataclass for programmatic LLM configuration (provider, API keys, model, temperature, etc.) and `load_llm_config_from_env()` helper for CLI use.
- Hexagonal architecture with 21+ extension interfaces for data providers, analyzers, strategies, and workflows.
- Research status tracking (pending, in_progress, completed, failed); static and agentic workflow executors; fundamentals workflow; research profile management with financial literacy levels.
- yfinance integration for market data and fundamentals; SEC EDGAR integration; multiple LLM provider support (Gemini, Ollama); market and fundamental data tools; intelligent caching; CLI (analyze, ask, profile, market, cache); documentation and tests.
- Market regime detection tools (trend, volatility, Wyckoff cycle, regime indicators) and comprehensive macro economic indicators (47+ across 9 categories) with FRED and yfinance fallbacks.
