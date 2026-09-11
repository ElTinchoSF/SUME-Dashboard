"""
Main entry point for SUME Dashboard Streamlit application.

Initializes page config, renders sidebar with global filters,
and routes to the selected page.
"""

import sys
import base64
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

    # Set wide layout to maximize content area
    st.set_page_config(
        page_title="SUME Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="locked"
    )

    # Load logo once for reuse
    logo_path = Path("Docs/Logo FBCB-UNL.png")
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode() if logo_path.exists() else ""

    # Custom CSS for FBCB institutional styling
    st.html("""
        <style>
        /* Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Lato:wght@400;700&display=swap');

        /* ══════════════════════════════════════════════
           HEADER: Make transparent, reduce height
           ══════════════════════════════════════════════ */
        .stAppHeader {
            background-color: rgba(255, 255, 255, 0.0) !important;
            visibility: visible !important;
            height: 2rem !important;
            z-index: 1 !important;
        }
        [data-testid="stToolbar"] { 
            background: transparent !important; 
            height: 2rem !important; 
            z-index: 1 !important;
        }
        [data-testid="stDecoration"] { display: none !important; }

        /* ══════════════════════════════════════════════
           LAYOUT: Minimal padding - maximum content space
           ══════════════════════════════════════════════ */
        .stMainBlockContainer {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        
        /* Our institutional header */
        .toolbar-header {
            background: linear-gradient(135deg, #00A94F 0%, #008C41 100%);
            padding: 0.5rem 2rem;
            margin: 0;
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            color: white;
            border-radius: 0 0 12px 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .toolbar-header img {
            height: 55px;
            width: auto;
            filter: brightness(0) invert(1);
            flex-shrink: 0;
            margin-left: 0.5rem;
        }
        .toolbar-header .header-text { 
            text-align: center; 
            flex: 1;
        }
        .toolbar-header h1 {
            margin: 0;
            font-family: 'Montserrat', sans-serif;
            font-weight: 700;
            font-size: 1.2rem;
            color: white;
            line-height: 1.2;
        }
        .toolbar-header .subtitle {
            font-family: 'Lato', sans-serif;
            font-size: 0.8rem;
            color: #dcfce7;
            margin: 0;
        }
        .toolbar-header .header-info { 
            text-align: right;
            color: #dcfce7;
            font-family: 'Lato', sans-serif;
            font-size: 0.85rem;
            flex-shrink: 0;
            margin-right: 0.5rem;
        }

        /* Kill vertical spacing between elements */
        .stMarkdown { margin: 0 !important; padding: 0 !important; }
        .stMarkdown p { margin: 0 !important; padding: 0 !important; }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { margin: 0.2rem 0 !important; }
        [data-testid="stVerticalBlock"] > div { margin: 0 !important; padding: 0 !important; }
        [data-testid="stVerticalBlockBorderWrapper"] { margin: 0 !important; }
        .stDivider { margin: 0 !important; padding: 0 !important; }
        .stDivider hr { margin: 0 !important; }
        .stMetric { margin: 0 !important; padding: 0.6rem !important; }
        
        /* Full width for ALL elements */
        .stPlotlyChart, .stAltairChart, .stVegaLiteChart { 
            width: 100% !important; 
            padding: 0 !important;
        }
        .stDataFrame { width: 100% !important; }
        [data-testid="stHorizontalBlock"] { 
            gap: 0.5rem; 
            width: 100% !important;
        }
        [data-testid="stHorizontalBlock"] > div { flex: 1; min-width: 0; }
        [data-testid="stColumn"] { width: 100% !important; padding: 0 !important; }
        .stTabs { width: 100% !important; }
        .stTabs [data-baseweb="tab-panel"] { padding: 0 !important; }
        
        #MainMenu { visibility: hidden; }
        
        /* Hide Streamlit pages navigation - keep radio buttons only */
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebarNavLink"] { display: none !important; }
        [data-testid="stSidebarNavItems"] { display: none !important; }
        [data-testid="stSidebarNavSectionHeader"] { display: none !important; }
        /* Also hide by element type for older Streamlit versions */
        nav[data-testid="stSidebarNav"] { display: none !important; }
        .css-1lwc55d { display: none !important; }
        
        /* Hide Streamlit deploy button - multiple selectors for compatibility */
        .stDeployButton { display: none !important; }
        [data-testid="stToolbar"] [data-testid="stDecoration"] { display: none !important; }
        button[title="View fullscreen"] { display: none !important; }
        /* Target deploy button by various methods */
        header button { display: none !important; }
        [data-testid="stHeader"] button { display: none !important; }
        .css-18e3th9 { display: none !important; }
        .css-1dp5lhl { display: none !important; }
        .css-164pbcr { display: none !important; }
        /* Hide by text content */
        button:contains("Deploy") { display: none !important; }
        a:contains("Deploy") { display: none !important; }
        
        /* ══════════════════════════════════════════════
           FOOTER: Minimal space, rounded corners
           ══════════════════════════════════════════════ */
        footer { 
            visibility: hidden !important;
            height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        .institution-footer {
            background-color: #244C5A;
            color: white;
            padding: 0.6rem 1.5rem;
            margin: 0.5rem 0 0 0;
            border-top: 3px solid #00A94F;
            border-radius: 12px 12px 0 0;
            font-family: 'Lato', sans-serif;
            font-size: 0.85rem;
            text-align: center;
        }

        /* ══════════════════════════════════════════════
           SIDEBAR
           ══════════════════════════════════════════════ */
        [data-testid="stSidebar"] {
            background-color: #f0fdf4;
            border-right: 1px solid #b2e8c4;
        }
        [data-testid="stSidebar"] > div {
            background-color: #f0fdf4;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #244C5A;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }
        .sidebar-nav-title {
            color: #244C5A;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
            font-size: 1rem;
            margin: 0 0 0.5rem 0;
            padding-bottom: 0.3rem;
            border-bottom: 2px solid #00A94F;
        }

        /* ══════════════════════════════════════════════
           KPI CARDS
           ══════════════════════════════════════════════ */
        .stMetric {
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border: 1px solid #b2e8c4;
            border-left: 4px solid #00A94F;
            border-radius: 8px;
            padding: 0.8rem !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .stMetric label {
            color: #244C5A !important;
            font-weight: 600 !important;
            font-family: 'Montserrat', sans-serif;
            font-size: 0.85rem;
        }
        .stMetric [data-testid="stMetricValue"] {
            color: #00A94F !important;
            font-weight: 700 !important;
            font-size: 1.6rem;
        }

        /* ══════════════════════════════════════════════
           BUTTONS
           ══════════════════════════════════════════════ */
        .stButton > button {
            background-color: #00A94F;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1.2rem;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }
        .stButton > button:hover {
            background-color: #008C41;
            color: white;
        }

        /* ══════════════════════════════════════════════
           TABS
           ══════════════════════════════════════════════ */
        .stTabs [data-baseweb="tab-list"] {
            background-color: #f0fdf4;
            border-radius: 8px 8px 0 0;
            border-bottom: 2px solid #dcfce7;
        }
        .stTabs [data-baseweb="tab"] {
            font-family: 'Montserrat', sans-serif;
            font-weight: 500;
            color: #244C5A;
        }
        .stTabs [aria-selected="true"] { background-color: #00A94F; color: white; }

        /* ══════════════════════════════════════════════
           RESPONSIVE
           ══════════════════════════════════════════════ */
        @media (max-width: 768px) {
            .toolbar-header {
                flex-direction: column;
                text-align: center;
                padding: 0.4rem 1rem;
            }
            .toolbar-header img { height: 35px; }
            .toolbar-header h1 { font-size: 1rem; }
            .toolbar-header .subtitle { font-size: 0.7rem; }
        }
        </style>
    """)

    # Header content
    st.markdown(f"""
        <div class="toolbar-header">
            <img src="data:image/png;base64,{logo_b64}" alt="FBCB-UNL Logo">
            <div class="header-text">
                <h1>SUME Dashboard</h1>
                <p class="subtitle">Sistema de Análisis de Circuitos Administrativos | Mesa de Entradas</p>
            </div>
            <div class="header-info">
                <div><strong>FBCB • UNL</strong></div>
                <div>Facultad de Bioquímica y Ciencias Biológicas</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<p class="sidebar-nav-title">📊 Navegación</p>', unsafe_allow_html=True)

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

    # Institutional footer
    st.markdown("""
        <div class="institution-footer">
            <div style="margin-bottom: 0.5rem;">
                <strong>SUME Dashboard v1.0.0</strong> | Mesa de Entradas FBCB-UNL
            </div>
            <div style="color: #b2e8c4;">
                Universidad Nacional del Litoral | Facultad de Bioquímica y Ciencias Biológicas
            </div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
