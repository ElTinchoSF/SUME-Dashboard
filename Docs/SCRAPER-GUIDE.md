# SUME Scraper — Guía Técnica

## Resumen

Scraper para extraer expedientes y movimientos de SUME (Sistema Único de Mesa de Entradas) de la FBCB-UNL. Diseñado para obtener datos de circuitos administrativos con fines de certificación ISO 9001.

**Resultado actual**: 1,615 expedientes, 16,096 movimientos (dataset anual 2025 completo).

---

## Arquitectura

```
src/scraper/
├── config.py        # Configuración tipada (Pydantic)
├── client.py        # HTTP client con retry, rate limiting, logging
├── parser.py        # Parsing HTML de páginas de SUME
├── normalizer.py    # Normalización de nombres de dependencias
└── main.py          # Orquestador del flujo completo
```

### Flujo de datos

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Búsqueda   │ ──▶ │  Listing    │ ──▶ │  Detalle    │ ──▶ │  SQLite     │
│  SUME       │     │  Parser     │     │  Parser     │     │  DB         │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
   POST a             Extrae            Extrae movimientos   Persiste en
   buscar/            datos del         de cada expediente   transacción
   con filtros        expediente        (tabla de pases)     única
```

---

## Estructura de SUME (2026)

### Header Search (Búsqueda Simple)

**Endpoint**: `POST https://servicios.unl.edu.ar/expedientes/buscar/`

**Parámetros**:
```python
{
    "header_search": "numero",      # Buscar por número
    "header_search_text": "FBCB"    # Filtro por facultad
}
```

**Resultado**: Página con tabla de resultados y paginación.

**Por qué funciona**: SUME permite buscar expedientes por prefijo del número. "FBCB" trae todos los expedientes de la Facultad de Bioquímica y Ciencias Biológicas.

### Advanced Search (Búsqueda Avanzada)

**Endpoint**: `POST https://servicios.unl.edu.ar/expedientes/buscar/`

**Parámetros requeridos** (TODOS deben estar presentes, incluso vacíos):
```python
{
    "numero": "",                    # Filtro por número
    "descripcion": "",               # Filtro por descripción
    "palabraClave": "",              # Palabra clave
    "selectOrigen": "interno",       # Tipo de origen (interno/externo)
    "mesaEntrada": "5",              # ID de Mesa de Entradas - FBCB
    "oficina": "5",                  # CRÍTICO: auto-seleccionado por JS
    "concepto": "",                  # Filtro por concepto
    "fechaCdesde": "",               # Fecha desde (DD/MM/YYYY)
    "fechaChasta": "",               # Fecha hasta (DD/MM/YYYY)
    "tipoDR": "",                    # Tipo de documento respaldo
    "numeroDR": "",                  # Número de documento respaldo
}
```

**Descubrimiento crítico**: El parámetro `oficina=5` es **obligatorio** cuando se selecciona `mesaEntrada=5` (FBCB). JavaScript del navegador auto-selecciona la oficina cuando cambias la mesa de entrada. Sin este parámetro:
- SUME retorna 4,200+ páginas (todos los expedientes de FBCB, no solo Mesa de Entradas)
- Con `oficina=5`: 73 páginas (solo Mesa de Entradas)

**Formato de fechas**: DD/MM/YYYY (no ISO). El conversor en `config.py` transforma YYYY-MM-DD → DD/MM/YYYY.

### Detalle de Expediente

**Endpoint**: `GET https://servicios.unl.edu.ar/expedientes/expediente/{numero}`

**Contenido**: Solo tabla de movimientos (pases). No hay datos del expediente en esta página.

**Por qué**: La nueva versión de SUME (2026) separó la información: datos básicos en el listing, movimientos en el detalle.

### Paginación

**Formato**: `buscar/{pagina}/`

**Característica especial**: SUME muestra `...9104` en la paginación para indicar el total de páginas. El parser detecta este formato:

```python
# parser.py - Línea 140-145
elif text.startswith("..."):
    try:
        total_from_ellipsis = int(text[3:])
        max_page = max(max_page, total_from_ellipsis)
    except ValueError:
        pass
```

**Por qué**: SUME no muestra todas las páginas en la paginación. Usa `...{total}` para indicar cuántas hay.

---

## Configuración Detallada

### HTTP Client (`client.py`)

| Parámetro | Valor | Por qué |
|-----------|-------|---------|
| `delay_seconds` | 0.5s | Respetar el servidor; evitar rate limiting |
| `timeout_seconds` | 30s | SUME puede ser lento en horas pico |
| `max_retries` | 3 | Transitorios de red (500, 502, 503, 504) |
| `backoff_base` | 1.0s | Exponencial: 1s, 2s, 4s entre reintentos |
| `rate_limit_wait` | 60s | Espera en 429 Too Many Requests |
| `rate_limit_retries` | 3 | Reintentos después de rate limit |

**User-Agent**:
```
SUME-Dashboard/1.0 (Mesa de Entradas FBCB-UNL)
```
Identifica el scraper como herramienta institucional, no como bot genérico.

**Headers**:
```python
{
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}
```
Simula un navegador real con preferencia de español argentino.

### Selectores CSS (`config.py`)

```python
# Listing page
listing_table = "table.table"           # Tabla de resultados
listing_rows = "tbody tr"               # Filas del cuerpo
listing_detail_link = "td:first-child"  # Primera celda (número)

# Detail page
detail_numero = "h4.label"             # Número del expediente
movimientos_table = "table.table"      # Tabla de movimientos
movimientos_rows = "tbody tr"          # Filas de movimientos
movimientos_cells = "td"               # Celdas de cada fila
```

**Por qué estos selectores**: SUME usa Bootstrap 3 con clases genéricas `table`, `panel-body`, etc. No hay IDs o clases únicas, por lo que se depende de la estructura del DOM.

### Normalización de Dependencias (`normalizer.py`)

**Objetivo**: Preservar información de facultad en nombres de dependencias.

**Ejemplos**:
```
"Despacho General (Mesa de Entradas - FBCB)" → "Despacho General (FBCB)"
"Mesa de Entradas - FBCB"                     → "Mesa de Entradas - FBCB" (preservado)
"CETRI (Mesa de Entradas - Rectorado)"       → "CETRI (Rectorado)"
"MDE"                                         → "Mesa de Entradas" (override explícito)
```

**Reglas de precedencia**:
1. **Overrides explícitos** (máxima precedencia): `MDE` → `Mesa de Entradas`
2. **Parseo de paréntesis**: Extrae facultad de `(Mesa de Entradas - FACULTAD)` o `(FACULTAD)`
3. **Preservación de MDE**: Nombres exactos como `Mesa de Entradas` se mantienen
4. **Identidad**: Si no hay regla, retorna sin cambios

**Por qué**: El análisis de circuitos necesita agrupar dependencias correctamente. Sin normalización, "Despacho General (FBCB)" y "Despacho General (Rectorado)" serían distintas, aunque son la misma dependencia en facultades diferentes.

**Garantía de idempotencia**: `normalize(normalize(x)) == normalize(x)`. Se puede aplicar músinormalizar una vez o cien veces, el resultado es el mismo.

---

## Flujo de Scraping

### 1. Búsqueda Inicial

```python
# main.py - ScraperOrchestrator.run()
first_page_result = self._fetch_listing_page(1)
```

- Usa `POST` a `buscar/` con parámetros de búsqueda
- Si hay filtros de fecha, usa advanced search
- Si no, usa header search

### 2. Procesamiento de Páginas

```python
# Para cada página:
listing = parse_listing_page(html, base_url)
stop = self._process_listing_expedientes(listing.expedientes, page_num)
```

**Lógica de early stop** (optimización):
```python
# main.py - _process_listing_expedientes()
all_before_date_from = True

for expediente in expedientes:
    if expediente.fecha_alta < date_from:
        continue  # Saltar este expediente
    else:
        all_before_date_from = False  # Hay al menos uno en rango

# Solo parar si TODOS están fuera de rango
if all_before_date_from:
    return True  # Parar scraping
```

**Por qué**: Los expedientes están ordenados por fecha (más recientes primero). Si en una página todos son anteriores a `date_from`, no tiene sentido seguir paginando hacia atrás.

### 3. Procesamiento de Cada Expediente

```python
# Para cada expediente:
movimientos = self._fetch_and_parse_movimientos(expediente)

# Normalizar dependencias
for mov in movimientos:
    mov.dependencia = normalize(mov.dependencia, self.normalizer_rules)

# Persistir en transacción única
self._persist_expediente(expediente, movimientos)
```

### 4. Persistencia

```python
# main.py - _persist_expediente()
with transaction() as conn:
    # Verificar duplicado
    existing = conn.execute(
        "SELECT id FROM expedientes WHERE numero = ?",
        (expediente.numero,)
    ).fetchone()
    
    if existing:
        self.stats.duplicate_expedientes += 1
        return  # Saltar duplicado
    
    # Insertar expediente
    cursor = conn.execute(
        "INSERT INTO expedientes (...) VALUES (...)",
        (...)
    )
    expediente_id = cursor.lastrowid
    
    # Insertar movimientos (invertir orden)
    for i, mov in enumerate(reversed(movimientos), start=1):
        conn.execute(
            "INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia) VALUES (?, ?, ?, ?)",
            (expediente_id, i, mov.fecha_recepcion, mov.dependencia)
        )
```

**Decisión clave**: `reversed(movimientos)` — SUME muestra movimientos del más reciente al más antiguo (orden inverso cronológico). Al invertir, `orden=1` es el más antiguo (primera recepción), lo cual es más intuitivo para análisis de circuitos.

**Constraint UNIQUE**: `expedientes.numero` previene duplicados. Si el mismo expediente aparece en múltiples búsquedas, se ignora silenciosamente.

---

## Decisiones de Diseño

### 1. Parsing Directo (No Selenium/Playwright)

**Decisión**: Usar BeautifulSoup + requests en lugar de un browser headless.

**Por qué**:
- SUME no requiere JavaScript para mostrar datos (solo para el dropdown de oficinas, que resolvemos con parámetros)
- Más rápido: ~0.5s por request vs ~2-5s con browser
- Menos recursos: no necesita Chrome/Firefox
- Más estable: no depende de versiones de navegador

### 2. Extracción de Datos del Listing (No del Detalle)

**Decisión**: Extraer número, concepto, descripción, fecha_alta del listing page, no del detail page.

**Por qué**: La página de detalle de SUME (2026) solo muestra la tabla de movimientos. Los datos básicos del expediente están en el listing.

### 3. Transacción por Expediente

**Decisión**: Cada expediente se persiste en su propia transacción.

**Por qué**:
- Si falla un expediente, los anteriores se mantienen
- Permite reanudar el scraping después de un error
- Evita transacciones demasiado largas que bloqueen la DB

### 4. Normalización Configurable (YAML)

**Decisión**: Reglas de normalización en archivo YAML, no en código.

**Por qué**:
- Fácil de modificar sin cambiar código
- Permite overrides explícitos para casos edge
- Versionable y auditable
- Separación de responsabilidades

### 5. Filtros de Fecha Post-Scrape

**Decisión**: Filtrar por fecha DURANTE el scraping (no después).

**Por qué**:
- Evita descargar expedientes innecesarios
- Reduce tiempo de ejecución significativamente
- Early stop cuando no hay más expedientes en rango

### 6. Inversión de Orden de Movimientos

**Decisión**: Invertir el orden de movimientos al persistir (`reversed(movimientos)`).

**Por qué**: SUME muestra el más reciente primero. Para análisis de circuitos, es más intuitivo que `orden=1` sea el primero (más antiguo).

---

## Errores Conocidos y Soluciones

### 1. "KeyError: 'concepto'" en Dashboard

**Problema**: El SQL de `data.py` no incluía `concepto` en el SELECT.

**Solución**: Agregar `concepto` a la query SQL:
```python
query = "SELECT numero, concepto, fecha_alta, palabras_clave, origenes FROM expedientes"
```

### 2. Fechas Fuera de Rango

**Problema**: SUME retorna expedientes de otros años al buscar por rango de fechas.

**Solución**: Limpieza post-scrape con DELETE:
```sql
DELETE FROM movimientos WHERE expediente_id IN (
    SELECT id FROM expedientes WHERE fecha_alta < '2025-01-01'
);
DELETE FROM expedientes WHERE fecha_alta < '2025-01-01';
```

### 3. Paginación con "...9104"

**Problema**: SUME no muestra todas las páginas, usa `...{total}`.

**Solución**: Parser detecta formato `...NNNN`:
```python
elif text.startswith("..."):
    total_from_ellipsis = int(text[3:])
```

### 4. oficina=5 Auto-Select

**Problema**: Sin `oficina=5`, la búsqueda retorna todos los expedientes de FBCB (4,200+ páginas).

**Solución**: Incluir `oficina=5` en parámetros de advanced search. Este valor es auto-seleccionado por JavaScript cuando `mesaEntrada=5`.

### 5. Duplicados entre Semestres

**Problema**: Al scrapear primer y segundo semestre por separado, algunos expedientes aparecen en ambos (creados en un semestre pero con movimientos en el otro).

**Solución**: Constraint UNIQUE en `expedientes.numero` + verificación de duplicado antes de insertar.

---

## Comandos de Uso

### Scraping Completo (2025)

```bash
# Primer semestre (enero-junio 2025)
python -m src.pipeline run --phase scraper \
  --date-from 2025-01-01 --date-to 2025-06-30

# Segundo semestre (julio-diciembre 2025)
python -m src.pipeline run --phase scraper \
  --date-from 2025-07-01 --date-to 2025-12-31
```

### Scraping Limitado (Testing)

```bash
# Solo primeras 5 páginas
python -m src.pipeline run --phase scraper --max-pages 5
```

### Scraping sin Filtros

```bash
# Todos los expedientes de FBCB
python -m src.pipeline run --phase scraper
```

### Pipeline Completo

```bash
# Inicializar DB + Scraping + Análisis + Reporte
python -m src.pipeline run --phase all
```

---

## Rendimiento

| Métrica | Valor |
|---------|-------|
| Tiempo promedio por request | ~0.5s |
| Tiempo promedio por expediente | ~1.5s (listing + detail) |
| Páginas por minuto | ~10-15 |
| Tiempo estimado dataset anual | ~3-4 horas |

**Optimizaciones aplicadas**:
- Early stop con filtros de fecha
- Connection pooling (requests.Session)
- Rate limiting para evitar 429
- Solo se extraen datos necesarios (no HTML completo)

---

## Extensibilidad

### Agregar Nuevo Campo

1. Actualizar `ExpedienteDict` en `parser.py`
2. Actualizar `parse_listing_page()` o `parse_detail_page()`
3. Actualizar schema en `database/schema.sql`
4. Actualizar `INSERT` en `_persist_expediente()`
5. Actualizar queries en `data.py` del dashboard

### Cambiar Filtros de Búsqueda

1. Actualizar `_get_advanced_search_params()` en `config.py`
2. Agregar nuevos parámetros al dict `params`
3. Documentar en esta guía

### Agregar Nueva Dependencia

1. Agregar regla en `config/normalization_rules.yaml`
2. Si es override explícito, agregar a `explicit_overrides`
3. Probar con `normalize()` en Python

---

## Troubleshooting

### "HTTP Error 429 Too Many Requests"

**Causa**: Demasiadas requests en poco tiempo.

**Solución**: Aumentar `delay_seconds` en config:
```python
config = ScraperConfig(delay_seconds=1.0)  # Default: 0.5
```

### "HTTP Error 420" (para búsqueda avanzada)

**Causa**: Faltan parámetros en la búsqueda avanzada.

**Solución**: Verificar que TODOS los parámetros estén presentes, especialmente `oficina=5`.

### "ParseError: unexpected end of tag"

**Causa**: HTML malformado de SUME.

**Solución**: BeautifulSoup es tolerante, pero si persiste, guardar HTML crudo y analizar:
```python
client.save_raw_html(content, "debug_page")
```

### "Database is locked"

**Causa**: Múltiples instancias del scraper corriendo.

**Solución**: Asegurar que solo una instancia acceda a la DB. SQLite no soporta escritura concurrente.

---

## Referencias

- [SUME FBCB-UNL](https://servicios.unl.edu.ar/expedientes/)
- [ISO 9001:2015 - Requisitos para sistemas de gestión de calidad](https://www.iso.org/standard/62085.html)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
