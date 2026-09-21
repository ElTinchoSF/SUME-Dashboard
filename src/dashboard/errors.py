"""
Error display helpers for Streamlit pages.

Provides consistent error handling with user-friendly messages
and backend logging.
"""

import traceback

import streamlit as st

from src.dashboard.logging_config import get_logger

logger = get_logger("errors")


def render_page_error(e: Exception, page_name: str) -> None:
    """
    Display a user-friendly error message and log the exception.

    Call this inside an except block to show a clean message to the user
    while preserving the full traceback in logs.
    """
    error_type = type(e).__name__
    error_msg = str(e) or "Sin detalles disponibles"

    logger.error(
        "Error in page '%s': %s: %s",
        page_name,
        error_type,
        error_msg,
        exc_info=True,
    )

    st.error(
        f"**Ocurrió un error al cargar la página \"{page_name}\".**\n\n"
        f"Detalle: `{error_type}: {error_msg[:200]}`\n\n"
        "Si el problema persiste, contacte al administrador del sistema."
    )


def render_data_error(e: Exception, context: str) -> None:
    """
    Display an error related to data loading or processing.
    """
    error_type = type(e).__name__
    error_msg = str(e) or "Sin detalles disponibles"

    logger.error(
        "Data error in '%s': %s: %s",
        context,
        error_type,
        error_msg,
        exc_info=True,
    )

    st.error(
        f"**Error al cargar datos** ({context}).\n\n"
        f"Detalle: `{error_msg[:200]}`\n\n"
        "Verifique que la base de datos esté disponible y contiene datos."
    )


def render_warning(message: str, context: str = "") -> None:
    """Log a warning and display it to the user."""
    if context:
        logger.warning("[%s] %s", context, message)
    else:
        logger.warning(message)
    st.warning(message)
