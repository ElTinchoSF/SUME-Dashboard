"""
Scraper orchestrator for SUME Dashboard.

Coordinates the complete scraping workflow:
1. Search SUME with faculty filter and date range (semester support)
2. Paginate through all result pages
3. For each detail URL: fetch → parse → normalize → persist in single transaction
4. Save raw HTML snapshots to data/raw/
5. Generate post-run validation report
6. Handle duplicates via UNIQUE constraint on expedientes.numero
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from src.config import get_settings
from src.database import get_connection, transaction
from src.database.models import ExpedienteInputDict, MovimientoInputDict, DependenciaInputDict
from src.database.connection import close_connection
from src.scraper.client import SUMEClient, RequestResult
from src.scraper.config import ScraperConfig
from src.scraper.parser import (
    parse_listing_page,
    parse_detail_page,
    parse_movimientos_table,
    ExpedienteDict,
    MovimientoDict,
)
from src.scraper.normalizer import get_normalizer, normalize, NormalizationRules

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
        return self.stats.duplicate_expedientes > 0

    def print_summary(self) -> None:
        """Print a formatted validation summary."""
        print("\n" + "=" * 60)
        print("SCRAPER VALIDATION REPORT")
        print("=" * 60)
        print(f"Total expedientes processed: {self.stats.total_expedientes}")
        print(f"Total movimientos extracted: {self.stats.total_movimientos}")
        print(f"Expedientes with zero movimientos: {self.stats.expedientes_with_zero_movimientos}")
        print(f"Duplicate expedientes (blocked by UNIQUE): {self.stats.duplicate_expedientes}")
        print(f"Missing required fields: {self.stats.missing_required_fields}")
        print(f"Parse errors: {self.stats.parse_errors}")
        print(f"HTTP errors: {self.stats.http_errors}")
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

        if self.missing_fields_expedientes:
            print(f"\nExpedientes with missing required fields:")
            for item in self.missing_fields_expedientes[:10]:
                print(f"  - {item['numero']}: missing {item['fields']}")

        if self.parse_error_details:
            print(f"\nParse errors:")
            for item in self.parse_error_details[:5]:
                print(f"  - {item['url']}: {item['error']}")

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

    def run(self, year: int = 2025, semester: Optional[int] = None) -> ValidationReport:
        """
        Execute the complete scraping workflow.

        Args:
            year: Year to scrape (default 2025)
            semester: Optional semester (1 for Jan-Jun, 2 for Jul-Dec, None for full year)

        Returns:
            ValidationReport with statistics and any issues found.
        """
        import time
        self.stats.start_time = time.time()
        logger.info(f"Starting scraper run for year={year}, semester={semester}")

        try:
            # Build search parameters
            search_params = self.config.get_search_params(year, semester)
            logger.info(f"Search params: {search_params}")

            # Execute search and pagination
            detail_urls = self._fetch_all_detail_urls(search_params)
            logger.info(f"Found {len(detail_urls)} expediente detail URLs")

            # Process each expediente
            for i, detail_url in enumerate(detail_urls, 1):
                logger.info(f"Processing {i}/{len(detail_urls)}: {detail_url}")
                self._process_expediente(detail_url, i, len(detail_urls))

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

    def _fetch_all_detail_urls(self, search_params: dict) -> list[str]:
        """
        Search SUME and paginate through all result pages.

        Args:
            search_params: Search parameters for SUME advanced search.

        Returns:
            List of all detail URLs found.
        """
        all_urls = []
        page = 1

        while True:
            logger.info(f"Fetching listing page {page}")

            # Add page parameter if not first page
            params = search_params.copy()
            if page > 1:
                params["page"] = page

            result = self.client.search(params)

            if result.error:
                logger.error(f"Search failed on page {page}: {result.error}")
                self.stats.http_errors += 1
                break

            if result.status_code != 200:
                logger.error(f"Search returned status {result.status_code} on page {page}")
                self.stats.http_errors += 1
                break

            # Save raw HTML for this listing page
            self.client.save_raw_html(result.content, f"listing_page_{page}")

            # Parse listing page
            listing = parse_listing_page(
                result.content,
                self.config.base_url,
            )

            if not listing.detail_urls:
                logger.info(f"No more results on page {page}, stopping pagination")
                break

            all_urls.extend(listing.detail_urls)
            logger.info(f"Page {page}: found {len(listing.detail_urls)} expedientes")

            # Check for next page
            if not listing.next_page_url:
                logger.info("No next page link found, stopping pagination")
                break

            page += 1

            # Safety limit
            if page > 1000:
                logger.warning("Reached maximum page limit (1000), stopping")
                break

        return all_urls

    def _process_expediente(self, detail_url: str, index: int, total: int) -> None:
        """
        Process a single expediente: fetch, parse, normalize, persist.

        Args:
            detail_url: URL of the expediente detail page
            index: Current index (1-based)
            total: Total number of expedientes
        """
        try:
            # Fetch detail page
            result = self.client.get_detail(self._extract_detail_id(detail_url))

            if result.error:
                logger.error(f"Failed to fetch {detail_url}: {result.error}")
                self.stats.http_errors += 1
                return

            if result.status_code != 200:
                logger.error(f"Detail page returned status {result.status_code}: {detail_url}")
                self.stats.http_errors += 1
                return

            # Save raw HTML snapshot
            detail_id = self._extract_detail_id(detail_url)
            self.client.save_raw_html(result.content, f"detail_{detail_id}")

            # Parse detail page
            try:
                expediente = parse_detail_page(result.content, detail_url)
            except ValueError as e:
                logger.error(f"Parse error for {detail_url}: {e}")
                self.stats.parse_errors += 1
                self.validation_report.parse_error_details.append({
                    "url": detail_url,
                    "error": str(e),
                })
                return

            # Parse movimientos
            movimientos = parse_movimientos_table(result.content)

            # Normalize dependencies in movimientos
            for mov in movimientos:
                mov.dependencia = normalize(mov.dependencia, self.normalizer_rules)

            # Also normalize origenes if present
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
            logger.exception(f"Unexpected error processing {detail_url}: {e}")
            self.stats.parse_errors += 1
            self.validation_report.parse_error_details.append({
                "url": detail_url,
                "error": f"Unexpected error: {e}",
            })

    def _extract_detail_id(self, detail_url: str) -> str:
        """Extract the detail ID from a detail URL."""
        import re
        match = re.search(r"[?&]id=(\d+)", detail_url)
        if match:
            return match.group(1)
        # Fallback: use last path segment
        return detail_url.split("/")[-1].split("?")[0]

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
                logger.info(f"Duplicate expediente skipped: {expediente.numero}")
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

            # Insert movimientos
            for mov in movimientos:
                conn.execute(
                    """
                    INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                    VALUES (?, ?, ?, ?)
                    """,
                    (expediente_id, mov.orden, mov.fecha_recepcion, mov.dependencia),
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
                        (dep_name, dep_name),  # nombre_original same as nombre for now
                    )

    def _generate_validation_report(self) -> None:
        """Generate and log the validation report."""
        self.validation_report.print_summary()

        # Log summary
        logger.info("Scraper run completed", extra=self.stats.to_dict())

        if self.validation_report.has_critical_errors():
            logger.error("Validation failed: duplicate expedientes detected")
            sys.exit(1)


def run_scraper(year: int = 2025, semester: Optional[int] = None) -> ValidationReport:
    """
    Convenience function to run the scraper.

    Args:
        year: Year to scrape (default 2025)
        semester: Optional semester (1 or 2)

    Returns:
        ValidationReport with results.
    """
    orchestrator = ScraperOrchestrator()
    return orchestrator.run(year=year, semester=semester)


def run_scraper_cli(args: list[str]) -> int:
    """
    CLI entry point for the scraper.

    Args:
        args: Command line arguments (e.g., ['--year', '2025', '--semester', '1'])

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    import argparse

    parser = argparse.ArgumentParser(description="SUME Scraper")
    parser.add_argument("--year", type=int, default=2025, help="Year to scrape")
    parser.add_argument("--semester", type=int, choices=[1, 2], help="Semester to scrape (1 or 2)")
    parser.add_argument("--config", type=str, help="Path to config file")

    parsed = parser.parse_args(args)

    config = None
    if parsed.config:
        config = ScraperConfig.load(Path(parsed.config))

    orchestrator = ScraperOrchestrator(config)
    report = orchestrator.run(year=parsed.year, semester=parsed.semester)

    return 1 if report.has_critical_errors() else 0


if __name__ == "__main__":
    sys.exit(run_scraper_cli(sys.argv[1:]))