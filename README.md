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
  <b>Read the <a href="MANIFESTO.md">Manifesto</a></b> to understand the vision for democratizing financial research.
</p>

---

## Why Copinance OS?

Copinance OS treats **financial computation and research orchestration as first-class concerns**. Numbers, indicators, and regime logic live in a **deterministic domain layer** with explicit data contracts — not in prompt text. LLMs sit in an **explanation and question-driven layer**: they reason over tool outputs and narrative context, while prices, macro series, and filing-derived facts come from **providers and domain code** you can test and audit.

Deterministic narration is now literacy-tiered across instrument summaries, market-regime labels, macro interpretation labels, and report-envelope fallback copy. Provide `financial_literacy` (`beginner` / `intermediate` / `advanced`) via profile or run context; uncomputable metrics stay `null` (no legacy fallback synthesis).

<table align="center">
<tr>
  <td align="center" width="33%">
    <b>Deterministic domain</b><br>
    Strategies, indicators, and composable analysis pipelines — with predictable outputs for the same inputs.<br>
    Pydantic models at boundaries; no untyped DataFrames across modules.
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
    Broad macro dashboards (FRED-backed indicators) alongside equities, options (QuantLib BSM Greeks plus vanna/charm/volga where available), aggregate **positioning** (GEX, vanna/charm, mispricing, moneyness, pin risk), and fundamentals.<br>
    SEC EDGAR access via <a href="https://edgartools.readthedocs.io/">edgartools</a> for filings and LLM tool-calling over filing text when configured.
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

**Recommended (with make):**

```bash
git clone https://github.com/copinance/copinance-os.git
cd copinance-os
make setup
```

`make setup` creates a virtual environment, installs all dependencies, and sets up pre-commit hooks.

**Manual setup:**

```bash
git clone https://github.com/copinance/copinance-os.git
cd copinance-os
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Local LLM support (Ollama):**

```bash
pip install -e ".[ollama]"
```

**Verify install:** with `.venv` active, `copinance version` should print the package version.

### Configure an LLM

Question-driven analysis (`--question`, natural-language root) requires an LLM backend. Add one of the following to a `.env` file in the project root:

**Gemini (recommended):**
```bash
COPINANCEOS_LLM_PROVIDER=gemini
COPINANCEOS_GEMINI_API_KEY=your-key   # from https://aistudio.google.com
```

**OpenAI:**
```bash
COPINANCEOS_LLM_PROVIDER=openai
COPINANCEOS_OPENAI_API_KEY=sk-...
COPINANCEOS_OPENAI_MODEL=gpt-4o-mini
```

**Ollama (local):**
```bash
COPINANCEOS_LLM_PROVIDER=ollama
COPINANCEOS_OLLAMA_BASE_URL=http://localhost:11434
COPINANCEOS_OLLAMA_MODEL=llama3.2
```

Deterministic analysis (`copinance analyze equity AAPL`) runs without any LLM key.

### Using the CLI

The entry point after install is `copinance`. You can substitute `python -m copinance_os.interfaces.cli` from the repo root if you prefer not to install.

```bash
# Natural language question (question-driven; full tool suite)
copinance "How is Tesla doing financially?"

# Profile management
copinance profile create --literacy beginner --name "My Profile"
copinance profile list

# Deterministic analysis (no LLM key required)
copinance analyze equity AAPL --timeframe mid_term
copinance analyze options AAPL
# Multiple option expiries in one run (repeat -e per date)
copinance analyze options AAPL -e 2026-06-19 -e 2026-09-18

# Aggregate options surface (bias, IV/skew, gamma regime, GEX, vanna/charm, mispricing, pin risk, …)
copinance analyze positioning SPY --window near
copinance analyze --json positioning SPY -w near

# Question-driven analysis
copinance analyze equity AAPL --question "What are the key financial risks?"

# Macro / market regime
copinance analyze macro
copinance analyze macro --market-index QQQ --lookback-days 90

# Streaming question-driven output (tokens to stdout)
copinance analyze --stream equity AAPL --question "Explain the current trend"
copinance --stream "What is the VIX telling us?"
```

### Machine-readable output

Pass `--json` before a subcommand or question to get JSON to stdout — useful for scripts and CI:

```bash
copinance analyze --json equity AAPL --timeframe mid_term
copinance analyze --json positioning SPY -w near
copinance analyze --json macro --question "Risk-on or risk-off?"
copinance --json "Summarize labor and inflation"
copinance market --json quote AAPL
copinance market --json history AAPL --start 2026-01-01 --end 2026-03-14
copinance market --json options SPY
```

Analyze/export contract (stable top-level keys):

- `analyze --json ...` and root `copinance --json "..."` emit `RunJobResult` with `success`, `results`, `error_message`, `report`, and `report_exclusion_reason`.
- Deterministic results are also persisted under `.copinance/results/v2/` (when not using memory storage), with the same structured methodology envelope used in JSON output.
- `analyze positioning` emits the full aggregate `OptionsPositioningResult` under `results`, with uncomputable metrics preserved as `null` (no synthetic `0.0` fallback values).

### Shell completion

```bash
copinance --install-completion zsh   # or bash / fish
```

Open a new terminal after running the above. Tab completes subcommands and flags.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `copinance "…"` | Natural-language research question (question-driven; full tool suite) |
| `copinance analyze equity <SYMBOL>` | Equity analysis — deterministic or question-driven with `--question` |
| `copinance analyze options <SYMBOL>` | Options chain snapshot analysis; BSM Greeks via QuantLib when configured (first- and higher-order Greeks on contracts when inputs are valid); repeat `-e` / `--expiration` for multiple expiries. Single-expiry deterministic runs also include a **`positioning`** block (aggregate surface metrics). |
| `copinance analyze positioning <SYMBOL>` | Deterministic aggregate options positioning only (`--window` / `-w`: `near` or `mid`; default `near`); same payload shape as the instrument executor’s **`positioning`**. Missing inputs are surfaced as `null` (never synthesized as `0.0`), and empty/invalid positioning windows fail with a validation error rather than a silent empty payload. |
| `copinance analyze macro` | Macro + market regime dashboard |
| `copinance market search "…"` | Search instruments by name or symbol |
| `copinance market quote <SYMBOL>` | Current quote |
| `copinance market history <SYMBOL>` | Historical OHLCV |
| `copinance market options <SYMBOL>` | Options chain snapshot with Greeks; repeat `-e` for multiple expiries |
| `copinance market fundamentals <SYMBOL>` | Financial statements and ratios |
| `copinance profile create` | Create an analysis profile (sets literacy level) |
| `copinance cache info` / `clear` | Cache management |
| `copinance version` | Print version |

Common flags: `--json` (machine output), `--stream` (live token output), `--timeframe short_term|mid_term|long_term`, `--question "…"` (question-driven mode), `--profile-id <id>` (use a saved profile).

Full reference: [User Guide — CLI](https://copinance.github.io/copinance-os/user-guide/cli/)

---

## Multi-turn conversations (library)

Multi-turn question-driven analysis (follow-up questions with memory of prior answers) is supported through the library API. Pass `conversation_history` (`list[LLMConversationTurn]`) on `AnalyzeInstrumentRequest` or `AnalyzeMarketRequest`. Successful runs include `conversation_turns` in results for chaining.

The CLI is single-turn by design — one question per invocation. See the [library guide](https://copinance.github.io/copinance-os/getting-started/library#multi-turn-question-driven-analysis) for the full API.

---

## Development

### Setup

```bash
git clone https://github.com/copinance/copinance-os.git
cd copinance-os
make setup           # venv + deps + pre-commit hooks
source .venv/bin/activate
```

### Code quality

All three checks must pass before committing:

```bash
make quality         # black + ruff + mypy (all at once)
# or individually:
black src/ tests/
ruff check src/ tests/ --fix
mypy src/
```

Pre-commit hooks run `black` and `ruff` automatically on every edited `.py` file.

### Testing

```bash
make test            # full suite with coverage
pytest --no-cov      # fast loop without coverage
pytest -m unit       # unit tests only
pytest -m integration  # integration tests only
pytest --cov=copinance_os --cov-report=html  # explicit HTML report
```

### Make targets

| Target | Description |
|--------|-------------|
| `make setup` | Create venv, install deps, install pre-commit hooks |
| `make quality` | Run black + ruff + mypy |
| `make test` | Run full test suite with coverage |
| `make coverage` | Run tests and open HTML coverage report |
| `make check` | quality + test combined |
| `make docs-serve` | Start local Nextra docs server |
| `make clean` | Remove build artifacts and caches |

---

## Documentation

- **[Manifesto](MANIFESTO.md)** — Vision and philosophy
- **[Documentation site](https://copinance.github.io/copinance-os/)** — Introduction (home), then the sections below in sidebar order
  - **[Getting Started](https://copinance.github.io/copinance-os/getting-started/installation/)** — Installation, Quick Start, Configuration, Using as a Library
  - **[User Guide](https://copinance.github.io/copinance-os/user-guide/cli/)** — CLI Reference, Analysis Modes
  - **[Analysis Reference](https://copinance.github.io/copinance-os/analysis-reference/)** — Market Data Tools, Macro & Market Regime, Options & Greeks (BSM, higher-order Greeks, chain metadata, aggregate positioning), SEC Filings (EDGAR)
  - **[Examples](https://copinance.github.io/copinance-os/examples/)** — Equity Deep Dive, Macro Dashboard, Options Session
  - **[Developer Guide](https://copinance.github.io/copinance-os/developer-guide/architecture/)** — Architecture, Extending, Testing, [API Reference](https://copinance.github.io/copinance-os/developer-guide/api-reference/) (ports and extension interfaces)
- **[docs/README.md](docs/README.md)** — Build the docs site locally (Nextra)
- **[Library — Options positioning context](https://copinance.github.io/copinance-os/getting-started/library#options-positioning-context)** — Library integration notes for aggregate positioning and Greek enrichment (I/O contracts, pitfalls, tests)
- **[Developer Guide — Agent progress & chat integration (clients)](https://copinance.github.io/copinance-os/developer-guide/agent-progress-client-integration)** — LLM-facing integration guidance for progress events, payload grounding, methodology rendering, and UI patterns
- **[CONTRIBUTING.md](CONTRIBUTING.md)** · **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** · **[GOVERNANCE.md](GOVERNANCE.md)** · **[CHANGELOG.md](CHANGELOG.md)**

---

## Contributing

Contributions are welcome. Read the [Manifesto](MANIFESTO.md) for context, then [CONTRIBUTING.md](CONTRIBUTING.md) for workflow and standards.

- Report bugs and request features via [Issues](https://github.com/copinance/copinance-os/issues)
- Improve documentation (including the [docs site](https://copinance.github.io/copinance-os/) or this README)
- Submit pull requests against `main` following CONTRIBUTING

Community: [Code of Conduct](CODE_OF_CONDUCT.md) · [Governance](GOVERNANCE.md) · [Discussions](https://github.com/copinance/copinance-os/discussions)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

---

## Star history

[![Star History Chart](https://api.star-history.com/svg?repos=copinance/copinance-os&type=Timeline)](https://star-history.com/#copinance/copinance-os&Timeline)


## VHS

```bash
copinance profile create --literacy beginner --name "My Profile"
copinance analyze equity AAPL --timeframe mid_term
copinance analyze options AAPL
copinance analyze --stream equity AAPL --question "Explain the current trend"
copinance analyze macro
copinance "How is Tesla doing financially?"
```
