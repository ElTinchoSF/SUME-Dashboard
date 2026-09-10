# Guía del Scraper SUME Dashboard

## Visión General

El scraper descarga expedientes y sus movimientos del sistema SUME (Sistema Único de Mesa de Entradas) de la Universidad Nacional del Litoral. Los datos se almacenan en una base de datos SQLite para su análisis posterior.

## Ubicación

```
src/scraper/          # Código fuente del scraper
src/pipeline/run.py   # CLI para ejecutar el scraper
data/sume.db          # Base de datos SQLite (resultado)
```

## Comandos Básicos

### Ejecutar el pipeline completo

```bash
python3 -m src.pipeline run --phase all
```

Ejecuta: init-db → scraper → analyzer → reporter

### Ejecutar solo el scraper

```bash
python3 -m src.pipeline run --phase scraper
```

### Inicializar la base de datos

```bash
python3 -m src.pipeline run --phase init-db
```

## Opciones de Filtrado

### 1. Filtrar por cantidad de páginas

Controla cuántas páginas del listado de SUME se descargan. Cada página contiene aproximadamente 15 expedientes.

```bash
# Scrapear solo las primeras 5 páginas (~75 expedientes)
python3 -m src.pipeline run --phase scraper --max-pages 5

# Scrapear 10 páginas (~150 expedientes)
python3 -m src.pipeline run --phase scraper --max-pages 10

# Scrapear todas las páginas disponibles (puede tardar varios minutos)
python3 -m src.pipeline run --phase scraper
```

**Nota:** Sin `--max-pages`, el scraper descarga todas las páginas disponibles.

### 2. Filtrar por rango de fechas

Filtra expedientes por su **fecha de creación** (`fecha_alta`). Los expedientes fuera del rango se eliminan después del scraping.

```bash
# Solo expedientes de 2026
python3 -m src.pipeline run --phase scraper --date-from 2026-01-01 --date-to 2026-12-31

# Primer semestre de 2026
python3 -m src.pipeline run --phase scraper --date-from 2026-01-01 --date-to 2026-06-30

# Desde julio 2026 en adelante
python3 -m src.pipeline run --phase scraper --date-from 2026-07-01

# Hasta septiembre 2026
python3 -m src.pipeline run --phase scraper --date-to 2026-09-30
```

**Formato de fecha:** `YYYY-MM-DD` (ISO 8601)

**Comportamiento:**
1. El scraper descarga TODOS los expedientes del listado
2. Después del scraping, se filtran y eliminan los expedientes fuera del rango
3. Solo quedan expedientes con `fecha_alta` dentro del rango especificado
4. Los circuitos completos de esos expedientes se preservan

### 3. Combinar filtros

Se pueden combinar ambos filtros:

```bash
# Primer semestre de 2026, máximo 10 páginas
python3 -m src.pipeline run --phase scraper --max-pages 10 --date-from 2026-01-01 --date-to 2026-06-30

# Último trimestre 2026, todas las páginas
python3 -m src.pipeline run --phase scraper --date-from 2026-10-01 --date-to 2026-12-31
```

## Otras Fases del Pipeline

### Analizador (analyzer)

Procesa los datos scrapingados y calcula circuitos, estadísticas y métricas.

```bash
python3 -m src.pipeline run --phase analyzer
```

**Salida:**
- Circuitos únicos por concepto
- Circuitos modales (más frecuentes)
- Estadísticas de pasos
- Tiempos de permanencia
- Detección de outliers
- Tráfico por dependencia

### Reportero (reporter)

Genera reportes en diferentes formatos.

```bash
# Reporte Markdown
python3 -m src.pipeline run --phase reporter --output reports/iso9001.md --format markdown

# Reporte Excel
python3 -m src.pipeline run --phase reporter --output reports/iso9001.xlsx --format excel

# Reporte de un concepto específico
python3 -m src.pipeline run --phase reporter --conceptos "Gestión Alumno" --output reports/alumno.md
```

## Flujo de Trabajo Recomendado

### Flujo completo (primera vez)

```bash
# 1. Inicializar base de datos
python3 -m src.pipeline run --phase init-db

# 2. Scrapear datos (ej: primer semestre 2026)
python3 -m src.pipeline run --phase scraper --date-from 2026-01-01 --date-to 2026-06-30

# 3. Analizar datos
python3 -m src.pipeline run --phase analyzer

# 4. Generar reporte
python3 -m src.pipeline run --phase reporter --output reports/iso9001.md
```

### Flujo rápido (datos ya existentes)

```bash
# Solo actualizar datos de un período específico
python3 -m src.pipeline run --phase scraper --date-from 2026-07-01 --date-to 2026-09-30
python3 -m src.pipeline run --phase analyzer
```

## Estructura de la Base de Datos

### Tabla `expedientes`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | ID interno |
| numero | TEXT | Número del expediente (ej: FBCB-1234567-26) |
| concepto | TEXT | Tipo de trámite |
| fecha_alta | DATE | **Fecha de creación** (usada para filtrado) |
| estado | TEXT | Estado actual |
| descripcion | TEXT | Descripción del trámite |
| palabras_clave | TEXT | Palabras clave |
| origenes | TEXT | Dependencia de origen |

### Tabla `movimientos`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | ID interno |
| expediente_id | INTEGER | FK a expedientes |
| orden | INTEGER | Orden cronológico (1 = primer paso) |
| fecha_recepcion | DATE | Fecha de recepción en la dependencia |
| dependencia | TEXT | Dependencia destino |

### Tabla `circuitos`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | ID interno |
| circuito | TEXT | JSON con la secuencia de dependencias |
| concepto | TEXT | Tipo de trámite |
| frecuencia | INTEGER | Cantidad de expedientes con este circuito |
| es_mas_frecuente | BOOLEAN | Si es el circuito modal |

## Configuración

### Archivo de configuración

`config/settings.yaml`:

```yaml
sume:
  base_url: "https://servicios.unl.edu.ar/expedientes/"
  faculty_filter: "FBCB"
  delay_seconds: 0.5

database:
  path: "data/sume.db"
```

### Variables de entorno

Se pueden sobreescribir con variables de entorno:

```bash
export SUME_SCRAPER_DELAY_SECONDS=1.0
export SUME_SCRAPER_FACULTY_FILTER="FBCB"
export SUME_DATABASE_PATH="data/sume.db"
```

## Consideraciones Importantes

### Límites del scraping

- **SUME no permite filtrado por fecha en la búsqueda** — el scraper descarga todo y filtra después
- **Velocidad:** Cada página toma ~5-10 segundos (incluyendo delay entre requests)
- **Duración estimada:**
  - 10 páginas: ~1-2 minutos
  - 50 páginas: ~5-10 minutos
  - Todas las páginas: ~15-30 minutos (depende de la cantidad total)

### Normalización de dependencias

El scraper normaliza automáticamente los nombres de dependencias:

| SUME | Normalizado |
|------|-------------|
| `Despacho General (Mesa de Entradas - FBCB)` | `Despacho General (FBCB)` |
| `Mesa de Entradas - FBCB` | `Mesa de Entradas - FBCB` |
| `CETRI (Mesa de Entradas - Rectorado)` | `CETRI (Rectorado)` |

### Orden de movimientos

- SUME muestra los movimientos del más nuevo al más viejo
- El scraper invierte el orden al almacenar
- `orden=1` = primer paso (más antiguo)
- `orden=N` = último paso (más reciente)

### Duplicados

- Los expedientes con el mismo número (`numero`) se ignoran (constraint UNIQUE)
- Se muestra un reporte de duplicados al final del scraping

## Ejemplos Prácticos

### Ejemplo 1: Análisis trimestral Q1 2026

```bash
# Scrapear y analizar solo el primer trimestre
python3 -m src.pipeline run --phase scraper --date-from 2026-01-01 --date-to 2026-03-31
python3 -m src.pipeline run --phase analyzer
python3 -m src.pipeline run --phase reporter --output reports/q1-2026.md
```

### Ejemplo 2: Muestra rápida para pruebas

```bash
# Solo 5 páginas (~75 expedientes)
python3 -m src.pipeline run --phase scraper --max-pages 5
python3 -m src.pipeline run --phase analyzer
```

### Ejemplo 3: Actualizar datos recientes

```bash
# Agregar expedientes de la última semana (si ya hay datos previos)
python3 -m src.pipeline run --phase scraper --date-from 2026-09-01
python3 -m src.pipeline run --phase analyzer
```

## Solución de Problemas

### Error: "Database not initialized"

```bash
python3 -m src.pipeline run --phase init-db
```

### Error: "Connection refused" o timeout

El servidor SUME puede estar lento. Intentar:
1. Aumentar el delay: `export SUME_SCRAPER_DELAY_SECONDS=2.0`
2. Reducir páginas: `--max-pages 5`
3. Reintentar más tarde

### Datos incompletos

Verificar que el scraping se completó revisando el reporte final:
```
SCRAPER VALIDATION REPORT
=========================
Total expedientes processed: 100
Total movimientos extracted: 751
Expedientes with zero movimientos: 0
```

Si `Expedientes with zero movimientos` es alto, puede haber problemas de parsing.
