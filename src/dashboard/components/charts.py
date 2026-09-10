"""
Reusable Plotly chart builders for SUME Dashboard.

Provides consistent styling across all dashboard pages:
- FBCB institutional green: #00A94F (Pantone 355C)
- UNL turquoise: #0088AA (Pantone 314C)
- Modal circuits = green (#00A94F)
- Atypical/outlier circuits = orange (#E65100)
- Background = light gray (#F5F5F5)
"""

import json
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# Color palette - FBCB institutional colors
COLORS = {
    # FBCB institutional green (Pantone 355C)
    "modal": "#00A94F",       # Green for modal circuits
    "fbcb": "#00A94F",        # Primary FBCB green
    "fbcb_hover": "#008C41",  # FBCB green hover
    "fbcb_light": "#b2e8c4",  # FBCB green light
    "fbcb_50": "#f0fdf4",     # FBCB green 50 (background)
    "fbcb_100": "#dcfce7",    # FBCB green 100

    # UNL institutional colors
    "unl": "#0088AA",         # UNL turquoise (Pantone 314C)
    "unl_dark": "#244C5A",    # UNL complement (Pantone 7477C)

    # Semantic colors
    "atypical": "#E65100",    # Orange for atypical/outlier circuits
    "primary": "#00A94F",     # Primary = FBCB green
    "secondary": "#575756",   # Gray (accompanying gray K:80)
    "background": "#F5F5F5",  # Light gray background
    "white": "#FFFFFF",
    "text": "#212121",
    "grid": "#E0E0E0",

    # KPI card colors
    "kpi_green": "#00A94F",   # FBCB green
    "kpi_blue": "#0088AA",    # UNL turquoise
    "kpi_orange": "#E65100",  # Orange (outliers)
    "kpi_purple": "#7B1FA2",  # Purple (accent)
}

# Common layout settings
DEFAULT_LAYOUT = {
    "font": {"family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "color": COLORS["text"]},
    "plot_bgcolor": COLORS["white"],
    "paper_bgcolor": COLORS["white"],
    "margin": {"l": 60, "r": 30, "t": 60, "b": 50},
    "xaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
    "yaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
    "hoverlabel": {"bgcolor": COLORS["white"], "font_size": 12, "font_family": "Inter"},
}


def apply_default_layout(fig: go.Figure, title: str = "", height: int = 400,
                         show_legend: bool = True, **kwargs) -> go.Figure:
    """Apply default layout styling to a figure."""
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": COLORS["text"]}, "x": 0.02, "xanchor": "left"},
        height=height,
        showlegend=show_legend,
        legend={"bgcolor": "rgba(255,255,255,0.9)", "bordercolor": COLORS["grid"], "borderwidth": 1},
        **{k: v for k, v in DEFAULT_LAYOUT.items()},
        **kwargs,
    )
    return fig


def kpi_card(label: str, value: str | int | float, delta: Optional[str] = None,
             delta_color: str = "normal", help_text: Optional[str] = None) -> None:
    """
    Render a KPI card using Streamlit's metric.

    Args:
        label: Metric label.
        value: Metric value (formatted as string).
        delta: Optional delta indicator.
        delta_color: "normal", "inverse", or "off".
        help_text: Optional tooltip text.
    """
    import streamlit as st
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color, help=help_text)


def bar_chart_horizontal(df: pd.DataFrame, x: str, y: str, title: str = "",
                         color_col: Optional[str] = None,
                         color_map: Optional[dict] = None,
                         height: int = 400,
                         text_auto: bool = True,
                         hover_data: Optional[list] = None,
                         max_label_length: int = 25) -> go.Figure:
    """
    Create a horizontal bar chart with truncated labels for readability.

    Args:
        df: DataFrame with data.
        x: Column for x-axis (values).
        y: Column for y-axis (categories).
        title: Chart title.
        color_col: Optional column to color bars by.
        color_map: Optional dict mapping color_col values to colors.
        height: Chart height in pixels.
        text_auto: Show value labels on bars.
        hover_data: Additional columns to show on hover.
        max_label_length: Maximum character length for y-axis labels.

    Returns:
        Plotly Figure object.
    """
    # Truncate long labels for display
    display_df = df.copy()
    original_labels = display_df[y].copy()
    display_df[y] = display_df[y].apply(
        lambda label: label[:max_label_length] + "..." if len(str(label)) > max_label_length else label
    )

    fig = px.bar(
        display_df,
        x=x,
        y=y,
        orientation="h",
        color=color_col,
        color_discrete_map=color_map,
        text_auto=text_auto,
        hover_data=hover_data,
        title=title,
    )

    fig.update_traces(
        textposition="outside",
        textfont={"size": 11, "color": COLORS["text"]},
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>" + x + ": %{x}<extra></extra>",
    )

    fig.update_yaxes(autorange="reversed", title="")
    fig.update_xaxes(title="")

    return apply_default_layout(fig, title=title, height=height)


def line_chart_monthly(df: pd.DataFrame, date_col: str, value_col: str,
                       title: str = "", cumulative_col: Optional[str] = None,
                       height: int = 400,
                       show_markers: bool = True) -> go.Figure:
    """
    Create a monthly trend line chart with optional cumulative line.

    Args:
        df: DataFrame with monthly data.
        date_col: Column with date strings (YYYY-MM).
        value_col: Column with count values.
        title: Chart title.
        cumulative_col: Optional column with cumulative values.
        height: Chart height.
        show_markers: Show markers on lines.

    Returns:
        Plotly Figure object.
    """
    fig = go.Figure()

    # Main count line
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df[value_col],
        mode="lines+markers" if show_markers else "lines",
        name="Cantidad mensual",
        line={"color": COLORS["primary"], "width": 3},
        marker={"size": 8, "color": COLORS["primary"]},
        hovertemplate="<b>%{x}</b><br>Expedientes: %{y}<extra></extra>",
    ))

    # Cumulative line if provided
    if cumulative_col and cumulative_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[cumulative_col],
            mode="lines+markers" if show_markers else "lines",
            name="Acumulado",
            line={"color": COLORS["secondary"], "width": 2, "dash": "dot"},
            marker={"size": 6, "color": COLORS["secondary"]},
            hovertemplate="<b>%{x}</b><br>Acumulado: %{y}<extra></extra>",
            yaxis="y2",
        ))

        fig.update_layout(
            yaxis2={"title": "Acumulado", "overlaying": "y", "side": "right", "showgrid": False},
        )

    fig.update_xaxes(title="Mes", tickangle=-45)
    fig.update_yaxes(title="Expedientes")

    return apply_default_layout(fig, title=title, height=height)


def histogram_steps(df: pd.DataFrame, bins: int = 20, title: str = "",
                    mean_line: Optional[float] = None,
                    median_line: Optional[float] = None,
                    mode_line: Optional[float] = None,
                    height: int = 400) -> go.Figure:
    """
    Create a histogram of step counts with optional mean/median/mode lines.

    Args:
        df: DataFrame with step count data (must have 'step_count' column or similar).
        bins: Number of histogram bins.
        title: Chart title.
        mean_line: Optional mean value to show as vertical line.
        median_line: Optional median value to show as vertical line.
        mode_line: Optional mode value to show as vertical line.
        height: Chart height.

    Returns:
        Plotly Figure object.
    """
    # Determine step count column
    step_col = "step_count" if "step_count" in df.columns else df.columns[0]
    step_counts = df[step_col].dropna()

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=step_counts,
        nbinsx=bins,
        name="Distribución",
        marker={"color": COLORS["primary"], "opacity": 0.7},
        hovertemplate="Pasos: %{x}<br>Frecuencia: %{y}<extra></extra>",
    ))

    # Add vertical lines for statistics
    line_configs = [
        (mean_line, "Media", COLORS["primary"], "dash"),
        (median_line, "Mediana", COLORS["kpi_green"], "dot"),
        (mode_line, "Moda", COLORS["kpi_orange"], "dashdot"),
    ]

    for value, name, color, dash in line_configs:
        if value is not None and value > 0:
            fig.add_vline(
                x=value,
                line={"color": color, "width": 2, "dash": dash},
                annotation_text=f"{name}: {value:.1f}",
                annotation_position="top",
                annotation={"font": {"color": color, "size": 11}},
            )

    fig.update_xaxes(title="Número de pasos", dtick=1)
    fig.update_yaxes(title="Frecuencia")

    return apply_default_layout(fig, title=title, height=height, show_legend=False)


def boxplot_permanence(df: pd.DataFrame, x: str, y: str, title: str = "",
                       height: int = 500,
                       points: str = "outliers",
                       notched: bool = False,
                       max_label_length: int = 22) -> go.Figure:
    """
    Create a boxplot of permanence days by dependencia with truncated labels.

    Args:
        df: DataFrame with permanence data.
        x: Column for x-axis (dependencia).
        y: Column for y-axis (permanence_days).
        title: Chart title.
        height: Chart height.
        points: "outliers", "suspectedoutliers", "all", or False.
        notched: Show notched boxplot.
        max_label_length: Maximum character length for x-axis labels.

    Returns:
        Plotly Figure object.
    """
    # Truncate long labels for readability
    display_df = df.copy()
    display_df[x] = display_df[x].apply(
        lambda label: label[:max_label_length] + "..." if len(str(label)) > max_label_length else label
    )

    fig = px.box(
        display_df,
        x=x,
        y=y,
        points=points,
        notched=notched,
        title=title,
        color_discrete_sequence=[COLORS["primary"]],
    )

    fig.update_traces(
        marker={"size": 4, "opacity": 0.6},
        line={"width": 2},
        hovertemplate="<b>%{x}</b><br>Días: %{y}<extra></extra>",
    )

    fig.update_xaxes(title="", tickangle=-45, tickfont={"size": 10})
    fig.update_yaxes(title="Días de permanencia")

    return apply_default_layout(fig, title=title, height=height, show_legend=False)


def sankey_circuit(circuit_json: str, counts: list[int], title: str = "",
                   height: int = 500,
                   modal_color: str = COLORS["modal"],
                   atypical_color: str = COLORS["atypical"]) -> go.Figure:
    """
    Create a Sankey diagram for a circuit.

    Args:
        circuit_json: JSON string of circuit sequence (list of dependency names).
        counts: List of counts for each transition (length = len(circuit) - 1).
        title: Chart title.
        height: Chart height.
        modal_color: Color for modal circuit flows.
        atypical_color: Color for atypical circuit flows.

    Returns:
        Plotly Figure object.
    """
    try:
        circuit = json.loads(circuit_json)
    except (json.JSONDecodeError, TypeError):
        circuit = []

    if len(circuit) < 2:
        fig = go.Figure()
        fig.add_annotation(text="Circuito con menos de 2 pasos", x=0.5, y=0.5,
                          showarrow=False, font={"size": 16, "color": COLORS["secondary"]})
        return apply_default_layout(fig, title=title, height=height, show_legend=False)

    # Build nodes and links
    nodes = []
    node_indices = {}

    for i, step in enumerate(circuit):
        if step not in node_indices:
            node_indices[step] = len(nodes)
            nodes.append(step)

    source = []
    target = []
    value = []
    link_colors = []

    for i in range(len(circuit) - 1):
        src = node_indices[circuit[i]]
        tgt = node_indices[circuit[i + 1]]
        cnt = counts[i] if i < len(counts) else 1

        source.append(src)
        target.append(tgt)
        value.append(cnt)
        # Color first link (MDE -> first) differently
        link_colors.append(modal_color if i == 0 else atypical_color)

    # Node colors - MDE is special
    node_colors = []
    for node in nodes:
        if node.startswith("Mesa de Entradas"):
            node_colors.append(COLORS["kpi_blue"])
        else:
            node_colors.append(COLORS["primary"])

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node={
            "label": nodes,
            "color": node_colors,
            "pad": 20,
            "thickness": 30,
            "line": {"color": COLORS["grid"], "width": 1},
            "hovertemplate": "<b>%{label}</b><br>Total: %{value}<extra></extra>",
        },
        link={
            "source": source,
            "target": target,
            "value": value,
            "color": link_colors,
            "hovertemplate": "<b>%{source.label}</b> → <b>%{target.label}</b><br>Expedientes: %{value}<extra></extra>",
        },
    )])

    return apply_default_layout(fig, title=title, height=height, show_legend=False)


def parallel_sets(circuits_df: pd.DataFrame, title: str = "",
                  height: int = 500,
                  max_circuits: int = 10) -> go.Figure:
    """
    Create a parallel sets diagram for comparing multiple circuits.

    Args:
        circuits_df: DataFrame with circuito_json, concepto, frecuencia, es_mas_frecuente.
        title: Chart title.
        height: Chart height.
        max_circuits: Maximum circuits to display.

    Returns:
        Plotly Figure object.
    """
    # Limit circuits for readability
    display_df = circuits_df.head(max_circuits).copy()

    # Parse all circuits
    all_steps = []
    for _, row in display_df.iterrows():
        try:
            circuit = json.loads(row["circuito_json"])
            all_steps.append(circuit)
        except (json.JSONDecodeError, TypeError):
            all_steps.append([])

    # Find max steps for alignment
    max_steps = max(len(c) for c in all_steps) if all_steps else 0

    if max_steps < 2:
        fig = go.Figure()
        fig.add_annotation(text="Datos insuficientes para diagrama de conjuntos paralelos",
                          x=0.5, y=0.5, showarrow=False, font={"size": 16, "color": COLORS["secondary"]})
        return apply_default_layout(fig, title=title, height=height, show_legend=False)

    # Build parallel coordinates style visualization
    # Using Sankey-like approach but with all circuits
    fig = go.Figure()

    # Create a layered view: each step position is a layer
    step_positions = list(range(max_steps))

    for idx, (_, row) in enumerate(display_df.iterrows()):
        circuit = all_steps[idx]
        freq = row.get("frecuencia", 1)
        is_modal = row.get("es_mas_frecuente", False)

        color = COLORS["modal"] if is_modal else COLORS["atypical"]
        opacity = 0.8 if is_modal else 0.4
        width = max(2, min(10, freq / display_df["frecuencia"].max() * 10))

        for step_idx in range(len(circuit) - 1):
            if step_idx + 1 < len(circuit):
                fig.add_trace(go.Scatter(
                    x=[step_idx, step_idx + 1],
                    y=[circuit[step_idx], circuit[step_idx + 1]],
                    mode="lines",
                    line={"color": color, "width": width},
                    showlegend=False,
                    hoverinfo="skip",
                    opacity=opacity,
                ))

        # Add node markers
        for step_idx, step_name in enumerate(circuit):
            fig.add_trace(go.Scatter(
                x=[step_idx],
                y=[step_name],
                mode="markers+text",
                marker={"size": 12, "color": color, "opacity": opacity},
                text=[f"{freq}"],
                textposition="top center",
                textfont={"size": 10, "color": color},
                showlegend=False,
                hovertemplate=f"<b>{step_name}</b><br>Frecuencia: {freq}<extra></extra>",
            ))

    fig.update_xaxes(
        title="Paso del circuito",
        tickvals=step_positions,
        ticktext=[f"Paso {i}" for i in step_positions],
        range=[-0.5, max_steps - 0.5],
    )
    fig.update_yaxes(title="Dependencia", autorange="reversed")

    return apply_default_layout(fig, title=title, height=height, show_legend=False)


def circuit_frequency_table(circuits_df: pd.DataFrame, title: str = "",
                            height: int = 400) -> go.Figure:
    """
    Create a formatted table for circuit frequencies.

    Args:
        circuits_df: DataFrame with circuito_json, concepto, frecuencia, es_mas_frecuente.
        title: Table title.
        height: Table height.

    Returns:
        Plotly Figure object (Table trace).
    """
    display_df = circuits_df.copy()

    # Format circuit for display
    def format_circuit(circuito_json: str) -> str:
        try:
            circuit = json.loads(circuito_json)
            return " → ".join(circuit)
        except (json.JSONDecodeError, TypeError):
            return str(circuito_json)

    display_df["Circuito"] = display_df["circuito_json"].apply(format_circuit)
    display_df["Frecuencia"] = display_df["frecuencia"]
    display_df["%"] = (display_df["frecuencia"] / display_df["frecuencia"].sum() * 100).round(1)
    display_df["Modal"] = display_df["es_mas_frecuente"].apply(lambda x: "✅ Sí" if x else "No")

    # Color rows by modal status
    row_colors = []
    for _, row in display_df.iterrows():
        if row["es_mas_frecuente"]:
            row_colors.append(COLORS["modal"])
        else:
            row_colors.append(COLORS["white"])

    fig = go.Figure(data=[go.Table(
        header={
            "values": ["Circuito", "Frecuencia", "%", "Es Modal"],
            "fill_color": COLORS["primary"],
            "font": {"color": COLORS["white"], "size": 12},
            "align": ["left", "center", "center", "center"],
            "height": 35,
        },
        cells={
            "values": [
                display_df["Circuito"],
                display_df["Frecuencia"],
                display_df["%"],
                display_df["Modal"],
            ],
            "fill_color": [row_colors],
            "font": {"color": COLORS["text"], "size": 11},
            "align": ["left", "center", "center", "center"],
            "height": 30,
        },
    )])

    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": COLORS["text"]}, "x": 0.02},
        height=height,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )

    return fig


def dependency_traffic_bar(df: pd.DataFrame, title: str = "",
                           top_n: int = 10,
                           height: int = 400,
                           max_label_length: int = 22) -> go.Figure:
    """
    Create horizontal bar chart for top N dependencias by traffic.

    Args:
        df: DataFrame with dependencia, total_expedientes, pct_expedientes.
        title: Chart title.
        top_n: Number of top dependencias to show.
        height: Chart height.
        max_label_length: Maximum character length for labels.

    Returns:
        Plotly Figure object.
    """
    top_df = df.head(top_n).copy()
    # Truncate dependency names for readability
    top_df["label"] = top_df["dependencia"].apply(
        lambda dep: dep[:max_label_length] + "..." if len(dep) > max_label_length else dep
    ) + " (" + top_df["pct_expedientes"].astype(str) + "%)"

    return bar_chart_horizontal(
        top_df,
        x="total_expedientes",
        y="label",
        title=title,
        height=height,
        hover_data=["pct_expedientes", "total_movimientos"],
        max_label_length=max_label_length + 10,  # Account for percentage suffix
    )


def concept_distribution_pie(df: pd.DataFrame, title: str = "",
                             height: int = 400) -> go.Figure:
    """
    Create a pie chart for concept distribution.

    Args:
        df: DataFrame with concepto, cantidad, porcentaje.
        title: Chart title.
        height: Chart height.

    Returns:
        Plotly Figure object.
    """
    fig = px.pie(
        df,
        values="cantidad",
        names="concepto",
        title=title,
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Cantidad: %{value}<br>Porcentaje: %{percent}<extra></extra>",
    )

    fig.update_layout(
        height=height,
        showlegend=True,
        legend={"orientation": "v", "x": 1.05, "y": 0.5},
        margin={"l": 20, "r": 150, "t": 60, "b": 20},
    )

    return apply_default_layout(fig, title=title, height=height, show_legend=True)


def render_kpi_row(kpis: list[dict]) -> None:
    """
    Render a row of KPI cards.

    Args:
        kpis: List of dicts with keys: label, value, delta (optional), help (optional).
    """
    import streamlit as st

    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            st.metric(
                label=kpi["label"],
                value=kpi["value"],
                delta=kpi.get("delta"),
                delta_color=kpi.get("delta_color", "normal"),
                help=kpi.get("help"),
            )