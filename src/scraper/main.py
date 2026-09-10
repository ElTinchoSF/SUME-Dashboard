"""
Scraper orchestrator for SUME Dashboard.

Coordinates the complete scraping workflow:
1. Search SUME with faculty filter using header search
2. Parse listing pages to extract expediente data directly
3. Paginate through all result pages
4. For each expediente: fetch detail page for movimientos
5. Normalize and persist in single transaction
6. Save raw HTML snapshots to data/raw/
7. Generate post-run validation report
8. Handle duplicates via UNIQUE constraint on expedientes.numero

Updated for new SUME structure (2026):
- Header search: POST to buscar/ with header_search=numero, header_search_text=FBCB
- Listing table: numero, descripcion, concepto, origen, fecha_alta, ultimo_movimiento
- Detail page: movimientos table only (fecha_envio, fecha_recepcion, dependencia_destino)
- Pagination: buscar/{page}/
"""

import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.database import get_connection, transaction
from src.database.connection import close_connection
from src.scraper.client import SUMEClient
from src.scraper.config import ScraperConfig
from src.scraper.parser import (
    parse_listing_page,
    parse_detail_page,
    parse_movimientos_table,
    ExpedienteDict,
    MovimientoDict,
)
from src.scraper.normalizer import get_normalizer, normalize

logger = logging.getLogger(__name__)


@dataclass
class ScraperStats:
    """Statistics collected during a scraping run."""

    total_expedientes: int = 0
    total_movimientos: int = 0
    expedientes_with_zero_movimientos: int = 0
    duplicate_expedientes: int = 0
    missing_required_fields: int = 0
    parse_errors: int = 0
    http_errors: int = 0
    pages_scraped: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "total_expedientes": self.total_expedientes,
            "total_movimientos": self.total_movimientos,
            "expedientes_with_zero_movimientos": self.expedientes_with_zero_movimientos,
            "duplicate_expedientes": self.duplicate_expedientes,
            "missing_required_fields": self.missing_required_fields,
            "parse_errors": self.parse_errors,
            "http_errors": self.http_errors,
            "pages_scraped": self.pages_scraped,
            "duration_seconds": round(self.duration_seconds, 2),
        }


@dataclass
class ValidationReport:
    """Post-run validation report."""

    stats: ScraperStats
    duplicates: list[str] = field(default_factory=list)
    zero_movimientos_expedientes: list[str] = field(default_factory=list)
    missing_fields_expedientes: list[dict] = field(default_factory=list)
    parse_error_details: list[dict] = field(default_factory=list)

    def has_critical_errors(self) -> bool:
        """Check if there are critical errors that should fail the run."""
        return self.stats.http_errors > 10  # Too many HTTP errors

    def print_summary(self) -> None:
        """Print a formatted validation summary."""
        print("\n" + "=" * 60)
        print("SCRAPER VALIDATION REPORT")
        print("=" * 60)
        print(f"Total expedientes processed: {self.stats.total_expedientes}")
        print(f"Total movimientos extracted: {self.stats.total_movimientos}")
        print(f"Expedientes with zero movimientos: {self.stats.expedientes_with_zero_movimientos}")
        print(f"Duplicate expedientes (skipped): {self.stats.duplicate_expedientes}")
        print(f"Missing required fields: {self.stats.missing_required_fields}")
        print(f"Parse errors: {self.stats.parse_errors}")
        print(f"HTTP errors: {self.stats.http_errors}")
        print(f"Pages scraped: {self.stats.pages_scraped}")
        print(f"Duration: {self.stats.duration_seconds:.1f}s")

        if self.duplicates:
            print(f"\nDuplicate expedientes (not inserted):")
            for num in self.duplicates[:10]:
                print(f"  - {num}")
            if len(self.duplicates) > 10:
                print(f"  ... and {len(self.duplicates) - 10} more")

        if self.zero_movimientos_expedientes:
            print(f"\nExpedientes with zero movimientos:")
            for num in self.zero_movimientos_expedientes[:10]:
                print(f"  - {num}")
            if len(self.zero_movimientos_expedientes) > 10:
                print(f"  ... and {len(self.zero_movimientos_expedientes) - 10} more")

        if self.parse_error_details:
            print(f"\nParse errors:")
            for item in self.parse_error_details[:5]:
                print(f"  - {item.get('url', 'N/A')}: {item['error']}")

        print("=" * 60)


class ScraperOrchestrator:
    """
    Main orchestrator for the SUME scraping process.

    Manages the complete workflow from search to persistence
    with validation and error recovery.
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        """
        Initialize the orchestrator.

        Args:
            config: Scraper configuration. If None, loads from global settings.
        """
        self.config = config or ScraperConfig.load()
        self.client = SUMEClient(self.config)
        self.normalizer_rules = get_normalizer(Path(self.config.normalization_rules_path))
        self.stats = ScraperStats()
        self.validation_report = ValidationReport(stats=self.stats)

    def run(self, max_pages: Optional[int] = None) -> ValidationReport:
        """
        Execute the complete scraping workflow.

        Args:
            max_pages: Maximum number of pages to scrape (None for all)

        Returns:
            ValidationReport with statistics and any issues found.
        """
        self.stats.start_time = time.time()
        logger.info(f"Starting scraper run (max_pages={max_pages})")

        try:
            # Step 1: Fetch first page to get total pages
            first_page_result = self._fetch_listing_page(1)
            if not first_page_result:
                logger.error("Failed to fetch first listing page")
                return self.validation_report

            # Parse first page
            first_listing = parse_listing_page(
                first_page_result,
                self.config.base_url,
            )

            total_pages = first_listing.total_pages
            logger.info(f"Total pages available: {total_pages}")

            if max_pages:
                total_pages = min(total_pages, max_pages)
                logger.info(f"Limiting to {total_pages} pages")

            # Process first page expedientes
            self._process_listing_expedientes(first_listing.expedientes, 1)

            # Step 2: Process remaining pages
            for page_num in range(2, total_pages + 1):
                logger.info(f"Fetching page {page_num}/{total_pages}")

                page_result = self._fetch_listing_page(page_num)
                if not page_result:
                    logger.error(f"Failed to fetch page {page_num}")
                    self.stats.http_errors += 1
                    continue

                # Parse page
                listing = parse_listing_page(
                    page_result,
                    self.config.base_url,
                )

                # Process expedientes from this page
                self._process_listing_expedientes(listing.expedientes, page_num)

                self.stats.pages_scraped += 1

            # Generate validation report
            self._generate_validation_report()

        except Exception as e:
            logger.exception(f"Scraper run failed: {e}")
            self.stats.parse_errors += 1
            self.validation_report.parse_error_details.append({
                "url": "N/A",
                "error": str(e),
            })
        finally:
            self.stats.end_time = time.time()
            self.client.close()
            close_connection()

        return self.validation_report

    def _fetch_listing_page(self, page_num: int) -> Optional[str]:
        """
        Fetch a single listing page.

        Args:
            page_num: Page number to fetch (1 for first page)

        Returns:
            HTML content or None on error
        """
        if page_num == 1:
            # First page: use header search
            search_params = self.config.get_search_params()
            result = self.client.search(search_params)
        else:
            # Subsequent pages: use page URL
            page_url = self.config.get_page_url(page_num)
            result = self.client.get(page_url)

        if result.error:
            logger.error(f"HTTP error on page {page_num}: {result.error}")
            return None

        if result.status_code != 200:
            logger.error(f"Status {result.status_code} on page {page_num}")
            return None

        # Save raw HTML
        self.client.save_raw_html(result.content, f"listing_page_{page_num}")

        return result.content

    def _process_listing_expedientes(self, expedientes: list[ExpedienteDict], page_num: int) -> None:
        """
        Process expedientes from a listing page.

        For each expediente:
        1. Fetch detail page for movimientos
        2. Parse movimientos table
        3. Normalize and persist

        Args:
            expedientes: List of ExpedienteDict from listing page
            page_num: Current page number (for logging)
        """
        for i, expediente in enumerate(expedientes, 1):
            logger.debug(f"Processing {expediente.numero} ({i}/{len(expedientes)} on page {page_num})")

            try:
                # Fetch detail page for movimientos
                movimientos = self._fetch_and_parse_movimientos(expediente)

                # Normalize dependencies
                for mov in movimientos:
                    mov.dependencia = normalize(mov.dependencia, self.normalizer_rules)

                if expediente.origenes:
                    expediente.origenes = normalize(expediente.origenes, self.normalizer_rules)

                # Persist in single transaction
                self._persist_expediente(expediente, movimientos)

                # Update stats
                self.stats.total_expedientes += 1
                self.stats.total_movimientos += len(movimientos)

                if len(movimientos) == 0:
                    self.stats.expedientes_with_zero_movimientos += 1
                    self.validation_report.zero_movimientos_expedientes.append(expediente.numero)

            except Exception as e:
                logger.exception(f"Error processing {expediente.numero}: {e}")
                self.stats.parse_errors += 1
                self.validation_report.parse_error_details.append({
                    "url": expediente.detail_url,
                    "error": str(e),
                })

    def _fetch_and_parse_movimientos(self, expediente: ExpedienteDict) -> list[MovimientoDict]:
        """
        Fetch detail page and parse movimientos table.

        Args:
            expediente: ExpedienteDict with detail_url

        Returns:
            List of MovimientoDict
        """
        # Extract numero from URL
        numero = expediente.numero

        # Fetch detail page
        result = self.client.get(expediente.detail_url)

        if result.error:
            logger.warning(f"Failed to fetch detail for {numero}: {result.error}")
            self.stats.http_errors += 1
            return []

        if result.status_code != 200:
            logger.warning(f"Detail page returned {result.status_code} for {numero}")
            self.stats.http_errors += 1
            return []

        # Save raw HTML
        self.client.save_raw_html(result.content, f"detail_{numero}")

        # Parse movimientos
        movimientos = parse_movimientos_table(result.content)

        return movimientos

    def _persist_expediente(self, expediente: ExpedienteDict, movimientos: list[MovimientoDict]) -> None:
        """
        Persist expediente and its movimientos in a single transaction.

        Handles duplicates via UNIQUE constraint on expedientes.numero.

        Args:
            expediente: Parsed expediente data
            movimientos: List of parsed movimientos
        """
        with transaction() as conn:
            # Check if expediente already exists
            existing = conn.execute(
                "SELECT id FROM expedientes WHERE numero = ?",
                (expediente.numero,),
            ).fetchone()

            if existing:
                self.stats.duplicate_expedientes += 1
                self.validation_report.duplicates.append(expediente.numero)
                logger.debug(f"Duplicate expediente skipped: {expediente.numero}")
                return

            # Insert expediente
            cursor = conn.execute(
                """
                INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expediente.numero,
                    expediente.concepto,
                    expediente.descripcion,
                    expediente.fecha_alta,
                    expediente.estado,
                    expediente.palabras_clave,
                    expediente.origenes,
                ),
            )
            expediente_id = cursor.lastrowid

            # Insert movimientos (reverse order: SUME shows newest first, we want oldest first)
            for i, mov in enumerate(reversed(movimientos), start=1):
                conn.execute(
                    """
                    INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                    VALUES (?, ?, ?, ?)
                    """,
                    (expediente_id, i, mov.fecha_recepcion, mov.dependencia),
                )

            # Update dependencias table (upsert)
            all_deps = {mov.dependencia for mov in movimientos}
            if expediente.origenes:
                all_deps.add(expediente.origenes)

            for dep_name in all_deps:
                # Check if dependency exists
                existing_dep = conn.execute(
                    "SELECT id, total_expedientes FROM dependencias WHERE nombre = ?",
                    (dep_name,),
                ).fetchone()

                if existing_dep:
                    conn.execute(
                        "UPDATE dependencias SET total_expedientes = total_expedientes + 1 WHERE id = ?",
                        (existing_dep[0],),
                    )
                else:
                    conn.execute(
                        "INSERT INTO dependencias (nombre, nombre_original, total_expedientes) VALUES (?, ?, 1)",
                        (dep_name, dep_name),
                    )

    def _generate_validation_report(self) -> None:
        """Generate and log the validation report."""
        self.validation_report.print_summary()
        logger.info("Scraper run completed", extra=self.stats.to_dict())


def run_scraper(year: int = 2025, semester: Optional[int] = None, max_pages: Optional[int] = None) -> ValidationReport:
    """
    Convenience function to run the scraper.

    Args:
        year: Year to scrape (default 2025, kept for compatibility)
        semester: Semester to scrape (kept for compatibility, not used in new SUME)
        max_pages: Maximum pages to scrape (None for all)

    Returns:
        ValidationReport with results.
    """
    orchestrator = ScraperOrchestrator()
    return orchestrator.run(max_pages=max_pages)


def run_scraper_cli(args: list[str]) -> int:
    """
    CLI entry point for the scraper.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    import argparse

    parser = argparse.ArgumentParser(description="SUME Scraper")
    parser.add_argument("--year", type=int, default=2025, help="Year to scrape (kept for compatibility)")
    parser.add_argument("--semester", type=int, choices=[1, 2], help="Semester (kept for compatibility)")
    parser.add_argument("--max-pages", type=int, help="Maximum pages to scrape")
    parser.add_argument("--config", type=str, help="Path to config file")

    parsed = parser.parse_args(args)

    config = None
    if parsed.config:
        config = ScraperConfig.load(Path(parsed.config))

    orchestrator = ScraperOrchestrator(config)
    report = orchestrator.run(max_pages=parsed.max_pages)

    return 1 if report.has_critical_errors() else 0


if __name__ == "__main__":
    sys.exit(run_scraper_cli(sys.argv[1:]))
