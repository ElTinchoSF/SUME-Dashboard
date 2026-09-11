# Guía de Asuntos - SUME Dashboard

## Descripción General

Los **Asuntos** son subcategorías dentro de cada concepto que permiten identificar el tipo específico de trámite o documento que contiene un expediente. Por ejemplo, dentro del concepto "Gestión Alumno", los asuntos incluyen "Certificado Analítico", "Historia Académica", "Materias Aprobadas", etc.

Esta funcionalidad habilita un filtrado en cascada: **Concepto → Asunto**, permitiendo análisis más granulares del tránsito administrativo.

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUME Dashboard                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Scraper    │───▶│  Análisis    │───▶│   Dashboard  │      │
│  │              │    │   Asuntos    │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   SQLite     │    │   Patrones   │    │   Filtros    │      │
│  │   Database   │◀──▶│   Regex      │    │   Cascada    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Proceso de Extracción

### 1. Patrones Regex por Concepto

Cada concepto tiene un conjunto de patrones regex que identifican sus asuntos en las descripciones de los expedientes.

**Archivo:** `src/analysis/asuntos.py`

```python
ASUNTO_PATTERNS = {
    "Gestión Alumno": [
        AsuntoPattern(
            asunto="Certificado Analítico",
            pattern=r"CERTIFICADO\s+ANAL[IÍ]TICO"
        ),
        AsuntoPattern(
            asunto="Historia Académica",
            pattern=r"HISTORIA\s+ACAD[EÉ]MICA"
        ),
        # ... más patrones
    ],
    # ... más conceptos
}
```

### 2. Extracción de Asuntos

El módulo `src/analysis/asuntos.py` contiene las siguientes funciones principales:

#### `extract_asunto(descripcion: str, concepto: str) -> Optional[str]`

Extrae el asunto de la descripción de un expediente usando patrones regex.

```python
# Ejemplo de uso
from src.analysis.asuntos import extract_asunto

asunto = extract_asunto(
    "Solicita CERTIFICADO ANALITICO de la carrera Bioquímica",
    "Gestión Alumno"
)
# Resultado: "Certificado Analítico"
```

#### `populate_asuntos_table() -> dict[str, int]`

Puebla las tablas `asuntos` y `expediente_asuntos` en la base de datos.

```python
from src.analysis.asuntos import populate_asuntos_table

counts = populate_asuntos_table()
# Resultado: {"Gestión Alumno": 13, "Gestión de Cargos Docentes": 9, ...}
```

### 3. Almacenamiento en Base de Datos

**Tablas:**

```sql
-- Tabla de asuntos (patrones disponibles)
CREATE TABLE asuntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto TEXT NOT NULL,
    asunto TEXT NOT NULL,
    patron_regex TEXT,
    UNIQUE(concepto, asunto)
);

-- Tabla de enlance expediente ↔ asunto
CREATE TABLE expediente_asuntos (
    expediente_id INTEGER NOT NULL,
    asunto_id INTEGER NOT NULL,
    PRIMARY KEY (expediente_id, asunto_id),
    FOREIGN KEY (expediente_id) REFERENCES expedientes(id),
    FOREIGN KEY (asunto_id) REFERENCES asuntos(id)
);
```

---

## Configuración de Asuntos

### Archivo de Propuesta YAML

**Archivo:** `config/asuntos_propuesta.yaml`

Este archivo define todos los asuntos disponibles por concepto y se utiliza como referencia para la validación.

```yaml
"Gestión Alumno":
  asuntos:
    - "Certificado Analítico"
    - "Historia Académica"
    - "Materias Aprobadas"
    - "Finalización de Carrera y Título en Trámite"
    - "Sanciones Disciplinarias"
    # ...

"Gestión de Cargos Docentes":
  asuntos:
    - "Solicitud de cargo Jefe de Trabajos Prácticos"
    - "Solicitud de cargo Ayudante de 1ra"
    - "Solicitud de cargo Profesor Titular"
    # ...
```

### Agregar Nuevo Asunto

Para agregar un nuevo asunto:

1. **Agregar al YAML:** Editar `config/asuntos_propuesta.yaml`
2. **Agregar patrón regex:** Editar `src/analysis/asuntos.py`
3. **Insertar en DB:** Ejecutar `populate_asuntos_table()` o inserción manual

```sql
-- Inserción manual en DB
INSERT INTO asuntos (concepto, asunto, patron_regex)
VALUES (
    'Gestión de Cargos Docentes',
    'Solicitud de cargo Profesor Titular',
    'PROFESOR\s+TITULAR'
);
```

---

## Uso en el Dashboard

### Filtros en Cascada

El dashboard implementa un sistema de filtros en cascada en el sidebar:

```
┌─────────────────────────────┐
│  📋 Conceptos               │  ← Paso 1: Seleccionar concepto
│  ┌─────────────────────┐   │
│  │ Gestión Alumno      │   │
│  └─────────────────────┘   │
├─────────────────────────────┤
│  📝 Asuntos                 │  ← Paso 2: Seleccionar asunto (se habilita)
│  ┌─────────────────────┐   │
│  │ Certificado Analítico│   │
│  └─────────────────────┘   │
└─────────────────────────────┘
```

### Flujo de Filtrado

1. **Sin filtro de asunto:**
   - Se muestran todos los expedientes del concepto seleccionado
   - Ejemplo: "Gestión Alumno" → 8,809 expedientes

2. **Con filtro de asunto:**
   - Se filtran expedientes por el asunto específico
   - Ejemplo: "Gestión Alumno" + "Certificado Analítico" → 3,286 expedientes

### Páginas que Soportan Filtrado por Asunto

| Página | Descripción | Soporte Asuntos |
|--------|-------------|-----------------|
| Resumen | KPIs generales | ✅ Parcial |
| Análisis por Concepto | Circuitos y estadísticas | ✅ Completo |
| Visualización de Circuitos | Diagramas Sankey | ✅ Completo |
| Análisis de Permanencia | Tiempos por dependencia | ✅ Completo |
| Ranking de Dependencias | Tráfico por dependencia | ✅ Parcial |

### Código de Ejemplo en Página

```python
from src.dashboard.data import FilterState, load_circuitos

def render_conceptos_page(filters: FilterState) -> None:
    # Los filtros incluyen asuntos automáticamente
    circuitos_df = load_circuitos("Gestión Alumno", filters)
    
    # Si filters.asuntos = ("Certificado Analítico",)
    # Solo se muestran circuitos de Certificado Analítico
```

---

## Base de Datos Actual

### Estadísticas (2025)

| Métrica | Valor |
|---------|-------|
| Total asuntos definidos | 101 |
| Total enlaces | 14,869 |
| Cobertura | 46.5% (14,869/31,956) |
| Conceptos con asuntos | 17 |

### Top 5 Asuntos por Volumen

| Concepto | Asunto | Expedientes |
|----------|--------|-------------|
| Gestión Alumno | Certificado Analítico | 3,286 |
| Gestión Alumno | Plan de estudios | 1,587 |
| Gestión Alumno | Finalización de Carrera | 1,173 |
| Gestión de Ingresos | Elevación de orden de trabajo | 460 |
| Gestión de Fondos | Solicitud de adelanto | 458 |

---

## Actualización Automática

### Al Ejecutar el Scraper

El scraper actualiza automáticamente los asuntos después de cada ejecución:

```python
# En src/scraper/main.py
def _update_asuntos(self) -> None:
    """Update asuntos for newly added expedientes."""
    from src.analysis.asuntos import populate_asuntos_table
    populate_asuntos_table()
```

### Manualmente

Para actualizar asuntos sin ejecutar el scraper:

```python
from src.analysis.asuntos import populate_asuntos_table

# Re-populate asuntos table
counts = populate_asuntos_table()
print(f"Actualizados: {sum(counts.values())} asuntos")
```

---

## Solución de Problemas

### Asuntos sin Coincidencias

Algunos asuntos definidos no tienen expedientes asociados. Esto es normal y puede indicar:

1. **Patrón regex no detecta la variación** → Actualizar patrón
2. **Asunto no existe en los datos** → Mantener para futuros expedientes
3. **Descripción con formato diferente** → Revisar y ajustar regex

### Baja Cobertura (46.5%)

La cobertura al 46.5% indica que:

- Más de la mitad de expedientes no matchean ningún patrón
- Algunos conceptos tienen asuntos muy genéricos
- Se pueden agregar más patrones para mejorar cobertura

### Rendimiento

Las consultas con filtro de asunto usan JOINs:

```sql
SELECT e.* FROM expedientes e
WHERE e.id IN (
    SELECT DISTINCT ea.expediente_id
    FROM expediente_asuntos ea
    JOIN asuntos a ON ea.asunto_id = a.id
    WHERE a.asunto IN (?, ?)
)
```

**Recomendación:** Mantener índices en `expediente_asuntos(expediente_id)` y `expediente_asuntos(asunto_id)`.

---

## Estructura de Archivos

```
src/
├── analysis/
│   └── asuntos.py              # Módulo de extracción de asuntos
├── dashboard/
│   ├── data.py                 # FilterState con campo asuntos
│   ├── components/
│   │   └── filters.py          # Widget de filtro de asuntos
│   └── pages/
│       ├── conceptos.py        # Soporte filtrado por asunto
│       └── circuitos.py        # Soporte filtrado por asunto
├── scraper/
│   └── main.py                 # Auto-update asuntos después de scraping
config/
└── asuntos_propuesta.yaml      # Propuesta de asuntos para validación
data/
└── sume.db                     # DB con tablas asuntos y expediente_asuntos
```

---

## Futuras Mejoras

1. **Mejorar cobertura:** Agregar más patrones regex para conceptos con baja detección
2. **Asuntos dinámicos:** Detectar nuevos asuntos automáticamente de descripciones
3. **Jerarquía de asuntos:** Soportar sub-asuntos (ej: Certificado Analítico → Analítico Simplificado)
4. **Exportar asuntos:** Generar reporte de asuntos por concepto en CSV/PDF
5. **Dashboard de asuntos:** Página dedicada para análisis de asuntos

---

## Referencias

- **Archivo de patrones:** `src/analysis/asuntos.py`
- **Configuración YAML:** `config/asuntos_propuesta.yaml`
- **Guía del scraper:** `Docs/SCRAPER-GUIDE.md`
- **Esquema de DB:** `src/database/schema.sql`
