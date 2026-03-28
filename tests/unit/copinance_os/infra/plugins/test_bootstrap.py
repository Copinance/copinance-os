"""Plugin registry bootstrap from specs and JSON."""

import json
from pathlib import Path

import pytest

from copinance_os.domain.plugins.spec import PluginSpec
from copinance_os.infra.plugins.bootstrap import (
    build_callable_registry_from_json,
    build_callable_registry_from_specs,
)


@pytest.mark.unit
def test_build_registry_from_specs() -> None:
    specs = [
        PluginSpec(
            name="sqrt",
            kind="tool",
            import_path="math",
            qualified_name="sqrt",
        )
    ]
    reg = build_callable_registry_from_specs(specs)
    assert reg.get("sqrt")(4.0) == 2.0


@pytest.mark.unit
def test_build_registry_from_json(tmp_path: Path) -> None:
    p = tmp_path / "plugins.json"
    p.write_text(
        json.dumps(
            [
                {
                    "name": "sqrt",
                    "kind": "tool",
                    "import_path": "math",
                    "qualified_name": "sqrt",
                }
            ]
        ),
        encoding="utf-8",
    )
    reg = build_callable_registry_from_json(p)
    assert reg.names() == ("sqrt",)


@pytest.mark.unit
def test_duplicate_name_raises() -> None:
    specs = [
        PluginSpec(name="x", kind="tool", import_path="math", qualified_name="sqrt"),
        PluginSpec(name="x", kind="tool", import_path="math", qualified_name="sqrt"),
    ]
    with pytest.raises(KeyError, match="already registered"):
        build_callable_registry_from_specs(specs)
