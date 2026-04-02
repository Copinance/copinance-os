"""Tool bundle discovery (PluginSpec, entry points, package scan)."""

from copinance_os.core.pipeline.tools.discovery.loader import (
    DEFAULT_SCAN_PACKAGE,
    TOOL_BUNDLE_ENTRY_GROUP,
    build_data_provider_tool_registry,
    collect_question_driven_tools,
    load_tools_from_plugin_specs,
)
from copinance_os.core.pipeline.tools.discovery.scan import scan_tool_bundle_factories
from copinance_os.core.pipeline.tools.discovery.specs import (
    DATA_PROVIDER_TOOL_BUNDLE_SPECS,
    QUESTION_DRIVEN_TOOL_BUNDLE_SPECS,
)

__all__ = [
    "DEFAULT_SCAN_PACKAGE",
    "TOOL_BUNDLE_ENTRY_GROUP",
    "DATA_PROVIDER_TOOL_BUNDLE_SPECS",
    "QUESTION_DRIVEN_TOOL_BUNDLE_SPECS",
    "build_data_provider_tool_registry",
    "collect_question_driven_tools",
    "load_tools_from_plugin_specs",
    "scan_tool_bundle_factories",
]
