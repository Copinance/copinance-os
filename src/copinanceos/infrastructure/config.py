"""Configuration management using pydantic-settings."""

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
    log_format: str = Field(default="json", description="Log format (json or console)")

    # Workflow settings
    default_workflow_timeout: int = Field(
        default=300, description="Default workflow timeout in seconds"
    )
    enable_agent_workflows: bool = Field(default=True, description="Enable agent AI workflows")

    # Storage configuration
    storage_type: str = Field(
        default="file",
        description="Storage backend type (file, memory). File storage persists data, memory storage is ephemeral.",
    )
    storage_path: str = Field(
        default=".copinance",
        description="Base path for file storage backend. Only used when storage_type is 'file'.",
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


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
