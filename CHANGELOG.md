# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Strategy

**Note:** This project is currently in active development with frequent architectural changes and improvements. As such, no package releases will be made until the project reaches a mature and stable state. All changes are tracked in the `[Unreleased]` section below. Once the project stabilizes, versioned releases will begin following Semantic Versioning.

## [Unreleased]

### Added

- **Executor-based analysis architecture**: `AnalysisExecutor` port with instrument, market, and question-driven executors; `JobRunner` for job execution (replaces workflow-based orchestration).
- **Analyze use case**: modes (auto, deterministic, question_driven) and scope-based routing; `DefaultJobRunner` in `run_job.py` resolves an executor per job, builds profile context, and runs analysis.
- **AnalysisProfile**: renamed from ResearchProfile; regime models moved to `domain/models/regime` (macro, market_regime).
- Documentation for analysis modes and library usage; updated CLI and configuration docs.
- Market instrument use cases: `GetInstrumentUseCase`, `SearchInstrumentsUseCase` (with `InstrumentSearchMode`: auto, symbol, general), plus use cases for market quote, historical data, and options chain.
- `market` CLI group with `search`, `quote`, `history`, and `options` subcommands for instrument lookup and market data.
- Market domain models: `MarketType`, `OptionSide`, `MarketDataPoint`, `OptionContract`, `OptionsChain` in `domain/models/market.py`.
- Persistence module (`infrastructure/persistence.py`): `PERSISTENCE_SCHEMA_VERSION = "v2"` and path helpers for versioned storage; cache, profile state, file storage, and analysis results use these paths.
- Unit and integration tests for market use cases, run job, market CLI, executors, and analyze use case.

### Changed

- Replaced workflow system with executor-based analysis: instrument, market, and question-driven executors; job execution centralized in `DefaultJobRunner`.
- Analyze and market CLIs extended with new options; profile and execution wired through job runner and Job model.
- Stock-centric flows replaced by market/instrument-centric: instrument search and data access via `market` use cases and `market` CLI.
- Cache manager, local file cache, profile state, and file storage use persistence schema v2 and shared path helpers.
- Containers, config, and tests updated for executor-based architecture; developer guide, user guide, and tools docs describe analysis modes and CLI usage.
- Enhanced CONTRIBUTING.md with commit message template, pull request guidance, and "Adding New Tools" section.
- MANIFESTO.md, README.md, and market regime documentation updated; `pandas-stubs` and yfinance type fixes for mypy/CI.

### Removed

- **Workflow system**: agentic, static, macro_regime, and base workflows; workflow executor factory (replaced by analysis executors and JobRunner).
- **Ask CLI**: removed; question-driven analysis available via `analyze` with question-driven mode.
- `research` CLI and research subcommands (replaced by `analyze` and market flows).
- Research use case, domain models, and research repository (superseded by job runner, Job model, and analysis executors).
- Stock use case and `stock` CLI (replaced by market use cases and `market` CLI).
- Workflow use case and dedicated workflow/stock tests (superseded by executor and analyze use case tests).
