<p align="center">
  <a href="https://github.com/copinance/copinance-os">
    <img src="docs/images/copinance-os-logo.png" alt="Copinance OS logo" height="80">
  </a>
</p>

<h1 align="center">Copinance OS</h1>
<h3 align="center">Open-source market analysis platform and financial research operating system</h3>

<p align="center">
  <a href="https://www.apache.org/licenses/LICENSE-2.0"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black"></a>
  <a href="CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg" alt="Contributor Covenant"></a>
  <a href="https://github.com/copinance/copinance-os/actions/workflows/ci.yml"><img src="https://github.com/copinance/copinance-os/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/copinance/copinance-os/actions/workflows/docs.yml"><img src="https://github.com/copinance/copinance-os/actions/workflows/docs.yml/badge.svg" alt="Docs"></a>
</p>

<p align="center">
  <b>Question-driven AI, deterministic instrument and market analysis, and macro research — as a composable Python library with a rich CLI.</b>
</p>

**Read [Manifesto](MANIFESTO.md)** to understand my vision for democratizing financial research.

---

## Why Copinance OS?

Copinance OS treats **financial computation and research orchestration as first-class concerns**. Numbers, indicators, and regime logic live in a **deterministic domain layer** with explicit data contracts — not in prompt text. LLMs sit in an **explanation and question-driven layer**: they reason over tool outputs and narrative context, while prices, macro series, and filing-derived facts come from **providers and domain code** you can test and audit.

<table align="center">
<tr>
  <td align="center" width="33%">
    <b>Deterministic domain</b><br>
    Pure strategies, indicators, and portfolio logic — composable pipelines with predictable outputs for the same inputs.<br>
    Pydantic models at boundaries; avoid passing untyped DataFrames across modules.
  </td>
  <td align="center" width="33%">
    <b>AI that explains, not invents</b><br>
    Question-driven analysis grounded in tools and structured results.<br>
    LLMs summarize and explore; they do not replace pricing, risk math, or data ingestion.
  </td>
  <td align="center" width="33%">
    <b>Orchestrated research</b><br>
    Workflows run through a research orchestrator — task decomposition, ordering, and clear extension points.<br>
    Swap runners, providers, and storage without rewriting the core.
  </td>
</tr>
<tr>
  <td align="center" width="33%">
    <b>Macro to micro</b><br>
    Broad macro dashboards (e.g. FRED-backed indicators) alongside equities, options (QuantLib), and fundamentals.<br>
    SEC EDGAR access via <a href="https://edgartools.readthedocs.io/">edgartools</a> for filings and text-aware agent tools.
  </td>
  <td align="center" width="33%">
    <b>Audience-aware output</b><br>
    Analysis profiles adapt depth and language to financial literacy (beginner → advanced).<br>
    Same engine; presentation tuned to who is reading.
  </td>
  <td align="center" width="33%">
    <b>Library + CLI</b><br>
    Hexagonal layout: use as a Python library in your app or ship analysis via the Typer/Rich CLI.<br>
    Apache 2.0 — integrate, extend, and contribute without vendor lock-in.
  </td>
</tr>
</table>

---

## Features

- **Adaptive Presentation**: Results can be tailored to financial literacy level (beginner, intermediate, advanced)
- **Dual Analysis Modes**: Deterministic instrument/market analysis and AI-powered question-driven analysis
- **Comprehensive Macro Analysis**: 47+ economic indicators across 9 categories (rates, credit, labor, housing, manufacturing, consumer, global, advanced)
- **Extensible Framework**: Easy to add new analysis strategies and data sources
- **Data Provider Integration**: yfinance (market & fundamentals), FRED (macro), **SEC EDGAR via [edgartools](https://edgartools.readthedocs.io/)** (filings & filing text for agent tools), plus pluggable providers
- **Multiple LLM Providers**: Support for Gemini and Ollama (local LLMs) with extensible provider architecture
- **Intelligent Caching**: Built-in caching system to reduce API calls and improve performance
- **Pure Library**: Framework-agnostic, integrate into any Python application
- **CLI Interface**: Rich command-line interface for direct usage
- **Clean Architecture**: Hexagonal architecture with clear separation of concerns
- **Fully Tested**: Comprehensive test coverage with pytest

## Architecture

Copinance OS is a **pure Python library** following clean hexagonal architecture:

```
copinance_os/
├── domain/                 # Entities, validation, strategy protocols (deterministic core)
│   ├── models/             # Pydantic entities (Job, Stock, market data, …)
│   ├── ports/              # Interfaces (data providers, repositories, tools, …)
│   └── strategies/         # ABCs for pluggable strategies (screening, valuation, …)
├── research/workflows/   # Application workflows (market, analyze, profile, fundamentals)
├── core/                   # Orchestration and execution
│   ├── orchestrator/       # ResearchOrchestrator, DefaultJobRunner, analyze runners
│   ├── execution_engine/   # Analysis executors
│   └── pipeline/tools/     # Tool registry and LLM-callable tools
├── data/                   # Data layer (providers, cache, repositories, analytics, schemas)
├── ai/llm/                 # LLM providers and analyzers (explanation layer)
├── infra/                  # Config, logging, DI container wiring, factories
└── interfaces/cli/         # Typer CLI
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
python -m copinance_os.interfaces.cli version
```

### Using the CLI

**Without installation (from project root):**
```bash
# Run directly as a module
python3 -m copinance_os.interfaces.cli analyze equity AAPL --timeframe mid_term
python -m copinance_os.interfaces.cli profile list
python3 -m copinance_os.interfaces.cli market search "Apple"
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
python -m copinance_os.interfaces.cli profile create --literacy intermediate --name "My Profile"
python -m copinance_os.interfaces.cli profile list
python -m copinance_os.interfaces.cli profile get <profile-id>

# Instrument search
python3 -m copinance_os.interfaces.cli market search "Apple"
python3 -m copinance_os.interfaces.cli market quote AAPL
python3 -m copinance_os.interfaces.cli market history AAPL --start 2026-01-01 --end 2026-03-14

# Options chain with BSM Greek columns (QuantLib; use --no-cache if Greeks are missing from cache)
copinance market options SPY
copinance market options AAPL -e 2026-06-19 --no-cache

# One-off analysis (results saved to .copinance/results/v2/)
python3 -m copinance_os.interfaces.cli analyze equity AAPL --timeframe mid_term
python3 -m copinance_os.interfaces.cli analyze equity AAPL --question "What are the key risks?"
python3 -m copinance_os.interfaces.cli analyze options AAPL --expiration 2026-06-19

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
pytest --cov=copinance_os --cov-report=html
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

From the container (`get_container(...)` from `copinance_os.infra.di`), you get:

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
| **Research orchestration** | `research_orchestrator()` | Run jobs (`run_job`) and workflows; inject a custom `JobRunner` via `ResearchOrchestrator` if needed |
| **Override points** | `analyze_instrument_runner()`, `analyze_market_runner()` | Replace with your own executor (see library docs) |

Request/response types live in `copinance_os.research.workflows.market`, `copinance_os.research.workflows.analyze`, `copinance_os.research.workflows.fundamentals`, and `copinance_os.research.workflows.profile`. The [Library API Reference](https://copinance.github.io/copinance-os/getting-started/library#library-api-reference) lists every request field and module path.

**Quick usage:**

1. **Install** in your project: `pip install copinance-os` (or `pip install -e .` from source).
2. **Configure the container:** pass `LLMConfig` for question-driven analysis; optionally `fred_api_key` for macro. See [Configuration](https://copinance.github.io/copinance-os/getting-started/configuration).
3. **Use cases (no jobs):** `uc = container.get_quote_use_case()` then `await uc.execute(GetQuoteRequest(symbol="AAPL"))`. The same pattern applies to search, historical data, options chain, fundamentals, and progressive analyze — see the library doc for all request types.
4. **Or run analysis via the orchestrator:** `orch = container.research_orchestrator()`, build a `Job`, then `await orch.run_job(job, {})`. Use `result.success`, `result.results`, `result.error_message`.

```python
import asyncio
from copinance_os.ai.llm.config import LLMConfig
from copinance_os.infra.di import get_container
from copinance_os.domain.models.job import Job, JobScope, JobTimeframe
from copinance_os.domain.models.market import MarketType

async def main():
    container = get_container(
        llm_config=LLMConfig(provider="gemini", api_key="your-api-key", model="gemini-1.5-pro"),
        fred_api_key="your-fred-api-key",  # optional
    )
    orchestrator = container.research_orchestrator()
    job = Job(
        scope=JobScope.INSTRUMENT,
        market_type=MarketType.EQUITY,
        instrument_symbol="AAPL",
        timeframe=JobTimeframe.MID_TERM,
        execution_type="deterministic_instrument_analysis",
    )
    result = await orchestrator.run_job(job, {})
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

## Star history

[![Star history chart](https://api.star-history.com/svg?repos=copinance/copinance-os&type=Timeline)](https://star-history.com/#copinance/copinance-os&Timeline)

## Support

GitHub Issues: [Report bugs or request features](https://github.com/copinance/copinance-os/issues)
