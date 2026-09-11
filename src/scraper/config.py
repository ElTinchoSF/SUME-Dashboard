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

    # Listing page selectors (header search results)
    listing_table: str = "table.table"
    listing_rows: str = "tbody tr"
    listing_detail_link: str = "td:first-child"
    pagination_container: str = "ul.pagination"
    pagination_links: str = "a"

    # Detail page selectors
    detail_numero: str = "h4.label"
    detail_panel_body: str = "div.panel-body"

    # Movimientos table selectors
    movimientos_table: str = "table.table"
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

    # SUME URL configuration (updated for new SUME structure)
    base_url: str = "https://servicios.unl.edu.ar/expedientes/"
    search_path: str = "buscar/"
    detail_path: str = "expediente"
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

    def get_detail_url(self, numero: str) -> str:
        """Construct a detail page URL from the expediente numero."""
        return f"{self.base_url.rstrip('/')}/{self.detail_path}/{numero}"

    def get_search_params(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
        """
        Build search parameters for SUME search.

        Uses advanced search with date filters when dates are provided.
        Falls back to simple header search when no dates.

        Args:
            date_from: Filter expedientes created from this date (YYYY-MM-DD).
            date_to: Filter expedientes created up to this date (YYYY-MM-DD).

        Returns:
            Dictionary of form data for the search.
        """
        # If date filters are provided, use advanced search form
        if date_from or date_to:
            return self._get_advanced_search_params(date_from, date_to)

        # Default: simple header search
        return {
            "header_search": "numero",
            "header_search_text": self.faculty_filter,
        }

    def _get_advanced_search_params(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
        """
        Build advanced search parameters with date filters.

        ALL form fields must be included (even empty ones) for SUME to process the search.
        When mesa de entrada is selected, the office dropdown auto-selects the same ID.

        Args:
            date_from: Filter expedientes created from this date (YYYY-MM-DD).
            date_to: Filter expedientes created up to this date (YYYY-MM-DD).

        Returns:
            Dictionary of form data for the advanced search.
        """
        from datetime import datetime

        # ALL form fields must be included (even empty ones)
        # oficina=5 is critical: when Mesa de Entradas - FBCB is selected,
        # the JS auto-selects the same office in the oficina dropdown
        params = {
            "numero": "",
            "descripcion": "",
            "palabraClave": "",
            "selectOrigen": "interno",
            "mesaEntrada": "5",
            "oficina": "5",  # Auto-selected by JS when mesa de entrada = FBCB
            "concepto": "",
            "fechaCdesde": "",
            "fechaChasta": "",
            "tipoDR": "",
            "numeroDR": "",
        }

        # Convert dates from YYYY-MM-DD to DD/MM/YYYY for SUME
        if date_from:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            params["fechaCdesde"] = dt.strftime("%d/%m/%Y")

        if date_to:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            params["fechaChasta"] = dt.strftime("%d/%m/%Y")

        return params

    def get_page_url(self, page: int) -> str:
        """
        Construct a pagination URL.

        Args:
            page: Page number (1-indexed)

        Returns:
            Full URL for the specified page.
        """
        return f"{self.base_url.rstrip('/')}/{self.search_path}{page}/"
