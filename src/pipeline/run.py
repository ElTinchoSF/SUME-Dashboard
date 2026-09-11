"""
CLI entry point for the SUME Dashboard pipeline.

Usage:
    python -m src.pipeline run --phase init-db
    python -m src.pipeline run --phase scraper --max-pages 5
    python -m src.pipeline run --phase analyzer
    python -m src.pipeline run --phase reporter --output reports/iso9001.md
    python -m src.pipeline run --phase all
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from src.analysis.circuits import run_full_circuit_analysis
from src.analysis.reports import generate_main_report
from src.analysis.statistics import run_full_statistics_analysis
from src.config import get_settings
from src.database import get_connection, init_database as db_init_database


def init_database() -> int:
    """
    Initialize the database schema.

    Returns:
        int: Exit code (0 for success).
    """
    print("Initializing database...")
    try:
        # This will create tables and indexes via connection initialization
        conn = get_connection()
        # Force schema initialization
        from src.database.connection import _initialize_schema
        _initialize_schema(conn)
        print("Database initialized successfully.")
        print(f"Database location: {get_settings().database.path}")
        return 0
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return 1


def run_scraper(max_pages: Optional[int] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> int:
    """
    Run the scraper phase.

    Args:
        max_pages: Maximum pages to scrape. If None, scrapes all pages.
        date_from: Filter expedientes created from this date (YYYY-MM-DD).
        date_to: Filter expedientes created up to this date (YYYY-MM-DD).

    Returns:
        int: Exit code (0 for success).
    """
    from src.scraper.main import run_scraper as scrape

    print(f"Running scraper phase{' (max ' + str(max_pages) + ' pages)' if max_pages else ''}...")
    if date_from or date_to:
        print(f"  - Date filter: {date_from or '...'} to {date_to or '...'}")
        print(f"  - Using advanced search with date filters")
    report = scrape(max_pages=max_pages, date_from=date_from, date_to=date_to)
    report.print_summary()

    return 1 if report.has_critical_errors() else 0


def _filter_expedientes_by_date(date_from: Optional[str], date_to: Optional[str]) -> None:
    """
    Filter expedientes by creation date, removing those outside the range.

    This runs AFTER scraping to ensure we only keep expedientes within the
    specified date range, while preserving their complete movements.

    Args:
        date_from: Start date (YYYY-MM-DD) or None for no lower bound.
        date_to: End date (YYYY-MM-DD) or None for no upper bound.
    """
    from src.database import get_connection, transaction

    conn = get_connection()

    # Build WHERE clause
    where_clauses = []
    params = []

    if date_from:
        where_clauses.append("fecha_alta >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("fecha_alta <= ?")
        params.append(date_to)

    if not where_clauses:
        return

    where_clause = "WHERE " + " AND ".join(where_clauses)

    # Count expedientes to be removed
    count_query = f"SELECT COUNT(*) FROM expedientes {where_clause}"
    cursor = conn.execute(count_query, params)
    count_to_keep = cursor.fetchone()[0]

    # Count total
    total_query = "SELECT COUNT(*) FROM expedientes"
    cursor = conn.execute(total_query)
    total_count = cursor.fetchone()[0]

    count_to_remove = total_count - count_to_keep

    if count_to_remove > 0:
        print(f"\n  - Filtering by date: keeping {count_to_keep} expedientes, removing {count_to_remove}")

        # Get IDs of expedientes to keep
        keep_query = f"SELECT id FROM expedientes {where_clause}"
        cursor = conn.execute(keep_query, params)
        keep_ids = {row[0] for row in cursor.fetchall()}

        # Get all expediente IDs
        cursor = conn.execute("SELECT id FROM expedientes")
        all_ids = {row[0] for row in cursor.fetchall()}

        # IDs to remove
        remove_ids = all_ids - keep_ids

        if remove_ids:
            with transaction() as conn:
                # Remove movimientos for expedientes to delete
                placeholders = ",".join("?" * len(remove_ids))
                conn.execute(f"DELETE FROM movimientos WHERE expediente_id IN ({placeholders})", list(remove_ids))

                # Remove expedientes
                conn.execute(f"DELETE FROM expedientes WHERE id IN ({placeholders})", list(remove_ids))

                # Remove orphaned dependencias (optional, could keep for reference)
                # conn.execute("DELETE FROM dependencias WHERE ...")

            print(f"  - Removed {len(remove_ids)} expedientes outside date range")
    else:
        print(f"\n  - All {total_count} expedientes are within date range")


def run_analyzer() -> int:
    """
    Run the analyzer phase.

    Returns:
        int: Exit code (0 for success).
    """
    print("Running analyzer phase...")
    try:
        conn = get_connection()
        print("  - Computing circuit frequencies and identifying modal circuits...")
        circuit_result = run_full_circuit_analysis(conn)
        print(f"  - Found {len(circuit_result)} unique circuits across {circuit_result['concepto'].nunique()} conceptos")
        modal_count = int(circuit_result['es_mas_frecuente'].sum())
        print(f"  - Identified {modal_count} modal circuits")

        print("  - Computing step statistics, permanence times, outliers, dependency traffic, concept distribution...")
        stats_result = run_full_statistics_analysis(conn)
        print(f"  - Step statistics for {len(stats_result['step_statistics'])} conceptos")
        print(f"  - Permanence times for {len(stats_result['permanence_times'])} movement steps")
        print(f"  - Outliers detected: {len(stats_result['outliers'][stats_result['outliers']['outlier_type'] != 'none'])}")
        print(f"  - Dependency traffic for {len(stats_result['dependency_traffic'])} dependencias")
        print(f"  - Concept distribution for {len(stats_result['concept_distribution'])} conceptos")

        print("Analyzer phase completed successfully.")
        return 0
    except Exception as e:
        print(f"Error running analyzer: {e}", file=sys.stderr)
        return 1


def run_reporter(output: Optional[str] = None, format: str = "markdown",
                 conceptos: Optional[str] = None) -> int:
    """
    Run the reporter phase.

    Args:
        output: Output file path.
        format: Output format (markdown, pdf, excel).
        conceptos: Comma-separated list of conceptos to include.

    Returns:
        int: Exit code (0 for success).
    """
    print(f"Running reporter phase (format: {format})...")
    try:
        output_path = Path(output) if output else Path("reports/iso9001.md")
        
        # Parse conceptos filter
        conceptos_filter = None
        if conceptos:
            conceptos_filter = [c.strip() for c in conceptos.split(",") if c.strip()]
        
        conn = get_connection()
        
        # First ensure analysis is done
        print("  - Running circuit analysis...")
        run_full_circuit_analysis(conn)
        
        print("  - Running statistics analysis...")
        run_full_statistics_analysis(conn)
        
        print(f"  - Generating report: {output_path}")
        generate_main_report(
            output_path=output_path,
            format_type=format,
            conceptos_filter=conceptos_filter,
            db=conn,
            templates_dir="templates",
        )
        
        print(f"Reporter phase completed successfully. Output: {output_path}")
        return 0
    except Exception as e:
        print(f"Error running reporter: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def run_all() -> int:
    """
    Run the complete pipeline.

    Returns:
        int: Exit code (0 for success).
    """
    print("Running complete pipeline...")
    print("This will run: init-db -> scraper -> analyzer -> reporter")

    # Run each phase in sequence
    for phase_func in [init_database, run_scraper, run_analyzer, run_reporter]:
        result = phase_func()
        if result != 0:
            print(f"Pipeline failed at {phase_func.__name__}", file=sys.stderr)
            return result

    print("Pipeline completed successfully.")
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m src.pipeline",
        description="SUME Dashboard Pipeline - ETL for administrative circuit analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.pipeline run --phase init-db
  python -m src.pipeline run --phase scraper --max-pages 5
  python -m src.pipeline run --phase scraper --date-from 2026-01-01 --date-to 2026-06-30
  python -m src.pipeline run --phase analyzer
  python -m src.pipeline run --phase reporter --output reports/iso9001.md --format markdown
  python -m src.pipeline run --phase all
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a pipeline phase")
    run_parser.add_argument(
        "--phase",
        choices=["init-db", "scraper", "analyzer", "reporter", "all"],
        required=True,
        help="Pipeline phase to run",
    )
    run_parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum pages to scrape (scraper phase)",
    )
    run_parser.add_argument(
        "--date-from",
        type=str,
        help="Filter expedientes created from this date (YYYY-MM-DD, scraper phase)",
    )
    run_parser.add_argument(
        "--date-to",
        type=str,
        help="Filter expedientes created up to this date (YYYY-MM-DD, scraper phase)",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        help="Output file path for reporter phase",
    )
    run_parser.add_argument(
        "--format",
        choices=["markdown", "pdf", "excel"],
        default="markdown",
        help="Output format for reporter phase",
    )
    run_parser.add_argument(
        "--conceptos",
        type=str,
        help="Comma-separated list of conceptos for reporter phase",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:]).

    Returns:
        int: Exit code.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help()
        return 1

    # Route to appropriate phase handler
    if args.phase == "init-db":
        return init_database()
    elif args.phase == "scraper":
        return run_scraper(args.max_pages, args.date_from, args.date_to)
    elif args.phase == "analyzer":
        return run_analyzer()
    elif args.phase == "reporter":
        return run_reporter(args.output, args.format, args.conceptos)
    elif args.phase == "all":
        return run_all()
    else:
        print(f"Unknown phase: {args.phase}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())