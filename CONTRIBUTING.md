# Contributing to Copinance OS

Thank you for your interest in contributing. This document covers workflow, standards, and extension patterns.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to maintainers@copinance-os.org.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/copinance-os.git`
3. Set up your environment: `make setup` (creates `.venv`, installs deps, and pre-commit hooks)
4. Create a branch: `git checkout -b feature/your-feature-name`

## Development Workflow

### Environment

```bash
make setup        # one-step: venv + deps + pre-commit
source .venv/bin/activate
```

Or manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

### Code quality

All three checks must pass before committing:

```bash
make quality      # black + ruff + mypy (all at once)
```

Or individually:
```bash
black src/ tests/
ruff check src/ tests/ --fix
mypy src/
```

Pre-commit hooks run `black` and `ruff` automatically on every edited `.py` file.

### Testing

```bash
make test           # full suite with coverage
pytest --no-cov     # fast loop without coverage
pytest -m unit
pytest -m integration
make coverage       # test + open HTML report
```

### Commit messages

Follow conventional commit format:

```
feat: add sentiment analysis tool
fix: correct market search case sensitivity
docs: update CLI reference
test: add tests for analyze use case
refactor: simplify repository interface
chore: bump dependency versions
```

A commit message template is available in [`.gitmessage`](.gitmessage).

## Architecture guidelines

### Layer responsibilities

| Layer | Path | Responsibility |
|-------|------|----------------|
| **Domain** | `domain/` | Entities, value objects, ports (interfaces), domain services. No I/O. |
| **Research** | `research/workflows/` | Use cases (analyze, market, profile, fundamentals, backtest). Thin — delegate to orchestrator. |
| **Data** | `data/` | Providers, cache, repositories, analytics adapters. Implements domain ports. |
| **Core** | `core/` | Orchestrator (`ResearchOrchestrator`, `DefaultJobRunner`), execution engine, pipeline tools. |
| **AI** | `ai/` | LLM provider adapters, streaming, prompt templates. Explanation/summarization — not numerical truth. |
| **Infra** | `infra/` | Settings, logging, DI composition root (`infra/di/`). The only place all layers are imported together. |
| **Interfaces** | `interfaces/cli/` | CLI entry (`main`, `dispatch`, lazy Typer `root`, `commands/`). Maps user input to use cases and the container. |

Key rules:
- `domain/` imports nothing from this project except other domain modules
- `infra/di/` is the composition root — the only place all layers are wired together; no business logic here
- `core/` must not import `research/`; workflow request types that executors need belong in `domain/models/`

### Adding a new feature

1. **Domain**: Define entities and ports if needed
2. **Research use cases**: Add or extend modules in `research/workflows/`
3. **Data / core / ai**: Implement adapters, executors, or LLM wiring as appropriate
4. **Interfaces**: Add CLI commands if needed
5. **Tests**: Mirror package layout under `tests/unit/copinance_os/`
6. **Documentation**: Update relevant docs in `docs/pages/` and docstrings; for cross-cutting integrator notes (e.g. options positioning I/O), add or extend Markdown under **`docs/integration/`** and link from the root **README** if end-users need it

## Pull request process

PRs should be atomic — one change or feature per PR. Use the [pull request template](.github/pull_request_template.md).

### Checklist

- [ ] `make quality` passes (black + ruff + mypy)
- [ ] `make test` passes (or `pytest -m unit` at minimum)
- [ ] Tests added or updated for the change
- [ ] Documentation updated (docs/pages/, docstrings, README if applicable)
- [ ] CHANGELOG updated for significant changes
- [ ] Commit messages follow conventional format

## Adding analysis executors

Executors implement the `AnalysisExecutor` port and run inside `DefaultJobRunner`:

```python
from copinance_os.domain.ports.analysis_execution import AnalysisExecutor
from copinance_os.domain.models.job import Job

class MyAnalysisExecutor(AnalysisExecutor):
    async def execute(self, job: Job, context: dict) -> dict:
        # Implementation
        pass

    async def validate(self, job: Job) -> bool:
        return job.execution_type == "my_executor"

    def get_executor_id(self) -> str:
        return "my_executor"
```

Register by extending `AnalysisExecutorFactory.create_all` in `copinance_os.core.execution_engine.factory`, or override `container.analysis_executors` in a custom container. Use `execution_type_from_scope_and_mode(scope, mode)` from `copinance_os.domain.models.analysis` when building jobs.

## Adding tools

Tools wrap data providers or standalone logic for use by LLMs in question-driven analysis:

1. Implement the `Tool` interface from `domain/ports/tools.py`
2. Add tests
3. Wire through a bundle factory and `PluginSpec` in `core.pipeline.tools.discovery`, or add a `tool_bundle_factory` in `core.pipeline.tools.bundles` for package scan

### Data provider tools

Extend `BaseDataProviderTool` for tools that wrap a provider:

```python
from copinance_os.core.pipeline.tools.data_provider.base import BaseDataProviderTool
from copinance_os.domain.ports.data_providers import MarketDataProvider
from copinance_os.domain.ports.tools import ToolResult, ToolSchema
from typing import Any

class MyDataProviderTool(BaseDataProviderTool[MarketDataProvider]):
    def get_name(self) -> str:
        return "get_custom_data"

    def get_description(self) -> str:
        return "Get custom data for a given symbol."

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["symbol"],
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        validated = self.validate_parameters(**kwargs)
        data = await self._provider.get_custom_data(validated["symbol"])
        return self._create_success_result(data=data, metadata={"symbol": validated["symbol"]})
```

### Standalone tools

Implement `Tool` directly for tools that don't wrap a provider:

```python
from copinance_os.domain.ports.tools import Tool, ToolResult, ToolSchema
from typing import Any

class MyStandaloneTool(Tool):
    def get_name(self) -> str:
        return "my_custom_tool"

    def get_description(self) -> str:
        return "Perform a custom operation."

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {"input": {"type": "string", "description": "Input parameter"}},
                "required": ["input"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        validated = self.validate_parameters(**kwargs)
        result = self._perform_operation(validated["input"])
        return ToolResult(success=True, data=result)
```

## Adding data providers

See [Developer Guide — Extending](https://copinance.github.io/copinance-os/developer-guide/extending) for step-by-step instructions including the `domain/ports/` interface selection, container registration, and test patterns.

## Questions?

- Open an [issue](https://github.com/copinance/copinance-os/issues) for architecture or design questions
- Check existing issues and PRs for similar work
- [Discussions](https://github.com/copinance/copinance-os/discussions) for open-ended conversation
