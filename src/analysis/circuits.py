"""
Circuit analysis module for SUME Dashboard.

Implements process mining algorithms to reconstruct administrative circuits
from expediente movement sequences, compute frequencies, and identify modal circuits.
"""

import json
import logging
from collections import Counter
from typing import Any

import pandas as pd
import sqlite3

from src.config import get_settings
from src.database.connection import get_connection
from src.database.models import ExpedienteDict, MovimientoDict

logger = logging.getLogger(__name__)


def reconstruct_circuit(expediente: ExpedienteDict, movimientos: list[MovimientoDict]) -> list[str]:
    """
    Reconstruct the complete administrative circuit for an expediente.

    Injects the MDE (Mesa de Entradas) step as orden 0 using the expediente's
    fecha_alta, then appends all movimientos in chronological order.
    Filters out consecutive duplicate dependencies, keeping the one with
    the oldest fecha_recepcion.

    Args:
        expediente: Expediente dictionary with numero, concepto, fecha_alta, etc.
        movimientos: List of movimiento dictionaries with orden, fecha_recepcion, dependencia.

    Returns:
        Ordered list of dependency names representing the circuit.
        First element is always the MDE step.
    """
    # Sort movimientos by orden (now correct: 1 = oldest, N = newest)
    sorted_movimientos = sorted(movimientos, key=lambda m: m["orden"])

    # Build MDE step name - use the faculty from config or expediente origenes
    settings = get_settings()
    faculty = settings.sume.faculty_filter
    mde_step = f"Mesa de Entradas - {faculty}"

    # Start circuit with MDE injection (orden 0)
    circuit = [mde_step]

    # Filter consecutive duplicates, keeping the one with oldest fecha_recepcion
    for mov in sorted_movimientos:
        dependencia = mov["dependencia"]
        if not dependencia:
            continue

        # Check if this is a consecutive duplicate
        if circuit and dependencia == circuit[-1]:
            # Same as previous step - skip (consecutive duplicate)
            continue

        circuit.append(dependencia)

    return circuit


def _circuit_to_json(circuit: list[str]) -> str:
    """Convert a circuit list to JSON string for storage/comparison."""
    return json.dumps(circuit, ensure_ascii=False)


def _json_to_circuit(json_str: str) -> list[str]:
    """Convert JSON string back to circuit list."""
    return json.loads(json_str)


def compute_circuit_frequencies(db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Compute frequency distribution of circuits grouped by expediente concepto.

    Reads all expedientes with their movimientos from the database,
    reconstructs circuits, groups by concepto and circuit sequence,
    and computes frequencies.

    Args:
        db: Optional database connection. If None, uses thread-local connection.

    Returns:
        DataFrame with columns:
        - circuito_json: JSON string of the circuit sequence
        - concepto: Expediente concepto
        - frecuencia: Count of expedientes with this circuit
        - es_mas_frecuente: Boolean (will be set by identify_modal_circuits)
    """
    if db is None:
        db = get_connection()

    # Query expedientes with their movimientos, ordered by concepto and expediente
    query = """
        SELECT
            e.id as expediente_id,
            e.numero,
            e.concepto,
            e.fecha_alta,
            m.orden,
            m.fecha_recepcion,
            m.dependencia
        FROM expedientes e
        LEFT JOIN movimientos m ON e.id = m.expediente_id
        ORDER BY e.concepto, e.id, m.orden
    """

    df = pd.read_sql_query(query, db)

    if df.empty:
        logger.warning("No expedientes found in database")
        return pd.DataFrame(columns=["circuito_json", "concepto", "frecuencia", "es_mas_frecuente"])

    # Group by expediente to reconstruct circuits
    circuits_by_concepto: dict[str, list[list[str]]] = {}

    for expediente_id, group in df.groupby("expediente_id"):
        # Get expediente info from first row
        first_row = group.iloc[0]
        concepto = first_row["concepto"]
        fecha_alta = first_row["fecha_alta"]

        # Build expediente dict
        expediente = {
            "id": int(expediente_id),
            "numero": first_row["numero"],
            "concepto": concepto,
            "fecha_alta": fecha_alta,
        }

        # Build movimientos list (filter out NaN rows from LEFT JOIN)
        movimientos = []
        for _, row in group.iterrows():
            if pd.notna(row["orden"]):
                movimientos.append({
                    "orden": int(row["orden"]),
                    "fecha_recepcion": row["fecha_recepcion"],
                    "dependencia": row["dependencia"],
                })

        # Reconstruct circuit
        circuit = reconstruct_circuit(expediente, movimientos)

        # Group by concepto
        if concepto not in circuits_by_concepto:
            circuits_by_concepto[concepto] = []
        circuits_by_concepto[concepto].append(circuit)

    # Compute frequencies per concepto
    rows = []
    for concepto, circuits in circuits_by_concepto.items():
        # Count frequencies using JSON representation for exact matching
        circuit_json_list = [_circuit_to_json(c) for c in circuits]
        freq_counter = Counter(circuit_json_list)

        for circuito_json, frecuencia in freq_counter.items():
            rows.append({
                "circuito_json": circuito_json,
                "concepto": concepto,
                "frecuencia": frecuencia,
                "es_mas_frecuente": False,  # Will be set by identify_modal_circuits
            })

    result_df = pd.DataFrame(rows)

    if not result_df.empty:
        # Sort by concepto, then by frequency descending
        result_df = result_df.sort_values(["concepto", "frecuencia"], ascending=[True, False]).reset_index(drop=True)

    logger.info(f"Computed {len(result_df)} unique circuits across {len(circuits_by_concepto)} conceptos")
    return result_df


def identify_modal_circuits(freq_df: pd.DataFrame, min_samples: int | None = None) -> pd.DataFrame:
    """
    Identify the most frequent (modal) circuit for each concepto.

    For each concepto with sufficient samples (>= min_samples), marks the
    highest-frequency circuit as es_mas_frecuente = True.

    In case of ties (multiple circuits with same max frequency), marks the
    first encountered as modal and logs a warning.

    Args:
        freq_df: DataFrame from compute_circuit_frequencies with columns
                 circuito_json, concepto, frecuencia, es_mas_frecuente
        min_samples: Minimum total expedientes required for a concepto to have
                     a modal circuit. Defaults to analyzer.min_sample_threshold from config.

    Returns:
        Updated DataFrame with es_mas_frecuente column set appropriately.
    """
    if freq_df.empty:
        return freq_df

    if min_samples is None:
        settings = get_settings()
        min_samples = settings.analyzer.min_sample_threshold

    # Work on a copy
    result = freq_df.copy()

    # Compute total expedientes per concepto
    concepto_totals = result.groupby("concepto")["frecuencia"].sum().reset_index()
    concepto_totals.columns = ["concepto", "total_expedientes"]

    # Merge totals back
    result = result.merge(concepto_totals, on="concepto", how="left")

    # Process each concepto
    for concepto in result["concepto"].unique():
        concepto_mask = result["concepto"] == concepto
        concepto_rows = result[concepto_mask]
        total = concepto_rows["total_expedientes"].iloc[0]

        if total < min_samples:
            logger.info(f"Concepto '{concepto}' has only {total} expedientes (< {min_samples}), skipping modal identification")
            continue

        # Find max frequency
        max_freq = concepto_rows["frecuencia"].max()
        max_freq_rows = concepto_rows[concepto_rows["frecuencia"] == max_freq]

        if len(max_freq_rows) > 1:
            # Tie detected - log warning and pick first
            circuit_descriptions = [_json_to_circuit(row["circuito_json"]) for _, row in max_freq_rows.iterrows()]
            logger.warning(
                f"Tie detected for concepto '{concepto}': {len(max_freq_rows)} circuits "
                f"with frequency {max_freq}. Selecting first: {circuit_descriptions[0]}"
            )

        # Mark the first max-frequency circuit as modal
        first_max_idx = max_freq_rows.index[0]
        result.loc[first_max_idx, "es_mas_frecuente"] = True

    # Drop the helper column
    result = result.drop(columns=["total_expedientes"])

    modal_count = result["es_mas_frecuente"].sum()
    logger.info(f"Identified {modal_count} modal circuits across {result['concepto'].nunique()} conceptos")

    return result


def persist_circuit_frequencies(freq_df: pd.DataFrame, db: sqlite3.Connection | None = None) -> int:
    """
    Persist circuit frequencies to the circuitos table.

    Args:
        freq_df: DataFrame from identify_modal_circuits
        db: Optional database connection

    Returns:
        Number of rows inserted/updated
    """
    if db is None:
        db = get_connection()

    if freq_df.empty:
        return 0

    with db:
        # Clear existing data
        db.execute("DELETE FROM circuitos")

        # Insert new data
        inserted = 0
        for _, row in freq_df.iterrows():
            db.execute(
                """
                INSERT INTO circuitos (circuito, concepto, frecuencia, es_mas_frecuente)
                VALUES (?, ?, ?, ?)
                """,
                (
                    row["circuito_json"],
                    row["concepto"],
                    int(row["frecuencia"]),
                    bool(row["es_mas_frecuente"]),
                ),
            )
            inserted += 1

        db.commit()

    logger.info(f"Persisted {inserted} circuit frequency records")
    return inserted


def run_full_circuit_analysis(db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Run the complete circuit analysis pipeline.

    Convenience function that:
    1. Computes circuit frequencies
    2. Identifies modal circuits
    3. Persists results to database

    Args:
        db: Optional database connection

    Returns:
        Final DataFrame with modal circuits identified
    """
    if db is None:
        db = get_connection()

    logger.info("Starting full circuit analysis...")

    freq_df = compute_circuit_frequencies(db)
    freq_df = identify_modal_circuits(freq_df)
    persist_circuit_frequencies(freq_df, db)

    logger.info("Circuit analysis complete")
    return freq_df