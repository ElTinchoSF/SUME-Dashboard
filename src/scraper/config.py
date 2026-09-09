"""
Scraper-specific configuration for SUME Dashboard.

Provides typed configuration for HTTP client behavior, CSS selectors,
and scraper orchestration parameters.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SelectorConfig(BaseSettings):
    """CSS selectors for SUME HTML parsing."""

    # Listing page selectors
    listing_table: str = "table.tabla_expedientes"
    listing_rows: str = "tbody tr"
    listing_detail_link: str = "td:last-child a"
    pagination_container: str = "div.pagination"
    pagination_links: str = "a"

    # Detail page selectors
    detail_numero: str = "div.expediente-header h1"
    detail_concepto: str = "div.expediente-header span.concepto"
    detail_info_container: str = "div.expediente-info"
    detail_field_pattern: str = "p strong"

    # Movimientos table selectors
    movimientos_table: str = "table.tabla_movimientos"
    movimientos_rows: str = "tbody tr"
    movimientos_cells: str = "td"

    model_config = SettingsConfigDict(env_prefix="SUME_SELECTOR_")


class ScraperConfig(BaseSettings):
    """
    Main scraper configuration.

    Combines HTTP client settings, selectors, and orchestration parameters.
    """

    # HTTP client settings
    delay_seconds: float = Field(default=0.5, ge=0.0, description="Delay between requests")
    timeout_seconds: int = Field(default=30, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    backoff_base: float = Field(default=1.0, ge=0.1, description="Exponential backoff base (seconds)")
    rate_limit_wait: int = Field(default=60, ge=1, description="Wait time on 429 response (seconds)")
    rate_limit_retries: int = Field(default=3, ge=0, description="Max retries on 429")
    user_agent: str = Field(
        default="SUME-Dashboard/1.0 (Mesa de Entradas FBCB-UNL)",
        description="User-Agent header for requests",
    )

    # SUME URL configuration
    base_url: str = "https://servicios.unl.edu.ar/expedientes/"
    search_path: str = "busqueda_avanzada.php"
    detail_path: str = "ver_expediente.php"
    faculty_filter: str = "FBCB"

    # Selectors
    selectors: SelectorConfig = Field(default_factory=SelectorConfig)

    # Normalization rules path
    normalization_rules_path: str = "config/normalization_rules.yaml"

    # Output directories
    raw_html_dir: str = "data/raw"

    # Validation settings
    validate_after_run: bool = True

    model_config = SettingsConfigDict(
        env_prefix="SUME_SCRAPER_",
        extra="ignore",
    )

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ScraperConfig":
        """Load configuration, optionally from a specific path."""
        if config_path is not None:
            return cls(_yaml_file=config_path)
        return cls()

    def get_search_url(self) -> str:
        """Construct the full search URL."""
        return f"{self.base_url.rstrip('/')}/{self.search_path}"

    def get_detail_url(self, detail_id: str) -> str:
        """Construct a detail page URL from the detail ID."""
        return f"{self.base_url.rstrip('/')}/{self.detail_path}?id={detail_id}"

    def get_search_params(self, year: int, semester: Optional[int] = None) -> dict:
        """
        Build search parameters for SUME advanced search.

        Args:
            year: Year to search (e.g., 2025)
            semester: Optional semester (1 for Jan-Jun, 2 for Jul-Dec)

        Returns:
            Dictionary of query parameters for the search.
        """
        if semester == 1:
            fecha_desde = f"01/01/{year}"
            fecha_hasta = f"30/06/{year}"
        elif semester == 2:
            fecha_desde = f"01/07/{year}"
            fecha_hasta = f"31/12/{year}"
        else:
            fecha_desde = f"01/01/{year}"
            fecha_hasta = f"31/12/{year}"

        return {
            "numero": self.faculty_filter,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "buscar": "Buscar",
        }