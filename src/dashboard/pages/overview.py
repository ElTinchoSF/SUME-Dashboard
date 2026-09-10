"""
Page 1: Overview (Vista General).

Displays KPI cards, expedientes by concepto bar chart,
monthly trend line chart, and top 10 dependencias by traffic.
"""

import streamlit as st
import pandas as pd

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

    total_expedientes = len(expedientes_df)
    total_movimientos = int(expedientes_df.get("total_movimientos", pd.Series([0])).sum()) if "total_movimientos" in expedientes_df.columns else 0
    # We need to compute total movements from filtered data
    total_movimientos = _get_total_movimientos(filters)

    unique_conceptos = expedientes_df["concepto"].nunique()
    unique_dependencias = _get_unique_dependencias(filters)

    kpis = [
        {"label": "Total Expedientes", "value": f"{total_expedientes:,}",
         "help": "Número total de expedientes en el rango filtrado"},
        {"label": "Total Movimientos", "value": f"{total_movimientos:,}",
         "help": "Total de pasos/movimientos registrados"},
        {"label": "Conceptos Únicos", "value": f"{unique_conceptos}",
         "help": "Cantidad de tipos de trámite distintos"},
        {"label": "Dependencias Únicas", "value": f"{unique_dependencias}",
         "help": "Cantidad de dependencias distintas involucradas"},
    ]
    render_kpi_row(kpis)

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
            max_label_length=22,
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
            max_label_length=22,
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


def _get_unique_dependencias(filters: FilterState) -> int:
    """Get unique dependencias count for filtered expedientes."""
    from src.database.connection import get_connection

    db = get_connection()
    where_clause, params = filters.to_sql_where()

    query = f"""
        SELECT COUNT(DISTINCT m.dependencia) as total
        FROM movimientos m
        JOIN expedientes e ON m.expediente_id = e.id
        {where_clause}
    """

    cursor = db.execute(query, params)
    result = cursor.fetchone()
    return result[0] if result else 0