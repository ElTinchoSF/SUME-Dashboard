"""
Statistics module for SUME Dashboard.

Implements statistical analysis of administrative circuits including:
- Step count statistics per concepto
- Permanence time calculation between consecutive steps
- Outlier detection (frequency-based and structural)
- Dependency traffic ranking
- Concept distribution
"""

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
import sqlite3

from src.config import get_settings
from src.database.connection import get_connection
from src.database.models import CircuitoDict

logger = logging.getLogger(__name__)


def compute_step_statistics(freq_df: pd.DataFrame | None = None, db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Compute step count statistics per concepto.

    For each concepto, calculates min, max, mean, median, mode, and std
    of the number of steps in each circuit.

    Args:
        freq_df: DataFrame from compute_circuit_frequencies with circuito_json, concepto, frecuencia.
                 If None, loads from circuitos table.
        db: Optional database connection.

    Returns:
        DataFrame with columns:
        - concepto
        - min_steps, max_steps, mean_steps, median_steps, mode_steps, std_steps
        - total_circuitos (unique circuits), total_expedientes (sum of frequencies)
    """
    if db is None:
        db = get_connection()

    if freq_df is None:
        # Load from circuitos table
        query = "SELECT circuito, concepto, frecuencia FROM circuitos"
        freq_df = pd.read_sql_query(query, db)

    if freq_df.empty:
        logger.warning("No circuit data available for step statistics")
        return pd.DataFrame(columns=[
            "concepto", "min_steps", "max_steps", "mean_steps", "median_steps",
            "mode_steps", "std_steps", "total_circuitos", "total_expedientes"
        ])

    # Compute step count for each circuit
    def count_steps(circuito_json: str) -> int:
        try:
            circuit = json.loads(circuito_json)
            return len(circuit) if isinstance(circuit, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0

    freq_df = freq_df.copy()
    freq_df["step_count"] = freq_df["circuito"].apply(count_steps)

    # Expand by frequency to get per-expediente step counts
    expanded_rows = []
    for _, row in freq_df.iterrows():
        expanded_rows.extend([{"concepto": row["concepto"], "step_count": row["step_count"]}] * int(row["frecuencia"]))

    if not expanded_rows:
        return pd.DataFrame(columns=[
            "concepto", "min_steps", "max_steps", "mean_steps", "median_steps",
            "mode_steps", "std_steps", "total_circuitos", "total_expedientes"
        ])

    expanded_df = pd.DataFrame(expanded_rows)

    # Compute statistics per concepto
    stats_list = []
    for concepto, group in expanded_df.groupby("concepto"):
        step_counts = group["step_count"].values
        total_expedientes = len(step_counts)

        # Mode calculation - handle multiple modes by taking the smallest
        mode_result = pd.Series(step_counts).mode()
        mode_val = int(mode_result.iloc[0]) if not mode_result.empty else 0

        stats_list.append({
            "concepto": concepto,
            "min_steps": int(step_counts.min()),
            "max_steps": int(step_counts.max()),
            "mean_steps": float(step_counts.mean()),
            "median_steps": float(np.median(step_counts)),
            "mode_steps": mode_val,
            "std_steps": float(step_counts.std()) if len(step_counts) > 1 else 0.0,
            "total_circuitos": int(freq_df[freq_df["concepto"] == concepto]["frecuencia"].count()),
            "total_expedientes": total_expedientes,
        })

    result = pd.DataFrame(stats_list).sort_values("concepto").reset_index(drop=True)
    logger.info(f"Computed step statistics for {len(result)} conceptos")
    return result


def compute_permanence_times(db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Compute permanence times between consecutive steps for each expediente.

    Calculates the difference in days between fecha_recepcion of consecutive movimientos.
    For the final step (no next movement), permanence is None.

    Args:
        db: Optional database connection.

    Returns:
        DataFrame with columns:
        - expediente_id, numero, concepto
        - orden (step number)
        - dependencia (current step)
        - fecha_recepcion
        - permanence_days (days until next step, None for last step)
        - is_final_step (boolean)
    """
    if db is None:
        db = get_connection()

    query = """
        SELECT
            e.id as expediente_id,
            e.numero,
            e.concepto,
            m.orden,
            m.fecha_recepcion,
            m.dependencia
        FROM expedientes e
        JOIN movimientos m ON e.id = m.expediente_id
        ORDER BY e.id, m.orden
    """

    df = pd.read_sql_query(query, db)

    if df.empty:
        logger.warning("No movimientos found for permanence calculation")
        return pd.DataFrame(columns=[
            "expediente_id", "numero", "concepto", "orden", "dependencia",
            "fecha_recepcion", "permanence_days", "is_final_step"
        ])

    # Ensure fecha_recepcion is datetime
    df["fecha_recepcion"] = pd.to_datetime(df["fecha_recepcion"], errors="coerce")

    result_rows = []

    for expediente_id, group in df.groupby("expediente_id"):
        group = group.sort_values("orden").reset_index(drop=True)
        first_row = group.iloc[0]

        for i, row in group.iterrows():
            is_final = (i == len(group) - 1)

            if is_final:
                permanence_days = None
            else:
                next_fecha = group.iloc[i + 1]["fecha_recepcion"]
                current_fecha = row["fecha_recepcion"]
                if pd.notna(current_fecha) and pd.notna(next_fecha):
                    permanence_days = (next_fecha - current_fecha).days
                else:
                    permanence_days = None

            result_rows.append({
                "expediente_id": int(expediente_id),
                "numero": first_row["numero"],
                "concepto": first_row["concepto"],
                "orden": int(row["orden"]),
                "dependencia": row["dependencia"],
                "fecha_recepcion": row["fecha_recepcion"],
                "permanence_days": permanence_days,
                "is_final_step": is_final,
            })

    result = pd.DataFrame(result_rows)
    logger.info(f"Computed permanence times for {len(result)} movement steps across {df['expediente_id'].nunique()} expedientes")
    return result


def compute_permanence_stats_by_dependencia(permanence_df: pd.DataFrame | None = None, db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Compute permanence statistics grouped by dependencia.

    Args:
        permanence_df: DataFrame from compute_permanence_times. If None, computes it.
        db: Optional database connection.

    Returns:
        DataFrame with columns:
        - dependencia
        - count, mean_days, median_days, std_days, min_days, max_days
        - q25_days, q75_days (quartiles)
    """
    if permanence_df is None:
        permanence_df = compute_permanence_times(db)

    if permanence_df.empty:
        return pd.DataFrame(columns=[
            "dependencia", "count", "mean_days", "median_days", "std_days",
            "min_days", "max_days", "q25_days", "q75_days"
        ])

    # Filter out final steps (None permanence) and NaN
    valid_permanence = permanence_df[
        permanence_df["permanence_days"].notna() & (permanence_df["permanence_days"] >= 0)
    ].copy()

    if valid_permanence.empty:
        return pd.DataFrame(columns=[
            "dependencia", "count", "mean_days", "median_days", "std_days",
            "min_days", "max_days", "q25_days", "q75_days"
        ])

    stats_list = []
    for dependencia, group in valid_permanence.groupby("dependencia"):
        days = group["permanence_days"].values
        stats_list.append({
            "dependencia": dependencia,
            "count": len(days),
            "mean_days": float(days.mean()),
            "median_days": float(np.median(days)),
            "std_days": float(days.std()) if len(days) > 1 else 0.0,
            "min_days": int(days.min()),
            "max_days": int(days.max()),
            "q25_days": float(np.percentile(days, 25)),
            "q75_days": float(np.percentile(days, 75)),
        })

    result = pd.DataFrame(stats_list).sort_values("count", ascending=False).reset_index(drop=True)
    logger.info(f"Computed permanence stats for {len(result)} dependencias")
    return result


def detect_outliers(
    freq_df: pd.DataFrame | None = None,
    step_stats_df: pd.DataFrame | None = None,
    permanence_df: pd.DataFrame | None = None,
    db: sqlite3.Connection | None = None
) -> pd.DataFrame:
    """
    Detect outlier expedientes/circuits based on frequency and structural criteria.

    Two types of outliers:
    1. Frequency outliers: circuits with frequency < 5% of total expedientes for that concepto
    2. Structural outliers: circuits with step count > 2.5x modal step count, or containing loops

    Args:
        freq_df: DataFrame from compute_circuit_frequencies (or identify_modal_circuits).
        step_stats_df: DataFrame from compute_step_statistics.
        permanence_df: DataFrame from compute_permanence_times (for loop detection).
        db: Optional database connection.

    Returns:
        DataFrame with columns:
        - circuito_json, concepto, frecuencia, es_mas_frecuente
        - outlier_type: "frequency", "structural_steps", "structural_loop", or "none"
        - outlier_reason: Human-readable explanation
        - step_count: Number of steps in circuit
    """
    if db is None:
        db = get_connection()

    settings = get_settings()
    freq_threshold = settings.analyzer.outlier_frequency_threshold
    step_multiplier = settings.analyzer.outlier_step_multiplier

    if freq_df is None:
        query = "SELECT circuito, concepto, frecuencia, es_mas_frecuente FROM circuitos"
        freq_df = pd.read_sql_query(query, db)

    if freq_df.empty:
        logger.warning("No circuit data for outlier detection")
        return pd.DataFrame(columns=[
            "circuito_json", "concepto", "frecuencia", "es_mas_frecuente",
            "outlier_type", "outlier_reason", "step_count"
        ])

    if step_stats_df is None:
        step_stats_df = compute_step_statistics(freq_df, db)

    # Compute step count for each circuit
    def count_steps(circuito_json: str) -> int:
        try:
            circuit = json.loads(circuito_json)
            return len(circuit) if isinstance(circuit, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0

    def has_loop(circuito_json: str) -> bool:
        """Detect if circuit has repeated dependencies (loops)."""
        try:
            circuit = json.loads(circuito_json)
            if not isinstance(circuit, list):
                return False
            # Check for any repeated dependency (excluding MDE which is always first)
            seen = set()
            for dep in circuit:
                if dep in seen:
                    return True
                seen.add(dep)
            return False
        except (json.JSONDecodeError, TypeError):
            return False

    freq_df = freq_df.copy()
    freq_df["step_count"] = freq_df["circuito"].apply(count_steps)
    freq_df["has_loop"] = freq_df["circuito"].apply(has_loop)

    # Merge step stats to get modal step count per concepto
    modal_steps = step_stats_df.set_index("concepto")["mode_steps"].to_dict()

    # Compute total expedientes per concepto
    concepto_totals = freq_df.groupby("concepto")["frecuencia"].sum().to_dict()

    outlier_rows = []
    for _, row in freq_df.iterrows():
        concepto = row["concepto"]
        frecuencia = int(row["frecuencia"])
        total_concepto = concepto_totals.get(concepto, 1)
        step_count = int(row["step_count"])
        has_loop_flag = bool(row["has_loop"])
        modal_step_count = modal_steps.get(concepto, step_count)

        outlier_type = "none"
        outlier_reason = ""

        # Frequency outlier: < 5% of total for this concepto
        if frecuencia / total_concepto < freq_threshold:
            outlier_type = "frequency"
            outlier_reason = f"Frequency {frecuencia}/{total_concepto} ({frecuencia/total_concepto*100:.1f}%) below {freq_threshold*100:.0f}% threshold"

        # Structural outlier: step count > 2.5x modal
        elif step_count > modal_step_count * step_multiplier:
            outlier_type = "structural_steps"
            outlier_reason = f"Step count {step_count} exceeds {step_multiplier}x modal ({modal_step_count})"

        # Structural outlier: loops detected
        elif has_loop_flag:
            outlier_type = "structural_loop"
            outlier_reason = "Circuit contains repeated dependencies (loop detected)"

        outlier_rows.append({
            "circuito_json": row["circuito"],
            "concepto": concepto,
            "frecuencia": frecuencia,
            "es_mas_frecuente": bool(row.get("es_mas_frecuente", False)),
            "outlier_type": outlier_type,
            "outlier_reason": outlier_reason,
            "step_count": step_count,
        })

    result = pd.DataFrame(outlier_rows)

    # Summary log
    outlier_counts = result[result["outlier_type"] != "none"]["outlier_type"].value_counts().to_dict()
    logger.info(f"Outlier detection complete: {outlier_counts}")

    return result


def compute_dependency_traffic(db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Compute dependency traffic ranking.

    Counts unique expedientes and total movements per dependencia.

    Args:
        db: Optional database connection.

    Returns:
        DataFrame with columns:
        - dependencia
        - total_expedientes (unique expedientes passing through)
        - total_movimientos (total movement records)
        - pct_expedientes (percentage of all expedientes)
        - pct_movimientos (percentage of all movements)
    """
    if db is None:
        db = get_connection()

    query = """
        SELECT
            m.dependencia,
            COUNT(DISTINCT m.expediente_id) as total_expedientes,
            COUNT(*) as total_movimientos
        FROM movimientos m
        GROUP BY m.dependencia
        ORDER BY total_movimientos DESC
    """

    df = pd.read_sql_query(query, db)

    if df.empty:
        logger.warning("No movement data for dependency traffic")
        return pd.DataFrame(columns=[
            "dependencia", "total_expedientes", "total_movimientos",
            "pct_expedientes", "pct_movimientos"
        ])

    # Get total unique expedientes from the database (not sum of per-dependency counts)
    total_query = "SELECT COUNT(DISTINCT expediente_id) as total FROM movimientos"
    total_df = pd.read_sql_query(total_query, db)
    total_expedientes_all = total_df["total"].iloc[0]
    
    total_movimientos_all = df["total_movimientos"].sum()

    df["pct_expedientes"] = (df["total_expedientes"] / total_expedientes_all * 100).round(2)
    df["pct_movimientos"] = (df["total_movimientos"] / total_movimientos_all * 100).round(2)

    logger.info(f"Computed dependency traffic for {len(df)} dependencias")
    return df.reset_index(drop=True)


def compute_concept_distribution(db: sqlite3.Connection | None = None) -> pd.DataFrame:
    """
    Compute distribution of expedientes by concepto.

    Args:
        db: Optional database connection.

    Returns:
        DataFrame with columns:
        - concepto
        - cantidad (count of expedientes)
        - porcentaje (percentage of total)
    """
    if db is None:
        db = get_connection()

    query = """
        SELECT concepto, COUNT(*) as cantidad
        FROM expedientes
        GROUP BY concepto
        ORDER BY cantidad DESC
    """

    df = pd.read_sql_query(query, db)

    if df.empty:
        logger.warning("No expedientes for concept distribution")
        return pd.DataFrame(columns=["concepto", "cantidad", "porcentaje"])

    total = df["cantidad"].sum()
    df["porcentaje"] = (df["cantidad"] / total * 100).round(2)

    logger.info(f"Computed concept distribution for {len(df)} conceptos")
    return df.reset_index(drop=True)


def run_full_statistics_analysis(db: sqlite3.Connection | None = None) -> dict[str, pd.DataFrame]:
    """
    Run the complete statistics analysis pipeline.

    Returns a dictionary with all computed DataFrames:
    - step_statistics
    - permanence_times
    - permanence_by_dependencia
    - outliers
    - dependency_traffic
    - concept_distribution
    """
    if db is None:
        db = get_connection()

    logger.info("Starting full statistics analysis...")

    # Load circuit frequencies once
    freq_query = "SELECT circuito, concepto, frecuencia, es_mas_frecuente FROM circuitos"
    freq_df = pd.read_sql_query(freq_query, db)

    results = {}

    results["step_statistics"] = compute_step_statistics(freq_df, db)
    results["permanence_times"] = compute_permanence_times(db)
    results["permanence_by_dependencia"] = compute_permanence_stats_by_dependencia(results["permanence_times"], db)
    results["outliers"] = detect_outliers(freq_df, results["step_statistics"], results["permanence_times"], db)
    results["dependency_traffic"] = compute_dependency_traffic(db)
    results["concept_distribution"] = compute_concept_distribution(db)

    logger.info("Statistics analysis complete")
    return results