"""
Page 4: Reportes (Reportes ISO 9001).

Report generation UI with:
- Format selector (Markdown, PDF, Excel)
- Concepto selector (single/all)
- Generate buttons with progress indicator
- Download buttons for generated files
- Markdown preview
"""

import streamlit as st
import subprocess
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.dashboard.data import load_conceptos, FilterState
from src.dashboard.components.filters import render_filter_summary
from src.config import get_settings


def render_reportes_page(filters: FilterState) -> None:
    """Render the Reportes generation page."""
    st.header("📑 Reportes ISO 9001")
    render_filter_summary(filters)

    # Load available conceptos
    conceptos_df = load_conceptos()
    all_conceptos = conceptos_df["concepto"].tolist() if not conceptos_df.empty else []

    if not all_conceptos:
        st.warning("No hay conceptos disponibles para generar reportes.")
        return

    st.subheader("Configuración del Reporte")

    # Format selector
    col1, col2 = st.columns([1, 1])

    with col1:
        format_option = st.selectbox(
            "Formato de salida",
            options=["Markdown (.md)", "PDF (.pdf)", "Excel (.xlsx)"],
            index=0,
            key="report_format",
            help="Formato del archivo generado",
        )

    with col2:
        # Concepto selection: single or all
        report_scope = st.radio(
            "Alcance",
            options=["Todos los conceptos", "Concepto específico"],
            index=0,
            horizontal=True,
            key="report_scope",
            help="Generar reporte completo o por concepto individual",
        )

    # Concepto selector (only shown for specific concept)
    selected_concepto = None
    if report_scope == "Concepto específico":
        selected_concepto = st.selectbox(
            "Concepto",
            options=all_conceptos,
            index=0,
            key="report_concepto_selector",
            help="Seleccionar concepto para reporte individual",
        )

    st.divider()

    # Generate buttons
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button(
            "📄 Generar Reporte Completo",
            type="primary",
            use_container_width=True,
            disabled=report_scope == "Concepto específico",
            help="Generar reporte ISO 9001 completo con todas las secciones",
        ):
            _generate_report(
                format_option=format_option,
                conceptos=None,  # All conceptos
                scope_label="completo",
            )

    with col_btn2:
        if st.button(
            "📋 Generar Reporte por Concepto",
            type="secondary",
            use_container_width=True,
            disabled=report_scope != "Concepto específico" or not selected_concepto,
            help="Generar reporte focalizado para el concepto seleccionado",
        ):
            _generate_report(
                format_option=format_option,
                conceptos=[selected_concepto] if selected_concepto else None,
                scope_label=f"concepto_{selected_concepto}",
            )

    st.divider()

    # Preview section
    st.subheader("Vista Previa (Markdown)")
    if "last_report_md" in st.session_state:
        with st.expander("Ver reporte generado", expanded=True):
            st.markdown(st.session_state["last_report_md"])
    else:
        st.info("Genere un reporte para ver la vista previa aquí.")


def _generate_report(format_option: str, conceptos: Optional[list[str]], scope_label: str) -> None:
    """
    Generate report using the analysis CLI.

    Args:
        format_option: Selected format string.
        conceptos: List of conceptos to include, or None for all.
        scope_label: Label for the report scope (used in filename).
    """
    # Map format option to CLI argument
    format_map = {
        "Markdown (.md)": "markdown",
        "PDF (.pdf)": "pdf",
        "Excel (.xlsx)": "excel",
    }
    fmt = format_map.get(format_option, "markdown")

    # Build output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext_map = {"markdown": "md", "pdf": "pdf", "excel": "xlsx"}
    ext = ext_map.get(fmt, "md")
    output_filename = f"reporte_iso9001_{scope_label}_{timestamp}.{ext}"

    settings = get_settings()
    output_dir = Path(settings.reporter.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename

    # Build CLI command
    cmd = [
        "python", "-m", "src.analysis.reports",
        "--output", str(output_path),
        "--format", fmt,
    ]

    if conceptos:
        cmd.extend(["--conceptos", ",".join(conceptos)])

    cmd.append("--version-auto")

    # Show progress
    progress_placeholder = st.empty()
    progress_bar = st.progress(0)

    try:
        with progress_placeholder.container():
            st.info(f"Generando reporte {format_option.lower()}...")

        # Run the command
        progress_bar.progress(25)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=Path.cwd(),
        )

        progress_bar.progress(75)

        if result.returncode == 0:
            progress_bar.progress(100)
            progress_placeholder.empty()
            progress_bar.empty()

            st.success(f"✅ Reporte generado: {output_filename}")

            # Store for preview/download
            if fmt == "markdown":
                with open(output_path, "r", encoding="utf-8") as f:
                    st.session_state["last_report_md"] = f.read()
                st.session_state["last_report_path"] = str(output_path)
                st.session_state["last_report_format"] = "markdown"

            # Download button
            with open(output_path, "rb") as f:
                file_data = f.read()

            st.download_button(
                label=f"⬇️ Descargar {output_filename}",
                data=file_data,
                file_name=output_filename,
                mime=_get_mime_type(fmt),
                use_container_width=True,
            )

            # Also show the output path
            st.caption(f"Guardado en: {output_path}")

        else:
            progress_placeholder.empty()
            progress_bar.empty()
            st.error(f"❌ Error generando reporte:\n```\n{result.stderr}\n```")
            if result.stdout:
                st.code(result.stdout)

    except subprocess.TimeoutExpired:
        progress_placeholder.empty()
        progress_bar.empty()
        st.error("⏱️ Tiempo de espera agotado (5 min). El reporte puede ser muy grande.")

    except Exception as e:
        progress_placeholder.empty()
        progress_bar.empty()
        st.error(f"❌ Error inesperado: {type(e).__name__}: {e}")


def _get_mime_type(fmt: str) -> str:
    """Get MIME type for format."""
    mime_map = {
        "markdown": "text/markdown",
        "pdf": "application/pdf",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return mime_map.get(fmt, "application/octet-stream")


# Alternative: Direct function call (if reporter module exposes a function)
def _generate_report_direct(format_option: str, conceptos: Optional[list[str]], scope_label: str) -> None:
    """
    Alternative: Generate report by calling reporter functions directly.
    This avoids subprocess overhead but requires the reporter module to have a callable API.
    """
    # This would be used if src.analysis.reports exposes a generate_report() function
    # For now, we use the CLI approach above.
    pass