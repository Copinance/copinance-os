# Copinance OS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)
[![CI](https://github.com/copinance/copinance-os/actions/workflows/ci.yml/badge.svg)](https://github.com/copinance/copinance-os/actions/workflows/ci.yml)
[![Docs](https://github.com/copinance/copinance-os/actions/workflows/docs.yml/badge.svg)](https://github.com/copinance/copinance-os/actions/workflows/docs.yml)

Open-source stock research platform and framework with agentic AI and static workflows.

**Read [Manifesto](MANIFESTO.md)** to understand our vision for democratizing financial research.

## Features

- **Adaptive Presentation**: Results can be tailored to financial literacy level (beginner, intermediate, advanced)
- **Dual Workflow Support**: Both static analysis pipelines and agentic AI workflows
- **Extensible Framework**: Easy to add new research strategies and data sources
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
│   ├── models/          # Entities: ResearchProfile, Stock, Research
│   └── ports/           # 21 interfaces for extensibility
├── application/         # Use cases and services
│   └── use_cases/       # Business operations
├── infrastructure/      # Implementations
│   ├── repositories/    # Data persistence (in-memory included)
│   ├── workflows/       # Research executors
│   ├── containers/      # Dependency injection containers
│   └── config.py        # Configuration
└── cli/                 # CLI implementation (modular)
```

**Extension Interfaces Ready:**
- Data Provider interfaces (market, alternative, fundamental, macro)
- Analyzer interfaces (NLP, LLM, vision, quant, graph, portfolio)
- Strategy interfaces (screening, due diligence, valuation, risk, thematic, monitoring)
- Core interfaces (repositories, workflows)

See [Architecture](docs/developer-guide/architecture.md) for details.

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
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
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
python -m copinanceos.cli research create AAPL --workflow static
python -m copinanceos.cli profile list
python -m copinanceos.cli stock search "Apple"
```

**After installation:**
```bash
pip install -e .
copinance research create AAPL --timeframe mid_term --workflow static
copinance research execute <research-id>
copinance research get <research-id>
```

**Examples:**
```bash
# Profile management
python -m copinanceos.cli profile create --literacy intermediate --name "My Profile"
python -m copinanceos.cli profile list
python -m copinanceos.cli profile get <profile-id>

# Stock search
python -m copinanceos.cli stock search "Apple"

# Research with context
python -m copinanceos.cli research create AAPL --profile-id <profile-id>
python -m copinanceos.cli research run AAPL --workflow static
python -m copinanceos.cli research set-context <research-id> --profile-id <profile-id>
```

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
pytest --cov=copinance --cov-report=html
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

- **[Manifesto](MANIFESTO.md)** - Our vision and philosophy
- **[Documentation](https://copinance.github.io/copinance-os/)** - Complete documentation (hosted on GitHub Pages)
  - [Getting Started](https://copinance.github.io/copinance-os/getting-started/installation/) - Installation and quick start
  - [User Guide](https://copinance.github.io/copinance-os/user-guide/cli/) - CLI reference and workflows
  - [Developer Guide](https://copinance.github.io/copinance-os/developer-guide/architecture/) - Architecture and extending
  - [API Reference](https://copinance.github.io/copinance-os/api-reference/data-providers/) - Interfaces and APIs
- **[Contributing](CONTRIBUTING.md)** - How to contribute
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community standards
- **[Governance](GOVERNANCE.md)** - How we make decisions
- **[Changelog](CHANGELOG.md)** - Development history

## Core Concepts

### Research Profiles

Copinance OS uses `ResearchProfile` to provide context for research execution. This is **NOT a user management system** - your application handles authentication and users, we handle research context.

**Why?** Integration flexibility. Map your users to research profiles however you want.

### Financial Literacy Adaptation

Results automatically adapt to financial literacy level:
- **Beginner**: Simple explanations, basic metrics, educational
- **Intermediate**: Detailed analysis, common indicators
- **Advanced**: Comprehensive analysis, advanced metrics, technical

When running research commands, the system will prompt you to set your financial literacy level if you don't have a profile, ensuring personalized analysis from the start.

### Workflow Types

- **Static**: Predefined analysis pipeline
- **Agentic**: AI-powered dynamic analysis

## Integration

Copinance OS is designed as a **pure library** that integrates into any Python application:

- **No built-in API endpoints** - add your own with FastAPI, Flask, Django, etc.
- **No frontend** - build your own or integrate with existing apps
- **Flexible persistence** - use in-memory, PostgreSQL, MongoDB, or any database
- **Framework agnostic** - works with any Python web framework or application

See [Getting Started](docs/getting-started/quickstart.md) for detailed integration guides.

## Contributing

We welcome contributions! Read our [Manifesto](MANIFESTO.md) to understand our philosophy, then see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to Contribute:**
- 🐛 Report bugs and issues
- 💡 Propose new features
- 📝 Improve documentation
- 🔧 Submit pull requests
- ⭐ Star the repository
- 💬 Join discussions

**Community Guidelines:**
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Code of Conduct](CODE_OF_CONDUCT.md) - Our standards for community behavior
- [Governance](GOVERNANCE.md) - How we make decisions

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

## Support

GitHub Issues: [Report bugs or request features](https://github.com/copinance/copinance-os/issues)
