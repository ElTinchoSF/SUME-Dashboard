"""
Reporter module for SUME Dashboard.

CLI entry point for generating ISO 9001 evidence reports in multiple formats.
Uses Jinja2 templates for reproducible, version-controlled report generation.
"""

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import sqlite3

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.analysis.circuits import (
    compute_circuit_frequencies,
    identify_modal_circuits,
    run_full_circuit_analysis,
)
from src.analysis.statistics import run_full_statistics_analysis
from src.config import get_settings
from src.database.connection import get_connection

logger = logging.getLogger(__name__)


def get_git_commit_hash() -> str:
    """Get the short git commit hash, or 'unknown' if not available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "unknown"


def compute_data_hash(db: sqlite3.Connection) -> str:
    """
    Compute SHA256 hash of the database content for versioning.

    Hashes the row counts and key data from all main tables.
    """
    hasher = hashlib.sha256()

    tables = ["expedientes", "movimientos", "dependencias", "circuitos"]
    for table in tables:
        try:
            cursor = db.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            hasher.update(f"{table}:{count}".encode())
        except sqlite3.OperationalError:
            # Table might not exist
            pass

    # Also hash circuitos content for data sensitivity
    try:
        cursor = db.execute("SELECT circuito, concepto, frecuencia, es_mas_frecuente FROM circuitos ORDER BY id")
        for row in cursor:
            hasher.update(json.dumps(row, sort_keys=True, default=str).encode())
    except sqlite3.OperationalError:
        pass

    return hasher.hexdigest()[:12]


def get_report_version(db: sqlite3.Connection | None = None) -> str:
    """
    Generate report version string.

    Format: {date}.{commit_short}.{data_hash_short}
    Example: 2025-01-15.a1b2c3d.e4f5g6h7
    """
    if db is None:
        db = get_connection()

    date_str = datetime.now().strftime("%Y-%m-%d")
    commit = get_git_commit_hash()
    data_hash = compute_data_hash(db)

    settings = get_settings()
    version_format = settings.reporter.version_format

    return version_format.format(
        date=date_str,
        commit_short=commit,
        data_hash_short=data_hash,
    )


def setup_jinja_env(templates_dir: str | Path) -> Environment:
    """Setup Jinja2 environment with autoescape and custom filters."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Custom filters
    env.filters["to_json"] = lambda obj: json.dumps(obj, ensure_ascii=False, indent=2)
    env.filters["from_json"] = lambda s: json.loads(s)
    env.filters["format_number"] = lambda n: f"{n:,}" if isinstance(n, (int, float)) else str(n)
    env.filters["format_pct"] = lambda n: f"{n:.1f}%" if isinstance(n, (int, float)) else str(n)
    env.filters["round2"] = lambda n: round(float(n), 2) if isinstance(n, (int, float)) else n

    return env


def load_report_data(db: sqlite3.Connection | None = None, conceptos_filter: list[str] | None = None) -> dict[str, Any]:
    """
    Load all data needed for report generation.

    Args:
        db: Optional database connection.
        conceptos_filter: Optional list of conceptos to include. If None, includes all.

    Returns:
        Dictionary with all report data sections.
    """
    if db is None:
        db = get_connection()

    # Build WHERE clause for filtering
    where_clause = ""
    params = []
    if conceptos_filter:
        placeholders = ",".join(["?"] * len(conceptos_filter))
        where_clause = f"WHERE concepto IN ({placeholders})"
        params = conceptos_filter

    # Load circuit frequencies
    circuit_query = f"""
        SELECT circuito, concepto, frecuencia, es_mas_frecuente
        FROM circuitos
        {where_clause}
        ORDER BY concepto, frecuencia DESC
    """
    circuitos_df = pd.read_sql_query(circuit_query, db, params=params)

    # Load expedientes for summary stats
    exp_query = f"""
        SELECT concepto, COUNT(*) as total_expedientes,
               MIN(fecha_alta) as primera_fecha, MAX(fecha_alta) as ultima_fecha
        FROM expedientes
        {where_clause}
        GROUP BY concepto
    """
    expedientes_df = pd.read_sql_query(exp_query, db, params=params)

    # Load movimientos for detail
    mov_query = f"""
        SELECT e.concepto, m.orden, m.fecha_recepcion, m.dependencia, e.numero
        FROM movimientos m
        JOIN expedientes e ON m.expediente_id = e.id
        {where_clause}
        ORDER BY e.concepto, e.numero, m.orden
    """
    movimientos_df = pd.read_sql_query(mov_query, db, params=params)

    # Run full analyses
    circuit_analysis = run_full_circuit_analysis(db)
    stats_analysis = run_full_statistics_analysis(db)

    # Filter stats by conceptos if needed
    if conceptos_filter:
        for key, df in stats_analysis.items():
            if isinstance(df, pd.DataFrame) and "concepto" in df.columns:
                stats_analysis[key] = df[df["concepto"].isin(conceptos_filter)]

    # Prepare modal circuits for easy template access
    modal_circuits = {}
    if not circuit_analysis.empty:
        modal = circuit_analysis[circuit_analysis["es_mas_frecuente"]]
        for _, row in modal.iterrows():
            modal_circuits[row["concepto"]] = {
                "circuito": json.loads(row["circuito_json"]),
                "frecuencia": int(row["frecuencia"]),
                "total_concepto": int(circuit_analysis[circuit_analysis["concepto"] == row["concepto"]]["frecuencia"].sum()),
            }

    # Prepare concept summaries
    concept_summaries = {}
    for _, row in expedientes_df.iterrows():
        concepto = row["concepto"]
        concept_circuits = circuit_analysis[circuit_analysis["concepto"] == concepto]
        concept_summaries[concepto] = {
            "total_expedientes": int(row["total_expedientes"]),
            "primera_fecha": row["primera_fecha"],
            "ultima_fecha": row["ultima_fecha"],
            "unique_circuits": len(concept_circuits),
            "modal_circuit": modal_circuits.get(concepto),
        }

    return {
        "version": get_report_version(db),
        "generated_at": datetime.now().isoformat(),
        "conceptos_filter": conceptos_filter,
        "concept_summaries": concept_summaries,
        "circuitos": circuit_analysis.to_dict("records") if not circuit_analysis.empty else [],
        "step_statistics": stats_analysis["step_statistics"].to_dict("records") if not stats_analysis["step_statistics"].empty else [],
        "permanence_by_dependencia": stats_analysis["permanence_by_dependencia"].to_dict("records") if not stats_analysis["permanence_by_dependencia"].empty else [],
        "outliers": stats_analysis["outliers"].to_dict("records") if not stats_analysis["outliers"].empty else [],
        "dependency_traffic": stats_analysis["dependency_traffic"].to_dict("records") if not stats_analysis["dependency_traffic"].empty else [],
        "concept_distribution": stats_analysis["concept_distribution"].to_dict("records") if not stats_analysis["concept_distribution"].empty else [],
        "movimientos": movimientos_df.to_dict("records") if not movimientos_df.empty else [],
        "modal_circuits": modal_circuits,
    }


def render_template(env: Environment, template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template with the given context."""
    template = env.get_template(template_name)
    return template.render(**context)


def write_output(content: str, output_path: Path, format_type: str) -> None:
    """Write rendered content to file in the specified format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format_type == "markdown":
        output_path.write_text(content, encoding="utf-8")
    elif format_type == "pdf":
        # For PDF, we'd need weasyprint - write markdown and note conversion needed
        md_path = output_path.with_suffix(".md")
        md_path.write_text(content, encoding="utf-8")
        logger.info(f"Markdown written to {md_path}. Convert to PDF with: weasyprint {md_path} {output_path}")
        # Try to convert if weasyprint available
        try:
            import weasyprint
            weasyprint.HTML(string=content).write_pdf(str(output_path))
            logger.info(f"PDF generated at {output_path}")
        except ImportError:
            logger.warning("weasyprint not installed, PDF not generated. Install with: pip install weasyprint")
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
    elif format_type == "excel":
        # For Excel, we write structured data to multiple sheets
        import openpyxl
        from openpyxl.utils.dataframe import dataframe_to_rows

        wb = openpyxl.Workbook()

        # Summary sheet
        ws = wb.active
        ws.title = "Resumen"
        ws.append(["Métrica", "Valor"])
        ws.append(["Versión", context.get("version", "unknown")])
        ws.append(["Generado", context.get("generated_at", "unknown")])
        ws.append(["Conceptos filtrados", ", ".join(context.get("conceptos_filter", ["Todos"]))])

        # Concept distribution
        if context.get("concept_distribution"):
            ws2 = wb.create_sheet("Distribución Conceptos")
            df = pd.DataFrame(context["concept_distribution"])
            for r in dataframe_to_rows(df, index=False, header=True):
                ws2.append(r)

        # Circuitos
        if context.get("circuitos"):
            ws3 = wb.create_sheet("Circuitos")
            df = pd.DataFrame(context["circuitos"])
            for r in dataframe_to_rows(df, index=False, header=True):
                ws3.append(r)

        # Step statistics
        if context.get("step_statistics"):
            ws4 = wb.create_sheet("Estadísticas Pasos")
            df = pd.DataFrame(context["step_statistics"])
            for r in dataframe_to_rows(df, index=False, header=True):
                ws4.append(r)

        # Dependency traffic
        if context.get("dependency_traffic"):
            ws5 = wb.create_sheet("Tráfico Dependencias")
            df = pd.DataFrame(context["dependency_traffic"])
            for r in dataframe_to_rows(df, index=False, header=True):
                ws5.append(r)

        # Outliers
        if context.get("outliers"):
            ws6 = wb.create_sheet("Outliers")
            df = pd.DataFrame(context["outliers"])
            for r in dataframe_to_rows(df, index=False, header=True):
                ws6.append(r)

        wb.save(output_path)
        logger.info(f"Excel report generated at {output_path}")
    else:
        raise ValueError(f"Unsupported format: {format_type}")


def generate_main_report(
    output_path: Path,
    format_type: str,
    conceptos_filter: list[str] | None = None,
    db: sqlite3.Connection | None = None,
    templates_dir: str | Path = "templates",
) -> None:
    """Generate the main ISO 9001 report."""
    env = setup_jinja_env(templates_dir)

    # Load data
    global context
    context = load_report_data(db, conceptos_filter)

    # Render main template
    content = render_template(env, "report_main.md.j2", context)

    # Write output
    write_output(content, output_path, format_type)

    logger.info(f"Main report generated: {output_path} ({format_type})")


def generate_concepto_report(
    concepto: str,
    output_path: Path,
    format_type: str,
    db: sqlite3.Connection | None = None,
    templates_dir: str | Path = "templates",
) -> None:
    """Generate a per-concepto evidence sheet report."""
    env = setup_jinja_env(templates_dir)

    # Load data filtered to this concepto
    context = load_report_data(db, [concepto])
    context["single_concepto"] = concepto

    # Render concepto template
    content = render_template(env, "report_concepto.md.j2", context)

    # Write output
    write_output(content, output_path, format_type)

    logger.info(f"Concepto report for '{concepto}' generated: {output_path} ({format_type})")


def main() -> int:
    """CLI entry point for report generation."""
    parser = argparse.ArgumentParser(
        description="Generate ISO 9001 evidence reports from SUME Dashboard analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate main report in Markdown
  python -m src.analysis.reports --output reports/iso9001.md --format markdown

  # Generate main report in PDF
  python -m src.analysis.reports --output reports/iso9001.pdf --format pdf

  # Generate main report in Excel
  python -m src.analysis.reports --output reports/iso9001.xlsx --format excel

  # Generate report for specific conceptos
  python -m src.analysis.reports --output reports/iso9001.md --format markdown --conceptos "Gestión Alumno,Gestión de Becas"

  # Generate per-concepto evidence sheets
  python -m src.analysis.reports --output reports/concepto --format markdown --concepto "Gestión Alumno"

  # Auto-versioning
  python -m src.analysis.reports --output reports/iso9001.md --format markdown --version-auto
        """,
    )

    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file path (for single report) or directory (for multi-concepto)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "pdf", "excel"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--conceptos", "-c",
        help="Comma-separated list of conceptos to include in main report"
    )
    parser.add_argument(
        "--concepto",
        help="Single concepto for evidence sheet report (generates report_concepto template)"
    )
    parser.add_argument(
        "--version-auto",
        action="store_true",
        help="Auto-generate version from date, git commit, and data hash"
    )
    parser.add_argument(
        "--templates-dir", "-t",
        default="templates",
        help="Directory containing Jinja2 templates (default: templates)"
    )
    parser.add_argument(
        "--db-path",
        help="Path to SQLite database (overrides config.yaml)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Override DB path if provided
    if args.db_path:
        import os
        os.environ["SUME_DB_PATH"] = args.db_path
        from src.config import reload_settings
        reload_settings()

    db = get_connection()

    try:
        output_path = Path(args.output)

        if args.concepto:
            # Per-concepto evidence sheet
            if output_path.suffix == "":
                # Directory provided, create file inside
                safe_name = args.concepto.replace(" ", "_").replace("/", "_")
                output_path = output_path / f"reporte_{safe_name}.{args.format if args.format != 'excel' else 'xlsx'}"

            generate_concepto_report(
                concepto=args.concepto,
                output_path=output_path,
                format_type=args.format,
                db=db,
                templates_dir=args.templates_dir,
            )
        else:
            # Main report
            conceptos_filter = None
            if args.conceptos:
                conceptos_filter = [c.strip() for c in args.conceptos.split(",") if c.strip()]

            generate_main_report(
                output_path=output_path,
                format_type=args.format,
                conceptos_filter=conceptos_filter,
                db=db,
                templates_dir=args.templates_dir,
            )

        if args.version_auto:
            version = get_report_version(db)
            logger.info(f"Report version: {version}")

        return 0

    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())