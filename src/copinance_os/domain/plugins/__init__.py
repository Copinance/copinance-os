"""Config-addressable plugin specs and registries."""

from copinance_os.domain.plugins.registry import PluginRegistry, resolve_plugin_callable
from copinance_os.domain.plugins.spec import PluginSpec

__all__ = ["PluginRegistry", "PluginSpec", "resolve_plugin_callable"]
