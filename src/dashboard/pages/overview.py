"""
Page 1: Overview (Vista General).

Displays KPI cards, expedientes by concepto bar chart,
monthly trend line chart, and top 10 dependencias by traffic.
"""

import streamlit as st
import pandas as pd
import numpy as np

from src.dashboard.data import (
    load_expedientes,
    load_dependency_traffic,
    load_concept_distribution,
    load_monthly_trend,
    FilterState,
)
from src.dashboard.components.charts import (
    render_kpi_row,
    bar_chart_horizontal,
    line_chart_monthly,
    dependency_traffic_bar,
    concept_distribution_pie,
    apply_default_layout,
    COLORS,
)
from src.dashboard.components.filters import render_filter_summary


def render_overview_page(filters: FilterState) -> None:
    """Render the Overview page with KPIs and distribution charts."""
    # Page header
    st.header("📈 Vista General")
    render_filter_summary(filters)

    # Load data with filters
    with st.spinner("Cargando datos..."):
        expedientes_df = load_expedientes(filters)
        dep_traffic_df = load_dependency_traffic(filters)
        concept_dist_df = load_concept_distribution(filters)
        monthly_df = load_monthly_trend(filters)

    if expedientes_df.empty:
        st.warning("No hay expedientes que coincidan con los filtros seleccionados.")
        return

    # --- KPI Cards ---
    st.subheader("Indicadores Clave")

    total_iniciados = len(expedientes_df)
    total_movimientos = _get_total_movimientos(filters)
    tiempo_medio = _get_tiempo_medio_ciclo(filters)
    etapas_promedio = _get_etapas_promedio(filters)
    archivados = _get_archivados_count(filters)
    tasa_finalizacion = (archivados / total_iniciados * 100) if total_iniciados > 0 else 0
    top1 = _get_top_asunto(filters, n=1)
    top2 = _get_top_asunto(filters, n=2)

    # Row 1: Primary KPIs
    kpis_row1 = [
        {"label": "Expedientes Iniciados", "value": f"{total_iniciados:,}",
         "help": "Total de expedientes creados en el período"},
        {"label": "Total Movimientos", "value": f"{total_movimientos:,}",
         "help": "Total de pasos/movimientos registrados"},
        {"label": "Tiempo Medio de Ciclo", "value": f"{tiempo_medio:.1f} días",
         "help": "Promedio de días hábiles entre alta y última gestión"},
        {"label": "Etapas Promedio", "value": f"{etapas_promedio:.1f}",
         "help": "Promedio de pasos por expediente (promedio de promedios por concepto)"},
    ]
    render_kpi_row(kpis_row1)

    # Row 2: Archiving & Asunto KPIs
    kpis_row2 = [
        {"label": "Archivados", "value": f"{archivados:,}",
         "help": "Expedientes cuya última dependencia es Archivo Digital"},
        {"label": "Tasa de Finalización", "value": f"{tasa_finalizacion:.1f}%",
         "help": "Porcentaje de expedientes archivados sobre los iniciados"},
        {"label": "Asunto más Frecuente", "value": top1["label"],
         "help": f"{top1['count']:,} expedientes ({top1['pct']:.1f}%)"},
        {"label": "2° Asunto más Frecuente", "value": top2["label"],
         "help": f"{top2['count']:,} expedientes ({top2['pct']:.1f}%)"},
    ]
    render_kpi_row(kpis_row2)

    st.divider()

    # --- Row 1: Expedientes by Concepto + Monthly Trend ---
    st.subheader("Expedientes por Concepto")
    if not concept_dist_df.empty:
        fig = bar_chart_horizontal(
            concept_dist_df.head(15),
            x="cantidad",
            y="concepto",
            title="",
            height=500,
            hover_data=["porcentaje"],
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No hay datos de conceptos para mostrar.")

    st.divider()

    st.subheader("Tendencia Mensual")
    if not monthly_df.empty:
        fig = line_chart_monthly(
            monthly_df,
            date_col="mes",
            value_col="cantidad",
            title="",
            cumulative_col="acumulado",
            height=450,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No hay datos mensuales para mostrar.")

    st.divider()

    # --- Row 2: Top 10 Dependencias + Concept Distribution Pie ---
    st.subheader("Top 10 Dependencias por Tráfico")
    if not dep_traffic_df.empty:
        fig = dependency_traffic_bar(
            dep_traffic_df,
            title="",
            top_n=10,
            height=500,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No hay datos de dependencias para mostrar.")

    st.divider()

    st.subheader("Distribución de Conceptos")
    if not concept_dist_df.empty:
        fig = concept_distribution_pie(
            concept_dist_df.head(10),
            title="",
            height=550,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No hay distribución de conceptos para mostrar.")

    # --- Data Table (expandable) ---
    with st.expander("📋 Ver tabla de expedientes filtrados"):
        display_cols = ["numero", "concepto", "fecha_alta", "estado", "descripcion"]
        display_df = expedientes_df[display_cols].copy()
        display_df["fecha_alta"] = display_df["fecha_alta"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "numero": "Número",
                "concepto": "Concepto",
                "fecha_alta": "Fecha Alta",
                "estado": "Estado",
                "descripcion": "Descripción",
            },
        )


def _get_total_movimientos(filters: FilterState) -> int:
    """Get total movimientos count for filtered expedientes."""
    from src.database.connection import get_connection

    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT COUNT(*) as total
        FROM movimientos m
        JOIN expedientes e ON m.expediente_id = e.id
        {where_clause}
    """

    cursor = db.execute(query, params)
    result = cursor.fetchone()
    return result[0] if result else 0


def _get_archivados_count(filters: FilterState) -> int:
    """
    Count expedientes whose last movement is to 'Archivo Digital'.

    An expediente is considered archived only if its final destination
    (last movement by orden) is Archivo Digital.
    """
    from src.database.connection import get_connection

    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT COUNT(*) FROM (
            SELECT e.id
            FROM expedientes e
            JOIN movimientos m ON e.id = m.expediente_id
            JOIN (
                SELECT expediente_id, MAX(orden) as max_orden
                FROM movimientos
                GROUP BY expediente_id
            ) lm ON m.expediente_id = lm.expediente_id AND m.orden = lm.max_orden
            WHERE m.dependencia LIKE '%Archivo Digital%'
            {where_clause.replace('WHERE', 'AND', 1) if where_clause else ''}
        )
    """

    cursor = db.execute(query, params)
    result = cursor.fetchone()
    return result[0] if result else 0


def _get_tiempo_medio_ciclo(filters: FilterState) -> float:
    """
    Average business days (weekdays) between fecha_alta and last movement.

    Calculates the lifecycle time for each expediente as the number of
    weekdays between its creation date (fecha_alta) and its last movement date.
    """
    from src.database.connection import get_connection

    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT e.fecha_alta, MAX(m.fecha_recepcion) as fecha_ultima
        FROM expedientes e
        JOIN movimientos m ON e.id = m.expediente_id
        WHERE e.fecha_alta IS NOT NULL AND m.fecha_recepcion IS NOT NULL
        {('AND ' + where_clause.replace('WHERE ', '', 1)) if where_clause else ''}
        GROUP BY e.id
    """

    cursor = db.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        return 0.0

    business_days_list = []
    for fecha_alta, fecha_ultima in rows:
        try:
            start = pd.Timestamp(fecha_alta)
            end = pd.Timestamp(fecha_ultima)
            if end >= start:
                bd = int(np.busday_count(start.date(), end.date()))
                business_days_list.append(bd)
            elif end < start:
                # Some data inconsistency: last movement before creation
                business_days_list.append(0)
        except Exception:
            continue

    return float(np.mean(business_days_list)) if business_days_list else 0.0


def _get_etapas_promedio(filters: FilterState) -> float:
    """
    Average steps per expediente using promedio de promedios by concepto.

    For each concepto: avg_steps = total_movimientos / total_expedientes.
    Then averages those concepto-level averages across all conceptos.
    """
    from src.database.connection import get_connection

    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT AVG(concepto_avg) FROM (
            SELECT COUNT(m.id) * 1.0 / COUNT(DISTINCT e.id) as concepto_avg
            FROM expedientes e
            JOIN movimientos m ON e.id = m.expediente_id
            {where_clause}
            GROUP BY e.concepto
            HAVING COUNT(DISTINCT e.id) > 0
        )
    """

    cursor = db.execute(query, params)
    result = cursor.fetchone()
    return float(result[0]) if result and result[0] else 0.0


def _get_top_asunto(filters: FilterState, n: int = 1) -> dict:
    """
    Get the N-th most frequent asunto with count and percentage.

    Args:
        filters: FilterState to apply.
        n: 1 for most frequent, 2 for second most, etc.

    Returns:
        dict with keys: label, count, pct
    """
    from src.database.connection import get_connection

    db = get_connection()
    where_clause, params = filters.to_sql_where()

    # Get total expedientes for percentage calculation
    total_query = f"""
        SELECT COUNT(*) FROM expedientes e
        {where_clause}
    """
    cursor = db.execute(total_query, params)
    total = cursor.fetchone()[0]

    if total == 0:
        return {"label": "N/A", "count": 0, "pct": 0.0}

    # Get N-th most frequent asunto
    query = f"""
        SELECT a.asunto, COUNT(ea.expediente_id) as total
        FROM expediente_asuntos ea
        JOIN asuntos a ON ea.asunto_id = a.id
        JOIN expedientes e ON ea.expediente_id = e.id
        {where_clause}
        GROUP BY a.asunto
        ORDER BY total DESC
        LIMIT 1 OFFSET ?
    """

    cursor = db.execute(query, params + [n - 1])
    result = cursor.fetchone()

    if not result:
        return {"label": "N/A", "count": 0, "pct": 0.0}

    return {
        "label": result[0],
        "count": result[1],
        "pct": result[1] / total * 100,
    }