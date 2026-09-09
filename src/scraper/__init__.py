"""
Scraper package for SUME Dashboard.

Provides HTTP client, HTML parser, dependency normalizer, and orchestration
for extracting expedientes from the SUME public system.
"""

from src.scraper.client import SUMEClient
from src.scraper.parser import (
    parse_listing_page,
    parse_detail_page,
    parse_movimientos_table,
    ExpedienteDict,
    MovimientoDict,
)
from src.scraper.normalizer import (
    normalize,
    load_rules,
    NormalizationRules,
)
from src.scraper.main import run_scraper, ScraperConfig

__all__ = [
    # Client
    "SUMEClient",
    # Parser
    "parse_listing_page",
    "parse_detail_page",
    "parse_movimientos_table",
    "ExpedienteDict",
    "MovimientoDict",
    # Normalizer
    "normalize",
    "load_rules",
    "NormalizationRules",
    # Orchestrator
    "run_scraper",
    "ScraperConfig",
]