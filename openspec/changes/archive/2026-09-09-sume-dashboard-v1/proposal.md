# Proposal: SUME Dashboard v1 - Sistema de Análisis de Circuitos Administrativos

## Intent

Desarrollar un sistema completo (scraper + storage + análisis + dashboard) que permita a la Mesa de Entradas de la FBCB-UNL obtener, analizar y visualizar los circuitos administrativos reales de los expedientes como evidencia documental para la certificación ISO 9001. El sistema automatiza la extracción de datos del sistema SUME público, normaliza dependencias, descubre circuitos frecuentes por concepto y presenta resultados en un dashboard interactivo.

## Scope

### In Scope
- **Scraper SUME**: Extracción automatizada de ~4,000 expedientes/año (2025) desde `servicios.unl.edu.ar/expedientes/`
- **Normalizador de dependencias**: Estandarización de nombres (ej: "Alumnado (Mesa de Entradas - FBCB)" → "Alumnado (FBCB)")
- **Base de datos SQLite**: Esquema con 4 tablas (expedientes, movimientos, dependencias, circuitos)
- **Motor de análisis**: Minería de procesos - frecuencia de circuitos por concepto, circuitos modales, tiempos de permanencia, detección de atípicos
- **Dashboard Streamlit**: 4 páginas (Overview, Conceptos, Circuitos, Reportes) con filtros y exportación
- **Reportes ISO 9001**: Documentación de circuitos reales por tipo de asunto como evidencia

### Out of Scope
- Autenticación/autorización en SUME (sistema público sin auth)
- Scraping de años distintos a 2025 (extensible pero no en v1)
- Despliegue en producción/hosting (entrega local + documentación)
- Integración con otros sistemas UNL (SUME es la única fuente)
- Análisis predictivo o ML avanzado (solo descriptivo en v1)
- UI multi-idioma (solo español)

## Capabilities

### New Capabilities
- `sume-scraper`: Extracción robusta con rate limiting, reintentos y validación de integridad
- `dependency-normalizer`: Normalización determinística de nombres de dependencias SUME
- `circuit-analyzer`: Descubrimiento de circuitos administrativos frecuentes por concepto (process mining)
- `sume-dashboard`: Dashboard interactivo Streamlit con visualizaciones Plotly
- `iso9001-reporter`: Generación de reportes de evidencia para certificación

### Modified Capabilities
- None (greenfield project)

## Approach

Arquitectura modular en Python con 5 componentes desacoplados comunicados por SQLite:
1. **Scraper** (`src/scraper/`) → cliente HTTP + parser HTML + normalizador → escribe en `data/sume.db`
2. **Database** (`src/database/`) → esquema fijo, migraciones versionadas, conexión singleton
3. **Analysis** (`src/analysis/`) → consultas SQL + pandas → computa circuitos, frecuencias, métricas
4. **Dashboard** (`src/dashboard/`) → Streamlit multipágina, componentes reutilizables, filtros globales
5. **Tests** (`tests/`) → unitarios por módulo + integración end-to-end con datos sintéticos

Estrategia de scraping en 2 corridas validadas (sem1 → validar → sem2) para mitigar riesgos de calidad de datos.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/scraper/` | New | Cliente HTTP, parser, normalizador, orquestador principal |
| `src/database/` | New | Esquema SQLite, modelos, conexión, migraciones |
| `src/analysis/` | New | Circuitos, estadísticas, reportes analíticos |
| `src/dashboard/` | New | App Streamlit, 4 páginas, gráficos, filtros, exportación |
| `data/` | New | Directorio con raw/, processed/, sume.db |
| `tests/` | New | Suite completa (scraper, normalizer, analysis, dashboard) |
| `requirements.txt` | New | 7 dependencias core (requests, bs4, pandas, streamlit, plotly, lxml) |
| `README.md` | New | Documentación de uso, arquitectura, comandos |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cambios en HTML de SUME rompen parser | Medium | Selectores CSS robustos, tests de regresión con snapshots HTML, logging detallado |
| Rate limiting / bloqueo IP por UNL | Low | Delay 0.5s configurable, User-Agent identificado, backoff exponencial 3 reintentos |
| Datos inconsistentes en SUME (duplicados, faltantes) | High | Validación de integridad post-corrida, deduplicación por PK, reporte de anomalías |
| Normalización de dependencias incompleta | Medium | Reglas determinísticas documentadas, tabla de mapeo explícita, revisión manual muestra |
| Rendimiento scraping 4000+ expedientes | Low | Scraping por lotes, SQLite bulk insert, procesamiento en streaming |
| Dashboard no cubre necesidades usuario final | Medium | Iteración con stakeholders en fase 7, prototipos tempranos, feedback continuo |

## Rollback Plan

1. **Datos**: Eliminar `data/sume.db` y directorios `data/raw/`, `data/processed/` → estado previo limpio
2. **Código**: `git reset --hard HEAD~1` (commits atómicos por fase)
3. **Entorno**: `pip uninstall -r requirements.txt` + eliminar venv
4. **Configuración**: Sin cambios en sistema externo (solo lectura SUME público)

## Dependencies

- Python 3.11+
- Acceso de red a `servicios.unl.edu.ar` (puerto 443)
- Permisos escritura en directorio proyecto
- Navegador moderno para dashboard (Chrome/Firefox/Edge)

## Success Criteria

- [ ] Scraper extrae 100% expedientes 2025 (2 corridas validadas sin pérdida)
- [ ] Normalización cubre ≥99% dependencias únicas observadas
- [ ] Dashboard carga <3s con dataset completo (4k expedientes, ~40k movimientos)
- [ ] Circuitos modales identificados para ≥90% conceptos con ≥5 expedientes
- [ ] Reportes ISO 9001 generados para todos los conceptos con datos
- [ ] Cobertura tests ≥80% en módulos core (scraper, normalizer, analysis)
- [ ] Documentación técnica + manual usuario completos y validados