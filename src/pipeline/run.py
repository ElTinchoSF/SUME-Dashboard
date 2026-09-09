"""
CLI entry point for the SUME Dashboard pipeline.

Usage:
    python -m src.pipeline run --phase init-db
    python -m src.pipeline run --phase scraper --semester 1
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


def run_scraper(semester: Optional[int] = None) -> int:
    """
    Run the scraper phase.

    Args:
        semester: Optional semester to scrape (1 or 2). If None, scrapes full year.

    Returns:
        int: Exit code (0 for success).
    """
    print(f"Running scraper phase{' for semester ' + str(semester) if semester else ''}...")
    # TODO: Implement scraper orchestration (Phase 2)
    print("Scraper not yet implemented (Phase 2).")
    print("This will:")
    print("  - Search SUME with faculty FBCB and date range")
    print("  - Paginate through all result pages")
    print("  - Fetch, parse, normalize, and persist each expediente")
    print("  - Save raw HTML snapshots to data/raw/")
    print("  - Generate validation report")
    return 0


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
  python -m src.pipeline run --phase scraper --semester 1
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
        "--semester",
        type=int,
        choices=[1, 2],
        help="Semester for scraper phase (1 or 2)",
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
        return run_scraper(args.semester)
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