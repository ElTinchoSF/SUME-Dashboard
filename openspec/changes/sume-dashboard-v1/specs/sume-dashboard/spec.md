# Sume Dashboard Specification

## Purpose

Interactive Streamlit dashboard for visualizing administrative circuits, exploring expediente patterns, and generating ISO 9001 evidence reports. Four-page layout with global filters and export capabilities.

## Requirements

### Requirement: Global Filters

The system SHALL provide persistent global filters applied across all dashboard pages.

#### Scenario: Filter by date range

- GIVEN the dashboard loads with data from 2025
- WHEN the user selects date range "01/03/2025 - 31/03/2025" in the sidebar
- THEN all pages SHALL update to show only expedientes with fecha_alta in that range
- AND the filter state SHALL persist when navigating between pages

#### Scenario: Filter by concepto

- GIVEN the dashboard loads with 20 conceptos
- WHEN the user selects "Gestión Alumno" and "Gestión de Becas" in the multiselect
- THEN all pages SHALL show only data for those conceptos
- AND the filter SHALL support "Select All" and "Clear All" actions

#### Scenario: Filter by dependencia

- GIVEN the dashboard loads with 50+ dependencias
- WHEN the user selects "Alumnado (FBCB)" in the dependency filter
- THEN all pages SHALL show only expedientes that passed through that dependencia
- AND the filter SHALL support search/typeahead for long lists

### Requirement: Page 1 - Overview (Vista General)

The system SHALL display a summary page with key metrics and distributions.

#### Scenario: KPI cards

- GIVEN filtered data
- WHEN the Overview page renders
- THEN the page SHALL show 4 KPI cards: Total Expedientes, Total Movimientos, Conceptos Únicos, Dependencias Únicas
- AND each card SHALL update reactively to filter changes

#### Scenario: Expedientes by concepto (bar chart)

- GIVEN filtered data
- WHEN the Overview page renders
- THEN the page SHALL show a horizontal bar chart: concepto vs count of expedientes
- AND the chart SHALL be interactive (hover for exact values, click to filter)

#### Scenario: Monthly trend (line chart)

- GIVEN filtered data
- WHEN the Overview page renders
- THEN the page SHALL show a line chart: month vs expedientes created
- AND the chart SHALL show both count and cumulative lines

#### Scenario: Top dependencias by traffic (bar chart)

- GIVEN filtered data
- WHEN the Overview page renders
- THEN the page SHALL show a horizontal bar chart: top 10 dependencias by expediente count
- AND the chart SHALL show percentage of total

### Requirement: Page 2 - Conceptos (Análisis por Concepto)

The system SHALL provide deep-dive analysis for a selected concepto.

#### Scenario: Concepto selector

- GIVEN the Conceptos page loads
- WHEN the user selects a concepto from the dropdown
- THEN the page SHALL update all visualizations for that concepto only

#### Scenario: Circuit frequency table

- GIVEN a selected concepto
- WHEN the Conceptos page renders
- THEN the page SHALL show a sortable table: Circuito (formatted), Frecuencia, %, Es Modal
- AND the modal circuit row SHALL be visually highlighted

#### Scenario: Step count distribution (histogram)

- GIVEN a selected concepto
- WHEN the Conceptos page renders
- THEN the page SHALL show a histogram: number of steps vs count of expedientes
- AND the histogram SHALL show mean, median, mode as vertical lines

#### Scenario: Permanence time boxplot

- GIVEN a selected concepto
- WHEN the Conceptos page renders
- THEN the page SHALL show a boxplot: dependencia vs permanence days
- AND outliers SHALL be marked individually

### Requirement: Page 3 - Circuitos (Visualización de Circuitos)

The system SHALL visualize administrative circuits as interactive flow diagrams.

#### Scenario: Sankey diagram for modal circuit

- GIVEN a selected concepto with modal circuit identified
- WHEN the Circuitos page renders
- THEN the page SHALL show a Sankey diagram of the modal circuit
- AND node widths SHALL be proportional to expediente count
- AND hovering a link SHALL show: source → target, count, % of total

#### Scenario: All circuits comparison

- GIVEN a selected concepto
- WHEN the user selects "Todos los circuitos" view
- THEN the page SHALL show a parallel sets diagram or grouped Sankey
- AND circuits SHALL be ordered by frequency descending

#### Scenario: Circuit detail table

- GIVEN a selected concepto
- WHEN the Circuitos page renders
- THEN the page SHALL show an expandable table per circuit with: expediente numbers, fechas, step-by-step path
- AND clicking an expediente SHALL link to SUME detail page (external)

### Requirement: Page 4 - Reportes (Reportes ISO 9001)

The system SHALL generate formatted reports for ISO 9001 certification evidence.

#### Scenario: Report generation

- GIVEN the Reportes page loads
- WHEN the user clicks "Generar Reporte Completo"
- THEN the system SHALL generate a markdown/PDF report with:
  - Executive summary (period, total expedientes, coverage)
  - Per-concepto section: modal circuit, frequency, step stats, top dependencias
  - Atypical circuits appendix
  - Dependency traffic ranking
  - Data quality notes (anomalies, coverage %)

#### Scenario: Export formats

- GIVEN a generated report
- WHEN the user selects export format
- THEN the system SHALL support: Markdown (.md), PDF (.pdf), Excel (.xlsx)
- AND Excel export SHALL have separate sheets per section

#### Scenario: Per-concepto report

- GIVEN the Reportes page loads
- WHEN the user selects a single concepto and clicks "Generar Reporte"
- THEN the system SHALL generate a focused report for that concepto only

### Requirement: Performance and Responsiveness

The system SHALL load and respond within acceptable limits.

#### Scenario: Initial load time

- GIVEN the dashboard starts with full 2025 dataset (~4000 expedientes)
- WHEN the user opens the dashboard
- THEN the initial page render SHALL complete in <3 seconds
- AND data loading SHALL use Streamlit caching (@st.cache_data)

#### Scenario: Filter interaction latency

- GIVEN the dashboard is loaded
- WHEN the user changes a global filter
- THEN the page SHALL update in <1 second
- AND the system SHALL use cached filtered DataFrames

### Requirement: Accessibility and Usability

The system SHALL be usable by administrative staff with basic computer skills.

#### Scenario: Clear visual hierarchy

- GIVEN any dashboard page
- WHEN the page renders
- THEN the page SHALL have: clear page title, section headers, descriptive chart titles
- AND color coding SHALL be consistent (modal circuit = green, atypical = orange)

#### Scenario: Tooltips and help

- GIVEN any chart or metric
- WHEN the user hovers over a chart element or metric label
- THEN a tooltip SHALL explain the metric definition and calculation

## Non-Functional Requirements

### Technology Stack

- The dashboard SHALL be built with Streamlit ≥1.28
- Visualizations SHALL use Plotly ≥5.18 for interactivity
- The dashboard SHALL run locally with `streamlit run src/dashboard/app.py`

### Data Freshness

- The dashboard SHALL read from the SQLite database (data/sume.db)
- The dashboard SHALL NOT modify the database (read-only)

### Browser Compatibility

- The dashboard SHALL work in Chrome, Firefox, Edge (latest 2 versions)
- The dashboard SHALL be responsive to window width ≥1200px

## Constraints and Assumptions

- Single-user local deployment (no authentication required)
- Spanish language only for UI labels and reports
- Data volume: ~4000 expedientes, ~40k movimientos, ~50 dependencias, ~20 conceptos
- Report generation may take 10-30 seconds for full dataset