"""
Global filter widgets for SUME Dashboard.

Provides reusable filter components with session state persistence
across page navigation.
"""

import streamlit as st
from datetime import date, timedelta
from typing import Optional

from src.dashboard.data import FilterState, load_conceptos, load_dependencias


# Session state keys
FILTER_KEY = "dashboard_filters"
DATE_RANGE_KEY = "date_range"
CONCEPTOS_KEY = "selected_conceptos"
DEPENDENCIAS_KEY = "selected_dependencias"


def init_filter_state() -> None:
    """Initialize filter state in session if not present."""
    if FILTER_KEY not in st.session_state:
        # Default to full year range
        today = date.today()
        start_of_year = date(today.year, 1, 1)
        end_of_year = date(today.year, 12, 31)

        st.session_state[FILTER_KEY] = FilterState(
            date_range=(start_of_year.isoformat(), end_of_year.isoformat()),
            conceptos=(),
            dependencias=(),
        )
        st.session_state[DATE_RANGE_KEY] = (start_of_year, end_of_year)
        st.session_state[CONCEPTOS_KEY] = []
        st.session_state[DEPENDENCIAS_KEY] = []


def get_filter_state() -> FilterState:
    """Get current filter state from session."""
    init_filter_state()
    return st.session_state[FILTER_KEY]


def set_filter_state(filters: FilterState) -> None:
    """Update filter state in session."""
    init_filter_state()
    st.session_state[FILTER_KEY] = filters


def reset_filters() -> None:
    """Reset all filters to defaults."""
    today = date.today()
    start_of_year = date(today.year, 1, 1)
    end_of_year = date(today.year, 12, 31)

    st.session_state[FILTER_KEY] = FilterState(
        date_range=(start_of_year.isoformat(), end_of_year.isoformat()),
        conceptos=(),
        dependencias=(),
    )
    st.session_state[DATE_RANGE_KEY] = (start_of_year, end_of_year)
    st.session_state[CONCEPTOS_KEY] = []
    st.session_state[DEPENDENCIAS_KEY] = []


def render_date_range_filter() -> tuple[Optional[str], Optional[str]]:
    """
    Render date range picker widget.

    Returns:
        Tuple of (start_date_str, end_date_str) in ISO format, or (None, None).
    """
    init_filter_state()

    current_range = st.session_state.get(DATE_RANGE_KEY, (None, None))

    # Default to current year if not set
    if current_range[0] is None:
        today = date.today()
        current_range = (date(today.year, 1, 1), date(today.year, 12, 31))
        st.session_state[DATE_RANGE_KEY] = current_range

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Fecha inicio",
            value=current_range[0],
            key="filter_date_start",
            help="Fecha de alta del expediente (inicio del rango)",
        )

    with col2:
        end_date = st.date_input(
            "Fecha fin",
            value=current_range[1],
            key="filter_date_end",
            help="Fecha de alta del expediente (fin del rango)",
        )

    # Update session state
    if start_date != current_range[0] or end_date != current_range[1]:
        st.session_state[DATE_RANGE_KEY] = (start_date, end_date)
        filters = get_filter_state()
        new_filters = FilterState(
            date_range=(start_date.isoformat() if start_date else None,
                       end_date.isoformat() if end_date else None),
            conceptos=filters.conceptos,
            dependencias=filters.dependencias,
        )
        set_filter_state(new_filters)

    return (
        start_date.isoformat() if start_date else None,
        end_date.isoformat() if end_date else None,
    )


def render_concepto_filter() -> list[str]:
    """
    Render concepto multiselect with Select All / Clear All.

    Returns:
        List of selected concepto strings.
    """
    init_filter_state()

    # Load available conceptos
    conceptos_df = load_conceptos()
    all_conceptos = conceptos_df["concepto"].tolist() if not conceptos_df.empty else []

    current = st.session_state.get(CONCEPTOS_KEY, [])

    # Ensure current selection is valid
    current = [c for c in current if c in all_conceptos]

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        selected = st.multiselect(
            "Conceptos",
            options=all_conceptos,
            default=current,
            key="filter_conceptos",
            help="Filtrar por tipo de trámite/concepto",
            placeholder="Seleccionar conceptos...",
        )

    with col2:
        if st.button("Todos", key="btn_select_all_conceptos", use_container_width=True,
                     help="Seleccionar todos los conceptos"):
            selected = all_conceptos
            st.session_state[CONCEPTOS_KEY] = selected
            st.rerun()

    with col3:
        if st.button("Ninguno", key="btn_clear_all_conceptos", use_container_width=True,
                     help="Deseleccionar todos los conceptos"):
            selected = []
            st.session_state[CONCEPTOS_KEY] = selected
            st.rerun()

    # Update session state if changed
    if selected != current:
        st.session_state[CONCEPTOS_KEY] = selected
        filters = get_filter_state()
        new_filters = FilterState(
            date_range=filters.date_range,
            conceptos=tuple(selected),
            dependencias=filters.dependencias,
        )
        set_filter_state(new_filters)

    return selected


def render_dependencia_filter() -> list[str]:
    """
    Render dependencia searchable multiselect with typeahead.

    Returns:
        List of selected dependencia strings.
    """
    init_filter_state()

    # Load available dependencias
    deps_df = load_dependencias()
    all_dependencias = deps_df["nombre"].tolist() if not deps_df.empty else []

    current = st.session_state.get(DEPENDENCIAS_KEY, [])

    # Ensure current selection is valid
    current = [d for d in current if d in all_dependencias]

    selected = st.multiselect(
        "Dependencias",
        options=all_dependencias,
        default=current,
        key="filter_dependencias",
        help="Filtrar por dependencias por donde pasó el expediente (búsqueda con autocompletado)",
        placeholder="Buscar y seleccionar dependencias...",
        max_selections=20,  # Reasonable limit for performance
    )

    # Update session state if changed
    if selected != current:
        st.session_state[DEPENDENCIAS_KEY] = selected
        filters = get_filter_state()
        new_filters = FilterState(
            date_range=filters.date_range,
            conceptos=filters.conceptos,
            dependencias=tuple(selected),
        )
        set_filter_state(new_filters)

    return selected


def render_global_filters_sidebar() -> FilterState:
    """
    Render all global filters in the sidebar.

    Returns:
        Current FilterState after rendering.
    """
    init_filter_state()

    with st.sidebar:
        st.header("🔍 Filtros Globales")

        # Date range
        st.subheader("📅 Rango de fechas")
        render_date_range_filter()

        st.divider()

        # Concepto filter
        st.subheader("📋 Conceptos")
        render_concepto_filter()

        st.divider()

        # Dependencia filter
        st.subheader("🏢 Dependencias")
        render_dependencia_filter()

        st.divider()

        # Reset button
        if st.button("🔄 Restablecer filtros", use_container_width=True,
                     help="Volver a valores por defecto (todo el año, todos los conceptos/dependencias)"):
            reset_filters()
            st.rerun()

        # Show active filter summary
        filters = get_filter_state()
        active_count = 0
        if filters.date_range[0] or filters.date_range[1]:
            active_count += 1
        if filters.conceptos:
            active_count += 1
        if filters.dependencias:
            active_count += 1

        if active_count > 0:
            st.caption(f"🔍 {active_count} filtro{'s' if active_count > 1 else ''} activo{'s' if active_count > 1 else ''}")

    return get_filter_state()


def render_filter_summary(filters: FilterState) -> None:
    """
    Render a compact summary of active filters.

    Args:
        filters: Current FilterState to display.
    """
    parts = []

    if filters.date_range[0] or filters.date_range[1]:
        start = filters.date_range[0] or "inicio"
        end = filters.date_range[1] or "hoy"
        parts.append(f"📅 {start} → {end}")

    if filters.conceptos:
        if len(filters.conceptos) <= 3:
            parts.append(f"📋 {', '.join(filters.conceptos)}")
        else:
            parts.append(f"📋 {len(filters.conceptos)} conceptos")

    if filters.dependencias:
        if len(filters.dependencias) <= 3:
            parts.append(f"🏢 {', '.join(filters.dependencias)}")
        else:
            parts.append(f"🏢 {len(filters.dependencias)} dependencias")

    if parts:
        st.caption(" | ".join(parts))
    else:
        st.caption("Sin filtros activos (mostrando todos los datos)")