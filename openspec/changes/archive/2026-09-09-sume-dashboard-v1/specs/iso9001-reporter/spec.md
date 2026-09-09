# ISO 9001 Reporter Specification

## Purpose

Generates structured, auditable reports documenting real administrative circuits by tipo de asunto (concepto) as documentary evidence for ISO 9001 certification of the Mesa de Entradas FBCB-UNL.

## Requirements

### Requirement: Evidence Report Structure

The system SHALL generate reports following a standardized structure aligned with ISO 9001 process documentation requirements.

#### Scenario: Complete report structure

- GIVEN the reporter is executed for the full 2025 dataset
- WHEN the report is generated
- THEN the report SHALL contain these sections in order:
  1. **Portada**: Título, período, fecha generación, versión, responsable
  2. **Resumen Ejecutivo**: Alcance, total expedientes, conceptos cubiertos, período
  3. **Metodología**: Fuente de datos (SUME), proceso de extracción, normalización, análisis
  4. **Análisis por Concepto** (una subsección por cada concepto con datos):
     - Concepto y descripción
     - Total expedientes
     - Circuito modal (secuencia, frecuencia, %)
     - Tabla de todos los circuitos observados
     - Estadísticas de pasos (min, max, media, mediana, moda)
     - Top 5 dependencias por tráfico
     - Tiempos de permanencia (promedio por dependencia)
     - Circuitos atípicos detectados
  5. **Análisis Transversal**: Ranking de dependencias, distribución temporal, cobertura
  6. **Calidad de Datos**: Anomalías detectadas, % cobertura, limitaciones
  7. **Anexos**: Glosario, detalle de expedientes por circuito (opcional)

### Requirement: Per-Concepto Evidence Sheet

The system SHALL produce a standalone evidence sheet for each concepto suitable for ISO 9001 auditor review.

#### Scenario: Concepto evidence sheet content

- GIVEN concepto "Gestión Alumno" with 500 expedientes
- WHEN the reporter generates the evidence sheet
- THEN the sheet SHALL include:
  - **Identificación**: Concepto, código SAM, total expedientes, período
  - **Circuito Real Predominante**: Diagrama de flujo (texto/mermaid), frecuencia, %
  - **Variantes de Circuito**: Tabla con todos los circuitos, frecuencias, %
  - **Indicadores de Desempeño**: Pasos promedio, tiempo total promedio, tiempo por dependencia
  - **Desviaciones**: Circuitos atípicos con descripción de la desviación
  - **Conclusión**: Si el circuito real coincide con el diseñado (pendiente validación MDE)

### Requirement: Traceability to Source Data

The system SHALL maintain traceability from report findings to raw SUME data.

#### Scenario: Expediente traceability

- GIVEN a report states "Circuito A: MDE → Despacho → Alumnado (45 expedientes, 90%)"
- WHEN an auditor requests evidence
- THEN the reporter SHALL provide (in appendix or separate file):
  - List of 45 expediente numbers with SUME detail URLs
  - For each: fecha_alta, secuencia completa de movimientos con fechas
- AND the traceability data SHALL be exportable as CSV

### Requirement: Data Quality Disclosure

The system SHALL explicitly document data quality issues in the report.

#### Scenario: Quality disclosure section

- GIVEN the scraping/analysis pipeline detected anomalies
- WHEN the report is generated
- THEN the "Calidad de Datos" section SHALL include:
  - Total expedientes en SUME vs extraídos (coverage %)
  - Expedientes con 0 movimientos (count, %)
  - Dependencias no normalizadas (count, examples)
  - Expedientes con fechas inconsistentes (count)
  - Duplicados detectados y resueltos
  - Limitaciones conocidas (ej: "Solo expedientes FBCB 2025")

### Requirement: Automated Report Generation

The system SHALL support programmatic report generation for integration into CI/CD or scheduled runs.

#### Scenario: CLI report generation

- GIVEN the reporter module is installed
- WHEN the user runs `python -m src.analysis.reports --output reports/iso9001_2025.md`
- THEN the reporter SHALL generate the full report in Markdown format
- AND the reporter SHALL exit with code 0 on success, non-zero on error

#### Scenario: Selective concept reporting

- GIVEN the user wants reports only for top 5 conceptos
- WHEN the user runs `python -m src.analysis.reports --conceptos "Gestión Alumno,Gestión de Becas,..."`
- THEN the reporter SHALL generate reports only for those conceptos

### Requirement: Export Formats

The system SHALL support multiple output formats for different audiences.

#### Scenario: Markdown for version control

- GIVEN the reporter generates a report
- WHEN format=markdown is selected
- THEN the output SHALL be a .md file with proper headers, tables, mermaid diagrams
- AND the file SHALL be suitable for Git version control

#### Scenario: PDF for formal submission

- GIVEN the reporter generates a report
- WHEN format=pdf is selected
- THEN the output SHALL be a .pdf file with professional formatting
- AND the PDF SHALL include page numbers, table of contents, header/footer

#### Scenario: Excel for data analysis

- GIVEN the reporter generates a report
- WHEN format=excel is selected
- THEN the output SHALL be a .xlsx file with sheets:
  - Resumen_Ejecutivo
  - Circuitos_Por_Concepto
  - Estadisticas_Pasos
  - Tiempos_Permanencia
  - Circuitos_Atipicos
  - Ranking_Dependencias
  - Calidad_Datos
  - Trazabilidad_Expedientes

### Requirement: Report Versioning

The system SHALL version reports to track changes over time.

#### Scenario: Version metadata

- GIVEN a report is generated
- WHEN the report is created
- THEN the report SHALL include metadata: version (YYYY.MM.DD.N), git commit hash, data hash (SHA256 of sume.db)
- AND re-generating with unchanged data SHALL produce identical version hash

## Non-Functional Requirements

### Auditability

- The report generation process SHALL be fully deterministic
- The same input data SHALL always produce the same report content
- All calculations SHALL be reproducible from the SQLite database

### Completeness

- The report SHALL cover 100% of conceptos with ≥5 expedientes
- Conceptos with <5 expedientes SHALL be listed in an "Insuficiente Muestra" appendix

### Timeliness

- Full report generation SHALL complete in <60 seconds for 4000 expedientes
- Per-concepto sheet generation SHALL complete in <5 seconds

## Constraints and Assumptions

- Reports are generated in Spanish
- The reporter reads from the analysis database (circuitos table) and raw data
- ISO 9001 certification process requires: process identification, process interaction, performance indicators, evidence of effectiveness
- The MDE-FBCB will validate if real circuits match designed circuits (outside system scope)
- Report templates are maintained as Jinja2 templates for flexibility