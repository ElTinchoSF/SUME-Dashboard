"""
Unit tests for statistics module.

Tests step statistics, permanence times, outlier detection,
dependency traffic, and concept distribution with known datasets.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.statistics import (
    compute_step_statistics,
    compute_permanence_times,
    compute_permanence_stats_by_dependencia,
    detect_outliers,
    compute_dependency_traffic,
    compute_concept_distribution,
    run_full_statistics_analysis,
)
from src.database.connection import get_connection
from src.database.schema import init_db


@pytest.fixture
def temp_db():
    """Create a temporary database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    # Insert test data
    # Concepto A: 3 expedientes, 2 circuitos (modal: 2, outlier: 1)
    # Concepto B: 2 expedientes, 1 circuito
    test_data = [
        # Expedientes
        ("EXP-2025-001", "Concepto A", "Desc 1", "2025-01-15", "En trámite", "kw1", "FBCB"),
        ("EXP-2025-002", "Concepto A", "Desc 2", "2025-01-20", "En trámite", "kw2", "FBCB"),
        ("EXP-2025-003", "Concepto A", "Desc 3", "2025-02-01", "Finalizado", "kw3", "FBCB"),
        ("EXP-2025-004", "Concepto B", "Desc 4", "2025-01-10", "En trámite", "kw4", "FBCB"),
        ("EXP-2025-005", "Concepto B", "Desc 5", "2025-01-25", "Finalizado", "kw5", "FBCB"),
    ]

    for num, conc, desc, fecha, estado, kw, orig in test_data:
        conn.execute(
            "INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (num, conc, desc, fecha, estado, kw, orig),
        )

    # Movimientos
    # EXP-2025-001 (Concepto A): MDE -> Dep1 -> Dep2 -> Dep3 (4 steps)
    # EXP-2025-002 (Concepto A): MDE -> Dep1 -> Dep2 -> Dep3 (4 steps) - SAME as 001
    # EXP-2025-003 (Concepto A): MDE -> Dep1 -> Dep4 -> Dep5 -> Dep6 -> Dep7 (6 steps) - OUTLIER structural
    # EXP-2025-004 (Concepto B): MDE -> Dep1 -> Dep2 (3 steps)
    # EXP-2025-005 (Concepto B): MDE -> Dep1 -> Dep2 (3 steps) - SAME as 004

    movimientos = [
        # EXP-001
        (1, 1, "2025-01-15", "Mesa de Entradas - FBCB"),
        (1, 2, "2025-01-16", "Dependencia 1"),
        (1, 3, "2025-01-18", "Dependencia 2"),
        (1, 4, "2025-01-20", "Dependencia 3"),
        # EXP-002
        (2, 1, "2025-01-20", "Mesa de Entradas - FBCB"),
        (2, 2, "2025-01-21", "Dependencia 1"),
        (2, 3, "2025-01-23", "Dependencia 2"),
        (2, 4, "2025-01-25", "Dependencia 3"),
        # EXP-003 (long circuit - structural outlier)
        (3, 1, "2025-02-01", "Mesa de Entradas - FBCB"),
        (3, 2, "2025-02-02", "Dependencia 1"),
        (3, 3, "2025-02-05", "Dependencia 4"),
        (3, 4, "2025-02-08", "Dependencia 5"),
        (3, 5, "2025-02-10", "Dependencia 6"),
        (3, 6, "2025-02-12", "Dependencia 7"),
        # EXP-004
        (4, 1, "2025-01-10", "Mesa de Entradas - FBCB"),
        (4, 2, "2025-01-11", "Dependencia 1"),
        (4, 3, "2025-01-13", "Dependencia 2"),
        # EXP-005
        (5, 1, "2025-01-25", "Mesa de Entradas - FBCB"),
        (5, 2, "2025-01-26", "Dependencia 1"),
        (5, 3, "2025-01-28", "Dependencia 2"),
    ]

    for exp_id, orden, fecha, dep in movimientos:
        conn.execute(
            "INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia) VALUES (?, ?, ?, ?)",
            (exp_id, orden, fecha, dep),
        )

    # Dependencias
    deps = [
        ("Mesa de Entradas - FBCB", "Mesa de Entradas - FBCB", 5),
        ("Dependencia 1", "Dependencia 1", 5),
        ("Dependencia 2", "Dependencia 2", 4),
        ("Dependencia 3", "Dependencia 3", 2),
        ("Dependencia 4", "Dependencia 4", 1),
        ("Dependencia 5", "Dependencia 5", 1),
        ("Dependencia 6", "Dependencia 6", 1),
        ("Dependencia 7", "Dependencia 7", 1),
    ]
    for nom, nom_orig, total in deps:
        conn.execute(
            "INSERT INTO dependencias (nombre, nombre_original, total_expedientes) VALUES (?, ?, ?)",
            (nom, nom_orig, total),
        )

    # Circuitos (pre-computed for testing)
    circuitos = [
        (json.dumps(["Mesa de Entradas - FBCB", "Dependencia 1", "Dependencia 2", "Dependencia 3"]), "Concepto A", 2, 1),
        (json.dumps(["Mesa de Entradas - FBCB", "Dependencia 1", "Dependencia 4", "Dependencia 5", "Dependencia 6", "Dependencia 7"]), "Concepto A", 1, 0),
        (json.dumps(["Mesa de Entradas - FBCB", "Dependencia 1", "Dependencia 2"]), "Concepto B", 2, 1),
    ]
    for circ, conc, freq, modal in circuitos:
        conn.execute(
            "INSERT INTO circuitos (circuito, concepto, frecuencia, es_mas_frecuente) VALUES (?, ?, ?, ?)",
            (circ, conc, freq, modal),
        )

    conn.commit()
    yield conn
    conn.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def freq_df(temp_db):
    """Load circuit frequencies from test DB."""
    return pd.read_sql_query("SELECT circuito, concepto, frecuencia, es_mas_frecuente FROM circuitos", temp_db)


class TestStepStatistics:
    """Tests for compute_step_statistics."""

    def test_compute_step_statistics_basic(self, temp_db, freq_df):
        result = compute_step_statistics(freq_df, temp_db)

        assert not result.empty
        assert list(result.columns) == [
            "concepto", "min_steps", "max_steps", "mean_steps",
            "median_steps", "mode_steps", "std_steps",
            "total_circuitos", "total_expedientes"
        ]

        # Concepto A: circuits with 4 steps (freq 2) and 6 steps (freq 1)
        # Expanded: [4, 4, 6] -> min=4, max=6, mean=4.67, median=4, mode=4, std~0.94
        conc_a = result[result["concepto"] == "Concepto A"].iloc[0]
        assert conc_a["min_steps"] == 4
        assert conc_a["max_steps"] == 6
        assert abs(conc_a["mean_steps"] - 4.667) < 0.01
        assert conc_a["median_steps"] == 4
        assert conc_a["mode_steps"] == 4
        assert conc_a["total_expedientes"] == 3

        # Concepto B: circuits with 3 steps (freq 2)
        # Expanded: [3, 3] -> min=3, max=3, mean=3, median=3, mode=3, std=0
        conc_b = result[result["concepto"] == "Concepto B"].iloc[0]
        assert conc_b["min_steps"] == 3
        assert conc_b["max_steps"] == 3
        assert conc_b["mean_steps"] == 3
        assert conc_b["median_steps"] == 3
        assert conc_b["mode_steps"] == 3
        assert conc_b["std_steps"] == 0
        assert conc_b["total_expedientes"] == 2

    def test_compute_step_statistics_empty(self, temp_db):
        # Empty freq_df
        empty_df = pd.DataFrame(columns=["circuito", "concepto", "frecuencia", "es_mas_frecuente"])
        result = compute_step_statistics(empty_df, temp_db)
        assert result.empty


class TestPermanenceTimes:
    """Tests for compute_permanence_times and compute_permanence_stats_by_dependencia."""

    def test_compute_permanence_times(self, temp_db):
        result = compute_permanence_times(temp_db)

        assert not result.empty
        assert list(result.columns) == [
            "expediente_id", "numero", "concepto", "orden", "dependencia",
            "fecha_recepcion", "permanence_days", "is_final_step"
        ]

        # Check EXP-001: 4 movements, 3 permanence intervals
        exp1 = result[result["numero"] == "EXP-2025-001"].sort_values("orden")
        assert len(exp1) == 4
        # orden 1: 2025-01-15 to 2025-01-16 = 1 day
        assert exp1.iloc[0]["permanence_days"] == 1
        # orden 2: 2025-01-16 to 2025-01-18 = 2 days
        assert exp1.iloc[1]["permanence_days"] == 2
        # orden 3: 2025-01-18 to 2025-01-20 = 2 days
        assert exp1.iloc[2]["permanence_days"] == 2
        # orden 4: final step = NaN (no next step)
        assert pd.isna(exp1.iloc[3]["permanence_days"])
        assert exp1.iloc[3]["is_final_step"] == True

    def test_compute_permanence_stats_by_dependencia(self, temp_db):
        perm_df = compute_permanence_times(temp_db)
        result = compute_permanence_stats_by_dependencia(perm_df, temp_db)

        assert not result.empty
        assert "dependencia" in result.columns
        assert "mean_days" in result.columns
        assert "median_days" in result.columns

        # Mesa de Entradas appears in all 5 expedientes as first step
        mde_row = result[result["dependencia"] == "Mesa de Entradas - FBCB"].iloc[0]
        assert mde_row["count"] == 5  # 5 occurrences as first step
        assert mde_row["mean_days"] > 0


class TestOutlierDetection:
    """Tests for detect_outliers."""

    def test_detect_frequency_outliers(self, temp_db, freq_df):
        step_stats = compute_step_statistics(freq_df, temp_db)
        perm_df = compute_permanence_times(temp_db)
        result = detect_outliers(freq_df, step_stats, perm_df, temp_db)

        assert not result.empty
        assert "outlier_type" in result.columns
        assert "outlier_reason" in result.columns

        # Concepto A: 3 total expedientes
        # Circuit 1 (4 steps): freq 2 -> 2/3 = 66.7% > 5% -> not frequency outlier
        # Circuit 2 (6 steps): freq 1 -> 1/3 = 33.3% > 5% -> not frequency outlier
        # But Circuit 2 has 6 steps vs modal 4 -> 6 > 4*2.5=10? No, 6 < 10 -> not structural
        # Wait, let's check: modal steps for Concepto A is 4 (mode), 6 > 4*2.5=10? No.
        # So no outliers expected in this test data with default thresholds

        # Let's verify no outliers detected for this data
        outliers = result[result["outlier_type"] != "none"]
        # With current test data and default thresholds (5% freq, 2.5x steps), no outliers
        assert len(outliers) == 0

    def test_detect_structural_step_outlier(self, temp_db):
        # Create data with clear structural outlier
        # Modal: 3 steps, Outlier: 10 steps (10 > 3*2.5=7.5)
        freq_df = pd.DataFrame([
            {"circuito": json.dumps(["MDE", "D1", "D2", "D3"]), "concepto": "Test", "frecuencia": 10, "es_mas_frecuente": True},
            {"circuito": json.dumps(["MDE", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10"]), "concepto": "Test", "frecuencia": 1, "es_mas_frecuente": False},
        ])
        step_stats = pd.DataFrame([{
            "concepto": "Test", "min_steps": 4, "max_steps": 11, "mean_steps": 4.6,
            "median_steps": 4, "mode_steps": 4, "std_steps": 2.0,
            "total_circuitos": 2, "total_expedientes": 11
        }])
        perm_df = pd.DataFrame()  # Empty

        result = detect_outliers(freq_df, step_stats, perm_df, temp_db)
        outlier_row = result[result["outlier_type"] == "structural_steps"]
        assert len(outlier_row) == 1
        assert outlier_row.iloc[0]["step_count"] == 11

    def test_detect_loop_outlier(self, temp_db):
        # Circuit with repeated dependency
        freq_df = pd.DataFrame([
            {"circuito": json.dumps(["MDE", "D1", "D2", "D1", "D3"]), "concepto": "Test", "frecuencia": 2, "es_mas_frecuente": False},
        ])
        step_stats = pd.DataFrame([{
            "concepto": "Test", "min_steps": 5, "max_steps": 5, "mean_steps": 5,
            "median_steps": 5, "mode_steps": 5, "std_steps": 0,
            "total_circuitos": 1, "total_expedientes": 2
        }])
        perm_df = pd.DataFrame()

        result = detect_outliers(freq_df, step_stats, perm_df, temp_db)
        outlier_row = result[result["outlier_type"] == "structural_loop"]
        assert len(outlier_row) == 1


class TestDependencyTraffic:
    """Tests for compute_dependency_traffic."""

    def test_compute_dependency_traffic(self, temp_db):
        result = compute_dependency_traffic(temp_db)

        assert not result.empty
        assert list(result.columns) == [
            "dependencia", "total_expedientes", "total_movimientos",
            "pct_expedientes", "pct_movimientos"
        ]

        # Mesa de Entradas: 5 expedientes, 5 movimientos (one per expediente)
        mde = result[result["dependencia"] == "Mesa de Entradas - FBCB"].iloc[0]
        assert mde["total_expedientes"] == 5
        assert mde["total_movimientos"] == 5
        assert mde["pct_expedientes"] == 100.0

        # Dependencia 1: 5 expedientes, 5 movimientos
        d1 = result[result["dependencia"] == "Dependencia 1"].iloc[0]
        assert d1["total_expedientes"] == 5
        assert d1["total_movimientos"] == 5

        # Note: pct_expedientes can exceed 100% because expedientes appear in multiple dependencies
        # The sum of pct_movimientos should be 100% (each movement counted once)
        assert abs(result["pct_movimientos"].sum() - 100) < 0.1


class TestConceptDistribution:
    """Tests for compute_concept_distribution."""

    def test_compute_concept_distribution(self, temp_db):
        result = compute_concept_distribution(temp_db)

        assert not result.empty
        assert list(result.columns) == ["concepto", "cantidad", "porcentaje"]

        conc_a = result[result["concepto"] == "Concepto A"].iloc[0]
        assert conc_a["cantidad"] == 3
        assert conc_a["porcentaje"] == 60.0  # 3/5

        conc_b = result[result["concepto"] == "Concepto B"].iloc[0]
        assert conc_b["cantidad"] == 2
        assert conc_b["porcentaje"] == 40.0  # 2/5

        assert abs(result["porcentaje"].sum() - 100) < 0.1


class TestFullStatisticsAnalysis:
    """Integration test for run_full_statistics_analysis."""

    def test_run_full_statistics_analysis(self, temp_db):
        results = run_full_statistics_analysis(temp_db)

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

        # Verify data consistency
        assert len(results["concept_distribution"]) == 2
        assert len(results["dependency_traffic"]) >= 3
        assert len(results["step_statistics"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])