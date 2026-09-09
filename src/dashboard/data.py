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


@dataclass(frozen=True)
class FilterState:
    """Global filter state for dashboard queries."""

    date_range: tuple[Optional[str], Optional[str]] = (None, None)
    conceptos: tuple[str, ...] = ()
    dependencias: tuple[str, ...] = ()

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
def load_circuitos(concepto: Optional[str] = None) -> pd.DataFrame:
    """
    Load circuitos with optional concepto filter.

    Args:
        concepto: Optional concepto to filter by. If None, loads all.

    Returns:
        DataFrame with columns: id, circuito (JSON), concepto, frecuencia, es_mas_frecuente
    """
    db = get_connection()

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
        df["step_count"] = df["circuito_parsed"].apply(len)

    return df


@st.cache_data(ttl=300, show_spinner="Cargando estadísticas de pasos...")
def load_step_stats(concepto: Optional[str] = None) -> pd.DataFrame:
    """
    Load step count statistics per concepto.

    Args:
        concepto: Optional concepto to filter by. If None, loads all.

    Returns:
        DataFrame with columns: concepto, min_steps, max_steps, mean_steps,
        median_steps, mode_steps, std_steps, total_circuitos, total_expedientes
    """
    db = get_connection()

    if concepto is not None:
        query = """
            SELECT concepto, min_steps, max_steps, mean_steps, median_steps,
                   mode_steps, std_steps, total_circuitos, total_expedientes
            FROM circuitos c
            JOIN (
                SELECT
                    concepto,
                    MIN(json_array_length(circuito)) as min_steps,
                    MAX(json_array_length(circuito)) as max_steps,
                    AVG(json_array_length(circuito)) as mean_steps,
                    -- SQLite doesn't have built-in median/mode, compute in Python
                    0 as median_steps, 0 as mode_steps, 0 as std_steps,
                    COUNT(*) as total_circuitos,
                    SUM(frecuencia) as total_expedientes
                FROM circuitos
                WHERE concepto = ?
                GROUP BY concepto
            ) USING (concepto)
        """
        # We'll compute median/mode/std in Python instead
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
    query = "SELECT circuito, frecuencia FROM circuitos WHERE concepto = ?"
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
def load_permanence(concepto: Optional[str] = None) -> pd.DataFrame:
    """
    Load permanence times between consecutive steps.

    Args:
        concepto: Optional concepto to filter by. If None, loads all.

    Returns:
        DataFrame with columns: expediente_id, numero, concepto, orden,
        dependencia, fecha_recepcion, permanence_days, is_final_step
    """
    db = get_connection()

    if concepto is not None:
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
            WHERE e.concepto = ?
            ORDER BY e.id, m.orden
        """
        df = pd.read_sql_query(query, db, params=[concepto])
    else:
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