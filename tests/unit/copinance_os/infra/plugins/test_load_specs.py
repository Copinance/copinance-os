"""JSON plugin spec loading."""

import json
from pathlib import Path

import pytest

from copinance_os.domain.plugins.spec import PluginSpec
from copinance_os.infra.plugins.load_specs import load_plugin_specs_from_json


@pytest.mark.unit
def test_load_array_format(tmp_path: Path) -> None:
    data = [
        {
            "name": "lr",
            "kind": "indicator",
            "import_path": "copinance_os.domain.indicators.returns",
            "qualified_name": "log_returns_from_prices",
        }
    ]
    p = tmp_path / "p.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    specs = load_plugin_specs_from_json(p)
    assert len(specs) == 1
    assert specs[0].name == "lr"


@pytest.mark.unit
def test_load_wrapped_format(tmp_path: Path) -> None:
    p = tmp_path / "p.json"
    p.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": "a",
                        "kind": "strategy",
                        "import_path": "math",
                        "qualified_name": "sqrt",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    specs = load_plugin_specs_from_json(p)
    assert len(specs) == 1
    assert isinstance(specs[0], PluginSpec)


@pytest.mark.unit
def test_load_invalid_structure(tmp_path: Path) -> None:
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"foo": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="Plugin file"):
        load_plugin_specs_from_json(p)
