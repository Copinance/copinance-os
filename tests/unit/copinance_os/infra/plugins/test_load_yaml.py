"""YAML plugin spec loading (optional PyYAML)."""

from pathlib import Path

import pytest

pytest.importorskip("yaml")

from copinance_os.infra.plugins.load_specs import load_plugin_specs_from_yaml


@pytest.mark.unit
def test_load_yaml_list(tmp_path: Path) -> None:
    p = tmp_path / "p.yaml"
    p.write_text(
        """
- name: sqrt
  kind: tool
  import_path: math
  qualified_name: sqrt
""",
        encoding="utf-8",
    )
    specs = load_plugin_specs_from_yaml(p)
    assert len(specs) == 1
    assert specs[0].name == "sqrt"


@pytest.mark.unit
def test_load_yaml_wrapped(tmp_path: Path) -> None:
    p = tmp_path / "p.yaml"
    p.write_text(
        """
plugins:
  - name: sqrt
    kind: tool
    import_path: math
    qualified_name: sqrt
""",
        encoding="utf-8",
    )
    specs = load_plugin_specs_from_yaml(p)
    assert len(specs) == 1


@pytest.mark.unit
def test_load_yaml_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert load_plugin_specs_from_yaml(p) == []
