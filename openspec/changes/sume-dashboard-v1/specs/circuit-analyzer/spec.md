# Circuit Analyzer Specification

## Purpose

Process mining engine that discovers administrative circuits from expediente movement sequences, computes frequencies, identifies modal circuits per concept, and calculates performance metrics (times, steps, outliers).

## Requirements

### Requirement: Circuit Reconstruction

The system SHALL reconstruct the complete administrative circuit for each expediente as an ordered sequence of dependencies.

#### Scenario: Happy path - reconstruct circuit with initial MDE injection

- GIVEN an expediente with movimientos: [Despacho General, Alumnado, Secretaría Académica] and fecha_alta = 2025-06-15
- WHEN the analyzer reconstructs the circuit
- THEN the circuit SHALL be: [Mesa de Entradas - FBCB (orden 0, fecha_alta), Despacho General (orden 1), Alumnado (orden 2), Secretaría Académica (orden 3)]

#### Scenario: Expediente with zero movimientos

- GIVEN an expediente with no movimientos and fecha_alta = 2025-06-15
- WHEN the analyzer reconstructs the circuit
- THEN the circuit SHALL be: [Mesa de Entradas - FBCB (orden 0, fecha_alta)]

### Requirement: Circuit Frequency by Concept

The system SHALL compute frequency distribution of circuits grouped by expediente concepto.

#### Scenario: Frequency computation

- GIVEN 100 expedientes of concepto "Gestión Alumno" with various circuits
- WHEN the analyzer computes frequencies
- THEN the analyzer SHALL produce a table: circuito (JSON sequence), concepto, frecuencia, es_mas_frecuente
- AND the sum of frecuencias SHALL equal total expedientes for that concepto

### Requirement: Modal Circuit Identification

The system SHALL identify the most frequent circuit (mode) for each concepto with sufficient data.

#### Scenario: Modal circuit marked

- GIVEN concepto "Gestión Alumno" has circuits: Circuit A (45 expedientes), Circuit B (30), Circuit C (25)
- WHEN the analyzer identifies modal circuits
- THEN Circuit A SHALL have es_mas_frecuente = TRUE
- AND Circuits B and C SHALL have es_mas_frecuente = FALSE

#### Scenario: Tie handling

- GIVEN concepto "X" has Circuit A (10) and Circuit B (10) as top frequencies
- WHEN the analyzer identifies modal circuits
- THEN the analyzer SHALL mark the first encountered as es_mas_frecuente = TRUE
- AND the analyzer SHALL log a warning about the tie

### Requirement: Minimum Sample Threshold

The system SHALL only compute modal circuits for conceptos with ≥5 expedientes.

#### Scenario: Insufficient data

- GIVEN concepto "Auditoría" has only 3 expedientes
- WHEN the analyzer computes modal circuits
- THEN the analyzer SHALL NOT mark any circuit as es_mas_frecuente for this concepto
- AND the analyzer SHALL flag the concepto as "insufficient data"

### Requirement: Step Count Statistics

The system SHALL compute descriptive statistics for number of steps (movimientos) per expediente by concepto.

#### Scenario: Step statistics

- GIVEN expedientes of concepto "Gestión Alumno" with step counts: [5, 6, 5, 7, 5, 8, 5]
- WHEN the analyzer computes statistics
- THEN the analyzer SHALL produce: min=5, max=8, mean≈5.86, median=5, mode=5, std_dev≈1.07

### Requirement: Permanence Time Analysis

The system SHALL calculate time spent in each dependency (difference between consecutive movimiento fechas).

#### Scenario: Permanence time calculation

- GIVEN an expediente with movimientos:
  - orden 0: MDE-FBCB, fecha 2025-06-15
  - orden 1: Despacho General, fecha 2025-06-16
  - orden 2: Alumnado, fecha 2025-06-18
- WHEN the analyzer computes permanence
- THEN permanence in MDE-FBCB = 1 day, in Despacho General = 2 days
- AND the final dependency (Alumnado) SHALL have no permanence calculated (no exit date)

### Requirement: Atypical Circuit Detection

The system SHALL flag circuits that deviate significantly from the modal circuit for their concepto.

#### Scenario: Outlier detection by frequency

- GIVEN concepto "Gestión Alumno" modal circuit frequency = 45, total expedientes = 100
- WHEN the analyzer evaluates Circuit X with frequency = 2
- THEN Circuit X SHALL be flagged as atypical (frequency < 5% of total)
- AND the analyzer SHALL report: circuito, concepto, frecuencia, porcentaje_del_total

#### Scenario: Outlier detection by structure

- GIVEN modal circuit for "Gestión Alumno" has 6 steps
- WHEN an expediente has 15 steps with repeated dependencies (loops)
- THEN the analyzer SHALL flag this as structurally atypical
- AND the analyzer SHALL report the loop pattern detected

### Requirement: Dependency Traffic Ranking

The system SHALL rank dependencies by total expedientes processed.

#### Scenario: Traffic ranking

- GIVEN all expedientes and their movements
- WHEN the analyzer computes dependency traffic
- THEN the analyzer SHALL produce a ranked list: dependencia, total_expedientes, total_movimientos
- AND the ranking SHALL be sorted by total_expedientes descending

### Requirement: Concept Distribution

The system SHALL compute distribution of expedientes by concepto.

#### Scenario: Concept frequency table

- GIVEN 4000 expedientes across 20 conceptos
- WHEN the analyzer computes concept distribution
- THEN the analyzer SHALL produce: concepto, cantidad_expedientes, porcentaje
- AND the sum SHALL equal total expedientes

## Non-Functional Requirements

### Performance

- The analyzer SHALL process 4000 expedientes (~40k movimientos) in under 10 seconds
- The analyzer SHALL use vectorized pandas operations where possible

### Reproducibility

- The analyzer SHALL produce identical results given identical input data
- The analyzer SHALL log the SQL queries used for each computation

### Extensibility

- The analyzer SHALL expose a clean API for adding new metrics without modifying core logic
- The analyzer SHALL support pluggable outlier detection strategies

## Constraints and Assumptions

- Input data is stored in SQLite with schema defined in database spec
- All fechas are valid DATE values (validated at ingestion)
- Circuit sequences are compared by exact dependency name match (normalized)
- Time calculations use calendar days (not business days)
- Concepto values come directly from SUME (no further normalization in v1)