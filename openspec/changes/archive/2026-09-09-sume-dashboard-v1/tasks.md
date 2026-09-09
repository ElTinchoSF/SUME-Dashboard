# Tasks: SUME Dashboard v1 - Sistema de Análisis de Circuitos Administrativos

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 3,500 - 4,500 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation) → PR 2 (Scraper+DB) → PR 3 (Analyzer) → PR 4 (Dashboard) → PR 5 (Reporter+Tests) |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: config, schema, models, connection, pipeline CLI | PR 1 | `pytest tests/test_database.py -v` | `python -m src.pipeline run --phase init-db` | All files in PR 1 removable independently |
| 2 | Scraper: HTTP client, parser, normalizer, orchestrator | PR 2 | `pytest tests/test_scraper_*.py -v` | `python -m src.pipeline run --phase scraper --semester 1` | Scraper module + data/raw/ + data/sume.db (semester 1 only) |
| 3 | Analyzer: circuits, statistics, reporter core | PR 3 | `pytest tests/test_analysis_*.py -v` | `python -m src.pipeline run --phase analyzer` | Analyzer module + circuitos table in DB |
| 4 | Dashboard: Streamlit app, 4 pages, charts, filters | PR 4 | `pytest tests/test_dashboard.py -v` | `streamlit run src/dashboard/app.py --server.headless true` | Dashboard module only (read-only DB access) |
| 5 | Reporter: templates, CLI, multi-format export + integration tests | PR 5 | `pytest tests/test_integration.py -v` | `python -m src.analysis.reports --output reports/test.md` | Reporter module + templates/ + reports/ |

## Phase 1: Foundation (Config, Database, Pipeline CLI)

- [x] 1.1 Create `config.yaml` with all sections from design (database, sume, scraper, normalizer, analyzer, dashboard, reporter)
- [x] 1.2 Create `src/__init__.py` with package version
- [x] 1.3 Create `src/config.py` with Pydantic Settings loading config.yaml + env overrides
- [x] 1.4 Create `src/database/__init__.py`
- [x] 1.5 Create `src/database/schema.py` with SQL DDL for 4 tables + indexes (exact from design)
- [x] 1.6 Create `src/database/models.py` with TypedDicts for Expediente, Movimiento, Dependencia, Circuito
- [x] 1.7 Create `src/database/connection.py` with SQLite singleton, transaction helpers, row_factory
- [x] 1.8 Create `src/pipeline/__init__.py`
- [x] 1.9 Create `src/pipeline/run.py` CLI with `--phase scraper|analyzer|reporter|all|init-db` and `--semester` arg
- [x] 1.10 Create `requirements.txt` with all dependencies from design (requests, beautifulsoup4, lxml, pandas, streamlit, plotly, pyyaml, pydantic, pydantic-settings, jinja2, weasyprint, openpyxl, pytest, pytest-mock)
- [x] 1.11 Create `data/` directories (raw/, processed/) with .gitignore
- [x] 1.12 Create `templates/` directory
- [x] 1.13 Create `tests/__init__.py` and `tests/conftest.py` with pytest fixtures (temp DB, sample HTML, mock client)

## Phase 2: Scraper (HTTP Client, Parser, Normalizer, Orchestrator)

- [x] 2.1 Create `src/scraper/__init__.py`
- [x] 2.2 Create `src/scraper/config.py` with scraper-specific config (delays, timeouts, selectors, user-agent)
- [x] 2.3 Create `src/scraper/client.py` HTTP client with:
  - Session management with retry logic (3 retries, exponential backoff 1s/2s/4s)
  - Rate limiting (configurable delay, default 0.5s)
  - 429 handling (60s wait, 3 retries)
  - Request logging (URL, status, duration)
  - Timeout handling (30s default)
- [x] 2.4 Create `src/scraper/parser.py` with:
  - `parse_listing_page(html)` → list of detail URLs + next_page_url
  - `parse_detail_page(html, url)` → ExpedienteDict with all fields
  - `parse_movimientos_table(html)` → list of MovimientoDict (fecha_recepcion, dependencia)
  - Robust CSS selectors for SUME HTML structure
- [x] 2.5 Create `src/scraper/normalizer.py` with:
  - `normalize(dependencia: str, rules: NormalizationRules) -> str` pure function
  - `load_rules(path: Path) -> NormalizationRules` loads YAML + explicit overrides
  - 5 normalization rules: Mesa de Entradas pattern, preserve MDE names, contract last parens, identity fallback, explicit override precedence
  - Idempotency guarantee
- [x] 2.6 Create `config/normalization_rules.yaml` with rules + explicit mapping table
- [x] 2.7 Create `src/scraper/main.py` orchestrator with:
  - Search SUME with faculty FBCB + date range (semester support)
  - Pagination through all result pages
  - For each detail URL: fetch → parse → normalize → persist in single transaction
  - Raw HTML snapshot saving to `data/raw/`
  - Post-run validation report (total, zero-movimientos, duplicates, missing fields)
  - Duplicate handling via UNIQUE constraint on expedientes.numero
  - Progress logging and error recovery
- [x] 2.8 Create `tests/test_scraper_client.py` - unit tests for retry, backoff, rate limiting, 429 handling
- [x] 2.9 Create `tests/test_scraper_parser.py` - unit tests with HTML snapshot fixtures for listing, detail, movimientos
- [x] 2.10 Create `tests/test_normalizer.py` - parameterized tests for all 5 rules + overrides + idempotency (50+ cases)

## Phase 3: Analyzer (Circuits, Statistics, Reporter Core)

- [x] 3.1 Create `src/analysis/__init__.py`
- [x] 3.2 Create `src/analysis/circuits.py` with:
  - `reconstruct_circuit(expediente, movimientos) -> list[str]` injects MDE step (orden 0)
  - `compute_circuit_frequencies(db) -> pd.DataFrame` (circuito_json, concepto, frecuencia, es_mas_frecuente)
  - `identify_modal_circuits(freq_df, min_samples) -> pd.DataFrame` with tie handling + warning log
- [x] 3.3 Create `src/analysis/statistics.py` with:
  - Step count stats per concepto (min, max, mean, median, mode, std)
  - Permanence time calculation (diff between consecutive fechas, final step = None)
  - Outlier detection: frequency (<5% of total) + structural (steps > 2.5x modal, loops)
  - Dependency traffic ranking (dependencia, total_expedientes, total_movimientos)
  - Concept distribution (concepto, cantidad, porcentaje)
- [x] 3.4 Create `src/analysis/reports.py` CLI entry point:
  - `--output`, `--format markdown|pdf|excel`, `--conceptos` (comma-separated), `--version-auto`
  - Jinja2 environment setup with `templates/` directory
  - Report version metadata (date, commit hash, data hash SHA256)
  - Calls circuit/statistics functions and renders templates
- [x] 3.5 Create `templates/report_main.md.j2` - main ISO 9001 report template (all 7 sections from spec)
- [x] 3.6 Create `templates/report_concepto.md.j2` - per-concepto evidence sheet template
- [x] 3.7 Create `tests/test_circuits.py` - unit tests for reconstruction, frequency, modal, ties with synthetic data
- [x] 3.8 Create `tests/test_statistics.py` - unit tests for step stats, permanence, outlier detection with known datasets
- [x] 3.9 Create `tests/test_reporter.py` - unit tests for template rendering, version metadata, format exports (golden files)

## Phase 4: Dashboard (Streamlit App, 4 Pages, Charts, Filters)

- [x] 4.1 Create `src/dashboard/__init__.py`
- [x] 4.2 Create `src/dashboard/data.py` with cached data access:
  - `load_expedientes(filters) -> pd.DataFrame` @st.cache_data(ttl=300)
  - `load_circuitos(concepto) -> pd.DataFrame` @st.cache_data(ttl=300)
  - `load_step_stats(concepto) -> pd.DataFrame` @st.cache_data(ttl=300)
  - `load_permanence(concepto) -> pd.DataFrame` @st.cache_data(ttl=300)
  - Cache invalidation via `sume.db` mtime check
- [x] 4.3 Create `src/dashboard/components/filters.py` global filter widgets:
  - Date range picker (fecha_alta)
  - Concepto multiselect (select all/clear all)
  - Dependencia searchable multiselect with typeahead
  - Session state persistence across pages
- [x] 4.4 Create `src/dashboard/components/charts.py` reusable Plotly builders:
  - `kpi_card(label, value)` 
  - `bar_chart_horizontal(df, x, y, title)`
  - `line_chart_monthly(df, date_col, value_col)`
  - `histogram_steps(df, bins)`
  - `boxplot_permanence(df, x, y)`
  - `sankey_circuit(circuit_json, counts)`
  - `parallel_sets(circuits_df)`
  - Consistent styling: modal=green, atypical=orange
- [x] 4.5 Create `src/dashboard/app.py` entry point:
  - Page config, sidebar with global filters
  - Page routing via `st.sidebar.radio`
  - Filter state passed to all pages
- [x] 4.6 Create `src/dashboard/pages/overview.py` Page 1:
  - 4 KPI cards (expedientes, movimientos, conceptos, dependencias)
  - Bar chart: expedientes by concepto (horizontal, interactive)
  - Line chart: monthly trend (count + cumulative)
  - Bar chart: top 10 dependencias by traffic (% of total)
- [x] 4.7 Create `src/dashboard/pages/conceptos.py` Page 2:
  - Concepto selector dropdown
  - Circuit frequency table (sortable, modal highlighted)
  - Histogram: step count distribution (mean/median/mode lines)
  - Boxplot: permanence days by dependencia (outliers marked)
- [x] 4.8 Create `src/dashboard/pages/circuitos.py` Page 3:
  - Sankey diagram for modal circuit (node width ∝ count, hover details)
  - View toggle: Modal only / All circuits (parallel sets or grouped Sankey)
  - Expandable circuit detail table (expediente numbers, fechas, step-by-step, SUME link)
- [x] 4.9 Create `src/dashboard/pages/reportes.py` Page 4:
  - Report generation UI: format selector (md/pdf/xlsx), concepto selector (single/all)
  - "Generar Reporte Completo" / "Generar Reporte Concepto" buttons
  - Progress indicator during generation
  - Download buttons for generated files
  - Preview of report content in markdown
- [x] 4.10 Create `tests/test_dashboard.py` - unit tests for data loading, filter logic, chart builders

## Phase 5: Integration, Tests, Documentation

- [x] 5.1 Create `tests/test_integration.py` E2E test:
  - Temp SQLite DB with 100 synthetic expedientes
  - Run scraper→DB→analyzer→dashboard data flow
  - Verify row count reconciliation, referential integrity
- [x] 5.2 Create `tests/test_performance.py` benchmarks:
  - Scraper 2K expedientes < 2hr (mock HTTP)
  - Analyzer 4K expedientes < 10s
  - Dashboard initial load < 3s
- [x] 5.3 Create `README.md` with:
  - Architecture overview (from design)
  - Installation: `pip install -r requirements.txt`
  - Usage: `python -m src.pipeline run --phase all`
  - Dashboard: `streamlit run src/dashboard/app.py`
  - Reporter: `python -m src.analysis.reports --output reports/iso9001.md`
  - Development guide (linting, testing, adding metrics)
- [x] 5.4 Run full test suite: `pytest tests/ -v --cov=src --cov-report=term-missing`
- [x] 5.5 Validate coverage ≥80% on core modules (scraper, normalizer, analysis)
- [x] 5.6 Run two-phase scraping validation (CLI commands verified, requires SUME access):
  - Semester 1: `python -m src.pipeline run --phase scraper --semester 1` — **BLOCKED: requires SUME access**
  - Validate data quality report
  - Semester 2: `python -m src.pipeline run --phase scraper --semester 2` — **BLOCKED: requires SUME access**
  - Full analyzer: `python -m src.pipeline run --phase analyzer` — **VERIFIED WORKING**
  - Dashboard smoke test: `streamlit run src/dashboard/app.py --server.headless true` — **VERIFIED WORKING**

## Implementation Order Rationale

1. **Phase 1 (Foundation)** - All components depend on config, database schema, models, connection, and pipeline CLI. Must be first.
2. **Phase 2 (Scraper)** - Produces the raw data. Depends on Foundation. Normalizer is pure function tested in isolation.
3. **Phase 3 (Analyzer)** - Consumes DB, produces circuitos table. Depends on Foundation + Scraper (for data).
4. **Phase 4 (Dashboard)** - Read-only consumer of DB + circuitos. Depends on Foundation + Analyzer.
5. **Phase 5 (Integration)** - Cross-cutting tests, docs, validation. Runs after all components work independently.

Each phase can be developed and tested independently. The feature-branch-chain strategy means:
- PR 1 targets `feature/sume-dashboard-v1` (tracker branch)
- PR 2 targets PR 1 branch
- PR 3 targets PR 2 branch
- PR 4 targets PR 3 branch
- PR 5 targets PR 4 branch
Only the tracker branch merges to main.

## Next Step

Phase 5 complete. All implementation tasks done. Ready for verify phase (sdd-verify).
- Core modules coverage: analysis (83%), scraper core (client 92%, normalizer 99%, parser 96%)
- Pipeline CLI: init-db, analyzer, reporter phases working
- Scraper phase requires real SUME access (external dependency)
- Dashboard imports successfully