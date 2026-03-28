"""Plugin registry and dynamic resolution."""

import pytest

from copinance_os.domain.indicators.returns import log_returns_from_prices
from copinance_os.domain.plugins import PluginRegistry, PluginSpec, resolve_plugin_callable


@pytest.mark.unit
def test_plugin_registry_register_get() -> None:
    reg: PluginRegistry[str] = PluginRegistry()
    reg.register("a", "x")
    assert reg.get("a") == "x"
    assert reg.names() == ("a",)


@pytest.mark.unit
def test_plugin_registry_duplicate() -> None:
    reg: PluginRegistry[int] = PluginRegistry()
    reg.register("k", 1)
    with pytest.raises(KeyError):
        reg.register("k", 2)


@pytest.mark.unit
def test_resolve_plugin_callable_indicator() -> None:
    spec = PluginSpec(
        name="lr",
        kind="indicator",
        import_path="copinance_os.domain.indicators.returns",
        qualified_name="log_returns_from_prices",
    )
    fn = resolve_plugin_callable(spec)
    assert fn is log_returns_from_prices
    assert len(fn([100.0, 101.0])) == 1  # type: ignore[operator]
