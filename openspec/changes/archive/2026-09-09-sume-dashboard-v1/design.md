# Design: SUME Dashboard v1 - Sistema de Análisis de Circuitos Administrativos

## Technical Approach

Modular Python architecture with 5 decoupled components communicating through a single SQLite database (`data/sume.db`). The pipeline follows a batch-oriented ETL pattern: Scraper → Database → Analyzer → Dashboard/Reporter. Each component is independently runnable and testable. Configuration centralized in `config.yaml`. The scraper uses requests+BeautifulSoup with rate limiting and exponential backoff. The analyzer uses pandas for vectorized process mining computations. The dashboard uses Streamlit+Plotly with cached data loading. The reporter uses Jinja2 templates for reproducible ISO 9001 evidence documents.

## Architecture Decisions

### Decision: SQLite as Single Source of Truth

**Choice**: Single SQLite file (`data/sume.db`) shared by all components
**Alternatives considered**: PostgreSQL, separate databases per component, in-memory pandas DataFrames
**Rationale**: Zero-config deployment, ACID transactions for scraper writes, portable single-file artifact, sufficient for 4K rows/40K movements. No operational overhead for local deployment.

### Decision: Component Communication via Database Only

**Choice**: No direct API calls between components; all data exchange through SQLite tables
**Alternatives considered**: REST APIs, message queues, shared memory
**Rationale**: Simplifies deployment (single process), enables independent execution, natural audit trail, supports incremental runs. Batch-oriented pipeline doesn't need real-time streaming.

### Decision: Two-Phase Scraping with Validation Gates

**Choice**: Execute semester 1 → validate → semester 2, with manual gate between phases
**Alternatives considered**: Single full-year run, automated continuous scraping
**Rationale**: Mitigates SUME HTML change risk; validates data quality on 2K records before committing to full 4K; allows normalizer rule refinement after seeing real data.

### Decision: Normalization as Pure Function with Explicit Override Table

**Choice**: Deterministic rule-based normalizer + YAML override mapping file
**Alternatives considered**: ML-based normalization, fuzzy matching only, hardcoded rules only
**Rationale**: 99% coverage target achievable with documented rules; explicit overrides handle edge cases; pure function enables unit testing and idempotency guarantee; audit trail via original/normalized storage.

### Decision: Circuit Representation as JSON Array in SQLite

**Choice**: Store circuits as JSON arrays in `circuitos.circuito` column
**Alternatives considered**: Normalized circuit_steps table, string concatenation, separate circuit DB
**Rationale**: Variable-length sequences; JSON1 extension enables querying; single-row per circuit simplifies dashboard reads; pandas `json_normalize` handles analysis.

### Decision: Streamlit @st.cache_data for Dashboard Performance

**Choice**: Cache all database reads with TTL; invalidate on data refresh
**Alternatives considered**: No caching, Redis, manual session state
**Rationale**: Sub-3s load requirement; 4K rows fits in memory; cache invalidation via file mtime check on `sume.db`; no external dependencies.

### Decision: Jinja2 Templates for ISO 9001 Reports

**Choice**: Markdown/PDF/Excel generation from Jinja2 templates
**Alternatives considered**: Hardcoded string formatting, reportlab only, pandas to_excel only
**Rationale**: Separation of content/logic; version-controlled templates; supports mermaid diagrams in Markdown; professional PDF via weasyprint; multi-sheet Excel via openpyxl.

### Decision: Configuration via YAML with Pydantic Settings

**Choice**: Single `config.yaml` loaded by Pydantic `BaseSettings`
**Alternatives considered**: Environment variables only, JSON config, Python config module
**Rationale**: Type validation, nested structure, environment override support, single source for all components, human-readable.

## Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   SUME Web  │────▶│   SCRAPER    │────▶│  SQLite DB  │────▶│  ANALYZER    │
│  (HTTP/HTML)│     │  (requests,  │     │  (sume.db)  │     │  (pandas)    │
└─────────────┘     │   BeautifulSoup)     │  4 tables   │     └──────┬───────┘
                    └──────────────┘     └─────────────┘            │
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
                    │  Normalizer  │     │  Circuitos  │     │  DASHBOARD   │
                    │  (pure func) │     │  table JSON │     │  (Streamlit) │
                    └──────────────┘     └─────────────┘     └──────┬───────┘
                                                                    │
                                                                    ▼
                                                             ┌──────────────┐
                                                             │   REPORTER   │
                                                             │  (Jinja2)    │
                                                             └──────────────┘
```

**Detailed Flow:**

1. **Scraper** fetches SUME listing pages → extracts detail URLs → fetches each detail page → parses HTML → normalizes dependencies → writes to `expedientes`, `movimientos`, `dependencias` tables in single transaction per expediente
2. **Analyzer** reads `expedientes` + `movimientos` (joined, ordered) → injects MDE step (orden 0) → reconstructs circuits → computes frequencies, modal circuits, step stats, permanence times, outliers → writes `circuitos` table + analytics views
3. **Dashboard** reads cached DataFrames from DB → applies global filters → renders 4 pages with Plotly charts
4. **Reporter** queries same views as dashboard → renders Jinja2 templates → outputs Markdown/PDF/Excel

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `config.yaml` | Create | Central configuration: DB path, SUME URLs, delays, retries, normalization rules path |
| `src/__init__.py` | Create | Package initialization, version |
| `src/config.py` | Create | Pydantic Settings loading config.yaml with env overrides |
| `src/scraper/__init__.py` | Create | Scraper package exports |
| `src/scraper/config.py` | Create | Scraper-specific config (delays, timeouts, selectors) |
| `src/scraper/client.py` | Create | HTTP client with retry logic, rate limiting, logging |
| `src/scraper/parser.py` | Create | HTML parsing: listing pagination, detail extraction, movimientos table |
| `src/scraper/normalizer.py` | Create | Dependency normalization rules + explicit override mapping |
| `src/scraper/main.py` | Create | Orchestrator: search, paginate, extract, validate, persist |
| `src/database/__init__.py` | Create | Database package exports |
| `src/database/schema.py` | Create | SQL DDL for 4 tables + indexes + migrations |
| `src/database/models.py` | Create | Dataclasses/TypedDicts for table rows |
| `src/database/connection.py` | Create | SQLite connection singleton, transaction helpers, row factories |
| `src/analysis/__init__.py` | Create | Analysis package exports |
| `src/analysis/circuits.py` | Create | Circuit reconstruction, frequency computation, modal identification |
| `src/analysis/statistics.py` | Create | Step stats, permanence times, outlier detection, dependency ranking |
| `src/analysis/reports.py` | Create | CLI entry, Jinja2 rendering, multi-format export (md/pdf/xlsx) |
| `src/dashboard/__init__.py` | Create | Dashboard package exports |
| `src/dashboard/app.py` | Create | Streamlit entry point, page routing, global filter state |
| `src/dashboard/pages/overview.py` | Create | Page 1: KPIs, bar charts, trend line, top dependencies |
| `src/dashboard/pages/conceptos.py` | Create | Page 2: Circuit table, step histogram, permanence boxplot |
| `src/dashboard/pages/circuitos.py` | Create | Page 3: Sankey diagrams, parallel sets, circuit detail table |
| `src/dashboard/pages/reportes.py` | Create | Page 4: Report generation UI, format selection, download |
| `src/dashboard/components/charts.py` | Create | Reusable Plotly chart builders with consistent styling |
| `src/dashboard/components/filters.py` | Create | Global filter widgets with session state persistence |
| `src/pipeline/__init__.py` | Create | Pipeline orchestration package |
| `src/pipeline/run.py` | Create | CLI: `python -m src.pipeline run --phase scraper|analyzer|reporter|all` |
| `tests/__init__.py` | Create | Test package |
| `tests/conftest.py` | Create | Pytest fixtures: temp DB, sample HTML, mock client |
| `tests/test_scraper_client.py` | Create | Unit tests: retry logic, rate limiting, error handling |
| `tests/test_scraper_parser.py` | Create | Unit tests: HTML parsing with snapshot fixtures |
| `tests/test_normalizer.py` | Create | Unit tests: all normalization rules + overrides + idempotency |
| `tests/test_circuits.py` | Create | Unit tests: circuit reconstruction, frequency, modal logic |
| `tests/test_statistics.py` | Create | Unit tests: step stats, permanence, outlier detection |
| `tests/test_integration.py` | Create | E2E test: scraper→DB→analyzer→dashboard data flow |
| `requirements.txt` | Create | Dependencies: requests, beautifulsoup4, lxml, pandas, streamlit, plotly, pyyaml, pydantic, pydantic-settings, jinja2, weasyprint, openpyxl, pytest, pytest-mock |
| `README.md` | Create | Architecture overview, usage commands, development guide |
| `data/raw/` | Create | Directory for raw HTML snapshots (gitignored) |
| `data/processed/` | Create | Directory for intermediate files (gitignored) |
| `data/sume.db` | Create | SQLite database (gitignored, generated at runtime) |
| `templates/` | Create | Jinja2 templates for ISO 9001 reports |
| `templates/report_main.md.j2` | Create | Main report template with all sections |
| `templates/report_concepto.md.j2` | Create | Per-concepto evidence sheet template |

## Interfaces / Contracts

### Config Schema (`config.yaml`)

```yaml
database:
  path: "data/sume.db"
  
sume:
  base_url: "https://servicios.unl.edu.ar/expedientes/"
  search_path: "busqueda_avanzada.php"
  detail_path: "ver_expediente.php"
  faculty_filter: "FBCB"
  year: 2025

scraper:
  delay_seconds: 0.5
  timeout_seconds: 30
  max_retries: 3
  backoff_base: 1.0
  rate_limit_wait: 60
  user_agent: "SUME-Dashboard/1.0 (Mesa de Entradas FBCB-UNL)"

normalizer:
  rules_path: "config/normalization_rules.yaml"
  
analyzer:
  min_sample_threshold: 5
  outlier_frequency_threshold: 0.05
  outlier_step_multiplier: 2.5

dashboard:
  cache_ttl_seconds: 300
  page_size: 1000
  
reporter:
  templates_dir: "templates"
  output_dir: "reports"
  version_format: "{date}.{commit_short}.{data_hash_short}"
```

### Database Schema (SQLite)

```sql
-- expedientes
CREATE TABLE expedientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT UNIQUE NOT NULL,
    concepto TEXT NOT NULL,
    descripcion TEXT,
    fecha_alta DATE NOT NULL,
    estado TEXT,
    palabras_clave TEXT,
    origenes TEXT,
    fecha_extraccion DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- movimientos
CREATE TABLE movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expediente_id INTEGER NOT NULL REFERENCES expedientes(id),
    orden INTEGER NOT NULL,
    fecha_recepcion DATE NOT NULL,
    dependencia TEXT NOT NULL,
    UNIQUE(expediente_id, orden)
);

-- dependencias
CREATE TABLE dependencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    nombre_original TEXT NOT NULL,
    total_expedientes INTEGER DEFAULT 0
);

-- circuitos
CREATE TABLE circuitos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    circuito TEXT NOT NULL,  -- JSON array of dependency names
    concepto TEXT NOT NULL,
    frecuencia INTEGER NOT NULL,
    es_mas_frecuente BOOLEAN DEFAULT FALSE,
    UNIQUE(circuito, concepto)
);

-- Indexes
CREATE INDEX idx_expedientes_concepto ON expedientes(concepto);
CREATE INDEX idx_expedientes_fecha_alta ON expedientes(fecha_alta);
CREATE INDEX idx_movimientos_expediente ON movimientos(expediente_id);
CREATE INDEX idx_movimientos_dependencia ON movimientos(dependencia);
CREATE INDEX idx_circuitos_concepto ON circuitos(concepto);
```

### Normalizer Interface

```python
# src/scraper/normalizer.py
def normalize(dependencia: str, rules: NormalizationRules) -> str:
    """Pure function: same input always returns same output."""
    ...

def load_rules(path: Path) -> NormalizationRules:
    """Load YAML rules + explicit overrides."""
    ...
```

### Analyzer Interface

```python
# src/analysis/circuits.py
def reconstruct_circuit(expediente: Expediente, movimientos: list[Movimiento]) -> list[str]:
    """Returns ordered dependency names including injected MDE step."""
    ...

def compute_circuit_frequencies(db: Connection) -> pd.DataFrame:
    """Returns: circuito_json, concepto, frecuencia, es_mas_frecuente"""
    ...

def identify_modal_circuits(freq_df: pd.DataFrame, min_samples: int) -> pd.DataFrame:
    """Marks es_mas_frecuente per concepto with tie handling."""
    ...
```

### Dashboard Data Access

```python
# src/dashboard/data.py
@st.cache_data(ttl=300)
def load_expedientes(filters: FilterState) -> pd.DataFrame: ...

@st.cache_data(ttl=300)
def load_circuitos(concepto: str) -> pd.DataFrame: ...

@st.cache_data(ttl=300)
def load_step_stats(concepto: str) -> pd.DataFrame: ...

@st.cache_data(ttl=300)
def load_permanence(concepto: str) -> pd.DataFrame: ...
```

### Reporter CLI

```bash
python -m src.analysis.reports \
    --output reports/iso9001_2025.md \
    --format markdown \
    --conceptos "Gestión Alumno,Gestión de Becas" \
    --version-auto
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit - Scraper Client | Retry logic, backoff, rate limiting, 429 handling | Mock `requests.Session`; test timing with `time.monotonic` |
| Unit - Scraper Parser | Listing pagination, detail extraction, movimientos table | HTML snapshots from real SUME pages as fixtures; test selectors |
| Unit - Normalizer | All 5 rules + overrides + idempotency + edge cases | Parameterized tests with 50+ input/expected pairs |
| Unit - Circuits | Reconstruction with MDE injection, frequency, modal, ties | Synthetic expedientes with known circuits; assert exact outputs |
| Unit - Statistics | Step stats, permanence calc, outlier detection (freq + structure) | Known datasets with calculated expected values |
| Unit - Reporter | Template rendering, version metadata, format exports | Compare generated output to golden files |
| Integration | Scraper→DB→Analyzer→Dashboard data flow | Temp SQLite DB; run full pipeline on 100 synthetic expedientes |
| Integration | Referential integrity validation | Foreign key checks, row count reconciliation |
| E2E | Two-phase scraping with validation gate | Integration test with phase 1 + phase 2 data |
| Performance | Scraper 2K expedientes < 2hr; Analyzer 4K < 10s; Dashboard load < 3s | Benchmark fixtures; assert time budgets |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required (greenfield project). Rollout plan:

1. **Phase 1**: Deploy scraper + database → run semester 1 → validate data quality → refine normalizer rules
2. **Phase 2**: Run semester 2 → full analyzer run → validate circuitos table
3. **Phase 3**: Deploy dashboard → stakeholder review → iterate on visualizations
4. **Phase 4**: Generate ISO 9001 reports → MDE-FBCB validation → final delivery

Feature flags not needed; all components versioned together.

## Open Questions

- [ ] Confirm SUME HTML structure stability with UNL IT (selectors may need adjustment)
- [ ] Define exact faculty code mapping for MDE injection (FBCB, FHUC, FADU, etc.)
- [ ] Decide PDF engine: weasyprint (requires system deps) vs reportlab (pure Python)
- [ ] Confirm dashboard deployment target: local only or shared server?
- [ ] Define "concepto" normalization needs (some SUME conceptos may be similar but differently spelled)

---

*Design document for SUME Dashboard v1. Generated per SDD workflow.*