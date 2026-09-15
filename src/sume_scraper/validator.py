"""
SUME Scraper - Validaciones post-scraping.

Proporciona validaciones para verificar la integridad y completitud
de los datos después del scraping.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ValidationIssue:
    """Un problema encontrado durante la validación."""
    level: str  # "ERROR", "WARNING", "INFO"
    category: str
    message: str
    details: Optional[str] = None


@dataclass
class ValidationReport:
    """Reporte de validación del scraping."""
    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    
    def add_issue(self, level: str, category: str, message: str, details: Optional[str] = None) -> None:
        """Agregar un issue al reporte."""
        self.issues.append(ValidationIssue(level, category, message, details))
    
    def has_errors(self) -> bool:
        """Verificar si hay errores críticos."""
        return any(issue.level == "ERROR" for issue in self.issues)
    
    def has_warnings(self) -> bool:
        """Verificar si hay advertencias."""
        return any(issue.level == "WARNING" for issue in self.issues)
    
    def summary(self) -> str:
        """Obtener resumen del reporte."""
        errors = sum(1 for i in self.issues if i.level == "ERROR")
        warnings = sum(1 for i in self.issues if i.level == "WARNING")
        info = sum(1 for i in self.issues if i.level == "INFO")
        
        lines = [
            "=" * 60,
            "REPORTE DE VALIDACIÓN",
            "=" * 60,
            f"Errores: {errors}",
            f"Advertencias: {warnings}",
            f"Información: {info}",
            "",
        ]
        
        if self.stats:
            lines.append("Estadísticas:")
            for key, value in self.stats.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        
        if self.issues:
            lines.append("Issues encontrados:")
            for issue in self.issues:
                prefix = "  ❌" if issue.level == "ERROR" else "  ⚠️" if issue.level == "WARNING" else "  ℹ️"
                lines.append(f"{prefix} [{issue.category}] {issue.message}")
                if issue.details:
                    lines.append(f"      {issue.details}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def print_summary(self) -> None:
        """Imprimir resumen del reporte."""
        print(self.summary())


class ScrapingValidator:
    """
    Validador de datos post-scraping.
    
    Ejecuta varias validaciones para verificar la integridad
    y completitud de los datos en la base de datos.
    """
    
    def __init__(self, db_path: str):
        """
        Inicializar el validador.
        
        Args:
            db_path: Ruta a la base de datos SQLite
        """
        self.db_path = db_path
    
    def validate(self) -> ValidationReport:
        """
        Ejecutar todas las validaciones.
        
        Returns:
            Reporte de validación
        """
        report = ValidationReport()
        
        # Verificar que la DB existe
        if not Path(self.db_path).exists():
            report.add_issue("ERROR", "DB", f"Base de datos no encontrada: {self.db_path}")
            return report
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # 1. Verificar integridad de esquema
            self._check_schema(conn, report)
            
            # 2. Verificar integridad de datos
            self._check_data_integrity(conn, report)
            
            # 3. Verificar duplicados
            self._check_duplicates(conn, report)
            
            # 4. Verificar rangos de fechas
            self._check_date_ranges(conn, report)
            
            # 5. Verificar completitud
            self._check_completeness(conn, report)
            
            # 6. Recopilar estadísticas
            self._collect_stats(conn, report)
            
        finally:
            conn.close()
        
        return report
    
    def _check_schema(self, conn: sqlite3.Connection, report: ValidationReport) -> None:
        """Verificar que el esquema de la DB es correcto."""
        required_tables = ["expedientes", "movimientos", "dependencias"]
        
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        for table in required_tables:
            if table not in existing_tables:
                report.add_issue("ERROR", "SCHEMA", f"Tabla '{table}' no existe")
    
    def _check_data_integrity(self, conn: sqlite3.Connection, report: ValidationReport) -> None:
        """Verificar integridad de los datos."""
        # Verificar que no hay expedientes sin número
        cursor = conn.execute(
            "SELECT COUNT(*) FROM expedientes WHERE numero IS NULL OR numero = ''"
        )
        count = cursor.fetchone()[0]
        if count > 0:
            report.add_issue("ERROR", "INTEGRITY", f"{count} expedientes sin número")
        
        # Verificar que no hay expedientes sin concepto
        cursor = conn.execute(
            "SELECT COUNT(*) FROM expedientes WHERE concepto IS NULL OR concepto = ''"
        )
        count = cursor.fetchone()[0]
        if count > 0:
            report.add_issue("WARNING", "INTEGRITY", f"{count} expedientes sin concepto")
        
        # Verificar que no hay expedientes sin fecha
        cursor = conn.execute(
            "SELECT COUNT(*) FROM expedientes WHERE fecha_alta IS NULL"
        )
        count = cursor.fetchone()[0]
        if count > 0:
            report.add_issue("ERROR", "INTEGRITY", f"{count} expedientes sin fecha_alta")
        
        # Verificar movimientos sin dependencia
        cursor = conn.execute(
            "SELECT COUNT(*) FROM movimientos WHERE dependencia IS NULL OR dependencia = ''"
        )
        count = cursor.fetchone()[0]
        if count > 0:
            report.add_issue("WARNING", "INTEGRITY", f"{count} movimientos sin dependencia")
    
    def _check_duplicates(self, conn: sqlite3.Connection, report: ValidationReport) -> None:
        """Verificar duplicados."""
        cursor = conn.execute(
            """SELECT numero, COUNT(*) as cnt 
               FROM expedientes 
               GROUP BY numero 
               HAVING cnt > 1"""
        )
        duplicates = cursor.fetchall()
        
        if duplicates:
            report.add_issue(
                "WARNING",
                "DUPLICATES",
                f"{len(duplicates)} expedientes duplicados",
                f"Primeros: {', '.join(d[0] for d in duplicates[:5])}"
            )
    
    def _check_date_ranges(self, conn: sqlite3.Connection, report: ValidationReport) -> None:
        """Verificar rangos de fechas."""
        # Obtener rango de fechas en la DB
        cursor = conn.execute(
            "SELECT MIN(fecha_alta), MAX(fecha_alta) FROM expedientes"
        )
        min_date, max_date = cursor.fetchone()
        
        if min_date and max_date:
            report.stats["fecha_minima"] = min_date
            report.stats["fecha_maxima"] = max_date
            
            # Verificar si hay fechas fuera de rango razonable
            try:
                min_dt = datetime.strptime(min_date, "%Y-%m-%d")
                max_dt = datetime.strptime(max_date, "%Y-%m-%d")
                
                # Verificar si el rango es mayor a 5 años
                if (max_dt - min_dt).days > 5 * 365:
                    report.add_issue(
                        "WARNING",
                        "DATE_RANGE",
                        f"Rango de fechas muy amplio: {min_date} a {max_date}"
                    )
            except ValueError:
                report.add_issue("WARNING", "DATE_RANGE", "Formato de fecha inválido en la DB")
    
    def _check_completeness(self, conn: sqlite3.Connection, report: ValidationReport) -> None:
        """Verificar completitud de los datos."""
        # Contar expedientes
        cursor = conn.execute("SELECT COUNT(*) FROM expedientes")
        total_expedientes = cursor.fetchone()[0]
        
        # Contar expedientes con movimientos
        cursor = conn.execute(
            """SELECT COUNT(DISTINCT e.id) 
               FROM expedientes e 
               INNER JOIN movimientos m ON e.id = m.expediente_id"""
        )
        expedientes_con_movimientos = cursor.fetchone()[0]
        
        # Calcular porcentaje de completitud
        if total_expedientes > 0:
            porcentaje = (expedientes_con_movimientos / total_expedientes) * 100
            report.stats["expedientes_totales"] = total_expedientes
            report.stats["expedientes_con_movimientos"] = expedientes_con_movimientos
            report.stats["completitud_movimientos"] = f"{porcentaje:.1f}%"
            
            if porcentaje < 90:
                report.add_issue(
                    "WARNING",
                    "COMPLETENESS",
                    f"Solo {porcentaje:.1f}% de expedientes tienen movimientos"
                )
    
    def _collect_stats(self, conn: sqlite3.Connection, report: ValidationReport) -> None:
        """Recopilar estadísticas generales."""
        # Contar movimientos
        cursor = conn.execute("SELECT COUNT(*) FROM movimientos")
        report.stats["total_movimientos"] = cursor.fetchone()[0]
        
        # Contar dependencias
        cursor = conn.execute("SELECT COUNT(*) FROM dependencias")
        report.stats["total_dependencias"] = cursor.fetchone()[0]
        
        # Contar conceptos únicos
        cursor = conn.execute("SELECT COUNT(DISTINCT concepto) FROM expedientes")
        report.stats["conceptos_unicos"] = cursor.fetchone()[0]
        
        # Distribución por concepto
        cursor = conn.execute(
            """SELECT concepto, COUNT(*) as cnt 
               FROM expedientes 
               GROUP BY concepto 
               ORDER BY cnt DESC 
               LIMIT 5"""
        )
        top_conceptos = cursor.fetchall()
        report.stats["top_conceptos"] = {c[0]: c[1] for c in top_conceptos}
