"""
Page 2: Conceptos (Análisis por Concepto).

Deep-dive analysis for a selected concepto including:
- Step count histogram with mean/median/mode lines
- Permanence time boxplot by dependencia
- Circuit frequency table with modal highlighting
"""

import json
import streamlit as st
import pandas as pd

from src.dashboard.data import (
    load_circuitos,
    load_step_stats,
    load_permanence,
    load_conceptos,
    load_asuntos,
    load_asunto_distribution,
    ensure_asuntos_populated,
    FilterState,
    _compute_step_stats_from_freq,
)
from src.dashboard.components.charts import (
    histogram_steps,
    boxplot_permanence,
    circuit_frequency_table,
    bar_chart_horizontal,
    apply_default_layout,
    COLORS,
)
from src.dashboard.components.filters import render_filter_summary


def render_conceptos_page(filters: FilterState) -> None:
    """Render the Conceptos analysis page."""
    st.header("📋 Análisis por Concepto")
    render_filter_summary(filters)

    # Load available conceptos
    conceptos_df = load_conceptos()
    all_conceptos = conceptos_df["concepto"].tolist() if not conceptos_df.empty else []

    if not all_conceptos:
        st.warning("No hay conceptos disponibles en la base de datos.")
        return

    # Concepto selector
    selected_concepto = st.selectbox(
        "Seleccionar concepto",
        options=all_conceptos,
        index=0,
        key="concepto_selector",
        help="Elegir un concepto para analizar sus circuitos y estadísticas",
    )

    if not selected_concepto:
        st.info("Seleccione un concepto para continuar.")
        return

    # Asunto selector (cascada: solo muestra asuntos del concepto seleccionado)
    ensure_asuntos_populated()
    asuntos_df = load_asuntos(concepto=selected_concepto)
    all_asuntos = asuntos_df["asunto"].tolist() if not asuntos_df.empty else []

    # Get current asunto from filters if it matches this concepto
    current_asunto = None
    if filters.asuntos and len(filters.asuntos) == 1:
        if filters.asuntos[0] in all_asuntos:
            current_asunto = filters.asuntos[0]

    selected_asunto = st.selectbox(
        "Seleccionar asunto",
        options=["Todos los asuntos"] + all_asuntos,
        index=0 if current_asunto is None else all_asuntos.index(current_asunto) + 1,
        key="conceptos_asunto_selector",
        help="Filtrar por tipo de trámite específico (opcional)",
    )

    # Apply asunto filter if selected
    if selected_asunto and selected_asunto != "Todos los asuntos":
        page_filters = FilterState(
            date_range=filters.date_range,
            conceptos=filters.conceptos,
            dependencias=filters.dependencias,
            asuntos=(selected_asunto,),
        )
    else:
        page_filters = FilterState(
            date_range=filters.date_range,
            conceptos=filters.conceptos,
            dependencias=filters.dependencias,
            asuntos=(),
        )

    st.divider()

    # Load data for selected concepto with filters
    with st.spinner(f"Cargando datos para '{selected_concepto}'..."):
        circuitos_df = load_circuitos(selected_concepto, page_filters)
        step_stats_df = load_step_stats(selected_concepto, page_filters)
        permanence_df = load_permanence(selected_concepto, page_filters)

    if circuitos_df.empty:
        st.warning(f"No hay circuitos registrados para el concepto '{selected_concepto}'.")
        return

    # ================================================================
    # 1. EXPEDIENTES POR ASUNTO
    # ================================================================
    st.subheader("Expedientes por Asunto")

    asuntos_dist_df = load_asunto_distribution(selected_concepto, page_filters)
    if not asuntos_dist_df.empty:
        total_asuntos = asuntos_dist_df["total_expedientes"].sum()
        asuntos_dist_df = asuntos_dist_df.copy()
        asuntos_dist_df["porcentaje"] = (asuntos_dist_df["total_expedientes"] / total_asuntos * 100).round(1)

        fig = bar_chart_horizontal(
            asuntos_dist_df,
            x="total_expedientes",
            y="asunto",
            title="",
            height=max(300, len(asuntos_dist_df) * 40),
            hover_data=["porcentaje"],
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No hay datos de asuntos para este concepto.")

    st.divider()

    # ================================================================
    # 2. FRECUENCIA DE CIRCUITOS (tabla clickeable — va antes del histograma)
    # ================================================================
    st.subheader("Frecuencia de Circuitos")
    st.caption("Hacé click en una fila para filtrar el histograma de pasos")

    display_df = circuitos_df.copy()

    def format_circuit(circuito_json: str) -> str:
        try:
            circuit = json.loads(circuito_json)
            return " → ".join(circuit)
        except (json.JSONDecodeError, TypeError):
            return str(circuito_json)

    display_df["Circuito"] = display_df["circuito_json"].apply(format_circuit)
    display_df["Frecuencia"] = display_df["frecuencia"]
    display_df["% del total"] = (display_df["frecuencia"] / display_df["frecuencia"].sum() * 100).round(1)
    display_df["Es Modal"] = display_df["es_mas_frecuente"].apply(lambda x: "✅ Sí" if x else "No")

    # Interactive frequency table with row selection
    editor_result = st.dataframe(
        display_df[["Circuito", "Frecuencia", "% del total", "Es Modal"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Circuito": st.column_config.TextColumn("Circuito", width="large"),
            "Frecuencia": st.column_config.NumberColumn("Frecuencia", format="%d"),
            "% del total": st.column_config.NumberColumn("% del total", format="%.1f%%"),
            "Es Modal": st.column_config.TextColumn("Es Modal", width="small"),
        },
        on_select="rerun",
        key="conceptos_freq_table",
    )

    fig_table = circuit_frequency_table(circuitos_df, title="", height=min(400, 100 + len(circuitos_df) * 35))
    st.plotly_chart(fig_table, width="stretch")

    # Check if a circuit was selected — filter step stats accordingly
    selected_circuit_json = None
    if editor_result and editor_result.selection and editor_result.selection.rows:
        selected_idx = editor_result.selection.rows[0]
        selected_circuit_json = circuitos_df.iloc[selected_idx]["circuito_json"]

    # Compute step stats (filtered or full)
    if selected_circuit_json:
        selected_row = circuitos_df[circuitos_df["circuito_json"] == selected_circuit_json].iloc[0]
        selected_circuit_df = pd.DataFrame([selected_row])
        selected_circuit_df["concepto"] = selected_concepto
        filtered_step_stats_df = _compute_step_stats_from_freq(
            selected_circuit_df[["circuito", "concepto", "frecuencia"]]
        )
        filtered_circuitos_df = selected_circuit_df
    else:
        filtered_step_stats_df = step_stats_df
        filtered_circuitos_df = circuitos_df

    st.divider()

    # ================================================================
    # 3. DISTRIBUCIÓN DE CANTIDAD DE PASOS
    # ================================================================
    st.subheader("Distribución de Cantidad de Pasos")

    if not filtered_step_stats_df.empty:
        stats_row = filtered_step_stats_df.iloc[0]
        mean_steps = stats_row.get("mean_steps", 0)
        median_steps = stats_row.get("median_steps", 0)
        mode_steps = stats_row.get("mode_steps", 0)

        fig = histogram_steps(
            filtered_circuitos_df,
            bins=15,
            title="",
            mean_line=mean_steps,
            median_line=median_steps,
            mode_line=mode_steps,
            height=450,
        )
        st.plotly_chart(fig, width="stretch")

        st.caption(f"""
        **Estadísticas de pasos:**
        - Mínimo: {int(stats_row.get('min_steps', 0))} pasos
        - Máximo: {int(stats_row.get('max_steps', 0))} pasos
        - Media: {mean_steps:.1f} pasos
        - Mediana: {median_steps:.1f} pasos
        - Moda: {int(mode_steps)} pasos
        - Desv. estándar: {stats_row.get('std_steps', 0):.1f} pasos
        - Total expedientes: {int(stats_row.get('total_expedientes', 0)):,}
        """)
    else:
        st.info("No hay datos de pasos para mostrar.")

    st.divider()

    # ================================================================
    # 3. PERMANENCIA POR DEPENDENCIA
    # ================================================================
    st.subheader("Permanencia por Dependencia")

    if not permanence_df.empty:
        valid_permanence = permanence_df[
            permanence_df["permanence_days"].notna() &
            (permanence_df["permanence_days"] >= 0) &
            (~permanence_df["dependencia"].str.contains("Archivo Digital", case=False, na=False))
        ].copy()

        if not valid_permanence.empty:
            fig = boxplot_permanence(
                valid_permanence,
                x="dependencia",
                y="permanence_days",
                title="",
                height=500,
                points="outliers",
            )
            st.plotly_chart(fig, width="stretch")

            dep_stats = valid_permanence.groupby("dependencia")["permanence_days"].agg([
                "count", "mean", "median", "std", "min", "max"
            ]).round(1).sort_values("count", ascending=False)

            with st.expander("📊 Ver estadísticas detalladas por dependencia"):
                st.dataframe(
                    dep_stats.reset_index(),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "dependencia": "Dependencia",
                        "count": "N° Movimientos",
                        "mean": "Media (días)",
                        "median": "Mediana (días)",
                        "std": "Desv. Est.",
                        "min": "Mín (días)",
                        "max": "Máx (días)",
                    },
                )
        else:
            st.info("No hay datos de permanencia válidos (todos son pasos finales).")
    else:
        st.info("No hay datos de permanencia para mostrar.")

    st.divider()

    # ================================================================
    # 4. ESTADÍSTICAS COMPLETAS DE PASOS
    # ================================================================
    with st.expander("📈 Ver estadísticas completas de pasos"):
        if not filtered_step_stats_df.empty:
            st.dataframe(
                filtered_step_stats_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "concepto": "Concepto",
                    "min_steps": "Mín",
                    "max_steps": "Máx",
                    "mean_steps": "Media",
                    "median_steps": "Mediana",
                    "mode_steps": "Moda",
                    "std_steps": "Desv. Est.",
                    "total_circuitos": "Circuitos Únicos",
                    "total_expedientes": "Total Expedientes",
                },
            )
        else:
            st.info("No hay estadísticas disponibles.")
