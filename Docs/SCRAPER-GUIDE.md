# SUME Scraper — Guía Técnica (v3)

## Resumen

Scraper reutilizable para extraer expedientes y movimientos de SUME (Sistema Único de Mesa de Entradas) de la UNL. Diseñado para soportar múltiples unidades académicas con configuración por código de facultad.

**Características principales:**
- ✅ Reutilizable para cualquier facultad de la UNL
- ✅ Scraping por rangos de fecha (ISO y formato local)
- ✅ Actualización incremental (insert + update)
- ✅ **`--skip-existing`**: omit HTTP de expedientes ya en la DB (~8min vs ~2h)
- ✅ Validaciones post-scraping
- ✅ Movimientos completos (sin importar fecha del último movimiento)

---

## Arquitectura

```
src/sume_scraper/
├── __init__.py      # Exportaciones públicas
├── __main__.py      # Punto de entrada para python -m
├── config.py        # ScraperConfig (dataclass) + SelectorConfig (Pydantic)
├── client.py        # HTTP client con retry, rate limiting, logging
├── parser.py        # Parsing HTML de páginas de SUME
├── normalizer.py    # Normalización de nombres de dependencias
├── scraper.py       # SUMEScraper: lógica principal con --skip-existing
├── validator.py     # ScrapingValidator: validaciones post-scraping
├── cli.py           # CLI: argparse con todos los flags
└── __main__.py      # Entry point para python -m src.sume_scraper
```

### Flujo de datos

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Búsqueda   │ ──▶ │  Listing    │ ──▶ │  Detalle    │ ──▶ │  SQLite     │
│  SUME       │     │  Parser     │     │  Parser     │     │  DB         │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
   POST a             Extrae            Extrae movimientos   Insert o Update
   buscar/            datos del         de cada expediente   (upsert)
   con filtros        expediente        (tabla de pases)
```

---

## Instalación y Configuración

### Requisitos
- Python 3.11+
- Dependencias: `requests`, `beautifulsoup4`, `lxml`, `pydantic`, `pydantic-settings`

### Configuración
El scraper usa dos configuraciones:

#### `ScraperConfig` (dataclass)
Para parámetros de ejecución:

```python
from src.sume_scraper import ScraperConfig

config = ScraperConfig(
    faculty_code="FBCB",           # Código de facultad (requerido)
    date_from="2025-01-01",        # Fecha inicio (opcional)
    date_to="2025-12-31",          # Fecha fin (opcional)
    base_url="https://...",        # URL base de SUME
    delay_seconds=0.5,             # Delay entre requests
    timeout_seconds=30,            # Timeout HTTP
    max_retries=3,                 # Reintentos máximos
    raw_html_dir="data/raw",       # Directorio para HTML crudo
    db_path="data/sume.db",        # Ruta a la DB SQLite
)
```

#### `SelectorConfig` (Pydantic BaseSettings)
Para CSS selectors de parsing (se carga desde `config.yaml` o env vars):

```python
from src.sume_scraper.config import SelectorConfig

selectors = SelectorConfig()
# selectors.listing_rows — selector para filas del listing
# selectors.detail_title — selector para título del detalle
# etc.
```

### Formato de Fechas
El scraper acepta dos formatos:
- **ISO**: `YYYY-MM-DD` (ej: `2025-01-01`)
- **Local**: `DD/MM/YYYY` (ej: `01/01/2025`)

Ambos se convierten internamente a ISO para procesamiento.

---

## Uso

### CLI (Recomendado)

```bash
# Scraping completo de FBCB para 2025 (RECOMENDADO: skip existentes)
python -m src.sume_scraper \
  --faculty FBCB \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --skip-existing

# Scraping completo re-fetch (sobreescribe todos los existentes)
python -m src.sume_scraper \
  --faculty FBCB \
  --date-from 2025-01-01 \
  --date-to 2025-12-31

# Scraping con validación post-ejecución
python -m src.sume_scraper \
  --faculty FBCB \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --skip-existing \
  --validate

# Scraping por trimestre (incremental)
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-03-31 --skip-existing
python -m src.sume_scraper --faculty FBCB --date-from 2025-04-01 --date-to 2025-06-30 --skip-existing
python -m src.sume_scraper --faculty FBCB --date-from 2025-07-01 --date-to 2025-09-30 --skip-existing
python -m src.sume_scraper --faculty FBCB --date-from 2025-10-01 --date-to 2025-12-31 --skip-existing

# Limpiar DB y asuntos antes de scraping completo
python -m src.sume_scraper \
  --faculty FBCB \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --clean-all

# Limpiar solo DB (preserva asuntos) antes de scraping
python -m src.sume_scraper \
  --faculty FBCB \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --clean

# Scraping limitado (testing: solo 5 páginas)
python -m src.sume_scraper \
  --faculty FBCB \
  --max-pages 5

# Scraping de otra facultad
python -m src.sume_scraper \
  --faculty FCA \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --skip-existing

# Modo verbose (logging detallado)
python -m src.sume_scraper \
  --faculty FBCB \
  --date-from 2025-01-01 \
  --date-to 2025-12-31 \
  --skip-existing \
  -v
```

### Flags Disponibles

| Flag | Descripción | Requerido |
|------|-------------|-----------|
| `--faculty` | Código de la unidad académica (FBCB, FCA, FCV, etc.) | ✅ Sí |
| `--date-from` | Fecha de inicio (YYYY-MM-DD o DD/MM/YYYY) | No |
| `--date-to` | Fecha de fin (YYYY-MM-DD o DD/MM/YYYY) | No |
| `--skip-existing` | Omitir HTTP de expedientes ya en la DB — **mucho más rápido** | No |
| `--validate` | Ejecutar validaciones después del scraping | No |
| `--clean` | Limpiar DB antes de scraping (preserva asuntos) | No |
| `--clean-all` | Limpiar DB y asuntos antes de scraping | No |
| `--max-pages` | Limitar páginas a procesar (para testing) | No |
| `--db-path` | Ruta a la DB (default: `data/sume.db`) | No |
| `-v, --verbose` | Logging detallado (DEBUG level) | No |

### API Python

```python
from src.sume_scraper import SUMEScraper, ScraperConfig, ScrapingValidator

# Crear configuración
config = ScraperConfig(
    faculty_code="FBCB",
    date_from="2025-01-01",
    date_to="2025-12-31",
)

# Ejecutar scraping (con skip de existentes)
scraper = SUMEScraper(config, skip_existing=True)
result = scraper.run()
result.print_summary()

# Ejecutar scraping completo (re-fetch todo)
scraper = SUMEScraper(config, skip_existing=False)
result = scraper.run()
result.print_summary()

# Ejecutar validaciones
validator = ScrapingValidator(config.db_path)
validation = validator.validate()
validation.print_summary()
```

---

## Comportamiento de Actualización

### Scraping Incremental
El scraper soporta actualización incremental:

1. **Si el expediente NO existe**: Se inserta con todos sus movimientos
2. **Si el expediente YA existe**: Se reemplazan TODOS los movimientos

Esto permite:
- Actualizar datos sin perder registros existentes
- Ejecutar múltiples scrapings parciales (ej: por semestre)
- Corregir datos parciales sin empezar de cero

### Flag `--skip-existing` (Recomendado)

Cuando se usa `--skip-existing`, el scraper carga todos los números de expedientes existentes en la DB en un `set` (O(1) lookup), y **omite completamente la request HTTP** para cada uno. Solo fetchea el detalle de los que faltan.

**Impacto real medido:**

| Escenario | Con `--skip-existing` | Sin flag |
|-----------|----------------------|----------|
| 374 páginas, 3,176 existentes | ~8 minutos | ~2 horas |
| Solo 558 nuevos | 558 requests HTTP | 3,734 requests HTTP |
| DB ya tiene 5,826 registros | Casi instantáneo | Horas |

**Cuándo usar:**
- ✅ Scraping periódico (ej: semanal, mensual)
- ✅ Reanudar scraping interrumpido
- ✅ Actualizar solo los nuevos sin tocar existentes

**Cuándo NO usar:**
- ❌ Cuando necesitás forzar re-fetch de todos (datos corruptos)
- ❌ Primera ejecución (no hay existentes)

```bash
# Ejemplo típico: actualización mensual
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing
```

### Ejemplo de Flujo
```bash
# 1. Scraping primer semestre
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-06-30

# 2. Scraping segundo semestre (actualiza el primero)
python -m src.sume_scraper --faculty FBCB --date-from 2025-07-01 --date-to 2025-12-31

# 3. Actualizar todos los datos
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31
```

---

## Limpieza de Base de Datos

### Opción 1: Usar CLI (Recomendado)
```bash
# Limpiar solo DB (preserva tabla asuntos)
python -m src.sume_scraper --faculty FBCB --clean --date-from 2025-01-01 --date-to 2025-12-31

# Limpiar TODO: DB + asuntos
python -m src.sume_scraper --faculty FBCB --clean-all --date-from 2025-01-01 --date-to 2025-12-31
```

**Diferencia entre `--clean` y `--clean-all`:**

| Flag | Tablas eliminadas | Preserva |
|------|-------------------|----------|
| `--clean` | `expedientes`, `movimientos`, `dependencias` | `asuntos`, `expediente_asuntos` |
| `--clean-all` | Todas las tablas | Nada |

### Opción 2: SQL Directo
```sql
-- Eliminar datos en orden correcto (respetar foreign keys)
DELETE FROM expediente_asuntos;
DELETE FROM movimientos;
DELETE FROM asuntos;
DELETE FROM expedientes;
DELETE FROM dependencias;
```

### Opción 3: Python
```python
from src.sume_scraper.cli import _clean_database, _clean_database_and_asuntos

_clean_database("data/sume.db")           # preserva asuntos
_clean_database_and_asuntos("data/sume.db")  # elimina todo
```

**⚠️ IMPORTANTE**: La limpieza elimina TODOS los datos. Use con precaución.

---

## Validaciones Post-Scraping

El scraper incluye un validador que verifica:

### 1. Integridad del Esquema
- Verifica que todas las tablas requeridas existan

### 2. Integridad de Datos
- Expedientes sin número
- Expedientes sin concepto
- Expedientes sin fecha
- Movimientos sin dependencia

### 3. Duplicados
- Detecta expedientes duplicados por número

### 4. Rangos de Fechas
- Verifica que el rango de fechas sea razonable
- Detecta fechas fuera de rango

### 5. Completitud
- Calcula porcentaje de expedientes con movimientos
- Identifica expedientes incompletos

### Uso
```bash
# Con validación
python -m src.sume_scraper --faculty FBCB --validate

# Solo validación (sin scraping)
python -c "
from src.sume_scraper import ScrapingValidator
validator = ScrapingValidator('data/sume.db')
report = validator.validate()
report.print_summary()
"
```

---

## Estructura de SUME (2026)

### Búsqueda Correcta
```python
{
    "numero": "FBCB",           # Código de facultad
    "fechaCdesde": "01/01/2025", # Fecha desde (DD/MM/YYYY)
    "fechaChasta": "31/12/2025", # Fecha hasta (DD/MM/YYYY)
    # ... otros campos vacíos
}
```

**Por qué funciona**: SUME permite buscar por prefijo del número. "FBCB" trae todos los expedientes de la Facultad de Bioquímica y Ciencias Biológicas.

### Paginación
- **Formato**: `buscar/{pagina}/`
- **Total**: SUME muestra `...{total}` en la paginación
- **Por página**: ~10 expedientes

### Detalle de Expediente
- **Endpoint**: `GET /expediente/{numero}`
- **Contenido**: Solo tabla de movimientos (pases)
- **Los datos básicos están en el listing**

---

## Rendimiento

### Sin `--skip-existing`

| Métrica | Valor |
|---------|-------|
| Tiempo promedio por request | ~0.5s |
| Tiempo promedio por expediente | ~1.5s (listing + detail) |
| Páginas por minuto | ~10-15 |
| Tiempo estimado 3,740 expedientes | ~1-2 horas |

### Con `--skip-existing` (Recomendado)

| Métrica | Valor |
|---------|-------|
| Tiempo de carga de DB (set) | ~0.5s |
| Tiempo por expediente existente | ~0ms (skip HTTP) |
| Tiempo por expediente nuevo | ~1.5s (listing + detail) |
| 3,734 existentes + 558 nuevos | ~8 minutos |

### Optimizaciones aplicadas
- Connection pooling (requests.Session)
- Rate limiting para evitar 429
- Solo se extraen datos necesarios
- **`--skip-existing`**: O(1) lookup en set, skip HTTP completo

---

## Troubleshooting

### "HTTP Error 429 Too Many Requests"
**Causa**: Demasiadas requests en poco tiempo.
**Solución**: Aumentar `delay_seconds` en config:
```python
config = ScraperConfig(faculty_code="FBCB", delay_seconds=1.0)
```

### "HTTP Error 420"
**Causa**: Faltan parámetros en la búsqueda avanzada.
**Solución**: Verificar que TODOS los parámetros estén presentes.

### "Database is locked"
**Causa**: Múltiples instancias del scraper corriendo.
**Solución**: Asegurar que solo una instancia acceda a la DB.

### "ParseError: unexpected end of tag"
**Causa**: HTML malformado de SUME.
**Solución**: BeautifulSoup es tolerante, pero si persiste, guardar HTML crudo para análisis.

### Scraping muy lento (>1 hora para un año)
**Causa**: No se está usando `--skip-existing`.
**Solución**: Agregar el flag para omitir HTTP de expedientes existentes:
```bash
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --skip-existing
```

### Quiero re-fetch de TODOS los existentes
**Causa**: Datos corruptos o desactualizados.
**Solución**: No usar `--skip-existing`:
```bash
python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31
```

---

## Extensibilidad

### Agregar Nueva Facultad
1. Conocer el código de la facultad en SUME (ej: "FCA", "FCV")
2. Ejecutar: `python -m src.sume_scraper --faculty CODIGO --date-from ... --date-to ...`

### Agregar Nuevo Campo
1. Actualizar `SelectorConfig` en `config.py` (campos CSS selectors)
2. Actualizar `ExpedienteDict` en `parser.py`
3. Actualizar `parse_listing_page()` o `parse_detail_page()`
4. Actualizar schema en `database/schema.py`
5. Actualizar `INSERT` en `_upsert_expediente()`

### Cambiar Filtros de Búsqueda
1. Actualizar `get_search_params()` en `config.py`
2. Agregar nuevos parámetros al dict `params`

---

## Referencias

- [SUME FBCB-UNL](https://servicios.unl.edu.ar/expedientes/)
- [ISO 9001:2015](https://www.iso.org/standard/62085.html)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)
