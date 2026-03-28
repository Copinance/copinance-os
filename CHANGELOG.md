# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Strategy

**Note:** This project is currently in active development with frequent architectural changes and improvements. As such, no package releases will be made until the project reaches a mature and stable state. All changes are tracked in the `[Unreleased]` section below. Once the project stabilizes, versioned releases will begin following Semantic Versioning.

## [Unreleased]

### Added

- **SEC / EDGAR**: **`edgartools`** dependency and **`EdgarToolsFundamentalProvider`** in `copinance_os.data.providers.sec.edgartools`; DI **`sec_filings_provider`** for question-driven agent tools (`get_sec_filings`, `get_sec_filing_content`). SEC identity via **`EDGAR_IDENTITY`** / **`COPINANCEOS_EDGAR_IDENTITY`** (defaults in settings). **Cache** integration with per-entry TTL via `CacheManager` to limit EDGAR traffic.
- **Container/DI**: Optional `storage_type` and `storage_path` on `get_container()` for library integrators; pass `storage_type="memory"` to avoid creating a `.copinance` directory on disk without using `COPINANCEOS_STORAGE_TYPE`. Unit tests for container storage overrides.
- **Market search**: `EXCHANGE_DISPLAY_NAMES` and `format_exchange()` for human-readable market names (e.g. NMS → NASDAQ, NYQ → NYSE); "Market" column in search results; `longName`, `shortName`, and `exch_disp` from yfinance in results.
- **Container/DI**: Lazy container proxy so no container is created at import time; first `get_container()` or attribute access wins. Unit tests for container cache configuration.
- Integration executor test: question context passed so run reaches LLM check.
- `.gitignore`: `.cursor/` and normalize trailing newline.
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

- **README**: Centered hero (logo, title, subtitle, HTML badge row), bold tagline, and new **Why Copinance OS?** section with a value-proposition table (deterministic domain, AI explanation layer, orchestration, macro-to-micro scope, literacy-aware output, library + CLI); Manifesto link and horizontal rules preserved before **Features**.
- **Documentation & metadata**: Package description (`pyproject.toml`) and `copinance_os` module docstring aligned with README and docs: “market analysis” and “question-driven AI” (replacing “market research” / “agent AI” in those metadata strings). Extension point count raised to **23** and `OptionsChainGreeksEstimator` documented in architecture and extending guides; README architecture tree and MANIFESTO updated to match.
- **CLI / user guide**: Root `copinance --help` `market` summary aligned with the `market` Typer app (“options (BSM Greeks via QuantLib)”); `market options --expiration` Typer help aligned with the user guide default wording. CLI reference table (`market`, `cache`) and macro `--timeframe` default (`mid_term`) clarified.
- **Contributing**: `pip install -e ".[dev]"` only — removed nonexistent `.[dev,docs]` extra from the setup example.
- **Yahoo options:** Default `--expiration` now picks the earliest listed expiry **on or after today** (not raw `ticker.options[0]`), avoiding expired front months and missing BSM Greeks the day after expiry.
- **BSM / QuantLib:** Treat expiry **strictly before** evaluation as expired (`maturity < eval`); allow **same calendar day** as 0DTE. With normalized IV (see below), Greeks can compute for live expiries.
- **Yahoo options / BSM:** Normalize option-chain `impliedVolatility` when value is **> 1** (treat as percent points → divide by 100) so QuantLib BSM Greeks match σ as a fraction; fixes `-` Greeks when Yahoo returns values like `13.67` for ~13.7% vol.
- **CLI — `market options`:** Always shows Delta/Gamma/Theta/Vega/Rho columns by default (cells `-` when Greeks are not computed); `--no-greeks` hides them. Expanded help text and short flags for expiration/side. Docs (user guide, README, library API, options chain metadata) updated for BSM Greeks and `COPINANCEOS_OPTION_GREEKS_*` settings.
- **Documentation**: Aligned docs with current behavior and conventions: virtualenv is `.venv` (README, installation, CONTRIBUTING); README extension interfaces match architecture (LLM analyzer, data providers, strategies, repositories); CLI reference notes fast startup for `copinance --help` and `copinance version` (lazy subcommands); installation states that `make setup` creates `.venv`.
- **Documentation**: Library guide Storage and Persistence section now clarifies that `.copinance` is created by storage (repositories), not by cache; documents `storage_type="memory"` and env alternative; configuration and library API reference updated for storage options.
- **Market search**: Cache hits that are all "stub" instruments (e.g. bad symbol "APPLE") are treated as empty so the provider is queried and can return real results (e.g. AAPL). When symbol lookup fails, fall back to provider name search (yfinance Search) so queries like "APPLE" resolve to AAPL.
- **Container/DI**: `cache_enabled` and `cache_manager` overrides are applied when returning an existing container, so library callers (e.g. `get_container(cache_enabled=False)`) are no longer ignored.
- Replaced workflow system with executor-based analysis: instrument, market, and question-driven executors; job execution centralized in `DefaultJobRunner`.
- Analyze and market CLIs extended with new options; profile and execution wired through job runner and Job model.
- Stock-centric flows replaced by market/instrument-centric: instrument search and data access via `market` use cases and `market` CLI.
- Cache manager, local file cache, profile state, and file storage use persistence schema v2 and shared path helpers.
- Containers, config, and tests updated for executor-based architecture; developer guide, user guide, and tools docs describe analysis modes and CLI usage.
- Enhanced CONTRIBUTING.md with commit message template, pull request guidance, and "Adding New Tools" section.
- MANIFESTO.md, README.md, and market regime documentation updated; `pandas-stubs` and yfinance type fixes for mypy/CI.
