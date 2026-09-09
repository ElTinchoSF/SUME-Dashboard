"""
Page 3: Circuitos (Visualización de Circuitos).

Visualizes administrative circuits as interactive flow diagrams:
- Sankey diagram for modal circuit
- View toggle: Modal only / All circuits (parallel sets)
- Expandable circuit detail table with expediente links
"""

import json
import streamlit as st
import pandas as pd

from src.dashboard.data import (
    load_circuitos,
    load_conceptos,
    FilterState,
)
from src.dashboard.components.charts import (
    sankey_circuit,
    parallel_sets,
    apply_default_layout,
    COLORS,
)
from src.dashboard.components.filters import render_filter_summary


def render_circuitos_page(filters: FilterState) -> None:
    """Render the Circuitos visualization page."""
    st.header("🔄 Visualización de Circuitos")
    render_filter_summary(filters)

    # Load available conceptos
    conceptos_df = load_conceptos()
    all_conceptos = conceptos_df["concepto"].tolist() if not conceptos_df.empty else []

    if not all_conceptos:
        st.warning("No hay conceptos disponibles en la base de datos.")
        return

    # Concepto selector
    col_select, col_toggle = st.columns([3, 1])

    with col_select:
        selected_concepto = st.selectbox(
            "Seleccionar concepto",
            options=all_conceptos,
            index=0,
            key="circuitos_concepto_selector",
            help="Elegir un concepto para visualizar sus circuitos",
        )

    with col_toggle:
        view_mode = st.radio(
            "Vista",
            options=["Solo Modal", "Todos los Circuitos"],
            index=0,
            horizontal=True,
            key="circuitos_view_mode",
            help="Ver solo el circuito modal o comparar todos",
        )

    if not selected_concepto:
        st.info("Seleccione un concepto para continuar.")
        return

    st.divider()

    # Load circuitos for selected concepto
    with st.spinner(f"Cargando circuitos para '{selected_concepto}'..."):
        circuitos_df = load_circuitos(selected_concepto)

    if circuitos_df.empty:
        st.warning(f"No hay circuitos registrados para el concepto '{selected_concepto}'.")
        return

    # Separate modal and non-modal
    modal_df = circuitos_df[circuitos_df["es_mas_frecuente"]]
    other_df = circuitos_df[~circuitos_df["es_mas_frecuente"]]

    if view_mode == "Solo Modal":
        _render_modal_view(modal_df, selected_concepto)
    else:
        _render_all_circuits_view(circuitos_df, selected_concepto)

    st.divider()

    # --- Circuit Detail Table (expandable) ---
    with st.expander("📋 Ver detalle de circuitos y expedientes", expanded=False):
        _render_circuit_detail_table(circuitos_df, selected_concepto)


def _render_modal_view(modal_df: pd.DataFrame, concepto: str) -> None:
    """Render the modal circuit Sankey diagram."""
    st.subheader(f"Circuito Modal - {concepto}")

    if modal_df.empty:
        st.warning("No se ha identificado un circuito modal para este concepto.")
        return

    modal_row = modal_df.iloc[0]
    circuito_json = modal_row["circuito_json"]
    frecuencia = int(modal_row["frecuencia"])

    # For modal circuit, we need transition counts
    # These would ideally come from the analyzer; for now, use frequency as all transitions
    try:
        circuit = json.loads(circuito_json)
        # Create counts: each transition has the same frequency (simplified)
        counts = [frecuencia] * (len(circuit) - 1)
    except (json.JSONDecodeError, TypeError):
        circuit = []
        counts = []

    if len(circuit) < 2:
        st.info("El circuito modal tiene menos de 2 pasos.")
        return

    # Display circuit info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Frecuencia", f"{frecuencia:,}")
    with col2:
        st.metric("Pasos", len(circuit))
    with col3:
        pct = (frecuencia / circuitos_df["frecuencia"].sum() * 100) if 'circuitos_df' in globals() else 0
        st.metric("% del total", f"{pct:.1f}%")

    # Sankey diagram
    fig = sankey_circuit(
        circuito_json,
        counts,
        title=f"Circuito Modal: {concepto}",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Show circuit as text
    st.caption("**Secuencia del circuito:**")
    for i, step in enumerate(circuit):
        prefix = "🟢 " if i == 0 else ("→ " if i > 0 else "")
        st.caption(f"{prefix}{step} ({counts[i-1] if i > 0 else frecuencia} expedientes)")


def _render_all_circuits_view(circuitos_df: pd.DataFrame, concepto: str) -> None:
    """Render all circuits comparison view."""
    st.subheader(f"Todos los Circuitos - {concepto}")

    total_expedientes = circuitos_df["frecuencia"].sum()

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Circuitos Únicos", len(circuitos_df))
    with col2:
        st.metric("Total Expedientes", f"{total_expedientes:,}")
    with col3:
        modal_count = circuitos_df[circuitos_df["es_mas_frecuente"]]["frecuencia"].sum()
        st.metric("Cobertura Modal", f"{modal_count/total_expedientes*100:.1f}%" if total_expedientes > 0 else "0%")

    # Parallel sets diagram
    st.caption("Diagrama de Conjuntos Paralelos (circuitos ordenados por frecuencia)")
    fig = parallel_sets(circuitos_df, title="", height=550, max_circuits=12)
    st.plotly_chart(fig, use_container_width=True)

    # Frequency table
    st.caption("Tabla de frecuencias (ordenada descendente)")
    _render_frequency_table(circuitos_df)


def _render_frequency_table(circuitos_df: pd.DataFrame) -> None:
    """Render a sortable frequency table."""
    import json

    display_df = circuitos_df.copy()

    def format_circuit(circuito_json: str) -> str:
        try:
            circuit = json.loads(circuito_json)
            return " → ".join(circuit)
        except (json.JSONDecodeError, TypeError):
            return str(circuito_json)

    display_df["Circuito"] = display_df["circuito_json"].apply(format_circuit)
    display_df["Frecuencia"] = display_df["frecuencia"]
    display_df["%"] = (display_df["frecuencia"] / display_df["frecuencia"].sum() * 100).round(1)
    display_df["Modal"] = display_df["es_mas_frecuente"].apply(lambda x: "✅" if x else "")

    st.dataframe(
        display_df[["Modal", "Circuito", "Frecuencia", "%"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Modal": st.column_config.TextColumn("", width="small"),
            "Circuito": st.column_config.TextColumn("Circuito", width="large"),
            "Frecuencia": st.column_config.NumberColumn("Frecuencia", format="%d"),
            "%": st.column_config.NumberColumn("%", format="%.1f%%"),
        },
    )


def _render_circuit_detail_table(circuitos_df: pd.DataFrame, concepto: str) -> None:
    """Render expandable detail table per circuit with expediente numbers and SUME links."""
    from src.database.connection import get_connection

    db = get_connection()

    for _, circuit_row in circuitos_df.iterrows():
        circuito_json = circuit_row["circuito_json"]
        frecuencia = int(circuit_row["frecuencia"])
        es_modal = bool(circuit_row["es_mas_frecuente"])

        try:
            circuit = json.loads(circuito_json)
        except (json.JSONDecodeError, TypeError):
            continue

        modal_badge = " 🟢 **MODAL**" if es_modal else ""
        with st.expander(f"{'🟢' if es_modal else '🟠'} Circuito ({frecuencia} expedientes){modal_badge}", expanded=es_modal):
            # Show circuit path
            st.markdown("**Ruta:**")
            for i, step in enumerate(circuit):
                prefix = "1️⃣ " if i == 0 else f"{i+1}️⃣ "
                st.markdown(f"{prefix}{step}")

            # Get expedientes for this circuit
            expedientes = _get_expedientes_for_circuit(db, concepto, circuito_json)

            if expedientes:
                st.markdown("**Expedientes:**")
                for exp in expedientes:
                    numero = exp["numero"]
                    fecha_alta = exp["fecha_alta"]
                    # SUME detail link
                    settings = None
                    try:
                        from src.config import get_settings
                        settings = get_settings()
                        sume_url = f"{settings.sume.base_url}{settings.sume.detail_path}?numero={numero}"
                    except Exception:
                        sume_url = f"https://servicios.unl.edu.ar/expedientes/ver_expediente.php?numero={numero}"

                    st.markdown(f"- [{numero}]({sume_url}) — Alta: {fecha_alta}")
            else:
                st.caption("No se encontraron expedientes para este circuito.")


def _get_expedientes_for_circuit(db, concepto: str, circuito_json: str, limit: int = 50) -> list[dict]:
    """
    Get expedientes matching a specific circuit pattern.

    This is a simplified query - in production, you might want to use the circuitos table
    or a more sophisticated matching approach.
    """
    try:
        circuit = json.loads(circuito_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if len(circuit) < 2:
        return []

    # Build query to find expedientes with this exact circuit sequence
    # This is complex in SQL; we'll do a simplified version
    # For now, return expedientes with matching concepto and first few movements

    # Simple approach: get expedientes of this concepto with the first movement matching
    first_dep = circuit[1] if len(circuit) > 1 else None  # Skip MDE

    if not first_dep:
        return []

    query = """
        SELECT e.numero, e.fecha_alta
        FROM expedientes e
        JOIN movimientos m ON e.id = m.expediente_id
        WHERE e.concepto = ?
          AND m.orden = 1
          AND m.dependencia = ?
        ORDER BY e.fecha_alta DESC
        LIMIT ?
    """

    cursor = db.execute(query, (concepto, first_dep, limit))
    rows = cursor.fetchall()

    return [{"numero": row["numero"], "fecha_alta": row["fecha_alta"]} for row in rows]