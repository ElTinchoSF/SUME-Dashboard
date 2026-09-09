"""
Unit tests for circuits module.

Tests circuit reconstruction, frequency computation, modal identification,
and tie handling with synthetic data.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.circuits import (
    reconstruct_circuit,
    compute_circuit_frequencies,
    identify_modal_circuits,
    persist_circuit_frequencies,
    run_full_circuit_analysis,
    _circuit_to_json,
    _json_to_circuit,
)
from src.database.connection import get_connection, close_connection, set_connection_factory
from src.database.schema import INIT_SQL
from src.database.models import ExpedienteDict, MovimientoDict


@pytest.fixture
def temp_db():
    """Create a temporary database with test data."""
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

    # Insert test data
    # Concepto A: 5 expedientes with 3 different circuits
    # Concepto B: 3 expedientes with 1 circuit
    test_data = [
        # Expedientes
        ("EXP-2025-001", "Concepto A", "Desc 1", "2025-01-15", "En trámite", "kw1", "FBCB"),
        ("EXP-2025-002", "Concepto A", "Desc 2", "2025-01-20", "En trámite", "kw2", "FBCB"),
        ("EXP-2025-003", "Concepto A", "Desc 3", "2025-02-01", "Finalizado", "kw3", "FBCB"),
        ("EXP-2025-004", "Concepto A", "Desc 4", "2025-02-05", "En trámite", "kw4", "FBCB"),
        ("EXP-2025-005", "Concepto A", "Desc 5", "2025-02-10", "Finalizado", "kw5", "FBCB"),
        ("EXP-2025-006", "Concepto B", "Desc 6", "2025-01-10", "En trámite", "kw6", "FBCB"),
        ("EXP-2025-007", "Concepto B", "Desc 7", "2025-01-15", "En trámite", "kw7", "FBCB"),
        ("EXP-2025-008", "Concepto B", "Desc 8", "2025-01-20", "Finalizado", "kw8", "FBCB"),
    ]

    for num, conc, desc, fecha, estado, kw, orig in test_data:
        conn.execute(
            "INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (num, conc, desc, fecha, estado, kw, orig),
        )

    # Movimientos
    # EXP-001, 002, 003 (Concepto A): Same circuit -> MDE -> D1 -> D2 -> D3 (4 steps) - MODAL (freq 3)
    # EXP-004 (Concepto A): Different circuit -> MDE -> D1 -> D4 -> D5 (4 steps) - freq 1
    # EXP-005 (Concepto A): Another circuit -> MDE -> D1 -> D2 -> D6 -> D7 (5 steps) - freq 1
    # EXP-006, 007, 008 (Concepto B): Same circuit -> MDE -> D1 -> D2 (3 steps) - MODAL (freq 3)

    movimientos = [
        # EXP-001 (id=1)
        (1, 1, "2025-01-15", "Mesa de Entradas - FBCB"),
        (1, 2, "2025-01-16", "Dependencia 1"),
        (1, 3, "2025-01-18", "Dependencia 2"),
        (1, 4, "2025-01-20", "Dependencia 3"),
        # EXP-002 (id=2)
        (2, 1, "2025-01-20", "Mesa de Entradas - FBCB"),
        (2, 2, "2025-01-21", "Dependencia 1"),
        (2, 3, "2025-01-23", "Dependencia 2"),
        (2, 4, "2025-01-25", "Dependencia 3"),
        # EXP-003 (id=3)
        (3, 1, "2025-02-01", "Mesa de Entradas - FBCB"),
        (3, 2, "2025-02-02", "Dependencia 1"),
        (3, 3, "2025-02-05", "Dependencia 2"),
        (3, 4, "2025-02-07", "Dependencia 3"),
        # EXP-004 (id=4)
        (4, 1, "2025-02-05", "Mesa de Entradas - FBCB"),
        (4, 2, "2025-02-06", "Dependencia 1"),
        (4, 3, "2025-02-08", "Dependencia 4"),
        (4, 4, "2025-02-10", "Dependencia 5"),
        # EXP-005 (id=5)
        (5, 1, "2025-02-10", "Mesa de Entradas - FBCB"),
        (5, 2, "2025-02-11", "Dependencia 1"),
        (5, 3, "2025-02-13", "Dependencia 2"),
        (5, 4, "2025-02-15", "Dependencia 6"),
        (5, 5, "2025-02-17", "Dependencia 7"),
        # EXP-006 (id=6)
        (6, 1, "2025-01-10", "Mesa de Entradas - FBCB"),
        (6, 2, "2025-01-11", "Dependencia 1"),
        (6, 3, "2025-01-13", "Dependencia 2"),
        # EXP-007 (id=7)
        (7, 1, "2025-01-15", "Mesa de Entradas - FBCB"),
        (7, 2, "2025-01-16", "Dependencia 1"),
        (7, 3, "2025-01-18", "Dependencia 2"),
        # EXP-008 (id=8)
        (8, 1, "2025-01-20", "Mesa de Entradas - FBCB"),
        (8, 2, "2025-01-21", "Dependencia 1"),
        (8, 3, "2025-01-23", "Dependencia 2"),
    ]

    for exp_id, orden, fecha, dep in movimientos:
        conn.execute(
            "INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia) VALUES (?, ?, ?, ?)",
            (exp_id, orden, fecha, dep),
        )

    conn.commit()
    try:
        yield conn
    finally:
        conn.close()
        Path(db_path).unlink(missing_ok=True)


class TestCircuitToJson:
    """Tests for _circuit_to_json and _json_to_circuit."""

    def test_circuit_to_json_roundtrip(self):
        circuit = ["Mesa de Entradas - FBCB", "Dependencia 1", "Dependencia 2"]
        json_str = _circuit_to_json(circuit)
        restored = _json_to_circuit(json_str)
        assert restored == circuit

    def test_circuit_to_json_empty(self):
        circuit = []
        json_str = _circuit_to_json(circuit)
        restored = _json_to_circuit(json_str)
        assert restored == circuit

    def test_circuit_to_json_unicode(self):
        circuit = ["Mesa de Entradas - FBCB", "Área de Alumnos", "Secretaría Académica"]
        json_str = _circuit_to_json(circuit)
        restored = _json_to_circuit(json_str)
        assert restored == circuit


class TestReconstructCircuit:
    """Tests for reconstruct_circuit function."""

    def test_reconstruct_circuit_happy_path(self):
        """Test happy path with MDE injection."""
        expediente: ExpedienteDict = {
            "id": 1,
            "numero": "EXP-2025-001",
            "concepto": "Gestión Alumno",
            "fecha_alta": "2025-06-15",
        }
        movimientos: list[MovimientoDict] = [
            {"orden": 1, "fecha_recepcion": "2025-06-16", "dependencia": "Despacho General"},
            {"orden": 2, "fecha_recepcion": "2025-06-17", "dependencia": "Alumnado"},
            {"orden": 3, "fecha_recepcion": "2025-06-18", "dependencia": "Secretaría Académica"},
        ]

        circuit = reconstruct_circuit(expediente, movimientos)

        expected = [
            "Mesa de Entradas - FBCB",
            "Despacho General",
            "Alumnado",
            "Secretaría Académica",
        ]
        assert circuit == expected

    def test_reconstruct_circuit_zero_movimientos(self):
        """Test expediente with zero movimientos."""
        expediente: ExpedienteDict = {
            "id": 1,
            "numero": "EXP-2025-001",
            "concepto": "Gestión Alumno",
            "fecha_alta": "2025-06-15",
        }
        movimientos: list[MovimientoDict] = []

        circuit = reconstruct_circuit(expediente, movimientos)

        expected = ["Mesa de Entradas - FBCB"]
        assert circuit == expected

    def test_reconstruct_circuit_sorts_by_orden(self):
        """Test that movements are sorted by orden."""
        expediente: ExpedienteDict = {
            "id": 1,
            "numero": "EXP-2025-001",
            "concepto": "Gestión Alumno",
            "fecha_alta": "2025-06-15",
        }
        # Out of order
        movimientos: list[MovimientoDict] = [
            {"orden": 3, "fecha_recepcion": "2025-06-18", "dependencia": "Secretaría Académica"},
            {"orden": 1, "fecha_recepcion": "2025-06-16", "dependencia": "Despacho General"},
            {"orden": 2, "fecha_recepcion": "2025-06-17", "dependencia": "Alumnado"},
        ]

        circuit = reconstruct_circuit(expediente, movimientos)

        expected = [
            "Mesa de Entradas - FBCB",
            "Despacho General",
            "Alumnado",
            "Secretaría Académica",
        ]
        assert circuit == expected

    def test_reconstruct_circuit_skips_none_dependencia(self):
        """Test that None/empty dependencia is skipped."""
        expediente: ExpedienteDict = {
            "id": 1,
            "numero": "EXP-2025-001",
            "concepto": "Gestión Alumno",
            "fecha_alta": "2025-06-15",
        }
        movimientos: list[MovimientoDict] = [
            {"orden": 1, "fecha_recepcion": "2025-06-16", "dependencia": "Despacho General"},
            {"orden": 2, "fecha_recepcion": "2025-06-17", "dependencia": ""},
            {"orden": 3, "fecha_recepcion": "2025-06-18", "dependencia": "Secretaría Académica"},
        ]

        circuit = reconstruct_circuit(expediente, movimientos)

        expected = [
            "Mesa de Entradas - FBCB",
            "Despacho General",
            "Secretaría Académica",
        ]
        assert circuit == expected


class TestComputeCircuitFrequencies:
    """Tests for compute_circuit_frequencies function."""

    def test_compute_circuit_frequencies_basic(self, temp_db):
        result = compute_circuit_frequencies(temp_db)

        assert not result.empty
        assert list(result.columns) == ["circuito_json", "concepto", "frecuencia", "es_mas_frecuente"]

        # Concepto A: 5 expedientes, 3 circuits
        # Circuit 1 (MDE -> D1 -> D2 -> D3): freq 3
        # Circuit 2 (MDE -> D1 -> D4 -> D5): freq 1
        # Circuit 3 (MDE -> D1 -> D2 -> D6 -> D7): freq 1
        conc_a = result[result["concepto"] == "Concepto A"]
        assert len(conc_a) == 3
        freq_sum = conc_a["frecuencia"].sum()
        assert freq_sum == 5

        # Concepto B: 3 expedientes, 1 circuit
        conc_b = result[result["concepto"] == "Concepto B"]
        assert len(conc_b) == 1
        assert conc_b.iloc[0]["frecuencia"] == 3

        # Total expedientes
        total = result["frecuencia"].sum()
        assert total == 8

    def test_compute_circuit_frequencies_empty_db(self, temp_db):
        # Clear all data - delete in correct order due to foreign keys
        temp_db.execute("DELETE FROM movimientos")
        temp_db.execute("DELETE FROM expedientes")
        temp_db.commit()

        result = compute_circuit_frequencies(temp_db)
        assert result.empty
        assert list(result.columns) == ["circuito_json", "concepto", "frecuencia", "es_mas_frecuente"]

    def test_compute_circuit_frequencies_sorts_by_concepto_and_freq(self, temp_db):
        result = compute_circuit_frequencies(temp_db)

        # Should be sorted by concepto asc, frecuencia desc
        conceptos = result["concepto"].tolist()
        assert conceptos == sorted(conceptos)

        # Within each concepto, frequencies should be descending
        for concepto in result["concepto"].unique():
            subset = result[result["concepto"] == concepto]
            freqs = subset["frecuencia"].tolist()
            assert freqs == sorted(freqs, reverse=True)


class TestIdentifyModalCircuits:
    """Tests for identify_modal_circuits function."""

    def test_identify_modal_circuits_basic(self, temp_db):
        freq_df = compute_circuit_frequencies(temp_db)
        result = identify_modal_circuits(freq_df, min_samples=2)

        # Concepto A: 5 expedientes (>=2), modal should be circuit with freq 3
        # Concepto B: 3 expedientes (>=2), modal should be circuit with freq 3
        modal_a = result[(result["concepto"] == "Concepto A") & (result["es_mas_frecuente"])]
        assert len(modal_a) == 1
        assert modal_a.iloc[0]["frecuencia"] == 3

        modal_b = result[(result["concepto"] == "Concepto B") & (result["es_mas_frecuente"])]
        assert len(modal_b) == 1
        assert modal_b.iloc[0]["frecuencia"] == 3

        # Total modal circuits = 2
        assert result["es_mas_frecuente"].sum() == 2

    def test_identify_modal_circuits_insufficient_samples(self, temp_db):
        freq_df = compute_circuit_frequencies(temp_db)
        # Set min_samples higher than Concepto B's count (3)
        result = identify_modal_circuits(freq_df, min_samples=5)

        # Concepto A: 5 expedientes (>=5), should have modal
        modal_a = result[(result["concepto"] == "Concepto A") & (result["es_mas_frecuente"])]
        assert len(modal_a) == 1

        # Concepto B: 3 expedientes (<5), should NOT have modal
        modal_b = result[(result["concepto"] == "Concepto B") & (result["es_mas_frecuente"])]
        assert len(modal_b) == 0

    def test_identify_modal_circuits_tie_handling(self, temp_db):
        # Create a tie scenario by manually creating freq_df with tie
        freq_df = pd.DataFrame([
            {"circuito_json": json.dumps(["MDE", "D1", "D2"]), "concepto": "TieConcepto", "frecuencia": 5, "es_mas_frecuente": False},
            {"circuito_json": json.dumps(["MDE", "D1", "D3"]), "concepto": "TieConcepto", "frecuencia": 5, "es_mas_frecuente": False},
            {"circuito_json": json.dumps(["MDE", "D4"]), "concepto": "TieConcepto", "frecuencia": 2, "es_mas_frecuente": False},
        ])

        result = identify_modal_circuits(freq_df, min_samples=2)

        # Should mark first encountered as modal
        modal = result[result["es_mas_frecuente"]]
        assert len(modal) == 1
        assert modal.iloc[0]["frecuencia"] == 5
        # First one (D2) should be selected
        assert "D2" in _json_to_circuit(modal.iloc[0]["circuito_json"])

    def test_identify_modal_circuits_empty_df(self, temp_db):
        empty_df = pd.DataFrame(columns=["circuito_json", "concepto", "frecuencia", "es_mas_frecuente"])
        result = identify_modal_circuits(empty_df)
        assert result.empty


class TestPersistCircuitFrequencies:
    """Tests for persist_circuit_frequencies function."""

    def test_persist_circuit_frequencies(self, temp_db):
        freq_df = compute_circuit_frequencies(temp_db)
        freq_df = identify_modal_circuits(freq_df, min_samples=2)

        inserted = persist_circuit_frequencies(freq_df, temp_db)

        # Should have inserted all unique circuits
        assert inserted == len(freq_df)

        # Verify data in circuitos table
        cursor = temp_db.execute("SELECT COUNT(*) FROM circuitos")
        count = cursor.fetchone()[0]
        assert count == len(freq_df)

        # Verify modal flags
        cursor = temp_db.execute("SELECT COUNT(*) FROM circuitos WHERE es_mas_frecuente = 1")
        modal_count = cursor.fetchone()[0]
        assert modal_count == 2  # One modal per concepto

    def test_persist_circuit_frequencies_empty(self, temp_db):
        empty_df = pd.DataFrame(columns=["circuito_json", "concepto", "frecuencia", "es_mas_frecuente"])
        inserted = persist_circuit_frequencies(empty_df, temp_db)
        assert inserted == 0

    def test_persist_circuit_frequencies_overwrites(self, temp_db):
        freq_df = compute_circuit_frequencies(temp_db)
        freq_df = identify_modal_circuits(freq_df, min_samples=2)

        # First persist
        inserted1 = persist_circuit_frequencies(freq_df, temp_db)
        cursor = temp_db.execute("SELECT COUNT(*) FROM circuitos")
        count1 = cursor.fetchone()[0]

        # Second persist (should overwrite)
        inserted2 = persist_circuit_frequencies(freq_df, temp_db)
        cursor = temp_db.execute("SELECT COUNT(*) FROM circuitos")
        count2 = cursor.fetchone()[0]

        assert count1 == count2
        assert inserted1 == inserted2


class TestRunFullCircuitAnalysis:
    """Integration test for run_full_circuit_analysis."""

    def test_run_full_circuit_analysis(self, temp_db):
        result = run_full_circuit_analysis(temp_db)

        assert not result.empty
        assert list(result.columns) == ["circuito_json", "concepto", "frecuencia", "es_mas_frecuente"]

        # Check modal circuits identified
        # Default min_samples=5 from config, so only Concepto A (5 expedientes) gets modal
        modal_count = result["es_mas_frecuente"].sum()
        assert modal_count == 1  # One per conceito with sufficient samples (>=5)

        # Verify data persisted to circuitos table
        cursor = temp_db.execute("SELECT COUNT(*) FROM circuitos")
        db_count = cursor.fetchone()[0]
        assert db_count == len(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])