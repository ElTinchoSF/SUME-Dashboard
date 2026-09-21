"""
SUME Scraper - Reutilizable para unidades académicas de la UNL.

Este módulo proporciona un scraper reutilizable para extraer expedientes
y movimientos de SUME (Sistema Único de Mesa de Entradas) de diferentes
unidades académicas de la Universidad Nacional del Litoral.

Uso básico:
    from src.sume_scraper import SUMEScraper, ScraperConfig

    config = ScraperConfig(
        faculty_code="FBCB",
        date_from="2025-01-01",
        date_to="2025-12-31",
    )
    scraper = SUMEScraper(config)
    result = scraper.run()
    result.print_summary()
"""

from .config import ScraperConfig
from .scraper import SUMEScraper
from .validator import ScrapingValidator, ValidationReport

__all__ = [
    "SUMEScraper",
    "ScraperConfig",
    "ScrapingValidator",
    "ValidationReport",
]

__version__ = "1.0.0"
