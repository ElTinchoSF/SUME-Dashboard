"""
Main entry point for SUME Dashboard Streamlit application.

Initializes page config, renders sidebar with global filters,
and routes to the selected page.
"""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from src.dashboard.components.filters import render_global_filters_sidebar
from src.dashboard.pages.overview import render_overview_page
from src.dashboard.pages.conceptos import render_conceptos_page
from src.dashboard.pages.circuitos import render_circuitos_page
from src.dashboard.pages.reportes import render_reportes_page


def main() -> None:
    """Main Streamlit application entry point."""

    # Custom CSS for FBCB institutional styling
    st.markdown("""
        <style>
        /* FBCB institutional colors */
        :root {
            --fbcb-green: #00A94F;
            --fbcb-green-hover: #008C41;
            --fbcb-green-light: #b2e8c4;
            --fbcb-green-50: #f0fdf4;
            --fbcb-green-100: #dcfce7;
            --unl-turquoise: #0088AA;
            --unl-dark: #244C5A;
        }

        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        /* KPI cards styling - FBCB theme */
        .stMetric {
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border: 1px solid #b2e8c4;
            border-radius: 10px;
            padding: 1.2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .stMetric label {
            color: #244C5A !important;
            font-weight: 500 !important;
        }
        .stMetric [data-testid="stMetricValue"] {
            color: #00A94F !important;
            font-weight: 700 !important;
        }
        .stMetric [data-testid="stMetricDelta"] {
            color: #212121 !important;
        }

        /* Hide Streamlit default menu and footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Hide the auto-generated sidebar page links from multi-page detection */
        [data-testid="stSidebarNav"] {display: none !important;}

        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #f0fdf4;
        }

        /* Radio buttons in sidebar */
        .stRadio > div {
            gap: 0.5rem;
        }

        /* Success/Info/Warning boxes */
        .stAlert {
            border-radius: 8px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header
    st.title("📊 SUME Dashboard")
    st.caption("Sistema de Análisis de Circuitos Administrativos - FBCB UNL")

    # Render global filters in sidebar and get current filter state
    filters = render_global_filters_sidebar()

    # Page routing via radio buttons
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
        label_visibility="collapsed",
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
    st.caption("SUME Dashboard v1.0.0 | Mesa de Entradas FBCB-UNL")


if __name__ == "__main__":
    main()
