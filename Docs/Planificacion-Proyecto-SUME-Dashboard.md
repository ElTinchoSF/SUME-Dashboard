# PROYECTO DE INVESTIGACIÓN Y DESARROLLO

## Sistema de Análisis de Circuitos Administrativos para la Certificación ISO 9001 de la Mesa de Entradas de la Facultad de Bioquímica y Ciencias Biológicas de la Universidad Nacional del Litoral

---

**Autor:** Martín Galanti  
**Institución:** Universidad Nacional del Litoral  
**Facultad:** Facultad de Bioquímica y Ciencias Biológicas (FBCB)  
**Unidad Académica:** Mesa de Entradas - FBCB  
**Fecha de presentación:** Septiembre 2026  
**Duración estimada:** 12 meses  

---

## ÍNDICE

1. [Introducción](#1-introducción)
2. [Planteamiento del Problema](#2-plantamiento-del-problema)
3. [Justificación](#3-justificación)
4. [Objetivos](#4-objetivos)
5. [Marco Teórico](#5-marco-teórico)
6. [Metodología](#6-metodología)
7. [Arquitectura Técnica del Sistema](#7-arquitectura-técnica-del-sistema)
8. [Cronograma](#8-cronograma)
9. [Presupuesto y Financiamiento](#9-presupuesto-y-financiamiento)
10. [Bibliografía](#10-bibliografía)
11. [Anexos](#11-anexos)

---

## 1. INTRODUCCIÓN

El presente proyecto propone el desarrollo de un **Sistema de Análisis de Circuitos Administrativos** (en adelante, "SUME Dashboard") destinado a la Mesa de Entradas de la Facultad de Bioquímica y Ciencias Biológicas (FBCB) de la Universidad Nacional del Litoral (UNL). El sistema tiene como objetivo fundamental obtener datos objetivos y cuantificables que sirvan como insumo para el proceso de **certificación ISO 9001** de la mencionada dependencia.

La certificación ISO 9001 es un estándar internacional de gestión de calidad que exige, entre otros requisitos, la documentación y análisis de los procesos organizacionales. En el ámbito de una Mesa de Entradas universitaria, esto implica comprender y documentar los **circuitos administrativos** que recorren los expedientes según su tipo de asunto, identificando los patrones reales de flujo y estableciendo las bases para la comparación con los circuitos diseñados o esperados.

El proyecto se enmarca en la línea de **Investigación y Desarrollo Aplicado**, combinando técnicas de minería de datos web (web scraping), análisis de procesos administrativos y desarrollo de herramientas de visualización (dashboard) para la toma de decisiones gerenciales.

---

## 2. PLANTEAMIENTO DEL PROBLEMA

### 2.1 Contexto Institucional

La Mesa de Entradas (MDE) de la FBCB es la dependencia encargada de recibir, registrar y derivar la totalidad de la documentación administrativa que ingresa a la facultad. Según datos preliminares, la MDE procesa aproximadamente **4.000 expedientes anuales**, los cuales recorren diversos circuitos administrativos según su naturaleza y el tipo de gestión que requieren.

El sistema actual de seguimiento de expedientes, **SUME (Sistema Único de Mesa de Entradas)**, disponible en `servicios.unl.edu.ar/expedientes/`, registra el historial de movimientos (pases) de cada expediente a través de las distintas dependencias de la facultad. Este sistema constituye una fuente de datos valiosa pero subutilizada para el análisis de procesos.

### 2.2 Problema Central

**¿Cuáles son los circuitos administrativos reales que recorren los expedientes de la Mesa de Entradas de la FBCB según su tipo de asunto, y cómo se distribuyen estadísticamente dichos circuitos?**

### 2.3 Problemas Específicos

1. **Ausencia de datos objetivos:** No se cuenta con herramientas que permitan visualizar y analizar los patrones de flujo reales de los expedientes a través de las dependencias.

2. **Desconocimiento de circuitos frecuentes:** Se desconoce cuál es el circuito más frecuente para cada tipo de asunto, lo que dificulta la estandarización de procesos.

3. **Falta de documentación para ISO 9001:** La certificación ISO 9001 requiere evidencia documentada de los procesos, la cual actualmente no está disponible en formato analítico.

4. **Limitaciones del sistema SUME:** Aunque SUME registra los movimientos, no ofrece herramientas de análisis, visualización ni reporte que permitan a los responsables de la MDE tomar decisiones basadas en datos.

### 2.4 Preguntas de Investigación

- ¿Cuáles son los tipos de asunto (conceptos) más frecuentes en la MDE de la FBCB?
- ¿Cuáles son los circuitos administrativos más comunes para cada tipo de asunto?
- ¿Cuántos pasos (movimientos) tiene en promedio cada tipo de expediente?
- ¿Cuáles son las dependencias que mayor tráfico de expedientes procesan?
- ¿Cuál es el tiempo promedio de permanencia de un expediente en cada dependencia?
- ¿Existen circuitos atípicos o excepcionales que se desvían del patrón predominante?

---

## 3. JUSTIFICACIÓN

### 3.1 Pertinencia Institucional

La certificación ISO 9001 representa un compromiso institucional de la FBCB con la calidad y la mejora continua. Para alcanzar dicha certificación, es imperativo contar con datos objetivos que permitan:

- Documentar los procesos reales (no los teóricos)
- Identificar desviaciones entre el proceso diseñado y el ejecutado
- Establecer líneas base para indicadores de desempeño
- Fundamentar acciones de mejora con evidencia cuantitativa

### 3.2 Relevancia Metodológica

El proyecto propone una metodología innovadora que combina:

- **Web scraping** para la obtención automatizada de datos del sistema SUME
- **Minería de procesos** para el descubrimiento de circuitos administrativos
- **Visualización de datos** para la comunicación de resultados a diferentes niveles gerenciales

### 3.3 Impacto Esperado

- **Directo:** Herramienta operativa para la MDE de la FBCB
- **Indirecto:** Metodología replicable para otras facultades de la UNL
- **Estratégico:** Insumo para la certificación ISO 9001 de la dependencia

### 3.4 Alineación con Objetivos Institucionales

Este proyecto se alinea con los objetivos estratégicos de la UNL en materia de:
- Gestión de calidad y mejora continua
- Modernización de procesos administrativos
- Toma de decisiones basada en datos
- Eficiencia operativa en unidades académicas

---

## 4. OBJETIVOS

### 4.1 Objetivo General

Diseñar e implementar un sistema de análisis de circuitos administrativos que permita obtener, almacenar, analizar y visualizar los patrones de flujo de los expedientes de la Mesa de Entradas de la FBCB, como insumo para el proceso de certificación ISO 9001.

### 4.2 Objetivos Específicos

1. **Desarrollar un módulo de obtención de datos** mediante web scraping del sistema SUME que permita la extracción automatizada de información de expedientes y sus movimientos, con capacidad de ejecución periódica y configurable.

2. **Diseñar y implementar una base de datos** que almacene de forma estructurada la información de expedientes, conceptos, dependencias y movimientos, permitiendo consultas analíticas eficientes.

3. **Implementar un sistema de normalización de dependencias** que estandarice los nombres de las dependencias destino para permitir análisis comparativos consistentes.

4. **Desarrollar un dashboard interactivo** que visualice los circuitos administrativos más frecuentes, distribuciones estadísticas, tiempos de permanencia y otros indicadores relevantes para la toma de decisiones.

5. **Generar reportes analíticos** que documenten los circuitos reales de cada tipo de asunto como evidencia para el proceso de certificación ISO 9001.

6. **Validar el sistema** con datos reales del primer semestre 2025 antes de proceder a la extracción completa del período anual.

---

## 5. MARCO TEÓRICO

### 5.1 Gestión de Calidad e ISO 9001

La norma ISO 9001:2015 establece los requisitos para un sistema de gestión de calidad que puede ser utilizado por cualquier organización, independientemente de su tamaño o sector. Entre sus principios fundamentales se encuentran:

- **Enfoque al proceso:** Las actividades se gestionan como procesos interrelacionados que funcionan como un sistema coherente.
- **Mejora continua:** Las organizaciones deben evaluar regularmente el desempeño de sus procesos y implementar mejoras.
- **Toma de decisiones basada en evidencia:** Las decisiones se basan en el análisis y evaluación de datos e información.

Para la certificación ISO 9001, es requisito documentar los procesos organizacionales, incluyendo su interacción, indicadores de desempeño y evidencia de efectividad.

### 5.2 Minería de Procesos (Process Mining)

La minería de procesos es una disciplina que combina el análisis de procesos de negocios con la minería de datos. Su objetivo principal es descubrir, monitorear y mejorar procesos reales mediante el análisis de registros de eventos (event logs).

En el contexto de este proyecto, los "eventos" son los movimientos (pases) de los expedientes a través de las dependencias, y el "proceso" es el circuito administrativo que recorre cada expediente desde su creación hasta su archivado.

**Conceptos clave aplicados:**
- **Circuito administrativo:** Secuencia de dependencias por las que pasa un expediente
- **Frecuencia de circuito:** Número de expedientes que recorren una misma secuencia de dependencias
- **Caso:** Un expediente individual con su secuencia de movimientos
- **Actividad:** Cada paso o movimiento del expediente a una dependencia

### 5.3 Web Scraping

El web scraping es una técnica de obtención de datos que consiste en extraer información de páginas web de forma automatizada. En este proyecto se utiliza para obtener datos del sistema SUME, que es una aplicación web pública sin requisitos de autenticación.

**Consideraciones éticas y técnicas:**
- El sistema SUME es de acceso público
- No se requiere autenticación para la consulta
- Se respeta la tasa de acceso del servidor (rate limiting)
- Los datos obtenidos son de naturaleza administrativa y no contienen información personal sensible

### 5.4 Visualización de Datos

La visualización de datos es la representación gráfica de información y datos. Para este proyecto se utilizan técnicas de visualización interactiva que permiten:

- Explorar distribuciones de expedientes por concepto
- Visualizar circuitos administrativos como diagramas de flujo
- Analizar tendencias temporales
- Comparar métricas entre períodos

---

## 6. METODOLOGÍA

### 6.1 Enfoque Metodológico

El proyecto adopta un enfoque **cuantitativo-aplicado**, basado en la obtención y análisis de datos reales del sistema SUME. La metodología se estructura en las siguientes fases:

### 6.2 Fases del Proyecto

#### Fase 1: Obtención de Datos (Web Scraping)
- **Actividad:** Desarrollo de scraper para el sistema SUME
- **Fuente:** `servicios.unl.edu.ar/expedientes/`
- **Período:** Expedientes con fecha de alta desde 01/01/2025 hasta 31/12/2025
- **Estrategia:** Ejecución en dos corridas (primer semestre, luego segundo semestre)
- **Tecnologías:** Python, requests, BeautifulSoup
- **Validación:** Verificación de integridad de datos entre corridas

#### Fase 2: Almacenamiento y Normalización
- **Actividad:** Diseño e implementación de base de datos
- **Tecnología:** SQLite
- **Procesos:**
  - Almacenamiento de expedientes con metadatos completos
  - Normalización de nombres de dependencias
  - Inyección de dependencia inicial (MDE de origen)
  - Deduplicación y consistencia de datos

#### Fase 3: Análisis de Circuitos
- **Actividad:** Minería de procesos sobre datos almacenados
- **Análisis:**
  - Frecuencia de circuitos por concepto
  - Circuito más frecuente (moda) por concepto
  - Distribución de pasos por expediente
  - Tiempos de permanencia en cada dependencia
  - Identificación de circuitos atípicos

#### Fase 4: Desarrollo del Dashboard
- **Actividad:** Implementación de interfaz de visualización
- **Tecnología:** Python + Streamlit
- **Funcionalidades:**
  - Vista general con métricas clave
  - Análisis por concepto/asunto
  - Visualización de circuitos más frecuentes
  - Filtros por período, concepto y dependencia
  - Exportación de reportes

#### Fase 5: Validación y Documentación
- **Actividad:** Verificación con datos reales y documentación para ISO 9001
- **Entregables:**
  - Reporte de circuitos reales por tipo de asunto
  - Documentación de evidencia para certificación
  - Manual de usuario del dashboard

### 6.3 Estrategia de Scraping Detallada

#### 6.3.1 Flujo de Obtención de Datos

```
1. Búsqueda en SUME
   └─ Campo "Número de expediente": "FBCB"
   └─ Filtro "Fecha de Alta": desde 01/01/2025 hasta 31/12/2025
   
2. Paginación de Resultados
   └─ Extraer links de detalle de cada fila de resultados
   └─ Navegar por todas las páginas de resultados
   
3. Extracción de Detalle
   └─ Para cada expediente, acceder a su página de detalle
   └─ Extraer: Número, Concepto, Descripción, Fecha Alta, Estado,
      Palabras Clave, Orígenes
   
4. Extracción de Movimientos
   └─ De la tabla "Pases del Expediente":
      └─ Fecha de Recepción
      └─ Dependencia Destino (normalizada)
   
5. Inyección de Dependencia Inicial
   └─ Agregar registro 0: MDE de origen del expediente
   └─ Fecha: Fecha de Alta del expediente
   └─ Dependencia: "Mesa de Entradas - {facultad}"
```

#### 6.3.2 Normalización de Dependencias

**Regla de normalización:**
- Para dependencias con formato `{nombre} (Mesa de Entradas - {facultad})`:
  - Convertir a `{nombre} ({facultad})`
  - Ejemplo: `"Alumnado (Mesa de Entradas - FBCB)"` → `"Alumnado (FBCB)"`

- Para Mesas de Entradas (sin paréntesis):
  - Mantener sin cambios
  - Ejemplo: `"Mesa de Entradas - FBCB"` → `"Mesa de Entradas - FBCB"`

- **Regla general:** Si hay múltiples paréntesis, contraer siempre el último

#### 6.3.3 Parámetros Técnicos del Scraping

| Parámetro | Valor |
|-----------|-------|
| URL base | `servicios.unl.edu.ar/expedientes/` |
| Método HTTP | GET/POST (según formulación del sitio) |
| Delay entre requests | 0.5 segundos (configurable) |
| Timeout por request | 30 segundos |
| Reintentos en error | 3 con backoff exponencial |
| User-Agent | Identificación del proyecto |

#### 6.3.4 Estrategia de Ejecución

**Corrida 1:** Primer semestre (01/01/2025 - 30/06/2025)
- Ejecución y validación de integridad
- Verificación de normalización de dependencias
- Corrección de posibles problemas

**Corrida 2:** Segundo semestre (01/07/2025 - 31/12/2025)
- Ejecución después de validar corrida 1
- Consolidación de datos en base de datos

---

## 7. ARQUITECTURA TÉCNICA DEL SISTEMA

### 7.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────┐
│                    SUME Dashboard                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │   Scraper    │    │  Normalizer  │    │  Storage  │  │
│  │   (Python)   │───▶│   (Python)   │───▶│  (SQLite) │  │
│  └──────────────┘    └──────────────┘    └─────┬─────┘  │
│         │                                       │       │
│         │                                       ▼       │
│         │                               ┌───────────┐   │
│         │                               │  Analyzer │   │
│         │                               │  (Python) │   │
│         │                               └─────┬─────┘   │
│         │                                     │         │
│         │                                     ▼         │
│         │                             ┌──────────────┐  │
│         │                             │   Dashboard  │  │
│         │                             │ (Streamlit)  │  │
│         │                             └──────────────┘  │
│         │                                               │
│         │                                               │
│  ┌──────┴───────┐                                       │
│  │    SUME      │                                       │
│  │   (UNL)      │                                       │
│  └──────────────┘                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Estructura de Directorios del Proyecto

```
sume-dashboard/
├── Docs/
│   └── Planificacion-Proyecto-SUME-Dashboard.md
├── src/
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuración del scraper
│   │   ├── client.py          # Cliente HTTP para SUME
│   │   ├── parser.py          # Parser de páginas HTML
│   │   ├── normalizer.py      # Normalización de dependencias
│   │   └── main.py            # Punto de entrada del scraper
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py          # Esquema de la base de datos
│   │   ├── models.py          # Modelos de datos
│   │   └── connection.py      # Conexión SQLite
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── circuits.py        # Análisis de circuitos
│   │   ├── statistics.py      # Estadísticas descriptivas
│   │   └── reports.py         # Generación de reportes
│   └── dashboard/
│       ├── __init__.py
│       ├── app.py             # Aplicación Streamlit
│       ├── pages/
│       │   ├── overview.py    # Vista general
│       │   ├── concepts.py    # Análisis por concepto
│       │   ├── circuits.py    # Visualización de circuitos
│       │   └── reports.py     # Generación de reportes
│       └── components/
│           ├── charts.py      # Gráficos interactivos
│           └── filters.py     # Filtros de búsqueda
├── data/
│   ├── raw/                   # Datos crudos del scraper
│   ├── processed/             # Datos procesados
│   └── sume.db               # Base de datos SQLite
├── tests/
│   ├── test_scraper.py
│   ├── test_normalizer.py
│   └── test_analysis.py
├── requirements.txt
├── README.md
└── .gitignore
```

### 7.3 Modelo de Datos (SQLite)

#### Tabla: expedientes
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER PK | Identificador único |
| numero | TEXT UNIQUE | Número de expediente (ej: FBCB-1294475-26) |
| concepto | TEXT | Concepto/SAM de SUME |
| descripcion | TEXT | Descripción del asunto |
| fecha_alta | DATE | Fecha de creación |
| estado | TEXT | Estado actual (Archivado, Activo, etc.) |
| palabras_clave | TEXT | Palabras clave separadas por coma |
| origenes | TEXT | Orígenes del expediente |
| fecha_extraccion | DATETIME | Fecha y hora de extracción |

#### Tabla: movimientos
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER PK | Identificador único |
| expediente_id | INTEGER FK | Referencia a expediente |
| orden | INTEGER | Orden del movimiento (0 = MDE inicial) |
| fecha_recepcion | DATE | Fecha de recepción |
| dependencia | TEXT | Dependencia destino (normalizada) |

#### Tabla: dependencias
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER PK | Identificador único |
| nombre | TEXT UNIQUE | Nombre normalizado |
| nombre_original | TEXT | Nombre original del SUME |
| total_expedientes | INTEGER | Conteo de expedientes que la visitaron |

#### Tabla: circuitos
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER PK | Identificador único |
| circuito | TEXT | Secuencia de dependencias (JSON) |
| concepto | TEXT | Concepto del expediente |
| frecuencia | INTEGER | Cantidad de expedientes con este circuito |
| es_mas_frecuente | BOOLEAN | Si es el circuito más frecuente del concepto |

### 7.4 Dependencias del Sistema

```
# requirements.txt
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
pandas>=2.0.0
streamlit>=1.28.0
plotly>=5.18.0
sqlite3-api>=2.0.0
```

---

## 8. CRONOGRAMA

### 8.1 Cronograma General (12 meses)

| Fase | Actividad | Duración | Inicio | Fin |
|------|-----------|----------|--------|-----|
| **1** | **Planificación y Diseño** | **2 meses** | Mes 1 | Mes 2 |
| 1.1 | Análisis de requisitos y documentación | 2 semanas | Mes 1 Sem 1 | Mes 1 Sem 2 |
| 1.2 | Diseño de base de datos | 2 semanas | Mes 1 Sem 3 | Mes 1 Sem 4 |
| 1.3 | Diseño de arquitectura del scraper | 2 semanas | Mes 2 Sem 1 | Mes 2 Sem 2 |
| 1.4 | Diseño de interfaz del dashboard | 2 semanas | Mes 2 Sem 3 | Mes 2 Sem 4 |
| **2** | **Desarrollo del Scraper** | **2 meses** | Mes 3 | Mes 4 |
| 2.1 | Desarrollo del módulo HTTP | 2 semanas | Mes 3 Sem 1 | Mes 3 Sem 2 |
| 2.2 | Desarrollo del parser HTML | 2 semanas | Mes 3 Sem 3 | Mes 3 Sem 4 |
| 2.3 | Desarrollo del normalizador | 2 semanas | Mes 4 Sem 1 | Mes 4 Sem 2 |
| 2.4 | Integración y pruebas unitarias | 2 semanas | Mes 4 Sem 3 | Mes 4 Sem 4 |
| **3** | **Extracción de Datos - 1er Semestre** | **1 mes** | Mes 5 | Mes 5 |
| 3.1 | Ejecución del scraping (01/01/2025 - 30/06/2025) | 2 semanas | Mes 5 Sem 1 | Mes 5 Sem 2 |
| 3.2 | Validación de integridad de datos | 1 semana | Mes 5 Sem 3 | Mes 5 Sem 3 |
| 3.3 | Corrección de anomalías | 1 semana | Mes 5 Sem 4 | Mes 5 Sem 4 |
| **4** | **Almacenamiento y Normalización** | **1 mes** | Mes 6 | Mes 6 |
| 4.1 | Implementación de esquema SQLite | 1 semana | Mes 6 Sem 1 | Mes 6 Sem 1 |
| 4.2 | Carga y normalización de datos | 2 semanas | Mes 6 Sem 2 | Mes 6 Sem 3 |
| 4.3 | Verificación de consistencia | 1 semana | Mes 6 Sem 4 | Mes 6 Sem 4 |
| **5** | **Extracción de Datos - 2do Semestre** | **1 mes** | Mes 7 | Mes 7 |
| 5.1 | Ejecución del scraping (01/07/2025 - 31/12/2025) | 2 semanas | Mes 7 Sem 1 | Mes 7 Sem 2 |
| 5.2 | Consolidación de datos anuales | 2 semanas | Mes 7 Sem 3 | Mes 7 Sem 4 |
| **6** | **Análisis de Circuitos** | **2 meses** | Mes 8 | Mes 9 |
| 6.1 | Análisis exploratorio de datos | 2 semanas | Mes 8 Sem 1 | Mes 8 Sem 2 |
| 6.2 | Cálculo de frecuencias por concepto | 2 semanas | Mes 8 Sem 3 | Mes 8 Sem 4 |
| 6.3 | Identificación de circuitos más frecuentes | 3 semanas | Mes 9 Sem 1 | Mes 9 Sem 3 |
| 6.4 | Análisis de tiempos y dependencias | 1 semana | Mes 9 Sem 4 | Mes 9 Sem 4 |
| **7** | **Desarrollo del Dashboard** | **2 meses** | Mes 10 | Mes 11 |
| 7.1 | Desarrollo de módulo de métricas generales | 2 semanas | Mes 10 Sem 1 | Mes 10 Sem 2 |
| 7.2 | Desarrollo de módulo de análisis por concepto | 2 semanas | Mes 10 Sem 3 | Mes 10 Sem 4 |
| 7.3 | Desarrollo de módulo de visualización de circuitos | 2 semanas | Mes 11 Sem 1 | Mes 11 Sem 2 |
| 7.4 | Desarrollo de filtros y exportación | 2 semanas | Mes 11 Sem 3 | Mes 11 Sem 4 |
| **8** | **Pruebas, Documentación y Entrega** | **1 mes** | Mes 12 | Mes 12 |
| 8.1 | Pruebas de integración con usuarios | 1 semana | Mes 12 Sem 1 | Mes 12 Sem 1 |
| 8.2 | Corrección de observaciones | 1 semana | Mes 12 Sem 2 | Mes 12 Sem 2 |
| 8.3 | Documentación técnica y manual de usuario | 1 semana | Mes 12 Sem 3 | Mes 12 Sem 3 |
| 8.4 | Entrega final y capacitación | 1 semana | Mes 12 Sem 4 | Mes 12 Sem 4 |

### 8.2 Diagrama de Gantt Simplificado

```
Mes:    1    2    3    4    5    6    7    8    9   10   11   12
        ├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Fase 1  ████████████
Fase 2                 ████████████
Fase 3                              ██████
Fase 4                                   ██████
Fase 5                                        ██████
Fase 6                                             ████████████
Fase 7                                                          ████████████
Fase 8                                                                   ██████
```

### 8.3 Hito Clave

| Hito | Fecha Estimada | Entregable |
|------|----------------|------------|
| H1: Diseño aprobado | Final Mes 2 | Documento de diseño completo |
| H2: Scraper funcional | Final Mes 4 | Código probado con datos de prueba |
| H3: 1er semestre extraído | Final Mes 5 | Base de datos parcial validada |
| H4: Datos anuales consolidados | Final Mes 7 | Base de datos completa de 2025 |
| H5: Análisis completado | Final Mes 9 | Reporte de circuitos por concepto |
| H6: Dashboard funcional | Final Mes 11 | Aplicación desplegada |
| H7: Entrega final | Final Mes 12 | Sistema completo documentado |

**Duración total estimada:** 12 meses

---

## 9. PRESUPUESTO Y FINANCIAMIENTO

### 9.1 Recursos Humanos
| Rol | Dedicación | Costo Mensual | Duración | Total |
|-----|------------|---------------|----------|-------|
| Investigador principal | 20 horas/semana | - | 12 meses | Sin costo (personal propio) |

### 9.2 Recursos Materiales
| Elemento | Costo |
|----------|-------|
| Infraestructura computacional | Sin costo (equipamiento existente) |
| Software | Sin costo (herramientas open source) |
| Servicio de hosting (opcional) | $0 - $50 USD/mes |

### 9.3 Presupuesto Total Estimado
**Total:** $0 - $600 USD (dependiendo de decisiones de hosting para 12 meses)

**Nota:** El proyecto se desarrolla íntegramente con herramientas de código abierto y sobre equipamiento existente, por lo que el costo directo es mínimo.

---

## 10. BIBLIOGRAFÍA

1. International Organization for Standardization. (2015). *ISO 9001:2015 - Quality management systems - Requirements*. ISO.

2. Van der Aalst, W. (2016). *Process Mining: Data Science in Action*. Springer.

3. Foundation for Critical Thinking. (2020). *The Thinker's Guide to Analytic Thinking*. .

4. Consejo Nacional de Investigaciones Científicas y Técnicas. (2023). *Guía para la elaboración de proyectos de investigación*. CONICET.

5. Universidad Nacional del Litoral. (2024). *Pautas generales CAI+D 2024*. Secretaría de Ciencia, Arte y Tecnología.

6. McKinney, W. (2022). *Python for Data Analysis*. O'Reilly Media.

7. Streamlit. (2024). *Streamlit Documentation*. https://docs.streamlit.io

8. W3C. (2024). *Web Scraping Ethics and Best Practices*. .

---

## 11. ANEXOS

### Anexo A: Glosario de Términos

| Término | Definición |
|---------|------------|
| **Expediente** | Documento administrativo registrado en el sistema SUME, identificado por un número único |
| **Concepto (SAM)** | Clasificación del tipo de asunto administrativo |
| **Movimiento (Pase)** | Transferencia de un expediente de una dependencia a otra |
| **Circuito administrativo** | Secuencia de dependencias por las que pasa un expediente |
| **Dependencia** | Área o sector de la facultad por donde circulan los expedientes |
| **MDE** | Mesa de Entradas |
| **FBCB** | Facultad de Bioquímica y Ciencias Biológicas |
| **UNL** | Universidad Nacional del Litoral |
| **SUME** | Sistema Único de Mesa de Entradas |

### Anexo B: Estructura del Expediente en SUME

**URL de detalle:** `servicios.unl.edu.ar/expedientes/expediente/{facultad}-{número}-{año}`

**Campos del resumen:**
- Número
- Iniciado por
- Concepto
- Descripción
- Fecha de alta
- Estado
- Palabras claves
- Orígenes

**Tabla de movimientos (Pases del Expediente):**
- Fecha de envío (no utilizada)
- Fecha de recepción (utilizada como fecha del movimiento)
- Dependencia destino

### Anexo C: Listado de Conceptos de SUME

| Concepto | Descripción |
|----------|-------------|
| Accidentes y siniestros | Gestión de incidentes y accidentes |
| Actas de exámenes y de regularización | Documentación de actas académicas |
| Adhesiones, Homenajes, Declaraciones y Acontecimientos | Actos institucionales |
| Auditoría | Procesos de auditoría |
| Denuncia y Sumario | Expedientes disciplinarios |
| Ejecución obra publica | Obras y mantenimiento |
| Elecciones | Procesos electorales |
| Gestión Alumno | Trámites de alumnos |
| Gestión de Becas | Programas de becas |
| Gestión de Bienes Patrimoniales | Administración de bienes |
| Gestión de Cargos Docentes | Designación de docentes |
| Gestión de Compras y Contrataciones | Adquisiciones |
| Gestión de Convenios y Acuerdos | Convenios interinstitucionales |
| Gestión de Diplomas | Emisión de diplomas |
| Gestión de Fondos con cargo a rendición | Administración financiera |

### Anexo D: Ejemplo de Circuito Administrativo

**Expediente:** FBCB-1294475-26
**Concepto:** Gestión Alumno
**Descripción:** Solicita extensión de regularidad de asignaturas

**Circuito real (de más antiguo a más reciente):**

| Orden | Fecha | Dependencia |
|-------|-------|-------------|
| 0 | 30/06/2026 | Mesa de Entradas - FBCB |
| 1 | 30/06/2026 | Despacho General (FBCB) |
| 2 | 01/07/2026 | Alumnado (FBCB) |
| 3 | 01/07/2026 | Coordinación de Licenciatura en T.O (FBCB) |
| 4 | 06/07/2026 | Dirección Escuela Superior de Sanidad (FBCB) |
| 5 | 07/07/2026 | Secretaría Académica (FBCB) |
| 6 | 08/07/2026 | Despacho General (FBCB) |
| 7 | 23/07/2026 | Alumnado (FBCB) |
| 8 | 28/07/2026 | Mesa de Entradas - FBCB |
| 9 | 28/07/2026 | Archivo Digital (Mesa de Entradas - FBCB) |

**Circuito codificado:** `MDE-FBCB → Despacho General → Alumnado → Coordinación T.O → Dirección ESS → Sec. Académica → Despacho General → Alumnado → MDE-FBCB → Archivo Digital`

---

## DOCUMENTO DE CONTROL

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 1.0 | Septiembre 2026 | Martín Galanti | Versión inicial del documento de planificación |
| 1.1 | Septiembre 2026 | Martín Galanti | Adecuación del cronograma a 12 meses |

---

*Este documento constituye la planificación formal del proyecto de I+D para el Sistema de Análisis de Circuitos Administrativos de la Mesa de Entradas de la FBCB-UNL.*
