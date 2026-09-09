"""
Page 2: Conceptos (Análisis por Concepto).

Deep-dive analysis for a selected concepto including:
- Circuit frequency table with modal highlighting
- Step count histogram with mean/median/mode lines
- Permanence time boxplot by dependencia
"""

import json
import streamlit as st
import pandas as pd

from src.dashboard.data import (
    load_circuitos,
    load_step_stats,
    load_permanence,
    load_conceptos,
    FilterState,
)
from src.dashboard.components.charts import (
    histogram_steps,
    boxplot_permanence,
    circuit_frequency_table,
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

    st.divider()

    # Load data for selected concepto
    with st.spinner(f"Cargando datos para '{selected_concepto}'..."):
        circuitos_df = load_circuitos(selected_concepto)
        step_stats_df = load_step_stats(selected_concepto)
        permanence_df = load_permanence(selected_concepto)

    if circuitos_df.empty:
        st.warning(f"No hay circuitos registrados para el concepto '{selected_concepto}'.")
        return

    # --- Circuit Frequency Table ---
    st.subheader("Frecuencia de Circuitos")

    # Format for display
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

    # Style the dataframe
    def highlight_modal(row):
        if row["Es Modal"] == "✅ Sí":
            return ["background-color: #E8F5E9"] * len(row)
        return [""] * len(row)

    st.dataframe(
        display_df[["Circuito", "Frecuencia", "% del total", "Es Modal"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Circuito": st.column_config.TextColumn("Circuito", width="large"),
            "Frecuencia": st.column_config.NumberColumn("Frecuencia", format="%d"),
            "% del total": st.column_config.NumberColumn("% del total", format="%.1f%%"),
            "Es Modal": st.column_config.TextColumn("Es Modal", width="small"),
        },
    ).style.apply(highlight_modal, axis=1) if hasattr(st, 'style') else None

    # Also show as interactive Plotly table
    fig_table = circuit_frequency_table(circuitos_df, title="", height=min(400, 100 + len(circuitos_df) * 35))
    st.plotly_chart(fig_table, use_container_width=True)

    st.divider()

    # --- Row 1: Step Count Histogram ---
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Distribución de Cantidad de Pasos")

        if not step_stats_df.empty:
            stats_row = step_stats_df.iloc[0]
            mean_steps = stats_row.get("mean_steps", 0)
            median_steps = stats_row.get("median_steps", 0)
            mode_steps = stats_row.get("mode_steps", 0)

            fig = histogram_steps(
                circuitos_df,
                bins=15,
                title="",
                mean_line=mean_steps,
                median_line=median_steps,
                mode_line=mode_steps,
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Show statistics summary
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

    with col2:
        st.subheader("Permanencia por Dependencia")

        if not permanence_df.empty:
            # Filter out final steps (None permanence)
            valid_permanence = permanence_df[
                permanence_df["permanence_days"].notna() &
                (permanence_df["permanence_days"] >= 0)
            ].copy()

            if not valid_permanence.empty:
                fig = boxplot_permanence(
                    valid_permanence,
                    x="dependencia",
                    y="permanence_days",
                    title="",
                    height=400,
                    points="outliers",
                )
                st.plotly_chart(fig, use_container_width=True)

                # Show summary stats
                dep_stats = valid_permanence.groupby("dependencia")["permanence_days"].agg([
                    "count", "mean", "median", "std", "min", "max"
                ]).round(1).sort_values("count", ascending=False)

                with st.expander("📊 Ver estadísticas detalladas por dependencia"):
                    st.dataframe(
                        dep_stats.reset_index(),
                        use_container_width=True,
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

    # --- Additional: Step Statistics Summary ---
    with st.expander("📈 Ver estadísticas completas de pasos"):
        if not step_stats_df.empty:
            st.dataframe(
                step_stats_df,
                use_container_width=True,
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