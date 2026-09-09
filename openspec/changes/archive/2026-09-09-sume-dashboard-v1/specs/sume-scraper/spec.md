# Sume Scraper Specification

## Purpose

Automated web scraper for the SUME public system (`servicios.unl.edu.ar/expedientes/`) to extract expedientes and their movements for the year 2025, with robust error handling, rate limiting, and data integrity validation.

## Requirements

### Requirement: Search and Pagination

The system SHALL search SUME for expedientes from FBCB faculty with alta date in 2025 and paginate through all result pages.

#### Scenario: Happy path - search returns results

- GIVEN SUME is accessible and returns a results page for FBCB expedientes in 2025
- WHEN the scraper executes a search with filters "Número: FBCB" and "Fecha de Alta: 01/01/2025 - 31/12/2025"
- THEN the scraper SHALL extract all expediente detail URLs from the results page
- AND the scraper SHALL follow pagination links until all pages are processed

#### Scenario: Empty results for a date range

- GIVEN SUME returns zero results for a specific date range
- WHEN the scraper processes that range
- THEN the scraper SHALL log zero results and continue without error

### Requirement: Expediente Detail Extraction

The system SHALL extract complete metadata from each expediente detail page.

#### Scenario: Happy path - extract all fields

- GIVEN a valid expediente detail URL
- WHEN the scraper fetches and parses the detail page
- THEN the scraper SHALL extract: numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes
- AND all extracted fields SHALL be non-empty for required fields (numero, concepto, fecha_alta)

#### Scenario: Missing optional fields

- GIVEN an expediente detail page with empty palabras_clave or origenes
- WHEN the scraper parses the page
- THEN the scraper SHALL store empty strings for missing optional fields
- AND the scraper SHALL NOT fail the extraction

### Requirement: Movimientos (Pases) Extraction

The system SHALL extract the complete movement history (pases) from the expediente detail page.

#### Scenario: Happy path - extract all movimientos

- GIVEN an expediente detail page with a "Pases del Expediente" table
- WHEN the scraper parses the movimientos table
- THEN the scraper SHALL extract for each row: fecha_recepcion, dependencia_destino
- AND the scraper SHALL assign sequential orden starting from 1

#### Scenario: Expediente with no movimientos

- GIVEN an expediente detail page with empty movimientos table
- WHEN the scraper parses the page
- THEN the scraper SHALL record zero movimientos for that expediente
- AND the scraper SHALL still create the expediente record

### Requirement: Rate Limiting and Retry Logic

The system SHALL respect SUME server limits with configurable delays and exponential backoff retries.

#### Scenario: Successful request with delay

- GIVEN the scraper configuration has delay=0.5s
- WHEN the scraper makes consecutive HTTP requests
- THEN the scraper SHALL wait at least 0.5 seconds between requests

#### Scenario: Transient network error triggers retry

- GIVEN a request fails with timeout or 5xx error
- WHEN the scraper encounters the error
- THEN the scraper SHALL retry up to 3 times with exponential backoff (1s, 2s, 4s)
- AND if all retries fail, the scraper SHALL log the failure and continue with next expediente

#### Scenario: Rate limit response (429)

- GIVEN SUME returns HTTP 429 Too Many Requests
- WHEN the scraper receives the response
- THEN the scraper SHALL wait 60 seconds before retrying
- AND the scraper SHALL retry up to 3 times

### Requirement: Data Integrity Validation

The system SHALL validate extracted data completeness and consistency after each scraping run.

#### Scenario: Post-run validation reports anomalies

- GIVEN a scraping run completes
- WHEN the scraper runs validation
- THEN the scraper SHALL report: total expedientes, total movimientos, expedientes with zero movimientos, duplicate expediente numbers, missing required fields
- AND the scraper SHALL fail the run if duplicate expediente numbers are detected

### Requirement: Two-Phase Execution Strategy

The system SHALL support executing scraping in two validated phases (semester 1, then semester 2).

#### Scenario: Phase 1 execution and validation

- GIVEN the scraper is configured for date range 01/01/2025 - 30/06/2025
- WHEN the scraper executes phase 1
- THEN the scraper SHALL store raw HTML snapshots in data/raw/
- AND the scraper SHALL produce a validation report before phase 2 can start

## Non-Functional Requirements

### Performance

- The scraper SHOULD complete a full semester extraction (~2000 expedientes) within 2 hours
- The scraper SHALL use streaming processing to maintain constant memory usage

### Reliability

- The scraper SHALL be idempotent: re-running on same date range SHALL NOT create duplicates
- The scraper SHALL use expediente numero as natural primary key for deduplication

### Observability

- The scraper SHALL log every HTTP request (URL, status code, duration)
- The scraper SHALL log parsing errors with expediente URL and HTML snippet for debugging

## Constraints and Assumptions

- SUME is a public system requiring no authentication
- SUME HTML structure may change; CSS selectors should be robust
- Network connectivity to servicios.unl.edu.ar:443 is required
- Python 3.11+ runtime environment