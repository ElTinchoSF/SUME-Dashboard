# Integration Specification

## Purpose

Defines the interfaces, data flows, and contracts between the five SUME Dashboard components to ensure seamless end-to-end operation.

## Requirements

### Requirement: Scraper → Database Contract

The scraper SHALL write to the SQLite database using a defined schema and transaction protocol.

#### Scenario: Successful scrape writes expedientes and movimientos

- GIVEN the scraper extracts an expediente with 5 movimientos
- WHEN the scraper persists to database
- THEN the scraper SHALL insert into expedientes table (all metadata fields)
- AND the scraper SHALL insert 5 rows into movimientos table with correct expediente_id and orden (1-5)
- AND the scraper SHALL insert/update dependencias table with normalized names
- AND all inserts SHALL occur in a single transaction (atomic per expediente)

#### Scenario: Duplicate expediente handling

- GIVEN the scraper encounters an expediente numero already in database
- WHEN the scraper attempts to insert
- THEN the scraper SHALL skip the expediente (UPDATE or IGNORE on UNIQUE constraint)
- AND the scraper SHALL log the duplicate as "already processed"

#### Scenario: Dependency normalization at write time

- GIVEN the scraper has raw dependency "Alumnado (Mesa de Entradas - FBCB)"
- WHEN the scraper writes the movimiento
- THEN the scraper SHALL call the normalizer to get "Alumnado (FBCB)"
- AND the scraper SHALL store normalized name in movimientos.dependencia
- AND the scraper SHALL upsert dependencias table with both original and normalized

### Requirement: Database → Analyzer Contract

The analyzer SHALL read from the database using defined views/queries.

#### Scenario: Analyzer reads complete circuit data

- GIVEN the database has expedientes, movimientos, dependencias populated
- WHEN the analyzer runs circuit reconstruction
- THEN the analyzer SHALL query: expedientes joined with movimientos ordered by orden
- AND the analyzer SHALL inject orden 0 (MDE) using expediente.fecha_alta and faculty from numero
- AND the analyzer SHALL use dependencias.nombre (normalized) for all dependency references

#### Scenario: Analyzer writes circuit results

- GIVEN the analyzer computes circuit frequencies
- WHEN the analyzer persists results
- THEN the analyzer SHALL insert/update the circuitos table
- AND the circuitos.circuito field SHALL be JSON array of dependency names
- AND the analyzer SHALL set es_mas_frecuente correctly per concepto

### Requirement: Analyzer → Dashboard Contract

The dashboard SHALL consume pre-computed analysis results from the database.

#### Scenario: Dashboard reads circuitos table

- GIVEN the circuitos table is populated by analyzer
- WHEN the dashboard loads the Circuitos page
- THEN the dashboard SHALL query circuitos table filtered by concepto
- AND the dashboard SHALL parse circuito JSON for visualization
- AND the dashboard SHALL NOT re-compute frequencies (read-only)

#### Scenario: Dashboard reads aggregated statistics

- GIVEN the analyzer computed step statistics and permanence times
- WHEN the dashboard loads the Conceptos page
- THEN the dashboard SHALL read from analysis result tables/views
- AND the dashboard SHALL NOT perform heavy aggregation at runtime

### Requirement: Dashboard → Reporter Contract

The reporter SHALL use the same database views as the dashboard for consistency.

#### Scenario: Reporter uses analyzer-computed circuits

- GIVEN the reporter generates ISO 9001 report
- WHEN the reporter queries for modal circuits
- THEN the reporter SHALL query circuitos WHERE es_mas_frecuente = TRUE
- AND the reporter SHALL NOT re-run the analyzer logic

### Requirement: End-to-End Data Flow Validation

The system SHALL validate data integrity across component boundaries.

#### Scenario: Row count reconciliation

- GIVEN a full pipeline run completes
- WHEN the integration validation runs
- THEN the validation SHALL verify:
  - expedientes count in DB = expedientes scraped (minus duplicates)
  - sum of movimientos per expediente = total movimientos rows
  - distinct dependencias in movimientos = dependencias table rows
  - sum of circuitos.frecuencia per concepto = expedientes count per concepto
- AND any mismatch SHALL fail the validation with detailed report

#### Scenario: Referential integrity

- GIVEN the database is populated
- WHEN the validation runs
- THEN the validation SHALL verify:
  - All movimientos.expediente_id exist in expedientes.id
  - All movimientos.dependencia exist in dependencias.nombre
  - All circuitos.concepto exist in expedientes.concepto
- AND any orphan SHALL be reported as critical error

### Requirement: Configuration Management

The system SHALL use a single configuration source for all components.

#### Scenario: Shared configuration file

- GIVEN the project has config.yaml
- WHEN any component starts
- THEN the component SHALL read: database_path, sume_base_url, scraping_delay, retry_config, normalization_rules_path
- AND changes to config.yaml SHALL affect all components without code changes

### Requirement: Error Propagation and Handling

The system SHALL handle failures gracefully and provide actionable error messages.

#### Scenario: SUME unavailable during scraping

- GIVEN SUME returns 503 for 3 consecutive retries
- WHEN the scraper encounters persistent failure
- THEN the scraper SHALL save progress (last processed page)
- AND the scraper SHALL exit with code indicating "retryable failure"
- AND the orchestrator SHALL be able to resume from saved progress

#### Scenario: Database locked during concurrent access

- GIVEN the analyzer runs while scraper is writing
- WHEN the analyzer encounters SQLITE_BUSY
- THEN the analyzer SHALL retry with exponential backoff (max 30s)
- AND the analyzer SHALL log the contention event

### Requirement: Incremental Execution Support

The system SHALL support running components independently on new data.

#### Scenario: Scraper adds second semester data

- GIVEN first semester data exists in database
- WHEN the scraper runs for second semester
- THEN the scraper SHALL append new expedientes (no full reload)
- AND the analyzer SHALL recompute only affected conceptos (incremental)
- AND the dashboard SHALL reflect new data on next refresh

## Non-Functional Requirements

### Data Consistency

- All components SHALL use the same SQLite database file (data/sume.db)
- Database schema changes SHALL use versioned migrations
- No component SHALL modify another component's tables directly

### Observability

- Each component SHALL emit structured logs (JSON) with: timestamp, component, level, message, context
- Logs SHALL include correlation IDs for end-to-end tracing
- Metrics SHALL be exposed: scrape rate, parse errors, db write latency, query latency

### Deployment

- All components SHALL run in the same Python environment
- The pipeline SHALL be executable via a single CLI command: `python -m src.pipeline run --phase all`
- Individual phases SHALL be runnable: `python -m src.pipeline run --phase scraper|analyzer|reporter`

## Constraints and Assumptions

- SQLite is the single source of truth (no separate message queues or caches)
- Components communicate only through the database (no direct API calls)
- The pipeline is batch-oriented (not streaming)
- Manual intervention may be needed between phases (validation gates)
- Python 3.11+ with virtual environment isolation