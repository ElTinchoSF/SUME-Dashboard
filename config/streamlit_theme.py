"""
FBCB-UNL Streamlit Theme Helper
══════════════════════════════════════════════════════════════
Uso:
    from config.streamlit_theme import apply_theme, create_header, create_footer
    
    # Al inicio de app.py
    st.set_page_config(layout="wide", page_icon="📊")
    apply_theme()
    
    # Header institucional
    create_header("Mi Dashboard", "Subtítulo", "logo.png")
    
    # ... contenido ...
    
    # Footer institucional
    create_footer("Mi App v1.0")
══════════════════════════════════════════════════════════════
"""

import base64
from pathlib import Path
import streamlit as st


def apply_theme(css_path: str = "config/streamlit_theme.css") -> None:
    """
    Aplica el tema FBCB-UNL al dashboard.
    
    Args:
        css_path: Ruta al archivo CSS del tema
    """
    css_file = Path(css_path)
    if css_file.exists():
        st.html(css_file.read_text())
    else:
        st.warning(f"No se encontró el archivo CSS: {css_path}")


def create_header(
    title: str,
    subtitle: str = "",
    logo_path: str = None,
    org_info: str = "FBCB • UNL"
) -> None:
    """
    Crea el header institucional FBCB-UNL.
    
    Args:
        title: Título principal
        subtitle: Subtítulo descriptivo
        logo_path: Ruta al logo (opcional)
        org_info: Información de la organización a la derecha
    """
    logo_html = ""
    if logo_path:
        logo_file = Path(logo_path)
        if logo_file.exists():
            logo_b64 = base64.b64encode(logo_file.read_bytes()).decode()
            logo_html = f'<img src="data:image/png;base64,{logo_b64}" alt="Logo">'
    
    st.markdown(f"""
        <div class="toolbar-header">
            {logo_html}
            <div class="header-text">
                <h1>{title}</h1>
                {"<p class='subtitle'>" + subtitle + "</p>" if subtitle else ""}
            </div>
            <div class="header-info">
                <div><strong>{org_info}</strong></div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def create_footer(
    app_name: str = "Dashboard",
    org_name: str = "Facultad de Bioquímica y Ciencias Biológicas",
    extra_info: str = ""
) -> None:
    """
    Crea el footer institucional FBCB-UNL.
    
    Args:
        app_name: Nombre de la aplicación
        org_name: Nombre de la organización
        extra_info: Información adicional (opcional)
    """
    extra_html = f'<div style="color: #b2e8c4;">{extra_info}</div>' if extra_info else ""
    
    st.markdown(f"""
        <div class="institution-footer">
            <div style="margin-bottom: 0.5rem;">
                <strong>{app_name}</strong> | Mesa de Entradas FBCB-UNL
            </div>
            <div style="color: #b2e8c4;">
                {org_name}
            </div>
            {extra_html}
        </div>
    """, unsafe_allow_html=True)


# Color palette for direct use in Plotly charts
COLORS = {
    'primary': '#00A94F',      # Verde FBCB
    'primary_dark': '#008C41', # Verde hover
    'primary_light': '#b2e8c4',# Verde claro
    'bg_50': '#f0fdf4',        # Fondo verde muy claro
    'bg_100': '#dcfce7',       # Fondo verde claro
    'unl_turquoise': '#0088AA',# Turquesa UNL
    'unl_dark': '#244C5A',     # Verde oscuro UNL
    'gray': '#575756',         # Gris texto
    'white': '#ffffff',
    'black': '#000000',
}

# Font configuration for Plotly charts
CHART_FONTS = {
    'family': 'Montserrat, sans-serif',
    'size': 12,
    'color': '#244C5A'
}
