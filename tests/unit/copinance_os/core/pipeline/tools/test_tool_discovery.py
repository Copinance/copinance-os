"""Tests for PluginSpec / entry-point / scan tool bundle discovery."""

from unittest.mock import MagicMock

import pytest

from copinance_os.core.pipeline.tools.discovery import (
    DATA_PROVIDER_TOOL_BUNDLE_SPECS,
    build_data_provider_tool_registry,
    collect_question_driven_tools,
    load_tools_from_plugin_specs,
    scan_tool_bundle_factories,
)
from copinance_os.domain.models.tool_bundle_context import ToolBundleContext
from copinance_os.domain.ports.data_providers import FundamentalDataProvider, MarketDataProvider


def _market_provider() -> MarketDataProvider:
    p = MagicMock(spec=MarketDataProvider)
    p.get_provider_name = MagicMock(return_value="m")
    return p


def _fundamental_provider() -> FundamentalDataProvider:
    p = MagicMock(spec=FundamentalDataProvider)
    p.get_provider_name = MagicMock(return_value="f")
    return p


@pytest.mark.unit
def test_load_tools_from_plugin_specs_empty_context_returns_empty() -> None:
    ctx = ToolBundleContext()
    tools = load_tools_from_plugin_specs(DATA_PROVIDER_TOOL_BUNDLE_SPECS, ctx)
    assert tools == []


@pytest.mark.unit
def test_load_tools_from_plugin_specs_with_market_provider() -> None:
    ctx = ToolBundleContext(market_data_provider=_market_provider())
    tools = load_tools_from_plugin_specs(DATA_PROVIDER_TOOL_BUNDLE_SPECS, ctx)
    names = {t.get_name() for t in tools}
    assert "get_market_quote" in names


@pytest.mark.unit
def test_collect_question_driven_tools_without_entry_points_or_scan() -> None:
    ctx = ToolBundleContext(
        market_data_provider=_market_provider(),
        fundamental_data_provider=_fundamental_provider(),
    )
    tools = collect_question_driven_tools(
        ctx,
        load_entry_point_bundles=False,
        scan_bundles_package=None,
    )
    assert len(tools) > 0
    assert len({t.get_name() for t in tools}) == len(tools)


@pytest.mark.unit
def test_scan_default_bundles_package_finds_no_submodules() -> None:
    assert scan_tool_bundle_factories("copinance_os.core.pipeline.tools.bundles") == []


@pytest.mark.unit
def test_build_data_provider_tool_registry() -> None:
    reg = build_data_provider_tool_registry(market_data_provider=_market_provider())
    names = set(reg.list_tools())
    assert "get_market_quote" in names
