"""
Configuration management for SUME Dashboard.

Loads settings from config.yaml with environment variable overrides.
Uses Pydantic Settings for type validation and nested configuration.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    path: str = "data/sume.db"

    model_config = SettingsConfigDict(env_prefix="SUME_DB_")


class SUMEConfig(BaseSettings):
    """SUME web service configuration."""

    base_url: str = "https://servicios.unl.edu.ar/expedientes/"
    search_path: str = "busqueda_avanzada.php"
    detail_path: str = "ver_expediente.php"
    faculty_filter: str = "FBCB"
    year: int = 2025

    model_config = SettingsConfigDict(env_prefix="SUME_")


class ScraperConfig(BaseSettings):
    """Scraper configuration."""

    delay_seconds: float = 0.5
    timeout_seconds: int = 30
    max_retries: int = 3
    backoff_base: float = 1.0
    rate_limit_wait: int = 60
    user_agent: str = "SUME-Dashboard/1.0 (Mesa de Entradas FBCB-UNL)"

    model_config = SettingsConfigDict(env_prefix="SUME_SCRAPER_")


class NormalizerConfig(BaseSettings):
    """Normalizer configuration."""

    rules_path: str = "config/normalization_rules.yaml"

    model_config = SettingsConfigDict(env_prefix="SUME_NORMALIZER_")


class AnalyzerConfig(BaseSettings):
    """Analyzer configuration."""

    min_sample_threshold: int = 5
    outlier_frequency_threshold: float = 0.05
    outlier_step_multiplier: float = 2.5

    model_config = SettingsConfigDict(env_prefix="SUME_ANALYZER_")


class DashboardConfig(BaseSettings):
    """Dashboard configuration."""

    cache_ttl_seconds: int = 300
    page_size: int = 1000

    model_config = SettingsConfigDict(env_prefix="SUME_DASHBOARD_")


class ReporterConfig(BaseSettings):
    """Reporter configuration."""

    templates_dir: str = "templates"
    output_dir: str = "reports"
    version_format: str = "{date}.{commit_short}.{data_hash_short}"

    model_config = SettingsConfigDict(env_prefix="SUME_REPORTER_")


class Settings(BaseSettings):
    """Main application settings loaded from config.yaml."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    sume: SUMEConfig = Field(default_factory=SUMEConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    normalizer: NormalizerConfig = Field(default_factory=NormalizerConfig)
    analyzer: AnalyzerConfig = Field(default_factory=AnalyzerConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    reporter: ReporterConfig = Field(default_factory=ReporterConfig)

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Settings":
        """
        Load settings from config.yaml.

        Args:
            config_path: Optional path to config.yaml. If not provided,
                        looks for config.yaml in current working directory.

        Returns:
            Settings instance with validated configuration.
        """
        if config_path is not None:
            # Override the yaml_file in model_config for this instance
            return cls(_env_file=None, _yaml_file=config_path)
        return cls()


# Global settings instance (lazy-loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance, loading it if necessary."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings(config_path: Optional[Path] = None) -> Settings:
    """Force reload of settings from config file."""
    global _settings
    _settings = Settings.load(config_path)
    return _settings