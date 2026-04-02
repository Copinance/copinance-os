"""Load tool bundles from PluginSpecs, setuptools entry points, and package scan."""

from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import entry_points

import structlog

from copinance_os.core.pipeline.tools.discovery.scan import scan_tool_bundle_factories
from copinance_os.core.pipeline.tools.discovery.specs import (
    DATA_PROVIDER_TOOL_BUNDLE_SPECS,
    QUESTION_DRIVEN_TOOL_BUNDLE_SPECS,
)
from copinance_os.core.pipeline.tools.tool_registry import ToolRegistry
from copinance_os.domain.models.tool_bundle_context import ToolBundleContext
from copinance_os.domain.plugins.registry import resolve_plugin_callable
from copinance_os.domain.plugins.spec import PluginSpec
from copinance_os.domain.ports.data_providers import FundamentalDataProvider, MarketDataProvider
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)

# Third-party wheels register ``ToolBundleFactory`` callables under this group.
TOOL_BUNDLE_ENTRY_GROUP = "copinance_os.tool_bundles"

# Default package scanned for ``tool_bundle_factory`` (optional extension point).
DEFAULT_SCAN_PACKAGE = "copinance_os.core.pipeline.tools.bundles"


def _dedupe_tools_preserve_order(tools: list[Tool]) -> list[Tool]:
    seen: dict[str, Tool] = {}
    order: list[str] = []
    for t in tools:
        name = t.get_name()
        if name not in seen:
            order.append(name)
        else:
            logger.warning(
                "duplicate tool name in bundle load; later entry wins",
                tool_name=name,
            )
        seen[name] = t
    return [seen[k] for k in order]


def _tools_from_plugin_specs(
    specs: Sequence[PluginSpec],
    ctx: ToolBundleContext,
) -> list[Tool]:
    out: list[Tool] = []
    for spec in specs:
        if spec.kind != "tool":
            logger.debug("skipping non-tool plugin spec", name=spec.name, kind=spec.kind)
            continue
        raw = resolve_plugin_callable(spec)
        if not callable(raw):
            raise TypeError(f"Plugin spec {spec.name!r} did not resolve to a callable")
        chunk: list[Tool] = raw(ctx)
        out.extend(chunk)
    return out


def load_tools_from_plugin_specs(
    specs: Sequence[PluginSpec],
    ctx: ToolBundleContext,
) -> list[Tool]:
    """Resolve each :class:`~copinance_os.domain.plugins.spec.PluginSpec` and concatenate tools."""
    return _dedupe_tools_preserve_order(_tools_from_plugin_specs(specs, ctx))


def build_data_provider_tool_registry(
    *,
    market_data_provider: MarketDataProvider | None = None,
    fundamental_data_provider: FundamentalDataProvider | None = None,
) -> ToolRegistry:
    """Tools used by data-provider-centric flows (market + rule regime + fundamentals only)."""
    ctx = ToolBundleContext(
        market_data_provider=market_data_provider,
        fundamental_data_provider=fundamental_data_provider,
    )
    reg = ToolRegistry()
    reg.register_many(load_tools_from_plugin_specs(DATA_PROVIDER_TOOL_BUNDLE_SPECS, ctx))
    return reg


def _tools_from_entry_points(group: str, ctx: ToolBundleContext) -> list[Tool]:
    eps = entry_points()
    selected = eps.select(group=group)
    out: list[Tool] = []
    for ep in selected:
        factory = ep.load()
        if not callable(factory):
            logger.warning("entry point is not callable", group=group, name=ep.name)
            continue
        chunk: list[Tool] = factory(ctx)
        out.extend(chunk)
    return out


def collect_question_driven_tools(
    ctx: ToolBundleContext,
    *,
    builtin_specs: Sequence[PluginSpec] | None = None,
    extra_plugin_specs: Sequence[PluginSpec] | None = None,
    load_entry_point_bundles: bool = True,
    scan_bundles_package: str | None = DEFAULT_SCAN_PACKAGE,
) -> list[Tool]:
    """Assemble the question-driven tool list: builtins, optional extras, entry points, scan.

    Entry-point and scanned bundles are merged after builtins, then names are de-duplicated
    (last occurrence wins) to keep behaviour predictable when plugins overlap.
    """
    specs_list: list[PluginSpec] = []
    specs_list.extend(
        builtin_specs if builtin_specs is not None else QUESTION_DRIVEN_TOOL_BUNDLE_SPECS
    )
    if extra_plugin_specs:
        specs_list.extend(extra_plugin_specs)

    merged: list[Tool] = []
    merged.extend(_tools_from_plugin_specs(specs_list, ctx))
    if load_entry_point_bundles:
        merged.extend(_tools_from_entry_points(TOOL_BUNDLE_ENTRY_GROUP, ctx))
    if scan_bundles_package:
        for factory in scan_tool_bundle_factories(scan_bundles_package):
            merged.extend(factory(ctx))
    return _dedupe_tools_preserve_order(merged)
