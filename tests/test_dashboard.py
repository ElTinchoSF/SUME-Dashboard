"""
Unit tests for SUME Dashboard module.

Tests data loading, filter logic, and chart builders.
"""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pandas as pd
import numpy as np

# Import dashboard modules
from src.dashboard.data import (
    FilterState,
    load_expedientes,
    load_circuitos,
    load_step_stats,
    load_permanence,
    load_dependencias,
    load_conceptos,
    load_dependency_traffic,
    load_concept_distribution,
    load_monthly_trend,
    _get_db_mtime,
    invalidate_cache,
)
from src.dashboard.components.filters import (
    init_filter_state,
    get_filter_state,
    set_filter_state,
    reset_filters,
    FilterState as FilterStateComponent,
)
from src.dashboard.components.charts import (
    kpi_card,
    bar_chart_horizontal,
    line_chart_monthly,
    histogram_steps,
    boxplot_permanence,
    sankey_circuit,
    parallel_sets,
    circuit_frequency_table,
    dependency_traffic_bar,
    concept_distribution_pie,
    render_kpi_row,
    apply_default_layout,
    COLORS,
)


class TestFilterState:
    """Tests for FilterState dataclass and SQL generation."""

    def test_filter_state_defaults(self):
        """Test default filter state values."""
        filters = FilterState()
        assert filters.date_range == (None, None)
        assert filters.conceptos == ()
        assert filters.dependencias == ()

    def test_filter_state_with_values(self):
        """Test filter state with all values set."""
        filters = FilterState(
            date_range=("2025-01-01", "2025-12-31"),
            conceptos=("Gestión Alumno", "Gestión de Becas"),
            dependencias=("Alumnado (FBCB)", "Mesa de Entradas - FBCB"),
        )
        assert filters.date_range == ("2025-01-01", "2025-12-31")
        assert filters.conceptos == ("Gestión Alumno", "Gestión de Becas")
        assert filters.dependencias == ("Alumnado (FBCB)", "Mesa de Entradas - FBCB")

    def test_to_sql_where_empty(self):
        """Test SQL WHERE clause with no filters."""
        filters = FilterState()
        where_clause, params = filters.to_sql_where()
        assert where_clause == ""
        assert params == []

    def test_to_sql_where_date_range(self):
        """Test SQL WHERE with date range only."""
        filters = FilterState(date_range=("2025-03-01", "2025-03-31"))
        where_clause, params = filters.to_sql_where()
        assert "e.fecha_alta >= ?" in where_clause
        assert "e.fecha_alta <= ?" in where_clause
        assert params == ["2025-03-01", "2025-03-31"]

    def test_to_sql_where_conceptos(self):
        """Test SQL WHERE with conceptos filter."""
        filters = FilterState(conceptos=("Gestión Alumno", "Gestión de Becas"))
        where_clause, params = filters.to_sql_where()
        assert "e.concepto IN (?,?)" in where_clause
        assert params == ["Gestión Alumno", "Gestión de Becas"]

    def test_to_sql_where_dependencias(self):
        """Test SQL WHERE with dependencias filter."""
        filters = FilterState(dependencias=("Alumnado (FBCB)",))
        where_clause, params = filters.to_sql_where()
        assert "e.id IN (" in where_clause
        assert "dependencia IN (?)" in where_clause
        assert params == ["Alumnado (FBCB)"]

    def test_to_sql_where_combined(self):
        """Test SQL WHERE with all filters combined."""
        filters = FilterState(
            date_range=("2025-01-01", "2025-12-31"),
            conceptos=("Gestión Alumno",),
            dependencias=("Alumnado (FBCB)",),
        )
        where_clause, params = filters.to_sql_where()
        assert "WHERE" in where_clause
        assert "e.fecha_alta >= ?" in where_clause
        assert "e.concepto IN" in where_clause
        assert "dependencia IN" in where_clause
        assert len(params) == 4  # 2 dates + 1 concepto + 1 dependencia


class TestDataLoading:
    """Tests for data loading functions (mocked database)."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        return mock_conn

    @pytest.fixture
    def sample_expedientes_df(self):
        """Sample expedientes DataFrame."""
        return pd.DataFrame({
            "id": [1, 2, 3],
            "numero": ["EXP-001", "EXP-002", "EXP-003"],
            "concepto": ["Gestión Alumno", "Gestión de Becas", "Gestión Alumno"],
            "descripcion": ["Desc 1", "Desc 2", "Desc 3"],
            "fecha_alta": pd.to_datetime(["2025-01-15", "2025-02-20", "2025-03-10"]),
            "estado": ["En trámite", "Finalizado", "En trámite"],
            "palabras_clave": ["alumno, inscripcion", "beca, ayuda", "alumno, titulo"],
            "origenes": ["Mesa Entradas", "Mesa Entradas", "Mesa Entradas"],
            "fecha_extraccion": pd.to_datetime(["2025-01-15 10:00", "2025-02-20 11:00", "2025-03-10 12:00"]),
        })

    @pytest.fixture
    def sample_circuitos_df(self):
        """Sample circuitos DataFrame."""
        circuit1 = json.dumps(["Mesa de Entradas - FBCB", "Alumnado (FBCB)", "Secretaría Académica"])
        circuit2 = json.dumps(["Mesa de Entradas - FBCB", "Alumnado (FBCB)", "Dirección"])
        return pd.DataFrame({
            "id": [1, 2],
            "circuito": [circuit1, circuit2],
            "concepto": ["Gestión Alumno", "Gestión Alumno"],
            "frecuencia": [50, 30],
            "es_mas_frecuente": [True, False],
        })

    @patch("src.dashboard.data.get_connection")
    def test_load_expedientes_no_filters(self, mock_get_conn, sample_expedientes_df):
        """Test loading expedientes without filters."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = []

        # Mock pandas read_sql_query
        with patch("pandas.read_sql_query", return_value=sample_expedientes_df) as mock_read:
            filters = FilterState()
            result = load_expedientes(filters)

            assert len(result) == 3
            assert list(result.columns) == list(sample_expedientes_df.columns)
            mock_read.assert_called_once()

    @patch("src.dashboard.data.get_connection")
    def test_load_circuitos_with_concepto(self, mock_get_conn, sample_circuitos_df):
        """Test loading circuitos filtered by concepto."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        with patch("pandas.read_sql_query", return_value=sample_circuitos_df) as mock_read:
            result = load_circuitos("Gestión Alumno")

            assert len(result) == 2
            assert "circuito_parsed" in result.columns
            assert "step_count" in result.columns
            assert result["step_count"].tolist() == [3, 3]

    @patch("src.dashboard.data.get_connection")
    def test_load_step_stats_computation(self, mock_get_conn, sample_circuitos_df):
        """Test step statistics computation."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        with patch("pandas.read_sql_query", return_value=sample_circuitos_df):
            result = load_step_stats("Gestión Alumno")

            assert not result.empty
            assert "mean_steps" in result.columns
            assert "median_steps" in result.columns
            assert "mode_steps" in result.columns
            assert result.iloc[0]["mean_steps"] == 3.0

    @patch("src.dashboard.data.get_connection")
    def test_load_permanence_calculation(self, mock_get_conn):
        """Test permanence time calculation."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        # Sample data with movements
        mov_df = pd.DataFrame({
            "expediente_id": [1, 1, 2, 2],
            "numero": ["EXP-001", "EXP-001", "EXP-002", "EXP-002"],
            "concepto": ["Gestión Alumno"] * 4,
            "orden": [1, 2, 1, 2],
            "fecha_recepcion": pd.to_datetime(["2025-01-15", "2025-01-20", "2025-02-01", "2025-02-10"]),
            "dependencia": ["Alumnado", "Secretaría", "Alumnado", "Dirección"],
        })

        with patch("pandas.read_sql_query", return_value=mov_df):
            result = load_permanence("Gestión Alumno")

            assert len(result) == 4
            assert "permanence_days" in result.columns
            assert "is_final_step" in result.columns
            # First movimiento of EXP-001: 5 days permanence
            assert result.iloc[0]["permanence_days"] == 5
            # Last movimiento of EXP-001: NaN (final step, pandas converts None to NaN)
            assert pd.isna(result.iloc[1]["permanence_days"])
            assert bool(result.iloc[1]["is_final_step"]) is True

    @patch("src.dashboard.data.get_connection")
    def test_load_dependencias(self, mock_get_conn):
        """Test loading dependencias for filter dropdown."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        dep_df = pd.DataFrame({
            "nombre": ["Alumnado (FBCB)", "Secretaría Académica", "Dirección"],
            "total_expedientes": [100, 80, 50],
        })

        with patch("pandas.read_sql_query", return_value=dep_df):
            result = load_dependencias()

            assert len(result) == 3
            assert list(result.columns) == ["nombre", "total_expedientes"]

    @patch("src.dashboard.data.get_connection")
    def test_load_conceptos(self, mock_get_conn):
        """Test loading conceptos for filter dropdown."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        conc_df = pd.DataFrame({
            "concepto": ["Gestión Alumno", "Gestión de Becas"],
            "cantidad": [150, 80],
        })

        with patch("pandas.read_sql_query", return_value=conc_df):
            result = load_conceptos()

            assert len(result) == 2
            assert list(result.columns) == ["concepto", "cantidad"]


class TestFilterComponents:
    """Tests for filter component logic (without Streamlit)."""

    def test_init_filter_state(self):
        """Test filter state initialization."""
        # Clear any existing state
        import streamlit as st
        if hasattr(st, "session_state"):
            for key in ["dashboard_filters", "date_range", "selected_conceptos", "selected_dependencias"]:
                if key in st.session_state:
                    del st.session_state[key]

        init_filter_state()

        assert "dashboard_filters" in st.session_state
        assert isinstance(st.session_state["dashboard_filters"], FilterState)

    def test_get_set_filter_state(self):
        """Test getting and setting filter state."""
        import streamlit as st

        # Clear state
        for key in ["dashboard_filters", "date_range", "selected_conceptos", "selected_dependencias"]:
            if key in st.session_state:
                del st.session_state[key]

        filters = FilterState(
            date_range=("2025-01-01", "2025-12-31"),
            conceptos=("Test",),
            dependencias=("Dep1",),
        )
        set_filter_state(filters)
        retrieved = get_filter_state()

        assert retrieved.date_range == filters.date_range
        assert retrieved.conceptos == filters.conceptos
        assert retrieved.dependencias == filters.dependencias

    def test_reset_filters(self):
        """Test filter reset to defaults."""
        import streamlit as st

        # Set some values
        st.session_state["dashboard_filters"] = FilterState(
            date_range=("2025-03-01", "2025-03-31"),
            conceptos=("Test",),
            dependencias=("Dep1",),
        )

        reset_filters()

        filters = get_filter_state()
        today = date.today()
        assert filters.date_range[0] == date(today.year, 1, 1).isoformat()
        assert filters.date_range[1] == date(today.year, 12, 31).isoformat()
        assert filters.conceptos == ()
        assert filters.dependencias == ()


class TestChartBuilders:
    """Tests for chart builder functions."""

    def test_apply_default_layout(self):
        """Test default layout application."""
        fig = apply_default_layout(go.Figure(), title="Test Chart", height=400)

        assert fig.layout.title.text == "Test Chart"
        assert fig.layout.height == 400
        assert fig.layout.plot_bgcolor == COLORS["white"]
        assert fig.layout.font.family == "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

    def test_bar_chart_horizontal(self):
        """Test horizontal bar chart creation."""
        df = pd.DataFrame({
            "categoria": ["A", "B", "C"],
            "valor": [10, 20, 15],
        })

        fig = bar_chart_horizontal(df, x="valor", y="categoria", title="Test Bar")

        assert len(fig.data) == 1
        assert fig.data[0].orientation == "h"
        assert fig.layout.title.text == "Test Bar"

    def test_line_chart_monthly(self):
        """Test monthly line chart creation."""
        df = pd.DataFrame({
            "mes": ["2025-01", "2025-02", "2025-03"],
            "cantidad": [10, 15, 12],
            "acumulado": [10, 25, 37],
        })

        fig = line_chart_monthly(df, date_col="mes", value_col="cantidad",
                                  title="Test Line", cumulative_col="acumulado")

        assert len(fig.data) == 2  # Main line + cumulative
        assert fig.data[0].name == "Cantidad mensual"
        assert fig.data[1].name == "Acumulado"

    def test_histogram_steps(self):
        """Test histogram with stat lines."""
        df = pd.DataFrame({
            "step_count": [2, 3, 3, 4, 4, 4, 5, 5, 6],
        })

        fig = histogram_steps(df, bins=5, title="Test Hist",
                              mean_line=4.0, median_line=4.0, mode_line=4)

        assert len(fig.data) == 1
        assert fig.data[0].type == "histogram"
        # Check for vline annotations (stat lines)
        assert len(fig.layout.shapes) >= 3  # mean, median, mode lines

    def test_boxplot_permanence(self):
        """Test boxplot creation."""
        df = pd.DataFrame({
            "dependencia": ["A", "A", "B", "B", "C", "C"],
            "permanence_days": [1, 2, 3, 4, 5, 10],
        })

        fig = boxplot_permanence(df, x="dependencia", y="permanence_days", title="Test Box")

        assert len(fig.data) == 1
        assert fig.data[0].type == "box"

    def test_sankey_circuit(self):
        """Test Sankey diagram creation."""
        circuit_json = json.dumps(["Mesa de Entradas - FBCB", "Alumnado", "Secretaría"])
        counts = [100, 80]

        fig = sankey_circuit(circuit_json, counts, title="Test Sankey")

        assert len(fig.data) == 1
        assert fig.data[0].type == "sankey"
        assert len(fig.data[0].node.label) == 3
        assert len(fig.data[0].link.source) == 2

    def test_sankey_circuit_invalid_json(self):
        """Test Sankey with invalid JSON."""
        fig = sankey_circuit("invalid json", [], title="Test")

        # Should return a figure with annotation
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1

    def test_parallel_sets(self):
        """Test parallel sets diagram."""
        circuit1 = json.dumps(["MDE", "A", "B"])
        circuit2 = json.dumps(["MDE", "A", "C"])

        df = pd.DataFrame({
            "circuito_json": [circuit1, circuit2],
            "frecuencia": [50, 30],
            "es_mas_frecuente": [True, False],
        })

        fig = parallel_sets(df, title="Test Parallel", max_circuits=10)

        assert isinstance(fig, go.Figure)

    def test_circuit_frequency_table(self):
        """Test circuit frequency table."""
        circuit1 = json.dumps(["MDE", "A", "B"])
        circuit2 = json.dumps(["MDE", "A", "C"])

        df = pd.DataFrame({
            "circuito_json": [circuit1, circuit2],
            "frecuencia": [50, 30],
            "es_mas_frecuente": [True, False],
        })

        fig = circuit_frequency_table(df, title="Test Table")

        assert len(fig.data) == 1
        assert fig.data[0].type == "table"

    def test_dependency_traffic_bar(self):
        """Test dependency traffic bar chart."""
        df = pd.DataFrame({
            "dependencia": ["A", "B", "C"],
            "total_expedientes": [100, 80, 50],
            "pct_expedientes": [43.5, 34.8, 21.7],
            "total_movimientos": [200, 150, 100],
        })

        fig = dependency_traffic_bar(df, title="Test Traffic", top_n=10)

        assert len(fig.data) == 1
        assert fig.data[0].orientation == "h"

    def test_concept_distribution_pie(self):
        """Test concept distribution pie chart."""
        df = pd.DataFrame({
            "concepto": ["A", "B", "C"],
            "cantidad": [100, 80, 50],
            "porcentaje": [43.5, 34.8, 21.7],
        })

        fig = concept_distribution_pie(df, title="Test Pie")

        assert len(fig.data) == 1
        assert fig.data[0].type == "pie"


class TestCacheInvalidation:
    """Tests for cache invalidation logic."""

    @patch("src.dashboard.data.get_settings")
    @patch("pathlib.Path.stat")
    def test_get_db_mtime_exists(self, mock_stat, mock_get_settings):
        """Test getting DB mtime when file exists."""
        mock_settings = MagicMock()
        mock_settings.database.path = "data/sume.db"
        mock_get_settings.return_value = mock_settings

        mock_stat_result = MagicMock()
        mock_stat_result.st_mtime = 1234567890.0
        mock_stat.return_value = mock_stat_result

        mtime = _get_db_mtime()
        assert mtime == 1234567890.0

    @patch("src.dashboard.data.get_settings")
    @patch("pathlib.Path.stat", side_effect=OSError("File not found"))
    def test_get_db_mtime_not_exists(self, mock_stat, mock_get_settings):
        """Test getting DB mtime when file doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.database.path = "data/sume.db"
        mock_get_settings.return_value = mock_settings

        mtime = _get_db_mtime()
        assert mtime == 0.0

    @patch("streamlit.cache_data.clear")
    def test_invalidate_cache(self, mock_clear):
        """Test cache invalidation."""
        invalidate_cache()
        mock_clear.assert_called_once()


# Import plotly.graph_objects for chart tests
import plotly.graph_objects as go


if __name__ == "__main__":
    pytest.main([__file__, "-v"])