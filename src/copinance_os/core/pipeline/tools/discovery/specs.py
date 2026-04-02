"""Builtin :class:`~copinance_os.domain.plugins.spec.PluginSpec` lists (lazy import targets)."""

from copinance_os.domain.plugins.spec import PluginSpec

_B = "copinance_os.core.pipeline.tools.discovery.bundles"

_SPEC_MARKET_DATA = PluginSpec(
    name="market_data", kind="tool", import_path=_B, qualified_name="market_data_tools_bundle"
)
_SPEC_RULE_REGIME = PluginSpec(
    name="rule_based_regime",
    kind="tool",
    import_path=_B,
    qualified_name="rule_based_regime_tools_bundle",
)
_SPEC_FUNDAMENTALS = PluginSpec(
    name="fundamentals", kind="tool", import_path=_B, qualified_name="fundamental_data_tools_bundle"
)
_SPEC_MARKET_INDICATORS = PluginSpec(
    name="market_regime_indicators",
    kind="tool",
    import_path=_B,
    qualified_name="market_regime_indicators_bundle",
)
_SPEC_MACRO_INDICATORS = PluginSpec(
    name="macro_regime_indicators",
    kind="tool",
    import_path=_B,
    qualified_name="macro_regime_indicators_bundle",
)

DATA_PROVIDER_TOOL_BUNDLE_SPECS: tuple[PluginSpec, ...] = (
    _SPEC_MARKET_DATA,
    _SPEC_RULE_REGIME,
    _SPEC_FUNDAMENTALS,
)

QUESTION_DRIVEN_TOOL_BUNDLE_SPECS: tuple[PluginSpec, ...] = (
    _SPEC_MARKET_DATA,
    _SPEC_RULE_REGIME,
    _SPEC_MARKET_INDICATORS,
    _SPEC_MACRO_INDICATORS,
    _SPEC_FUNDAMENTALS,
)
