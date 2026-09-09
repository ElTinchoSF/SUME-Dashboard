"""
Main entry point for SUME Dashboard Streamlit application.

Initializes page config, renders sidebar with global filters,
and routes to the selected page.
"""

import streamlit as st

from src.dashboard.components.filters import render_global_filters_sidebar, get_filter_state
from src.dashboard.pages.overview import render_overview_page
from src.dashboard.pages.conceptos import render_conceptos_page
from src.dashboard.pages.circuitos import render_circuitos_page
from src.dashboard.pages.reportes import render_reportes_page


def main() -> None:
    """Main Streamlit application entry point."""
    # Page configuration
    st.set_page_config(
        page_title="SUME Dashboard - Análisis de Circuitos Administrativos",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS for better styling
    st.markdown("""
        <style>
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .stMetric {
            background-color: #FAFAFA;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 1rem;
        }
        .stMetric > div {
            padding: 0;
        }
        /* Hide Streamlit default menu and footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    # Header
    st.title("📊 SUME Dashboard")
    st.caption("Sistema de Análisis de Circuitos Administrativos - FBCB UNL")

    # Render global filters in sidebar and get current filter state
    filters = render_global_filters_sidebar()

    # Page routing
    page = st.sidebar.radio(
        "📄 Página",
        options=[
            "📈 Vista General",
            "📋 Análisis por Concepto",
            "🔄 Visualización de Circuitos",
            "📑 Reportes ISO 9001",
        ],
        index=0,
        key="page_selector",
    )

    st.divider()

    # Render selected page
    if page == "📈 Vista General":
        render_overview_page(filters)
    elif page == "📋 Análisis por Concepto":
        render_conceptos_page(filters)
    elif page == "🔄 Visualización de Circuitos":
        render_circuitos_page(filters)
    elif page == "📑 Reportes ISO 9001":
        render_reportes_page(filters)

    # Footer
    st.divider()
    st.caption("SUME Dashboard v1.0.0 | Mesa de Entradas FBCB-UNL | Datos actualizados automáticamente cada 5 min")


if __name__ == "__main__":
    main()