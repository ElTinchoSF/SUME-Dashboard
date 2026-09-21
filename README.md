# SUME Dashboard v1 — Sistema de Análisis de Circuitos Administrativos

> **Dashboard interactivo y generador de informes ISO 9001** para el análisis de circuitos administrativos del sistema SUME (Sistema Unificado de Mesa de Entradas) de la Facultad de Ciencias Bioquímicas y Biológicas (FBCB) — Universidad Nacional del Litoral (UNL).

---

## 📋 Resumen

Este proyecto implementa un pipeline ETL completo para extraer, analizar y visualizar los circuitos administrativos de expedientes en el sistema SUME. Genera informes de evidencia compatibles con ISO 9001 y un dashboard interactivo para exploración de datos.

### Características principales

| Componente | Descripción |
|------------|-------------|
| **Scraper** | Extracción automatizada con rate limiting, reintentos exponenciales, y snapshots HTML |
| **Normalizador** | Reglas determinísticas + tabla de overrides explícitos para nombres de dependencias |
| **Analizador** | Process mining: reconstrucción de circuitos, frecuencias, circuitos modales, estadísticas de pasos, tiempos de permanencia, detección de outliers |
| **Dashboard** | Streamlit + Plotly con 4 páginas: Resumen, Conceptos, Circuitos, Reportes |
| **Reporter** | Jinja2 templates → Markdown/PDF/Excel con versionado automático (fecha, commit, hash de datos) |

---

## 🏗️ Arquitectura

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
                                                              ┌──────────────┐
                                                              │   REPORTER   │
                                                              │  (Jinja2)    │
                                                              └──────────────┘
```

### Decisiones de arquitectura clave

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| **Base de datos** | SQLite único (`data/sume.db`) | Zero-config, ACID, portable, suficiente para 4K expedientes |
| **Comunicación** | Solo vía BD (sin APIs directas) | Despliegue simple, ejecución independiente, auditoría natural |
| **Scraping** | Dos fases con gate de validación | Mitiga riesgo de cambios en HTML SUME, permite refinar normalizador |
| **Normalizador** | Función pura + overrides YAML | 99% cobertura objetivo, testeable, idempotente, trazable |
| **Circuitos** | JSON array en SQLite | Longitud variable, JSON1 queryable, lectura simple en dashboard |
| **Dashboard** | `@st.cache_data` TTL 300s | Sub-3s carga, invalida por mtime de `sume.db` |
| **Reportes** | Jinja2 templates | Separación contenido/lógica, versionado, Mermaid en MD, PDF profesional |

---

## 📦 Instalación

### Requisitos previos

- **Python 3.11+**
- **Git**
- (Opcional) `weasyprint` para generación de PDF — requiere dependencias de sistema:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install python3-dev libpango-1.0-0 libharfbuzz0b libpangocairo-1.0-0

  # macOS (Homebrew)
  brew install pango cairo gdk-pixbuf libffi
  ```

  En macOS, `weasyprint` necesita una variable de entorno para encontrar las librerías de Homebrew:
  ```bash
  export DYLD_LIBRARY_PATH=/opt/homebrew/lib
  ```
  Agregá esa línea a tu `~/.zshrc` o `~/.bash_profile` para que esté siempre disponible.
  En Docker ya está configurado automáticamente.

### Pasos

```bash
# 1. Clonar repositorio
git clone <repository-url>
cd SUME-Dashboard

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Verificar configuración
cat config.yaml  # Revisar rutas, facultad, año, etc.
```

### Dependencias principales

| Paquete | Propósito |
|---------|-----------|
| `requests`, `beautifulsoup4`, `lxml` | Scraping HTTP/HTML |
| `pandas`, `numpy` | Análisis vectorizado |
| `streamlit`, `plotly` | Dashboard interactivo |
| `pydantic`, `pydantic-settings`, `pyyaml` | Configuración tipada |
| `jinja2` | Templates de reportes |
| `weasyprint`, `openpyxl` | Exportación PDF/Excel |
| `pytest`, `pytest-mock` | Testing |

---

## 🚀 Uso

### Pipeline completo (CLI)

```bash
# Inicializar base de datos
python -m src.pipeline run --phase init-db

# Scraping directo con src.sume_scraper (recomendado)
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing

# Análisis completo (circuitos + estadísticas)
python -m src.pipeline run --phase analyzer

# Generar informe
python -m src.pipeline run --phase reporter --output reports/iso9001.md --format markdown
```

### Scraping de expedientes

```bash
# Scraping completo de un año (con skip de existentes — rápido)
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing

# Scraping por trimestre
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-03-31 --skip-existing
python -m src.sume_scraper --faculty FBCB --date-from 2025-04-01 --date-to 2025-06-30 --skip-existing
python -m src.sume_scraper --faculty FBCB --date-from 2025-07-01 --date-to 2025-09-30 --skip-existing
python -m src.sume_scraper --faculty FBCB --date-from 2025-10-01 --date-to 2025-12-31 --skip-existing

# Scraping completo (re-fetch todo, sobreescribe existentes)
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31

# Scraping con validación post-ejecución
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing --validate

# Testing: solo primeras 5 páginas
python -m src.sume_scraper --faculty FBCB --max-pages 5

# Logging detallado
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing -v
```

**Flags disponibles:**

| Flag | Descripción |
|------|-------------|
| `--faculty` | Código de la unidad académica (FBCB, FCA, FCV, etc.) — **obligatorio** |
| `--date-from` | Fecha de inicio (YYYY-MM-DD o DD/MM/YYYY) |
| `--date-to` | Fecha de fin (YYYY-MM-DD o DD/MM/YYYY) |
| `--skip-existing` | No fetch detail pages de expedientes ya en la DB — **mucho más rápido** |
| `--validate` | Ejecutar validaciones después del scraping |
| `--clean` | Limpiar DB antes de scraping (preserva asuntos) |
| `--clean-all` | Limpiar DB y asuntos antes de scraping |
| `--max-pages` | Limitar páginas a procesar (para testing) |
| `--db-path` | Ruta a la DB (default: `data/sume.db`) |
| `-v, --verbose` | Logging detallado (DEBUG level) |

### Dashboard interactivo

```bash
# Ejecutar servidor Streamlit
streamlit run src/dashboard/app.py

# En modo headless (para CI/smoke test)
streamlit run src/dashboard/app.py --server.headless true --server.port 8501
```

### Docker (recomendado para producción)

```bash
# Construir y ejecutar
docker compose up -d

# Ver logs
docker compose logs -f dashboard

# Detener
docker compose down
```

El dashboard estará disponible en `http://localhost:8504`. La base de datos se monta como volume desde `./data/sume.db`.

**Páginas del dashboard:**
1. **Resumen** — KPIs, expedientes por concepto, tendencia mensual, top 10 dependencias
2. **Conceptos** — Selector de concepto, tabla de frecuencias de circuitos, histograma de pasos, boxplot de permanencia
3. **Circuitos** — Diagrama Sankey del circuito modal, toggle vista completa, tabla de detalle con links SUME
4. **Reportes** — Generación de informes (MD/PDF/Excel) con preview y descarga

### Generador de reportes (CLI directo)

```bash
# Informe principal Markdown
python -m src.analysis.reports --output reports/iso9001.md --format markdown

# Informe principal PDF
python -m src.analysis.reports --output reports/iso9001.pdf --format pdf

# Informe principal Excel (multi-hoja)
python -m src.analysis.reports --output reports/iso9001.xlsx --format excel

# Filtrar por conceptos específicos
python -m src.analysis.reports --output reports/iso9001.md --format markdown --conceptos "Gestión Alumno,Gestión de Becas"

# Hoja de evidencia por concepto
python -m src.analysis.reports --output reports/concepto --format markdown --concepto "Gestión Alumno"

# Versionado automático (fecha.commit.hash_datos)
python -m src.analysis.reports --output reports/iso9001.md --format markdown --version-auto
```

---

## 🧪 Testing

### Ejecutar suite completa

```bash
# Todos los tests con cobertura
pytest tests/ -v --cov=src --cov-report=term-missing

# Solo tests unitarios (rápidos)
pytest tests/ -v -m "not slow and not benchmark"

# Tests de integración
pytest tests/test_integration.py -v

# Benchmarks de rendimiento (marcados como slow)
pytest tests/test_performance.py -v -m benchmark
```

### Cobertura objetivo

| Módulo | Cobertura mínima |
|--------|------------------|
| `src.sume_scraper.*` | ≥ 80% |
| `src.analysis.*` | ≥ 80% |
| `src.normalizer` | ≥ 80% |

### Estructura de tests

```
tests/
├── conftest.py              # Fixtures compartidas (temp DB, HTML samples, mocks)
├── test_scraper_client.py   # Unit: retry, backoff, rate limiting, 429 handling
├── test_scraper_parser.py   # Unit: HTML parsing con snapshots
├── test_normalizer.py       # Unit: 5 reglas + overrides + idempotencia (50+ casos)
├── test_circuits.py         # Unit: reconstrucción, frecuencia, modal, empates
├── test_statistics.py       # Unit: pasos, permanencia, outliers, tráfico, distribución
├── test_reporter.py         # Unit: templates, versionado, exportación (golden files)
├── test_dashboard.py        # Unit: data loading, filtros, chart builders
├── test_integration.py      # E2E: 100 expedientes sintéticos, pipeline completo
└── test_performance.py      # Benchmarks: scraper 2K<2hr, analyzer 4K<10s, dashboard<3s
```

---

## 🛠️ Guía de desarrollo

### Estructura del proyecto

```
SUME-Dashboard/
├── config.yaml                    # Configuración central (Pydantic Settings)
├── config/normalization_rules.yaml # Reglas + overrides de normalización
├── requirements.txt               # Dependencias Python
├── Dockerfile                     # Multi-stage build (builder → production)
├── docker-compose.yml             # Servicio dashboard con volumes
├── .dockerignore                  # Exclusiones para Docker build
├── README.md                      # Este archivo
├── data/
│   ├── raw/                       # Snapshots HTML (gitignored)
│   ├── processed/                 # Archivos intermedios (gitignored)
│   └── sume.db                    # Base de datos SQLite (gitignored)
├── reports/                       # Reportes generados (gitignored)
├── logs/                          # Logs de aplicación (gitignored)
├── templates/
│   ├── report_main.md.j2          # Template informe principal ISO 9001 (7 secciones)
│   └── report_concepto.md.j2      # Template hoja de evidencia por concepto
├── src/
│   ├── __init__.py                # Package + versión
│   ├── config.py                  # Pydantic Settings loading config.yaml
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py              # SQL DDL: 4 tablas + índices
│   │   ├── models.py              # TypedDicts: Expediente, Movimiento, Dependencia, Circuito
│   │   └── connection.py          # Singleton SQLite, transacciones, row_factory
│   ├── sume_scraper/
│   │   ├── __init__.py
│   │   ├── config.py              # ScraperConfig (dataclass) + SelectorConfig
│   │   ├── client.py              # HTTP client: retry, rate limit, 429, logging
│   │   ├── parser.py              # parse_listing_page, parse_detail_page, parse_movimientos
│   │   ├── normalizer.py          # normalize(), load_rules(), 5 reglas + overrides
│   │   ├── scraper.py             # SUMEScraper: orquestador con --skip-existing
│   │   ├── validator.py           # ScrapingValidator: validación post-scraping
│   │   ├── cli.py                 # CLI: argparse con todos los flags
│   │   └── __main__.py            # Entry point para python -m src.sume_scraper
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── circuits.py            # reconstruct_circuit, compute_frequencies, identify_modal
│   │   ├── statistics.py          # step_stats, permanence, outliers, traffic, distribution
│   │   └── reports.py             # CLI, Jinja2, load_report_data, multi-format export
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── app.py                 # Entry point, routing, auth gate, global filters
│   │   ├── auth.py                # Autenticación: password gate, SHA-256, session expiry
│   │   ├── data.py                # @st.cache_data loaders (expedientes, circuitos, stats, etc.)
│   │   ├── errors.py              # Error/warning rendering helpers
│   │   ├── logging_config.py      # Centralized logging (console + file)
│   │   ├── validation.py          # DB health checks (schema, tables, columns)
│   │   ├── components/
│   │   │   ├── filters.py         # Global filter widgets + session state
│   │   │   └── charts.py          # Plotly builders: KPI, bar, line, histogram, boxplot, Sankey, parallel sets
│   │   └── pages/
│   │       ├── overview.py        # Page 1: KPIs, charts
│   │       ├── conceptos.py       # Page 2: Circuit table, hist, boxplot
│   │       ├── circuitos.py       # Page 3: Sankey, parallel sets, detail table
│   │       └── reportes.py        # Page 4: Report generation UI
│   └── pipeline/
│       ├── __init__.py
│       ├── run.py                 # CLI: --phase init-db|scraper|analyzer|reporter|all
│       └── __main__.py            # Entry point
└── tests/                         # Ver estructura arriba
```

### Convenciones de código

| Aspecto | Convención |
|---------|------------|
| **Formato** | Black (line-length=100), isort |
| **Tipado** | Type hints obligatorios en funciones públicas |
| **Docstrings** | Google style (Args, Returns, Raises) |
| **Logging** | `logging.getLogger(__name__)` en cada módulo |
| **Config** | Solo vía `config.yaml` + `get_settings()` |
| **BD** | Solo vía `get_connection()` + `transaction()` context manager |
| **Tests** | Fixtures en `conftest.py`, parametrizados, datos sintéticos deterministas |

### Añadir nueva métrica al análisis

1. **Definir en `statistics.py`**: Nueva función `compute_xxx()` que retorna `pd.DataFrame`
2. **Registrar en `run_full_statistics_analysis()`**: Agregar al dict de resultados
3. **Exponer en `dashboard/data.py`**: Nueva función `@st.cache_data load_xxx()`
4. **Añadir chart builder en `dashboard/components/charts.py`**: Función `xxx_chart(df)`
5. **Usar en página correspondiente**: Importar y renderizar
6. **Test unitario**: `tests/test_statistics.py` + `tests/test_dashboard.py`
7. **Actualizar templates** si va en reportes: `templates/report_main.md.j2`

### Añadir nueva regla de normalización

1. Editar `config/normalization_rules.yaml`:
   ```yaml
   rules:
     - name: "nueva_regla"
       pattern: "regex_pattern"
       replacement: "reemplazo"
   explicit_overrides:
     "Nombre Original Completo": "Nombre Normalizado"
   ```
2. Verificar en `tests/test_normalizer.py` (agregar casos parametrizados)
3. Ejecutar `pytest tests/test_normalizer.py -v`

### Linting y formateo

```bash
# Formatear código
black src/ tests/
isort src/ tests/

# Verificar tipos (opcional)
mypy src/

# Lint
ruff check src/ tests/
```

### Debugging del scraper

```bash
# Ver logs detallados
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing -v 2>&1 | tee scraper.log

# Inspeccionar snapshots HTML
ls data/raw/
cat data/raw/detail_FBCB-1234567-25.html

# Ver reporte de validación
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing --validate
```

---

## 📊 Esquema de base de datos

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
    nome_original TEXT NOT NULL,
    total_expedientes INTEGER DEFAULT 0
);

-- circuitos
CREATE TABLE circuitos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    circuito TEXT NOT NULL,  -- JSON array
    concepto TEXT NOT NULL,
    frecuencia INTEGER NOT NULL,
    es_mas_frecuente BOOLEAN DEFAULT FALSE,
    UNIQUE(circuito, concepto)
);
```

**Índices:** `idx_expedientes_concepto`, `idx_expedientes_fecha_alta`, `idx_movimientos_expediente`, `idx_movimientos_dependencia`, `idx_circuitos_concepto`

---

## 🔧 Configuración

### `config.yaml` — Secciones principales

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
  delay_seconds: 0.5          # Rate limit entre requests
  timeout_seconds: 30         # Timeout HTTP
  max_retries: 3              # Reintentos con backoff exponencial
  backoff_base: 1.0           # Base para backoff: 1s, 2s, 4s
  rate_limit_wait: 60         # Espera ante 429 (segundos)
  user_agent: "SUME-Dashboard/1.0 (Mesa de Entradas FBCB-UNL)"

normalizer:
  rules_path: "config/normalization_rules.yaml"

analyzer:
  min_sample_threshold: 5           # Mínimo expedientes para circuito modal
  outlier_frequency_threshold: 0.05 # < 5% = outlier frecuencia
  outlier_step_multiplier: 2.5      # > 2.5x pasos modal = outlier estructural

dashboard:
  cache_ttl_seconds: 300
  page_size: 1000

reporter:
  templates_dir: "templates"
  output_dir: "reports"
  version_format: "{date}.{commit_short}.{data_hash_short}"
```

### Variables de entorno (overrides)

Todas las claves de `config.yaml` pueden sobrescribirse con variables de entorno con prefijo `SUME_` y separadores `__`:

```bash
export SUME_DATABASE__PATH="/custom/path/sume.db"
export SUME_SCRAPER__DELAY_SECONDS=1.0
export SUME_ANALYZER__MIN_SAMPLE_THRESHOLD=10
```

### Autenticación (opcional)

El dashboard incluye autenticación por contraseña (deshabilitada por defecto). Para habilitar:

```yaml
# config.yaml
auth:
  enabled: true
  password: "mi_password_seguro"
  session_hours: 8
```

La contraseña se almacena como hash SHA-256 con salt estático. La sesión expira después de `session_hours` horas.

---

## 📝 Versionado de reportes

El reporter genera versiones automáticas con formato: `{date}.{commit_short}.{data_hash_short}`

Ejemplo: `2025-01-15.a1b2c3d.e4f5g6h7`

| Componente | Descripción |
|------------|-------------|
| `date` | Fecha de generación (YYYY-MM-DD) |
| `commit_short` | `git rev-parse --short HEAD` (o `unknown`) |
| `data_hash_short` | SHA256 truncado de conteos + contenido de tablas clave |

Esto garantiza **trazabilidad completa**: mismo commit + mismos datos = mismo hash = reporte reproducible.

---

## 🔍 Validación de datos (Two-Phase Scraping)

El diseño incluye gates de validación manual entre fases:

```bash
# 1. Scraping semestre 1 (con skip de existentes)
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-06-30 --skip-existing --validate
# Revisar: validation report (duplicados, campos faltantes, expedientes sin movimientos)
# Refinar: config/normalization_rules.yaml si hay dependencias no normalizadas

# 2. Scraping semestre 2
python -m src.sume_scraper --faculty FBCB --date-from 2025-07-01 --date-to 2025-12-31 --skip-existing --validate
# Revisar: validation report consolidado

# 3. Analizador completo
python -m src.pipeline run --phase analyzer
# Verificar: tabla circuitos poblada, circuitos modales identificados

# 4. Smoke test dashboard
streamlit run src/dashboard/app.py --server.headless true
# Verificar: carga < 3s, 4 páginas renderizan, filtros funcionan

# 5. Generar informes finales
python -m src.pipeline run --phase reporter --output reports/iso9001.md --format markdown --version-auto
```

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError: src` | Ejecutar desde raíz del proyecto: `python -m src.pipeline ...` |
| `sqlite3.OperationalError: database is locked` | Cerrar otras instancias; usa `PRAGMA busy_timeout=30000` (ya configurado) |
| `weasyprint` falla en PDF | Instalar dependencias de sistema (ver Instalación) y en macOS: `export DYLD_LIBRARY_PATH=/opt/homebrew/lib` |
| Dashboard no carga datos | Verificar que `data/sume.db` existe y tiene datos; ejecutar `init-db` y `analyzer` |
| Normalización incorrecta | Ajustar `config/normalization_rules.yaml`; añadir a `explicit_overrides` |
| Tests lentos | Usar `pytest -m "not slow"` para excluir benchmarks |
| Docker: `permission denied` | Verificar permisos de `data/sume.db`; ejecutar `chmod 664 data/sume.db` |
| Docker: puerto en uso | Cambiar `PORT` en `.env` o `docker-compose.yml`: `PORT=8505 docker compose up` |
| Backup de BD | `python scripts/backup_db.py --compress --keep 10` |

---

## 📄 Licencia

Desarrollado para la **Mesa de Entradas FBCB-UNL** — Sistema de Gestión de Calidad ISO 9001.

---

## 🤝 Contribución

1. Fork del repositorio
2. Crear rama: `git checkout -b feature/nueva-funcionalidad`
3. Implementar con tests correspondientes
4. Verificar: `pytest tests/ -v --cov=src --cov-report=term-missing`
5. Formatear: `black src/ tests/ && isort src/ tests/`
6. Commit convencional: `git commit -m "feat: descripción breve"`
7. Push y crear Pull Request

---

## 📞 Contacto

**Mesa de Entradas FBCB-UNL**  
Facultad de Ciencias Bioquímicas y Biológicas  
Universidad Nacional del Litoral  
Paraje El Pozo, S3000 ZAA Santa Fe, Argentina

---

*Generado automáticamente por SUME Dashboard v1.0.0*