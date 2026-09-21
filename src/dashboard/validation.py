"""
Data validation and health checks for SUME Dashboard.

Validates database schema, table presence, and data completeness
on startup. Provides a health report for display in the sidebar.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from src.config import get_settings
from src.database.connection import get_connection
from src.dashboard.logging_config import get_logger

logger = get_logger("validation")

REQUIRED_TABLES = ["expedientes", "movimientos", "dependencias", "circuitos"]
OPTIONAL_TABLES = ["asuntos"]

REQUIRED_COLUMNS = {
    "expedientes": ["id", "numero", "concepto", "fecha_alta"],
    "movimientos": ["id", "expediente_id", "orden", "fecha_recepcion", "dependencia"],
    "dependencias": ["id", "nombre", "total_expedientes"],
    "circuitos": ["id", "circuito", "concepto", "frecuencia", "es_mas_frecuente"],
}


@dataclass
class HealthIssue:
    """A single health issue found during validation."""
    level: str  # "error", "warning", "info"
    message: str
    detail: str = ""


@dataclass
class HealthReport:
    """Complete validation report for the dashboard database."""
    is_healthy: bool = True
    issues: list[HealthIssue] = field(default_factory=list)
    table_counts: dict[str, int] = field(default_factory=dict)
    db_path: str = ""
    db_size_mb: float = 0.0

    @property
    def errors(self) -> list[HealthIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[HealthIssue]:
        return [i for i in self.issues if i.level == "warning"]

    def add_error(self, message: str, detail: str = "") -> None:
        self.issues.append(HealthIssue("error", message, detail))
        self.is_healthy = False

    def add_warning(self, message: str, detail: str = "") -> None:
        self.issues.append(HealthIssue("warning", message, detail))

    def add_info(self, message: str, detail: str = "") -> None:
        self.issues.append(HealthIssue("info", message, detail))


def validate_database() -> HealthReport:
    """
    Run full validation on the dashboard database.

    Checks:
    1. DB file exists
    2. Connection works
    3. Required tables exist
    4. Required columns exist in each table
    5. Tables have data (non-empty)
    6. Data integrity basics (no NULL conceptos, etc.)

    Returns:
        HealthReport with all issues found.
    """
    report = HealthReport()

    # 1. Check DB file exists
    settings = get_settings()
    db_path = Path(settings.database.path)
    report.db_path = str(db_path)

    if not db_path.exists():
        report.add_error(
            "Base de datos no encontrada",
            f"Ruta: {db_path}",
        )
        return report

    report.db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 2)
    report.add_info(f"DB: {report.db_size_mb} MB")

    # 2. Try to connect
    try:
        conn = get_connection()
    except Exception as e:
        report.add_error(
            "No se pudo conectar a la base de datos",
            str(e),
        )
        return report

    # 3. Check required tables
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'schema_%'"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}
    except Exception as e:
        report.add_error("No se pudieron listar las tablas", str(e))
        return report

    missing_tables = [t for t in REQUIRED_TABLES if t not in existing_tables]
    if missing_tables:
        report.add_error(
            f"Tablas faltantes: {', '.join(missing_tables)}",
            "Ejecute el scraper para crear el esquema.",
        )
        return report

    # Check optional tables
    missing_optional = [t for t in OPTIONAL_TABLES if t not in existing_tables]
    if missing_optional:
        report.add_warning(
            f"Tablas opcionales no encontradas: {', '.join(missing_optional)}",
            "Algunas funciones pueden no estar disponibles.",
        )

    # 4. Check required columns
    for table, required_cols in REQUIRED_COLUMNS.items():
        try:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            existing_cols = {row[1] for row in cursor.fetchall()}
            missing_cols = [c for c in required_cols if c not in existing_cols]
            if missing_cols:
                report.add_error(
                    f"Columnas faltantes en '{table}': {', '.join(missing_cols)}",
                    "El esquema de la DB está desactualizado.",
                )
        except Exception as e:
            report.add_error(f"Error verificando columnas de '{table}'", str(e))

    # 5. Check table row counts
    for table in REQUIRED_TABLES:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            report.table_counts[table] = count

            if count == 0:
                report.add_warning(
                    f"Tabla '{table}' vacía",
                    "Los gráficos no mostrarán datos para esta sección.",
                )
        except Exception as e:
            report.add_warning(f"No se pudo contar '{table}'", str(e))

    # 6. Basic data integrity
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM expedientes WHERE concepto IS NULL OR concepto = ''"
        )
        null_conceptos = cursor.fetchone()[0]
        if null_conceptos > 0:
            report.add_warning(
                f"{null_conceptos} expedientes sin concepto",
                "Algunos expedientes no tienen categoría asignada.",
            )
    except Exception:
        pass

    try:
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT concepto) FROM expedientes"
        )
        unique_conceptos = cursor.fetchone()[0]
        report.add_info(f"{unique_conceptos} conceptos únicos")
    except Exception:
        pass

    if report.is_healthy and not report.errors:
        report.add_info("Base de datos OK")

    logger.info(
        "Validation complete: healthy=%s, errors=%d, warnings=%d",
        report.is_healthy,
        len(report.errors),
        len(report.warnings),
    )

    return report
