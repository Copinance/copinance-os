"""Config-driven simple long-only backtest runs (YAML / JSON).

Use these loaders for reproducible research runs (rule: strategies configurable via YAML/JSON).
Interactive/API inline payloads remain valid; file-based configs are the preferred path for
checked-in or shared research definitions.

Supported file shapes:

- **Flat mapping** — keys match ``SimpleLongOnlyWorkflowRequest`` (same as HTTP JSON body).
- **Wrapped** — ``{ "schema_version": "1", "run": { ... same fields ... } }`` for versioning
  and future metadata at the document root.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType
from typing import Any

from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.domain.backtest import SimpleBacktestResult
from copinance_os.research.workflows.backtest import SimpleLongOnlyWorkflowRequest

_yaml: ModuleType | None = None
try:
    import yaml as _yaml_mod

    _yaml = _yaml_mod
except ImportError:
    pass

_SIMPLE_LONG_ONLY_SCHEMA_V1 = "1"


def _normalize_simple_long_only_root(data: Any) -> dict[str, Any]:
    """Return the mapping to validate as ``SimpleLongOnlyWorkflowRequest``."""
    if data is None:
        raise ValueError("Config document is empty")
    if not isinstance(data, dict):
        raise ValueError("Config root must be a JSON object or YAML mapping")
    if "run" in data:
        inner = data["run"]
        if not isinstance(inner, dict):
            raise ValueError("'run' must be a mapping when present")
        ver = data.get("schema_version")
        if ver is not None and str(ver) != _SIMPLE_LONG_ONLY_SCHEMA_V1:
            raise ValueError(
                f"Unsupported schema_version {ver!r}; supported: {_SIMPLE_LONG_ONLY_SCHEMA_V1!r}"
            )
        return inner
    return data


def parse_simple_long_only_workflow_mapping(data: Any) -> SimpleLongOnlyWorkflowRequest:
    """Parse a decoded JSON/YAML object into ``SimpleLongOnlyWorkflowRequest``."""
    return SimpleLongOnlyWorkflowRequest.model_validate(_normalize_simple_long_only_root(data))


def parse_simple_long_only_workflow_json(text: str) -> SimpleLongOnlyWorkflowRequest:
    """Parse a JSON string (flat or wrapped with ``run``)."""
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    return parse_simple_long_only_workflow_mapping(raw)


def parse_simple_long_only_workflow_yaml(text: str) -> SimpleLongOnlyWorkflowRequest:
    """Parse a YAML string (flat or wrapped with ``run``). Requires PyYAML."""
    if _yaml is None:
        raise ImportError("YAML configs require PyYAML. Install with: pip install pyyaml")
    raw: Any = _yaml.safe_load(text)
    return parse_simple_long_only_workflow_mapping(raw)


def load_simple_long_only_workflow_request(path: Path | str) -> SimpleLongOnlyWorkflowRequest:
    """Load and validate a ``.json``, ``.yaml``, or ``.yml`` research backtest config file."""
    p = Path(path)
    suffix = p.suffix.lower()
    raw = p.read_text(encoding="utf-8")
    if suffix == ".json":
        return parse_simple_long_only_workflow_json(raw)
    if suffix in (".yaml", ".yml"):
        return parse_simple_long_only_workflow_yaml(raw)
    raise ValueError(f"Unsupported config extension {suffix!r}; use .json, .yaml, or .yml ({p})")


def run_simple_long_only_from_config_file(
    path: Path | str,
    *,
    orchestrator: ResearchOrchestrator,
) -> SimpleBacktestResult:
    """Load a YAML/JSON config and run the backtest through the orchestrator."""
    req = load_simple_long_only_workflow_request(path)
    return orchestrator.run_simple_long_only_backtest(req)
