# Copinance OS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)
[![CI](https://github.com/copinance/copinance-os/actions/workflows/ci.yml/badge.svg)](https://github.com/copinance/copinance-os/actions/workflows/ci.yml)
[![Docs](https://github.com/copinance/copinance-os/actions/workflows/docs.yml/badge.svg)](https://github.com/copinance/copinance-os/actions/workflows/docs.yml)

Open-source market analysis platform and framework with question-driven AI and deterministic instrument/market analysis.

**Read [Manifesto](MANIFESTO.md)** to understand my vision for democratizing financial research.

## Features

- **Adaptive Presentation**: Results can be tailored to financial literacy level (beginner, intermediate, advanced)
- **Dual Analysis Modes**: Deterministic instrument/market analysis and AI-powered question-driven analysis
- **Comprehensive Macro Analysis**: 47+ economic indicators across 9 categories (rates, credit, labor, housing, manufacturing, consumer, global, advanced)
- **Extensible Framework**: Easy to add new analysis strategies and data sources
- **Data Provider Integration**: Built-in yfinance and SEC EDGAR support + easy custom provider integration
- **Multiple LLM Providers**: Support for Gemini and Ollama (local LLMs) with extensible provider architecture
- **Intelligent Caching**: Built-in caching system to reduce API calls and improve performance
- **Pure Library**: Framework-agnostic, integrate into any Python application
- **CLI Interface**: Rich command-line interface for direct usage
- **Clean Architecture**: Hexagonal architecture with clear separation of concerns
- **Fully Tested**: Comprehensive test coverage with pytest

## Architecture

Copinance OS is a **pure Python library** following clean hexagonal architecture:

```
copinanceos/
├── domain/              # Core business logic (no dependencies)
│   ├── models/          # Entities: AnalysisProfile, Stock; Job (analysis execution context)
│   └── ports/           # 22 interfaces for extensibility
├── application/         # Use cases, default job runner (replaceable)
│   ├── use_cases/       # Business operations
│   └── run_job.py       # DefaultJobRunner (optional; implement JobRunner for custom orchestration)
├── infrastructure/      # Implementations
│   ├── repositories/    # Data persistence (in-memory included)
│   ├── executors/       # Analysis executors (deterministic and question-driven)
│   ├── containers/      # Dependency injection containers
│   └── config.py        # Configuration
└── cli/                 # CLI implementation (modular)
```

**Extension interfaces:** See [Architecture](https://copinance.github.io/copinance-os/developer-guide/architecture) for the full list. Key extension points:
- Data provider interfaces (market, fundamental, macro, alternative)
- LLM analyzer interface (Gemini, Ollama; plug in other providers)
- Strategy interfaces (screening, due diligence, valuation, risk, thematic, monitoring)
- Repositories, JobRunner, AnalysisExecutor, storage

See [Architecture](https://copinance.github.io/copinance-os/developer-guide/architecture) for details.

## Quick Start

### Prerequisites

- Python 3.11 or higher
- `make` (recommended for easiest setup)

### Installation

**Quick Setup (Recommended):**
```bash
git clone https://github.com/copinance/copinance-os.git
cd copinance-os
make setup
```

This will:
- Create a virtual environment
- Install all dependencies
- Set up pre-commit hooks

**Manual Setup (if you don't have make):**
```bash
git clone https://github.com/copinance/copinance-os.git
cd copinance-os
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Optional Dependencies:**
```bash
# For local LLM support (Ollama)
pip install -e ".[ollama]"

# Or install all optional dependencies
pip install -e ".[dev,ollama]"
```

**No Installation Needed:**
You can run the CLI directly without installing:
```bash
python -m copinanceos.cli version
```

### Using the CLI

**Without installation (from project root):**
```bash
# Run directly as a module
python3 -m copinanceos.cli analyze equity AAPL --timeframe mid_term
python -m copinanceos.cli profile list
python3 -m copinanceos.cli market search "Apple"
```

**After installation:**
```bash
pip install -e .
copinance analyze equity AAPL --timeframe mid_term
copinance profile list
copinance cache info
```

**Examples:**
```bash
# Profile management
python -m copinanceos.cli profile create --literacy intermediate --name "My Profile"
python -m copinanceos.cli profile list
python -m copinanceos.cli profile get <profile-id>

# Instrument search
python3 -m copinanceos.cli market search "Apple"
python3 -m copinanceos.cli market quote AAPL
python3 -m copinanceos.cli market history AAPL --start 2026-01-01 --end 2026-03-14

# Options chain with BSM Greek columns (QuantLib; use --no-cache if Greeks are missing from cache)
copinance market options SPY
copinance market options AAPL -e 2026-06-19 --no-cache

# One-off analysis (results saved to .copinance/results/v2/)
python3 -m copinanceos.cli analyze equity AAPL --timeframe mid_term
python3 -m copinanceos.cli analyze equity AAPL --question "What are the key risks?"
python3 -m copinanceos.cli analyze options AAPL --expiration 2026-06-19

# Question-driven analysis (AI uses the relevant market and fundamentals tools)
copinance analyze options AAPL --question "What's the put/call open interest?" --expiration 2026-06-19
copinance analyze macro --question "Is this a risk-on or risk-off environment?"

# Macro regime analysis (comprehensive economic indicators)
copinance analyze macro
copinance analyze macro --market-index QQQ --lookback-days 180
copinance analyze macro --include-labor --include-housing --include-consumer
copinance analyze macro --no-include-vix --no-include-market-breadth
```

For a complete CLI reference (all commands and options), see [User Guide - CLI](https://copinance.github.io/copinance-os/user-guide/cli).

## Testing

Run all tests:
```bash
pytest
```

Run specific test categories:
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# With coverage report
pytest --cov=copinanceos --cov-report=html
```

## Development

### Code Quality

Format code with black:
```bash
black src/ tests/
```

Lint with ruff:
```bash
ruff check src/ tests/
```

Type checking with mypy:
```bash
mypy src/
```

### Pre-commit Hooks

Install pre-commit hooks:
```bash
pre-commit install
```

Run manually:
```bash
pre-commit run --all-files
```

## Documentation

- **[Manifesto](MANIFESTO.md)** - My vision and philosophy
- **[Documentation](https://copinance.github.io/copinance-os/)** - Complete documentation (hosted on GitHub Pages)
  - [Getting Started](https://copinance.github.io/copinance-os/getting-started/installation/) — Installation, Quick Start, Configuration, Using as a Library
  - [Library API Reference](https://copinance.github.io/copinance-os/getting-started/library#library-api-reference) — Container methods, request/response types, module paths
  - [User Guide](https://copinance.github.io/copinance-os/user-guide/cli/) — CLI reference and analysis modes
  - [Tools](https://copinance.github.io/copinance-os/tools/) — Analysis tools (regime, macro) and data-provider tools
  - [Developer Guide](https://copinance.github.io/copinance-os/developer-guide/architecture/) — Architecture, extending, testing
  - [API Reference](https://copinance.github.io/copinance-os/api-reference/) — Data provider and extension interfaces
- **[Documentation Setup](docs/README.md)** - Local development setup for documentation
- **[Contributing](CONTRIBUTING.md)** - How to contribute
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community standards
- **[Governance](GOVERNANCE.md)** - How we make decisions
- **[Changelog](CHANGELOG.md)** - Development history

## Core Concepts

### Analysis Profiles

Copinance OS uses `AnalysisProfile` to provide context for analysis execution. This is **NOT a user management system** - your application handles authentication and users, we handle analysis context.

**Why?** Integration flexibility. Map your users to analysis profiles however you want.

### Financial Literacy Adaptation

Results automatically adapt to financial literacy level:
- **Beginner**: Simple explanations, basic metrics, educational
- **Intermediate**: Detailed analysis, common indicators
- **Advanced**: Comprehensive analysis, advanced metrics, technical

When running analyze commands, the system will prompt you to set your financial literacy level if you don't have a profile, ensuring personalized analysis from the start.

### Analysis Types

- **Deterministic**: Predefined analysis pipeline (instrument or market)
- **Question-driven**: AI-powered dynamic analysis

## Integration

Copinance OS is designed as a **pure library** that integrates into any Python application:

- **No built-in API endpoints** — add your own with FastAPI, Flask, Django, etc.
- **No frontend** — build your own or integrate with existing apps
- **Flexible persistence** — use in-memory, file, or plug in your own storage
- **Framework agnostic** — works with any Python web framework or application

### Using as a Library

**Full guide and API reference:** [Using Copinance OS as a Library](https://copinance.github.io/copinance-os/getting-started/library) — installation, configuration, **all container entry points**, **request/response types for every use case**, and examples.

### Library capabilities (what you can call)

From the container (`get_container(...)` from `copinanceos.infrastructure.containers`), you get:

| Category | Entry point | Purpose |
|----------|-------------|---------|
| **Market data** | `search_instruments_use_case()` | Search by name or symbol |
| | `get_instrument_use_case()` | Get cached instrument by symbol |
| | `get_quote_use_case()` | Current quote for a symbol |
| | `get_historical_data_use_case()` | OHLCV history for symbol and date range |
| | `get_options_chain_use_case()` | Options chain for an underlying |
| **Analyze** | `analyze_instrument_use_case()` | Progressive instrument analysis (deterministic or question-driven) |
| | `analyze_market_use_case()` | Progressive market analysis (deterministic or question-driven) |
| **Profiles** | `create_profile_use_case()`, `get_profile_use_case()`, `list_profiles_use_case()` | Create, get, list profiles |
| | `get_current_profile_use_case()`, `set_current_profile_use_case()`, `delete_profile_use_case()` | Current profile and delete |
| **Fundamentals** | `get_stock_fundamentals_use_case()` | Fundamentals for a symbol |
| **Job execution** | `job_runner()` | Run a `Job`; override for queues/custom orchestration |
| **Override points** | `analyze_instrument_runner()`, `analyze_market_runner()` | Replace with your own executor (see library docs) |

Request/response types live in `copinanceos.application.use_cases.market`, `copinanceos.application.use_cases.analyze`, `copinanceos.application.use_cases.fundamentals`, and `copinanceos.application.use_cases.profile`. The [Library API Reference](https://copinance.github.io/copinance-os/getting-started/library#library-api-reference) lists every request field and module path.

**Quick usage:**

1. **Install** in your project: `pip install copinance-os` (or `pip install -e .` from source).
2. **Configure the container:** pass `LLMConfig` for question-driven analysis; optionally `fred_api_key` for macro. See [Configuration](https://copinance.github.io/copinance-os/getting-started/configuration).
3. **Use cases (no jobs):** `uc = container.get_quote_use_case()` then `await uc.execute(GetQuoteRequest(symbol="AAPL"))`. The same pattern applies to search, historical data, options chain, fundamentals, and progressive analyze — see the library doc for all request types.
4. **Or run analysis via jobs:** `runner = container.job_runner()`, build a `Job`, then `await runner.run(job, {})`. Use `result.success`, `result.results`, `result.error_message`.

```python
import asyncio
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.containers import get_container
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType

async def main():
    container = get_container(
        llm_config=LLMConfig(provider="gemini", api_key="your-api-key", model="gemini-1.5-pro"),
        fred_api_key="your-fred-api-key",  # optional
    )
    runner = container.job_runner()
    job = Job(
        scope=JobScope.INSTRUMENT,
        market_type=MarketType.EQUITY,
        instrument_symbol="AAPL",
        timeframe=JobTimeframe.MID_TERM,
        execution_type="deterministic_instrument_analysis",
    )
    result = await runner.run(job, {})
    # result.success, result.results, result.error_message

asyncio.run(main())
```

See also: [Configuration](https://copinance.github.io/copinance-os/getting-started/configuration) (LLM/FRED, security), [API Reference](https://copinance.github.io/copinance-os/api-reference/data-providers) (interfaces), [Quick Start](https://copinance.github.io/copinance-os/getting-started/quickstart) (CLI).

## Contributing

We welcome contributions! Read my [Manifesto](MANIFESTO.md) to understand my philosophy, then see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to Contribute:**
- 🐛 Report bugs and issues
- 💡 Propose new features
- 📝 Improve documentation
- 🔧 Submit pull requests
- ⭐ Star the repository
- 💬 Join discussions

**Community Guidelines:**
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Code of Conduct](CODE_OF_CONDUCT.md) - My standards for community behavior
- [Governance](GOVERNANCE.md) - How we make decisions

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

## Support

GitHub Issues: [Report bugs or request features](https://github.com/copinance/copinance-os/issues)
