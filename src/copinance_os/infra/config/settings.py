"""Application settings (pydantic-settings)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    This class only handles application-level settings (storage, logging, etc.).
    LLM configuration is handled separately via LLMConfig and should not be
    included in this class.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="COPINANCEOS_",
        case_sensitive=False,
        extra="ignore",  # Ignore LLM-related and other extra environment variables
    )

    # Application
    app_name: str = Field(default="Copinance OS", description="Application name")
    environment: str = Field(
        default="development", description="Environment (development, staging, production)"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="console",
        description="Log format (json or console). Console uses compact level tags for CLI.",
    )

    # Analysis execution settings
    default_analysis_timeout: int = Field(
        default=300, description="Default analysis execution timeout in seconds"
    )
    enable_agent_analysis: bool = Field(
        default=True, description="Enable question-driven (agent) AI analysis"
    )

    # Storage configuration
    storage_type: str = Field(
        default="file",
        description="Storage backend type (file, memory). File storage persists data, memory storage is ephemeral.",
    )
    storage_path: str = Field(
        default=".copinance",
        description="Persistence root path. Versioned data/cache/results/state directories are created under this root when storage_type is 'file'. Empty or '.' is normalized to .copinance.",
    )

    def get_storage_path(self) -> str:
        """Return storage path, normalized so data is never written at project root."""
        p = (self.storage_path or "").strip()
        if not p or p == ".":
            return ".copinance"
        return p

    # Cache (tool results and agent prompt cache)
    cache_enabled: bool = Field(
        default=True,
        description="Enable built-in cache for tool results and agent prompts. Set to false to disable or when using your own cache via get_container(cache_manager=...).",
    )

    # Macroeconomic data (e.g., FRED)
    fred_api_key: str | None = Field(
        default=None,
        description="FRED API key for macroeconomic time series (set COPINANCEOS_FRED_API_KEY)",
    )
    fred_base_url: str = Field(
        default="https://api.stlouisfed.org/fred",
        description="Base URL for FRED API",
    )
    fred_rate_limit_delay: float = Field(
        default=0.1,
        description="Delay between FRED API requests in seconds (simple rate limiting)",
    )
    fred_timeout_seconds: float = Field(
        default=30.0,
        description="HTTP timeout for FRED API requests",
    )

    # SEC EDGAR (edgartools) — required by SEC for programmatic access
    edgar_identity: str = Field(
        default="Copinance copinance@gmail.com",
        description=(
            "Identity string for SEC EDGAR (name and email, e.g. 'Copinance user@example.com'). "
            "Override via COPINANCEOS_EDGAR_IDENTITY or EDGAR_IDENTITY."
        ),
    )

    # Option Greek estimation (BSM / QuantLib); see docs: Options chain metadata
    option_greeks_risk_free_rate: float | None = Field(
        default=None,
        description=(
            "Annualized risk-free rate for analytic BSM Greeks when estimating from a chain "
            "(e.g. 0.045). None uses built-in default. Env: COPINANCEOS_OPTION_GREEKS_RISK_FREE_RATE"
        ),
    )
    option_greeks_dividend_yield_default: float | None = Field(
        default=None,
        description=(
            "Default continuous dividend yield when chain metadata has no `dividend_yield`. "
            "None means 0. Env: COPINANCEOS_OPTION_GREEKS_DIVIDEND_YIELD_DEFAULT"
        ),
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings singleton.

    Cached after first call so pydantic-settings parses env vars only once per process.
    Tests that need a fresh instance should patch ``get_settings`` directly or reset
    the cache via ``copinance_os.infra.config.settings._settings = None``.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_storage_path_safe() -> str:
    """Return storage path, using .mock when get_settings() is mocked in tests."""
    raw = get_settings().get_storage_path()
    if not isinstance(raw, str):
        return ".mock"
    if "MagicMock" in raw:
        return ".mock"
    p = raw.strip()
    if not p or p == ".":
        return ".copinance"
    return p
