"""
Data access layer for SUME Dashboard.

Provides cached database queries with Streamlit's @st.cache_data decorator.
All functions are read-only and use TTL-based cache invalidation.
Cache is invalidated when the database file modification time changes.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
import sqlite3

from src.config import get_settings
from src.database.connection import get_connection


def _get_data_year_range() -> tuple[Optional[int], Optional[int]]:
    """
    Get the min and max years from the database.

    Returns:
        Tuple of (min_year, max_year) or (None, None) if no data.
    """
    try:
        conn = get_connection()
        cursor = conn.execute(
            "SELECT MIN(substr(fecha_alta, 1, 4)), MAX(substr(fecha_alta, 1, 4)) FROM expedientes WHERE fecha_alta IS NOT NULL"
        )
        row = cursor.fetchone()
        if row and row[0] and row[1]:
            return int(row[0]), int(row[1])
    except Exception:
        pass
    return None, None


@dataclass(frozen=True)
class FilterState:
    """Global filter state for dashboard queries."""

    date_range: tuple[Optional[str], Optional[str]] = (None, None)
    conceptos: tuple[str, ...] = ()
    dependencias: tuple[str, ...] = ()
    asuntos: tuple[str, ...] = ()

    def to_sql_where(self) -> tuple[str, list]:
        """
        Convert filter state to SQL WHERE clause and parameters.

        Returns:
            Tuple of (where_clause, parameters). where_clause includes leading "WHERE " or "AND ".
        """
        clauses = []
        params = []

        # Date range filter on expedientes.fecha_alta
        if self.date_range[0] is not None:
            clauses.append("e.fecha_alta >= ?")
            params.append(self.date_range[0])
        if self.date_range[1] is not None:
            clauses.append("e.fecha_alta <= ?")
            params.append(self.date_range[1])

        # Concepto filter
        if self.conceptos:
            placeholders = ",".join("?" * len(self.conceptos))
            clauses.append(f"e.concepto IN ({placeholders})")
            params.extend(self.conceptos)

        # Dependencia filter - expedientes that passed through selected dependencias
        if self.dependencias:
            placeholders = ",".join("?" * len(self.dependencias))
            clauses.append(f"""
                e.id IN (
                    SELECT DISTINCT expediente_id
                    FROM movimientos
                    WHERE dependencia IN ({placeholders})
                )
            """)
            params.extend(self.dependencias)

        # Asunto filter - expedientes matching selected asuntos
        if self.asuntos:
            placeholders = ",".join("?" * len(self.asuntos))
            clauses.append(f"""
                e.id IN (
                    SELECT DISTINCT ea.expediente_id
                    FROM expediente_asuntos ea
                    JOIN asuntos a ON ea.asunto_id = a.id
                    WHERE a.asunto IN ({placeholders})
                )
            """)
            params.extend(self.asuntos)

        if not clauses:
            return "", []

        where_clause = "WHERE " + " AND ".join(clauses)
        return where_clause, params


def _get_db_mtime() -> float:
    """
    Get the modification time of the database file.

    Used as a cache key to invalidate @st.cache_data when the database changes.

    Returns:
        Modification timestamp, or 0 if file doesn't exist.
    """
    settings = get_settings()
    db_path = Path(settings.database.path)
    try:
        return db_path.stat().st_mtime
    except OSError:
        return 0.0


@st.cache_data(ttl=300, show_spinner="Cargando expedientes...")
def load_expedientes(filters: FilterState) -> pd.DataFrame:
    """
    Load expedientes with applied filters.

    Args:
        filters: FilterState with date_range, conceptos, dependencias.

    Returns:
        DataFrame with columns: id, numero, concepto, descripcion, fecha_alta,
        estado, palabras_clave, origenes, fecha_extraccion
    """
    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT
            id, numero, concepto, descripcion, fecha_alta,
            estado, palabras_clave, origenes, fecha_extraccion
        FROM expedientes e
        {where_clause}
        ORDER BY e.fecha_alta DESC
    """

    df = pd.read_sql_query(query, db, params=params)

    if not df.empty:
        df["fecha_alta"] = pd.to_datetime(df["fecha_alta"], errors="coerce")
        df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"], errors="coerce")

    return df


@st.cache_data(ttl=300, show_spinner="Cargando circuitos...")
def load_circuitos(concepto: Optional[str] = None, filters: Optional[FilterState] = None) -> pd.DataFrame:
    """
    Load circuitos with optional concepto and date filters.

    When filters are applied, re-computes circuits on-the-fly from filtered expedientes
    instead of reading from the pre-computed circuitos table.

    Args:
        concepto: Optional concepto to filter by. If None, loads all.
        filters: Optional FilterState with date_range, conceptos, dependencias.

    Returns:
        DataFrame with columns: id, circuito (JSON), concepto, frecuencia, es_mas_frecuente
    """
    db = get_connection()

    # If filters are applied (especially date), re-compute circuits on-the-fly
    if filters and (filters.date_range[0] or filters.date_range[1] or filters.conceptos or filters.dependencias):
        return _compute_circuitos_with_filters(db, concepto, filters)

    # No filters: use pre-computed circuitos table
    if concepto is not None:
        query = "SELECT id, circuito, concepto, frecuencia, es_mas_frecuente FROM circuitos WHERE concepto = ? ORDER BY frecuencia DESC"
        df = pd.read_sql_query(query, db, params=[concepto])
    else:
        query = "SELECT id, circuito, concepto, frecuencia, es_mas_frecuente FROM circuitos ORDER BY concepto, frecuencia DESC"
        df = pd.read_sql_query(query, db)

    if not df.empty:
        # Parse circuito JSON for easier use
        df["circuito_parsed"] = df["circuito"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else []
        )
        df["circuito_json"] = df["circuito"]  # Keep original JSON string for display
        df["step_count"] = df["circuito_parsed"].apply(len)

    return df


def _compute_circuitos_with_filters(
    db: sqlite3.Connection,
    concepto: Optional[str],
    filters: FilterState,
) -> pd.DataFrame:
    """
    Re-compute circuits on-the-fly from filtered expedientes.

    This ensures circuits reflect only expedientes within the date range.
    """
    from src.analysis.circuits import reconstruct_circuit, identify_modal_circuits

    # Build WHERE clause for filters
    where_clauses = []
    params = []

    # Date range filter on expedientes.fecha_alta
    if filters.date_range[0] is not None:
        where_clauses.append("e.fecha_alta >= ?")
        params.append(filters.date_range[0])
    if filters.date_range[1] is not None:
        where_clauses.append("e.fecha_alta <= ?")
        params.append(filters.date_range[1])

    # Concepto filter
    if filters.conceptos:
        placeholders = ",".join("?" * len(filters.conceptos))
        where_clauses.append(f"e.concepto IN ({placeholders})")
        params.extend(filters.conceptos)

    # Dependencia filter
    if filters.dependencias:
        placeholders = ",".join("?" * len(filters.dependencias))
        where_clauses.append(f"""
            e.id IN (
                SELECT DISTINCT expediente_id
                FROM movimientos
                WHERE dependencia IN ({placeholders})
            )
        """)
        params.extend(filters.dependencias)

    # Asunto filter
    if filters.asuntos:
        placeholders = ",".join("?" * len(filters.asuntos))
        where_clauses.append(f"""
            e.id IN (
                SELECT DISTINCT ea.expediente_id
                FROM expediente_asuntos ea
                JOIN asuntos a ON ea.asunto_id = a.id
                WHERE a.asunto IN ({placeholders})
            )
        """)
        params.extend(filters.asuntos)

    # Additional concepto filter from function parameter
    if concepto is not None:
        where_clauses.append("e.concepto = ?")
        params.append(concepto)

    where_clause = ""
    if where_clauses:
        where_clause = "WHERE " + " AND ".join(where_clauses)

    # Query expedientes with their movimientos
    query = f"""
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
        {where_clause}
        ORDER BY e.concepto, e.id, m.orden
    """

    df = pd.read_sql_query(query, db, params=params)

    if df.empty:
        return pd.DataFrame(columns=["id", "circuito", "circuito_json", "circuito_parsed",
                                     "concepto", "frecuencia", "es_mas_frecuente", "step_count"])

    # Group by expediente to reconstruct circuits
    circuits_by_concepto: dict[str, list[list[str]]] = {}

    for expediente_id, group in df.groupby("expediente_id"):
        first_row = group.iloc[0]
        concepto_name = first_row["concepto"]
        fecha_alta = first_row["fecha_alta"]

        expediente = {
            "id": int(expediente_id),
            "numero": first_row["numero"],
            "concepto": concepto_name,
            "fecha_alta": fecha_alta,
        }

        movimientos = []
        for _, row in group.iterrows():
            if pd.notna(row["orden"]):
                movimientos.append({
                    "orden": int(row["orden"]),
                    "fecha_recepcion": row["fecha_recepcion"],
                    "dependencia": row["dependencia"],
                })

        circuit = reconstruct_circuit(expediente, movimientos)

        if concepto_name not in circuits_by_concepto:
            circuits_by_concepto[concepto_name] = []
        circuits_by_concepto[concepto_name].append(circuit)

    # Compute frequencies
    rows = []
    for concepto_name, circuits in circuits_by_concepto.items():
        circuit_counts = {}
        for circuit in circuits:
            circuit_key = json.dumps(circuit, ensure_ascii=False)
            circuit_counts[circuit_key] = circuit_counts.get(circuit_key, 0) + 1

        for circuit_json_str, freq in circuit_counts.items():
            rows.append({
                "circuito": circuit_json_str,
                "concepto": concepto_name,
                "frecuencia": freq,
                "es_mas_frecuente": False,
            })

    result_df = pd.DataFrame(rows)

    if not result_df.empty:
        # Identify modal circuits per concepto
        result_df = identify_modal_circuits(result_df)

        # Parse circuito JSON
        result_df["circuito_parsed"] = result_df["circuito"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else []
        )
        result_df["circuito_json"] = result_df["circuito"]
        result_df["step_count"] = result_df["circuito_parsed"].apply(len)
        result_df["id"] = range(1, len(result_df) + 1)

    return result_df


@st.cache_data(ttl=300, show_spinner="Cargando estadísticas de pasos...")
def load_step_stats(concepto: Optional[str] = None, filters: Optional[FilterState] = None) -> pd.DataFrame:
    """
    Load step count statistics per concepto.

    When filters are applied, re-computes statistics from filtered circuits.

    Args:
        concepto: Optional concepto to filter by. If None, loads all.
        filters: Optional FilterState with date_range, conceptos, dependencias.

    Returns:
        DataFrame with columns: concepto, min_steps, max_steps, mean_steps,
        median_steps, mode_steps, std_steps, total_circuitos, total_expedientes
    """
    # If filters are applied, use filtered circuits
    if filters and (filters.date_range[0] or filters.date_range[1] or filters.conceptos or filters.dependencias or filters.asuntos):
        circuitos_df = load_circuitos(concepto, filters)
        if circuitos_df.empty:
            return pd.DataFrame(columns=[
                "concepto", "min_steps", "max_steps", "mean_steps", "median_steps",
                "mode_steps", "std_steps", "total_circuitos", "total_expedientes"
            ])
        # Build freq_df from circuitos
        freq_df = circuitos_df[["circuito", "concepto", "frecuencia"]].copy()
        return _compute_step_stats_from_freq(freq_df)

    db = get_connection()

    if concepto is not None:
        return _compute_step_stats_for_concepto(db, concepto)

    # Load all and compute in Python
    query = "SELECT circuito, concepto, frecuencia FROM circuitos"
    freq_df = pd.read_sql_query(query, db)

    if freq_df.empty:
        return pd.DataFrame(columns=[
            "concepto", "min_steps", "max_steps", "mean_steps", "median_steps",
            "mode_steps", "std_steps", "total_circuitos", "total_expedientes"
        ])

    return _compute_step_stats_from_freq(freq_df)


def _compute_step_stats_for_concepto(db: sqlite3.Connection, concepto: str) -> pd.DataFrame:
    """Compute step stats for a single concepto from database."""
    query = "SELECT concepto, circuito, frecuencia FROM circuitos WHERE concepto = ?"
    freq_df = pd.read_sql_query(query, db, params=[concepto])
    return _compute_step_stats_from_freq(freq_df)


def _compute_step_stats_from_freq(freq_df: pd.DataFrame) -> pd.DataFrame:
    """Compute step statistics from frequency DataFrame."""
    import numpy as np

    def count_steps(circuito_json: str) -> int:
        try:
            circuit = json.loads(circuito_json)
            return len(circuit) if isinstance(circuit, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0

    freq_df = freq_df.copy()
    freq_df["step_count"] = freq_df["circuito"].apply(count_steps)

    # Expand by frequency
    expanded_rows = []
    for _, row in freq_df.iterrows():
        expanded_rows.extend([{"concepto": row["concepto"], "step_count": row["step_count"]}] * int(row["frecuencia"]))

    if not expanded_rows:
        return pd.DataFrame(columns=[
            "concepto", "min_steps", "max_steps", "mean_steps", "median_steps",
            "mode_steps", "std_steps", "total_circuitos", "total_expedientes"
        ])

    expanded_df = pd.DataFrame(expanded_rows)

    stats_list = []
    for concepto, group in expanded_df.groupby("concepto"):
        step_counts = group["step_count"].values
        total_expedientes = len(step_counts)

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

    return pd.DataFrame(stats_list).sort_values("concepto").reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner="Cargando tiempos de permanencia...")
def load_permanence(concepto: Optional[str] = None, filters: Optional[FilterState] = None) -> pd.DataFrame:
    """
    Load permanence times between consecutive steps.

    When filters are applied, re-computes permanence from filtered expedientes.

    Args:
        concepto: Optional concepto to filter by. If None, loads all.
        filters: Optional FilterState with date_range, conceptos, dependencias.

    Returns:
        DataFrame with columns: expediente_id, numero, concepto, orden,
        dependencia, fecha_recepcion, permanence_days, is_final_step
    """
    db = get_connection()

    # Build WHERE clause for filters
    where_clauses = []
    params = []

    # Date range filter on expedientes.fecha_alta
    if filters and filters.date_range[0] is not None:
        where_clauses.append("e.fecha_alta >= ?")
        params.append(filters.date_range[0])
    if filters and filters.date_range[1] is not None:
        where_clauses.append("e.fecha_alta <= ?")
        params.append(filters.date_range[1])

    # Concepto filter from filters
    if filters and filters.conceptos:
        placeholders = ",".join("?" * len(filters.conceptos))
        where_clauses.append(f"e.concepto IN ({placeholders})")
        params.extend(filters.conceptos)

    # Dependencia filter
    if filters and filters.dependencias:
        placeholders = ",".join("?" * len(filters.dependencias))
        where_clauses.append(f"""
            e.id IN (
                SELECT DISTINCT expediente_id
                FROM movimientos
                WHERE dependencia IN ({placeholders})
            )
        """)
        params.extend(filters.dependencias)

    # Asunto filter
    if filters and filters.asuntos:
        placeholders = ",".join("?" * len(filters.asuntos))
        where_clauses.append(f"""
            e.id IN (
                SELECT DISTINCT ea.expediente_id
                FROM expediente_asuntos ea
                JOIN asuntos a ON ea.asunto_id = a.id
                WHERE a.asunto IN ({placeholders})
            )
        """)
        params.extend(filters.asuntos)

    # Additional concepto filter from function parameter
    if concepto is not None:
        where_clauses.append("e.concepto = ?")
        params.append(concepto)

    where_clause = ""
    if where_clauses:
        where_clause = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        SELECT
            e.id as expediente_id,
            e.numero,
            e.concepto,
            m.orden,
            m.fecha_recepcion,
            m.dependencia
        FROM expedientes e
        JOIN movimientos m ON e.id = m.expediente_id
        {where_clause}
        ORDER BY e.id, m.orden
    """

    df = pd.read_sql_query(query, db, params=params)

    if df.empty:
        return pd.DataFrame(columns=[
            "expediente_id", "numero", "concepto", "orden", "dependencia",
            "fecha_recepcion", "permanence_days", "is_final_step"
        ])

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

    return pd.DataFrame(result_rows)


@st.cache_data(ttl=300, show_spinner="Cargando dependencias...")
def load_dependencias() -> pd.DataFrame:
    """
    Load all unique dependencias for filter dropdown.

    Returns:
        DataFrame with columns: nombre, total_expedientes
    """
    db = get_connection()
    query = "SELECT nombre, total_expedientes FROM dependencias ORDER BY total_expedientes DESC"
    return pd.read_sql_query(query, db)


@st.cache_data(ttl=300, show_spinner="Cargando conceptos...")
def load_conceptos() -> pd.DataFrame:
    """
    Load all unique conceptos for filter dropdown.

    Returns:
        DataFrame with columns: concepto, cantidad
    """
    db = get_connection()
    query = "SELECT concepto, COUNT(*) as cantidad FROM expedientes GROUP BY concepto ORDER BY cantidad DESC"
    return pd.read_sql_query(query, db)


@st.cache_data(ttl=300, show_spinner="Cargando asuntos...")
def load_asuntos(concepto: Optional[str] = None) -> pd.DataFrame:
    """
    Load asuntos for a given concepto (or all if None).

    Args:
        concepto: Filter by concepto name. If None, returns all asuntos.

    Returns:
        DataFrame with columns: concepto, asunto, total_expedientes
    """
    db = get_connection()

    if concepto:
        query = """
            SELECT a.concepto, a.asunto, COUNT(ea.expediente_id) as total_expedientes
            FROM asuntos a
            LEFT JOIN expediente_asuntos ea ON a.id = ea.asunto_id
            WHERE a.concepto = ?
            GROUP BY a.concepto, a.asunto
            ORDER BY total_expedientes DESC
        """
        params = [concepto]
    else:
        query = """
            SELECT a.concepto, a.asunto, COUNT(ea.expediente_id) as total_expedientes
            FROM asuntos a
            LEFT JOIN expediente_asuntos ea ON a.id = ea.asunto_id
            GROUP BY a.concepto, a.asunto
            ORDER BY a.concepto, total_expedientes DESC
        """
        params = []

    return pd.read_sql_query(query, db, params=params)


def ensure_asuntos_populated() -> bool:
    """
    Ensure asuntos table is populated. Returns True if data exists.

    This function checks if asuntos are populated and triggers
    extraction if the table is empty (first run or after DB reset).
    """
    db = get_connection()

    # Check if asuntos table has data
    cursor = db.execute("SELECT COUNT(*) FROM asuntos")
    count = cursor.fetchone()[0]

    if count == 0:
        # Table is empty, populate from patterns
        from src.analysis.asuntos import populate_asuntos_table
        populate_asuntos_table()
        return True

    return True


@st.cache_data(ttl=300, show_spinner="Cargando tráfico de dependencias...")
def load_dependency_traffic(filters: FilterState) -> pd.DataFrame:
    """
    Load dependency traffic ranking with applied filters.

    Args:
        filters: FilterState to apply to expedientes.

    Returns:
        DataFrame with columns: dependencia, total_expedientes, total_movimientos,
        pct_expedientes, pct_movimientos
    """
    db = get_connection()
    where_clause, params = filters.to_sql_where()

    # Modify where clause to work with movimientos table
    where_clause = where_clause.replace("e.fecha_alta", "e.fecha_alta").replace("e.concepto", "e.concepto").replace("e.id", "e.id")

    query = f"""
        SELECT
            m.dependencia,
            COUNT(DISTINCT m.expediente_id) as total_expedientes,
            COUNT(*) as total_movimientos
        FROM movimientos m
        JOIN expedientes e ON m.expediente_id = e.id
        {where_clause}
        GROUP BY m.dependencia
        ORDER BY total_movimientos DESC
    """

    df = pd.read_sql_query(query, db, params=params)

    if df.empty:
        return pd.DataFrame(columns=[
            "dependencia", "total_expedientes", "total_movimientos",
            "pct_expedientes", "pct_movimientos"
        ])

    total_expedientes_all = df["total_expedientes"].sum()
    total_movimientos_all = df["total_movimientos"].sum()

    if total_expedientes_all > 0:
        df["pct_expedientes"] = (df["total_expedientes"] / total_expedientes_all * 100).round(2)
    else:
        df["pct_expedientes"] = 0.0

    if total_movimientos_all > 0:
        df["pct_movimientos"] = (df["total_movimientos"] / total_movimientos_all * 100).round(2)
    else:
        df["pct_movimientos"] = 0.0

    return df.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner="Cargando distribución de conceptos...")
def load_concept_distribution(filters: FilterState) -> pd.DataFrame:
    """
    Load concept distribution with applied filters.

    Args:
        filters: FilterState to apply.

    Returns:
        DataFrame with columns: concepto, cantidad, porcentaje
    """
    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT concepto, COUNT(*) as cantidad
        FROM expedientes e
        {where_clause}
        GROUP BY concepto
        ORDER BY cantidad DESC
    """

    df = pd.read_sql_query(query, db, params=params)

    if df.empty:
        return pd.DataFrame(columns=["concepto", "cantidad", "porcentaje"])

    total = df["cantidad"].sum()
    if total > 0:
        df["porcentaje"] = (df["cantidad"] / total * 100).round(2)
    else:
        df["porcentaje"] = 0.0

    return df.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner="Cargando datos mensuales...")
def load_monthly_trend(filters: FilterState) -> pd.DataFrame:
    """
    Load monthly expediente count trend with applied filters.

    Args:
        filters: FilterState to apply.

    Returns:
        DataFrame with columns: mes, cantidad, acumulado
    """
    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT
            strftime('%Y-%m', fecha_alta) as mes,
            COUNT(*) as cantidad
        FROM expedientes e
        {where_clause}
        GROUP BY mes
        ORDER BY mes
    """

    df = pd.read_sql_query(query, db, params=params)

    if df.empty:
        return pd.DataFrame(columns=["mes", "cantidad", "acumulado"])

    df["acumulado"] = df["cantidad"].cumsum()
    return df


def invalidate_cache() -> None:
    """
    Clear all Streamlit data caches.

    Call this after data pipeline runs to force refresh on next load.
    """
    st.cache_data.clear()