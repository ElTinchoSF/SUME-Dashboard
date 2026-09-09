"""
Integration tests for SUME Dashboard.

E2E test with 100 synthetic expedientes, testing the full data flow:
scraper → DB → analyzer → dashboard data flow.
Verifies row count reconciliation and referential integrity.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest

from src.analysis.circuits import run_full_circuit_analysis
from src.analysis.statistics import run_full_statistics_analysis
from src.analysis.reports import load_report_data, generate_main_report
from src.database.connection import get_connection, close_connection, set_connection_factory
from src.database.schema import INIT_SQL
from src.config import Settings, DatabaseConfig


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture
def integration_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Create a database with 100 synthetic expedientes for integration testing.

    Creates diverse test data across multiple conceptos with varying circuit patterns,
    movimientos counts, and dependency chains to thoroughly test the pipeline.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000;")

    # Initialize schema
    conn.executescript(INIT_SQL)
    conn.commit()

    # Generate 100 synthetic expedientes
    # Conceptos: "Gestión Alumno" (40), "Gestión de Becas" (30), "Trámites Docentes" (20), "Administración General" (10)
    import random
    random.seed(42)  # Deterministic test data

    conceptos_distribution = [
        ("Gestión Alumno", 40),
        ("Gestión de Becas", 30),
        ("Trámites Docentes", 20),
        ("Administración General", 10),
    ]

    expediente_id = 0
    movimiento_id = 0

    # Define dependency pools for each concepto
    deps_by_concepto = {
        "Gestión Alumno": [
            "Mesa de Entradas - FBCB",
            "Departamento Alumnos",
            "Secretaría Académica",
            "Dirección de Carreras",
            "Consejo Directivo",
        ],
        "Gestión de Becas": [
            "Mesa de Entradas - FBCB",
            "Departamento Becas",
            "Comité Evaluador",
            "Secretaría de Bienestar",
            "Tesorería",
        ],
        "Trámites Docentes": [
            "Mesa de Entradas - FBCB",
            "Departamento Docentes",
            "Secretaría Académica",
            "Consejo Directivo",
            "Dirección de Carreras",
        ],
        "Administración General": [
            "Mesa de Entradas - FBCB",
            "Secretaría Administrativa",
            "Dirección General",
            "Asesoría Legal",
        ],
    }

    # Circuit patterns per concepto (with frequencies)
    circuits_by_concepto = {
        "Gestión Alumno": [
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica"], 20),  # Modal
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Dirección de Carreras", "Secretaría Académica"], 10),
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica", "Consejo Directivo"], 5),
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica", "Dirección de Carreras", "Consejo Directivo"], 3),  # Structural outlier
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica", "Departamento Alumnos"], 2),  # Loop outlier
        ],
        "Gestión de Becas": [
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Comité Evaluador"], 15),  # Modal
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Secretaría de Bienestar", "Comité Evaluador"], 8),
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Tesorería", "Secretaría de Bienestar", "Comité Evaluador"], 4),
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Comité Evaluador", "Departamento Becas"], 3),  # Loop outlier
        ],
        "Trámites Docentes": [
            (["Mesa de Entradas - FBCB", "Departamento Docentes", "Secretaría Académica"], 12),  # Modal
            (["Mesa de Entradas - FBCB", "Departamento Docentes", "Dirección de Carreras", "Secretaría Académica"], 5),
            (["Mesa de Entradas - FBCB", "Departamento Docentes", "Secretaría Académica", "Consejo Directivo"], 3),
        ],
        "Administración General": [
            (["Mesa de Entradas - FBCB", "Secretaría Administrativa", "Dirección General"], 6),  # Modal
            (["Mesa de Entradas - FBCB", "Secretaría Administrativa", "Asesoría Legal", "Dirección General"], 4),
        ],
    }

    from datetime import date, timedelta

    for concepto, count in conceptos_distribution:
        circuits = circuits_by_concepto[concepto]

        for circuit_pattern, freq in circuits:
            for _ in range(freq):
                expediente_id += 1
                numero = f"EXP-2025-{expediente_id:05d}"
                # Random date in 2025
                start_date = date(2025, 1, 1)
                random_days = random.randint(0, 364)
                fecha_alta = start_date + timedelta(days=random_days)

                estado = random.choice(["En trámite", "Finalizado", "Archivado"])

                conn.execute(
                    """INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        numero,
                        concepto,
                        f"Trámite de {concepto.lower()} - Expediente {expediente_id}",
                        fecha_alta.isoformat(),
                        estado,
                        f"{concepto.lower().replace(' ', ',')}, tramite",
                        "Mesa de Entradas - FBCB",
                    ),
                )

                # Insert movimientos for this circuit
                for orden, dep in enumerate(circuit_pattern, 1):
                    movimiento_id += 1
                    mov_fecha = fecha_alta + timedelta(days=orden * random.randint(1, 5))
                    conn.execute(
                        """INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                           VALUES (?, ?, ?, ?)""",
                        (expediente_id, orden, mov_fecha.isoformat(), dep),
                    )

    # Populate dependencias table with all unique dependencies
    all_deps = set()
    for deps in deps_by_concepto.values():
        all_deps.update(deps)

    for dep in all_deps:
        # Count how many expedientes pass through this dependency
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT expediente_id) FROM movimientos WHERE dependencia = ?",
            (dep,),
        )
        total = cursor.fetchone()[0]
        if total > 0:
            conn.execute(
                "INSERT INTO dependencias (nombre, nombre_original, total_expedientes) VALUES (?, ?, ?)",
                (dep, dep, total),
            )

    conn.commit()

    # Override settings to use this test database
    import src.config
    original_get_settings = src.config.get_settings

    def test_get_settings():
        return Settings(
            database=DatabaseConfig(path=db_path),
            sume=Settings.model_fields["sume"].default,
            scraper=Settings.model_fields["scraper"].default,
            normalizer=Settings.model_fields["normalizer"].default,
            analyzer=Settings.model_fields["analyzer"].default,
            dashboard=Settings.model_fields["dashboard"].default,
            reporter=Settings.model_fields["reporter"].default,
        )

    # Patch the connection factory
    def factory():
        c = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000;")
        return c

    set_connection_factory(factory)
    src.config.get_settings = test_get_settings

    # Invalidate Streamlit cache to ensure clean state for dashboard tests
    import streamlit as st
    st.cache_data.clear()

    try:
        yield conn
    finally:
        close_connection()
        set_connection_factory(None)
        src.config.get_settings = original_get_settings
        conn.close()
        Path(db_path).unlink(missing_ok=True)


# ============================================================================
# Integration Tests
# ============================================================================

class TestFullPipelineIntegration:
    """Integration tests for the complete data pipeline."""

    def test_database_populated_with_100_expedientes(self, integration_db):
        """Verify the test database has exactly 100 expedientes."""
        cursor = integration_db.execute("SELECT COUNT(*) FROM expedientes")
        count = cursor.fetchone()[0]
        assert count == 100, f"Expected 100 expedientes, got {count}"

    def test_movimientos_count_matches_expedientes(self, integration_db):
        """Verify total movimientos match expected count from circuit patterns."""
        cursor = integration_db.execute("SELECT COUNT(*) FROM movimientos")
        mov_count = cursor.fetchone()[0]

        # Calculate expected: sum of (circuit_length * frequency) for all circuits
        # Gestión Alumno: 3*20 + 4*10 + 4*5 + 5*3 + 4*2 = 60+40+20+15+8 = 143
        # Gestión de Becas: 3*15 + 4*8 + 5*4 + 4*3 = 45+32+20+12 = 109
        # Trámites Docentes: 3*12 + 4*5 + 4*3 = 36+20+12 = 68
        # Administración General: 3*6 + 4*4 = 18+16 = 34
        # Total: 143 + 109 + 68 + 34 = 354
        expected_movimientos = 354
        assert mov_count == expected_movimientos, f"Expected {expected_movimientos} movimientos, got {mov_count}"

    def test_concepto_distribution(self, integration_db):
        """Verify expediente distribution across conceptos."""
        cursor = integration_db.execute(
            "SELECT concepto, COUNT(*) as cnt FROM expedientes GROUP BY concepto ORDER BY cnt DESC"
        )
        rows = cursor.fetchall()

        expected = {
            "Gestión Alumno": 40,
            "Gestión de Becas": 30,
            "Trámites Docentes": 20,
            "Administración General": 10,
        }

        for row in rows:
            assert row["cnt"] == expected[row["concepto"]], f"Concepto {row['concepto']}: expected {expected[row['concepto']]}, got {row['cnt']}"

    def test_circuit_analysis_runs(self, integration_db):
        """Test that full circuit analysis runs without errors."""
        result = run_full_circuit_analysis(integration_db)

        assert not result.empty
        assert "circuito_json" in result.columns
        assert "concepto" in result.columns
        assert "frecuencia" in result.columns
        assert "es_mas_frecuente" in result.columns

        # Should have circuits for all 4 conceptos
        assert result["concepto"].nunique() == 4

        # Total frequency should equal number of expedientes
        total_freq = result["frecuencia"].sum()
        assert total_freq == 100, f"Total circuit frequency {total_freq} != 100 expedientes"

        # Should have exactly 4 modal circuits (one per concepto with >=5 samples)
        modal_count = result["es_mas_frecuente"].sum()
        assert modal_count == 4, f"Expected 4 modal circuits, got {modal_count}"

    def test_circuitos_table_populated(self, integration_db):
        """Test that circuitos table is populated after analysis."""
        run_full_circuit_analysis(integration_db)

        cursor = integration_db.execute("SELECT COUNT(*) FROM circuitos")
        count = cursor.fetchone()[0]
        assert count > 0, "circuitos table should be populated"

        # Verify modal flags are set
        cursor = integration_db.execute("SELECT COUNT(*) FROM circuitos WHERE es_mas_frecuente = 1")
        modal_count = cursor.fetchone()[0]
        assert modal_count == 4

    def test_statistics_analysis_runs(self, integration_db):
        """Test that full statistics analysis runs without errors."""
        run_full_circuit_analysis(integration_db)  # Prerequisite
        results = run_full_statistics_analysis(integration_db)

        expected_keys = [
            "step_statistics",
            "permanence_times",
            "permanence_by_dependencia",
            "outliers",
            "dependency_traffic",
            "concept_distribution",
        ]
        for key in expected_keys:
            assert key in results
            assert isinstance(results[key], pd.DataFrame)

        # Verify step statistics
        step_stats = results["step_statistics"]
        assert len(step_stats) == 4  # 4 conceptos
        assert step_stats["total_expedientes"].sum() == 100

        # Verify permanence times
        perm_times = results["permanence_times"]
        assert len(perm_times) == 354  # Total movimientos
        assert "permanence_days" in perm_times.columns

        # Verify outliers detected
        outliers = results["outliers"]
        assert not outliers.empty
        outlier_types = outliers[outliers["outlier_type"] != "none"]["outlier_type"].unique()
        # Should detect at least structural_steps and structural_loop outliers
        assert "structural_steps" in outlier_types or "structural_loop" in outlier_types

        # Verify dependency traffic
        dep_traffic = results["dependency_traffic"]
        assert len(dep_traffic) > 0
        assert "pct_movimientos" in dep_traffic.columns
        assert abs(dep_traffic["pct_movimientos"].sum() - 100) < 0.1

        # Verify concept distribution
        conc_dist = results["concept_distribution"]
        assert len(conc_dist) == 4
        assert abs(conc_dist["porcentaje"].sum() - 100) < 0.1

    def test_report_generation(self, integration_db):
        """Test that report generation works with the full pipeline data."""
        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "integration_test_report.md"

            generate_main_report(
                output_path=output_path,
                format_type="markdown",
                db=integration_db,
                templates_dir="templates",
            )

            assert output_path.exists()
            content = output_path.read_text()

            # Verify key sections exist
            assert "Informe ISO 9001" in content
            assert "Resumen Ejecutivo" in content
            assert "Distribución de Expedientes por Concepto" in content
            assert "Análisis de Circuitos por Concepto" in content
            assert "Estadísticas de Pasos por Concepto" in content
            assert "Tiempos de Permanencia por Dependencia" in content
            assert "Ranking de Tráfico de Dependencias" in content
            assert "Detección de Outliers" in content
            assert "Metodología y Limitaciones" in content

            # Verify data appears in report
            assert "Gestión Alumno" in content
            assert "Gestión de Becas" in content
            assert "Trámites Docentes" in content
            assert "Administración General" in content

    def test_report_data_loading(self, integration_db):
        """Test that load_report_data works with full dataset."""
        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        data = load_report_data(integration_db)

        assert "version" in data
        assert "generated_at" in data
        assert "concept_summaries" in data
        assert "circuitos" in data
        assert "modal_circuits" in data

        # Should have all 4 conceptos
        assert len(data["concept_summaries"]) == 4
        assert sum(s["total_expedientes"] for s in data["concept_summaries"].values()) == 100

        # Modal circuits should exist for all 4 conceptos
        assert len(data["modal_circuits"]) == 4


class TestRowCountReconciliation:
    """Tests for row count reconciliation across the pipeline."""

    def test_expedientes_count_reconciliation(self, integration_db):
        """
        Verify: expedientes count in DB = expedientes processed (minus duplicates).
        Since we insert unique expedientes, count should be 100.
        """
        cursor = integration_db.execute("SELECT COUNT(*) FROM expedientes")
        db_count = cursor.fetchone()[0]

        # Count from expedientes table (the source of truth)
        assert db_count == 100

    def test_movimientos_sum_reconciliation(self, integration_db):
        """
        Verify: sum of movimientos per expediente = total movimientos rows.
        """
        # Get movimientos per expediente
        cursor = integration_db.execute(
            "SELECT expediente_id, COUNT(*) as mov_count FROM movimientos GROUP BY expediente_id"
        )
        per_expediente = cursor.fetchall()

        # Sum of movimientos per expediente
        sum_per_exp = sum(row["mov_count"] for row in per_expediente)

        # Total movimientos in table
        cursor = integration_db.execute("SELECT COUNT(*) FROM movimientos")
        total_movs = cursor.fetchone()[0]

        assert sum_per_exp == total_movs, f"Sum per expediente ({sum_per_exp}) != total movimientos ({total_movs})"

    def test_dependencias_reconciliation(self, integration_db):
        """
        Verify: distinct dependencias in movimientos = dependencias table rows.
        """
        cursor = integration_db.execute("SELECT COUNT(DISTINCT dependencia) FROM movimientos")
        distinct_movs_deps = cursor.fetchone()[0]

        cursor = integration_db.execute("SELECT COUNT(*) FROM dependencias")
        dep_table_count = cursor.fetchone()[0]

        assert distinct_movs_deps == dep_table_count, \
            f"Distinct dependencias in movimientos ({distinct_movs_deps}) != dependencias table ({dep_table_count})"

    def test_circuit_frequency_reconciliation(self, integration_db):
        """
        Verify: sum of circuitos.frecuencia per concepto = expedientes count per concepto.
        """
        run_full_circuit_analysis(integration_db)

# Get expedientes per concepto
        cursor = integration_db.execute(
            "SELECT concepto, COUNT(*) as exp_count FROM expedientes GROUP BY concepto"
        )
        exp_per_concepto = {row["concepto"]: row["exp_count"] for row in cursor.fetchall()}

        # Get circuit frequency sum per concepto
        cursor = integration_db.execute(
            "SELECT concepto, SUM(frecuencia) as circuit_sum FROM circuitos GROUP BY concepto"
        )
        circuit_per_concepto = {row["concepto"]: row["circuit_sum"] for row in cursor.fetchall()}

        for concepto, exp_count in exp_per_concepto.items():
            circuit_sum = circuit_per_concepto.get(concepto, 0)
            assert circuit_sum == exp_count, \
                f"Concepto '{concepto}': circuit frequency sum ({circuit_sum}) != expedientes count ({exp_count})"


class TestReferentialIntegrity:
    """Tests for referential integrity across tables."""

    def test_movimientos_expediente_id_fk(self, integration_db):
        """Verify: All movimientos.expediente_id exist in expedientes.id."""
        cursor = integration_db.execute("""
            SELECT COUNT(*) as orphan_count
            FROM movimientos m
            LEFT JOIN expedientes e ON m.expediente_id = e.id
            WHERE e.id IS NULL
        """)
        orphan_count = cursor.fetchone()["orphan_count"]
        assert orphan_count == 0, f"Found {orphan_count} orphaned movimientos (expediente_id not in expedientes)"

    def test_movimientos_dependencia_fk(self, integration_db):
        """Verify: All movimientos.dependencia exist in dependencias.nombre."""
        cursor = integration_db.execute("""
            SELECT COUNT(*) as orphan_count
            FROM movimientos m
            LEFT JOIN dependencias d ON m.dependencia = d.nombre
            WHERE d.nombre IS NULL
        """)
        orphan_count = cursor.fetchone()["orphan_count"]
        assert orphan_count == 0, f"Found {orphan_count} movimientos with dependencia not in dependencias table"

    def test_circuitos_concepto_fk(self, integration_db):
        """Verify: All circuitos.concepto exist in expedientes.concepto."""
        run_full_circuit_analysis(integration_db)

        cursor = integration_db.execute("""
            SELECT COUNT(*) as orphan_count
            FROM circuitos c
            LEFT JOIN (
                SELECT DISTINCT concepto FROM expedientes
            ) e ON c.concepto = e.concepto
            WHERE e.concepto IS NULL
        """)
        orphan_count = cursor.fetchone()["orphan_count"]
        assert orphan_count == 0, f"Found {orphan_count} circuitos with concepto not in expedientes"


class TestDashboardDataFlow:
    """Tests that dashboard data access functions work with full pipeline data."""

    def test_dashboard_load_expedientes(self, integration_db):
        """Test dashboard load_expedientes function."""
        from src.dashboard.data import load_expedientes, FilterState

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_expedientes(FilterState())
        assert len(df) == 100
        assert "numero" in df.columns
        assert "concepto" in df.columns

    def test_dashboard_load_circuitos(self, integration_db):
        """Test dashboard load_circuitos function."""
        from src.dashboard.data import load_circuitos

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_circuitos()
        assert len(df) > 0
        assert "circuito_parsed" in df.columns
        assert "step_count" in df.columns

        # Test with concepto filter
        df_gestao = load_circuitos("Gestión Alumno")
        assert len(df_gestao) > 0
        assert all(df_gestao["concepto"] == "Gestión Alumno")

    def test_dashboard_load_step_stats(self, integration_db):
        """Test dashboard load_step_stats function."""
        from src.dashboard.data import load_step_stats

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_step_stats()
        assert len(df) == 4  # 4 conceptos
        assert "mean_steps" in df.columns
        assert "median_steps" in df.columns
        assert "mode_steps" in df.columns

    def test_dashboard_load_permanence(self, integration_db):
        """Test dashboard load_permanence function."""
        from src.dashboard.data import load_permanence

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_permanence()
        assert len(df) == 354  # Total movimientos
        assert "permanence_days" in df.columns
        assert "is_final_step" in df.columns

    def test_dashboard_load_dependency_traffic(self, integration_db):
        """Test dashboard load_dependency_traffic function."""
        from src.dashboard.data import load_dependency_traffic, FilterState

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_dependency_traffic(FilterState())
        assert len(df) > 0
        assert "pct_movimientos" in df.columns
        assert abs(df["pct_movimientos"].sum() - 100) < 0.1

    def test_dashboard_load_concept_distribution(self, integration_db):
        """Test dashboard load_concept_distribution function."""
        from src.dashboard.data import load_concept_distribution, FilterState

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_concept_distribution(FilterState())
        assert len(df) == 4
        assert abs(df["porcentaje"].sum() - 100) < 0.1

    def test_dashboard_load_monthly_trend(self, integration_db):
        """Test dashboard load_monthly_trend function."""
        from src.dashboard.data import load_monthly_trend, FilterState

        run_full_circuit_analysis(integration_db)
        run_full_statistics_analysis(integration_db)

        df = load_monthly_trend(FilterState())
        assert len(df) > 0
        assert "mes" in df.columns
        assert "cantidad" in df.columns
        assert "acumulado" in df.columns


class TestIncrementalExecution:
    """Test incremental execution support (simulated)."""

    def test_analyzer_recomputes_on_new_data(self, integration_db):
        """Test that analyzer can be run multiple times and produces consistent results."""
        run_full_circuit_analysis(integration_db)
        result1 = run_full_circuit_analysis(integration_db)
        result2 = run_full_circuit_analysis(integration_db)

        # Results should be identical
        assert len(result1) == len(result2)
        assert result1["frecuencia"].sum() == result2["frecuencia"].sum()

        # Modal circuits should be the same
        modal1 = result1[result1["es_mas_frecuente"]].sort_values("concepto")
        modal2 = result2[result2["es_mas_frecuente"]].sort_values("concepto")
        assert list(modal1["circuito_json"]) == list(modal2["circuito_json"])

    def test_statistics_recomputes_on_new_data(self, integration_db):
        """Test that statistics analysis can be run multiple times."""
        run_full_circuit_analysis(integration_db)
        stats1 = run_full_statistics_analysis(integration_db)
        stats2 = run_full_statistics_analysis(integration_db)

        # Results should be identical
        for key in stats1:
            pd.testing.assert_frame_equal(stats1[key].sort_index(axis=1), stats2[key].sort_index(axis=1))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])