"""YAML/JSON-driven simple long-only backtest configs."""

from pathlib import Path

import pytest

from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.research.workflows.backtest_config import (
    load_simple_long_only_workflow_request,
    parse_simple_long_only_workflow_json,
    parse_simple_long_only_workflow_mapping,
    parse_simple_long_only_workflow_yaml,
    run_simple_long_only_from_config_file,
)


@pytest.mark.unit
def test_parse_flat_mapping() -> None:
    req = parse_simple_long_only_workflow_mapping(
        {
            "strategy_id": "s",
            "closes": [100.0, 110.0],
            "weights": [1.0, 1.0],
            "initial_cash": 1000.0,
        }
    )
    assert req.strategy_id == "s"
    assert req.closes == [100.0, 110.0]


@pytest.mark.unit
def test_parse_wrapped_with_schema_version(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text(
        """
schema_version: "1"
run:
  strategy_id: demo
  closes: [100.0, 110.0, 121.0]
  weights: [1.0, 1.0, 1.0]
  initial_cash: 1000.0
""",
        encoding="utf-8",
    )
    req = load_simple_long_only_workflow_request(p)
    assert req.strategy_id == "demo"
    assert len(req.closes) == 3


@pytest.mark.unit
def test_unsupported_schema_version() -> None:
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        parse_simple_long_only_workflow_mapping(
            {"schema_version": "99", "run": {"closes": [1.0, 2.0], "weights": [1.0, 1.0]}}
        )


@pytest.mark.unit
def test_load_json_file(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(
        '{"strategy_id": "j", "closes": [10.0, 11.0], "weights": [1.0, 1.0]}',
        encoding="utf-8",
    )
    req = load_simple_long_only_workflow_request(p)
    assert req.strategy_id == "j"


@pytest.mark.unit
def test_parse_json_string() -> None:
    req = parse_simple_long_only_workflow_json(
        '{"closes": [1.0, 2.0], "weights": [0.5, 0.5], "strategy_id": "x"}'
    )
    assert req.weights == [0.5, 0.5]


@pytest.mark.unit
def test_parse_yaml_string() -> None:
    pytest.importorskip("yaml")
    req = parse_simple_long_only_workflow_yaml(
        "closes: [1.0, 2.0]\nweights: [1.0, 1.0]\nstrategy_id: y\n"
    )
    assert req.strategy_id == "y"


@pytest.mark.unit
def test_bad_extension(tmp_path: Path) -> None:
    p = tmp_path / "x.toml"
    p.write_text("a = 1", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported config extension"):
        load_simple_long_only_workflow_request(p)


@pytest.mark.unit
def test_run_from_config_file(tmp_path: Path) -> None:
    p = tmp_path / "run.json"
    p.write_text(
        '{"closes": [100.0, 110.0], "weights": [1.0, 1.0], "strategy_id": "t", "initial_cash": 1000.0}',
        encoding="utf-8",
    )
    orch = ResearchOrchestrator(DefaultJobRunner(profile_repository=None, analysis_executors=[]))
    out = run_simple_long_only_from_config_file(p, orchestrator=orch)
    assert out.equity_curve[-1] == pytest.approx(1100.0)


@pytest.mark.unit
def test_empty_document_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_simple_long_only_workflow_mapping(None)
