<p align="center">
  <a href="https://github.com/copinance/copinance-os">
    <img src="docs/images/copinance-os-logo.png" alt="Copinance OS logo" height="60">
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

![](docs/images/copinance-os.gif)

<p align="center">
  <b>Read <a href="MANIFESTO.md">Manifesto</a></b> to understand my vision for democratizing financial research.
</p>



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

**Verify install:** with `.venv` active, `copinance version` should print the package version.

### Using the CLI

After `**pip install -e .` (or `make setup`), the entry point is `copinance`. You can substitute `python -m copinance_os.interfaces.cli` anywhere below if you prefer the module form.

```bash
# Profile
copinance profile create --literacy beginner --name "My Profile"
copinance profile list

# Natural language (question-driven; not a subcommand)
copinance "How is Tesla doing financially?"

# Analysis (deterministic runs save results under .copinance/results/v2/)
copinance analyze equity AAPL --timeframe mid_term
copinance analyze options AAPL

# Macro research
copinance analyze --stream macro --question "Is credit leading equities?"
```

### More CLI features

Full CLI command reference: [User Guide - CLI](https://copinance.github.io/copinance-os/user-guide/cli/).

**Machine-readable output:** put `**--json`** on the `**analyze**` or `**market**` group before the subcommand, or `**--json**` before a natural-language question—stdout is JSON only (no Rich tables). `analyze --json` emits `**RunJobResult**`; `market --json` emits a command envelope (`command` plus payload).

```bash
copinance analyze --json equity AAPL --timeframe mid_term
copinance analyze --json macro --market-index SPY
copinance --json "Summarize labor and inflation"
copinance market --json quote AAPL
copinance market --json history AAPL --start 2026-01-01 --end 2026-03-14
```

**Shell completion (Tab):** The CLI is built with **Typer**; install shell integration so Tab can complete subcommands and flags. Activate your venv first (`source .venv/bin/activate`) so `**copinance`** is on `**PATH**`, then run one of:

```bash
copinance --install-completion bash
copinance --install-completion zsh   # default login shell on macOS; use this if bash completion never runs
copinance --install-completion fish
```

Follow the instructions Typer prints (usually adding a `source …` line to `**~/.bashrc**`, `**~/.zshrc**`, or the path shown for fish). Open a **new terminal** afterward. Completion works by **re-invoking `copinance`**; if the venv is not active, Tab will not find the command. It completes **commands and options** (e.g. `analyze`, `market`, `--json`); it does **not** complete arbitrary text for `**copinance "…"`** natural-language questions.

**Multi-turn question-driven analysis** (follow-up questions with memory of prior answers) is supported through `**AnalyzeInstrumentRequest` / `AnalyzeMarketRequest`** (`conversation_history` + new `question`), not via CLI flags. Successful runs include `**conversation_turns**` in `results` for chaining. See the [library guide](https://copinance.github.io/copinance-os/getting-started/library#multi-turn-question-driven-analysis).

Full flag reference: [User Guide - CLI](https://copinance.github.io/copinance-os/user-guide/cli/).

## Testing

The default `pytest` invocation includes **coverage** (see `pyproject.toml` `addopts`). For a faster loop without coverage:

```bash
pytest --no-cov
```

Run all tests with project defaults:

```bash
pytest
```

Run specific test categories:

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Explicit HTML coverage report (also produced by default unless --no-cov)
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

- **[Manifesto](MANIFESTO.md)** — Vision and philosophy
- **[Documentation site](https://copinance.github.io/copinance-os/)** — Full docs (GitHub Pages)
  - [Getting Started](https://copinance.github.io/copinance-os/getting-started/installation/) — Installation, Quick Start, Configuration, Library
  - [Library API Reference](https://copinance.github.io/copinance-os/getting-started/library#library-api-reference) — Container methods, request/response types, module paths
  - [User Guide](https://copinance.github.io/copinance-os/user-guide/cli/) — CLI and analysis modes
  - [Tools](https://copinance.github.io/copinance-os/tools/) — Regime and macro tools, data-provider tools
  - [Analytics](https://copinance.github.io/copinance-os/analytics/) — BSM/Greeks (QuantLib), options chain metadata
  - [Developer Guide](https://copinance.github.io/copinance-os/developer-guide/architecture/) — Architecture, extending, testing
  - [API Reference](https://copinance.github.io/copinance-os/api-reference/) — Data provider and extension interfaces
- **[docs/README.md](docs/README.md)** — Build the docs site locally (Nextra)
- **[CONTRIBUTING.md](CONTRIBUTING.md)** · **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** · **[GOVERNANCE.md](GOVERNANCE.md)** · **[CHANGELOG.md](CHANGELOG.md)**


## Contributing

Contributions are welcome. Read the [Manifesto](MANIFESTO.md) for context, then [CONTRIBUTING.md](CONTRIBUTING.md) for workflow and standards.

- Report bugs and request features via [Issues](https://github.com/copinance/copinance-os/issues)
- Improve documentation (including the [docs site](https://copinance.github.io/copinance-os/) or this README)
- Submit pull requests against `main` following CONTRIBUTING

Community: [Code of Conduct](CODE_OF_CONDUCT.md), [Governance](GOVERNANCE.md)

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

## Star history

[Star history chart](https://star-history.com/#copinance/copinance-os&Timeline)

## Support

GitHub Issues: [Report bugs or request features](https://github.com/copinance/copinance-os/issues)


## VHS

```bash

```
