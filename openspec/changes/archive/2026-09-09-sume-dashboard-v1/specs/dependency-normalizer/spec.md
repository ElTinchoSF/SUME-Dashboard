# Dependency Normalizer Specification

## Purpose

Deterministic normalization of SUME dependency names to enable consistent circuit analysis. Converts raw dependency strings from SUME into standardized canonical forms.

## Requirements

### Requirement: Normalize "Mesa de Entradas" Pattern

The system SHALL normalize dependencies matching the pattern `{nombre} (Mesa de Entradas - {facultad})` to `{nombre} ({facultad})`.

#### Scenario: Standard FBCB dependency

- GIVEN raw dependency "Alumnado (Mesa de Entradas - FBCB)"
- WHEN the normalizer processes the string
- THEN the normalized output SHALL be "Alumnado (FBCB)"

#### Scenario: Multiple faculties

- GIVEN raw dependency "Despacho General (Mesa de Entradas - FBCB)" and "Despacho General (Mesa de Entradas - FHUC)"
- WHEN the normalizer processes both strings
- THEN the normalized outputs SHALL be "Despacho General (FBCB)" and "Despacho General (FHUC)" respectively

### Requirement: Preserve Mesa de Entradas Names

The system SHALL keep Mesa de Entradas dependencies unchanged (no parentheses pattern).

#### Scenario: Mesa de Entradas without parentheses

- GIVEN raw dependency "Mesa de Entradas - FBCB"
- WHEN the normalizer processes the string
- THEN the normalized output SHALL be "Mesa de Entradas - FBCB"

### Requirement: Contract Last Parentheses (General Rule)

The system SHALL apply a general contraction rule: if a dependency has multiple parenthetical groups, contract only the last one.

#### Scenario: Dependency with multiple parentheses

- GIVEN raw dependency "Secretaría Académica (FBCB) (Mesa de Entradas - FBCB)"
- WHEN the normalizer processes the string
- THEN the normalized output SHALL be "Secretaría Académica (FBCB)"

### Requirement: Identity for Non-Matching Patterns

The system SHALL return the original string unchanged for dependencies not matching any normalization rule.

#### Scenario: Unknown dependency format

- GIVEN raw dependency "Dirección General de Administración"
- WHEN the normalizer processes the string
- THEN the normalized output SHALL be "Dirección General de Administración"

### Requirement: Explicit Mapping Table Support

The system SHALL support an explicit override mapping table for edge cases not covered by rules.

#### Scenario: Explicit override takes precedence

- GIVEN a mapping table entry: "Archivo Digital (Mesa de Entradas - FBCB)" → "Archivo Digital FBCB"
- WHEN the normalizer processes "Archivo Digital (Mesa de Entradas - FBCB)"
- THEN the normalized output SHALL be "Archivo Digital FBCB" (explicit override)
- AND the rule-based normalization SHALL NOT apply

### Requirement: Normalization Idempotency

The system SHALL guarantee that normalizing an already-normalized string produces the same result.

#### Scenario: Double normalization

- GIVEN normalized dependency "Alumnado (FBCB)"
- WHEN the normalizer processes it again
- THEN the output SHALL be "Alumnado (FBCB)"

### Requirement: Track Original Names

The system SHALL store both original and normalized names for auditability.

#### Scenario: Database persistence

- GIVEN raw dependency "Alumnado (Mesa de Entradas - FBCB)"
- WHEN the normalizer persists to database
- THEN the dependencias table SHALL have: nombre="Alumnado (FBCB)", nombre_original="Alumnado (Mesa de Entradas - FBCB)"

## Non-Functional Requirements

### Determinism

- The normalizer SHALL be a pure function: same input always produces same output
- The normalizer SHALL have no external dependencies or side effects

### Coverage

- The normalizer SHALL cover ≥99% of unique dependencies observed in SUME data
- Uncovered dependencies SHALL be logged for manual review

### Performance

- The normalizer SHALL process 10,000+ dependency strings in under 1 second

## Constraints and Assumptions

- Input strings are UTF-8 encoded Spanish text
- Faculty codes are standard UNL abbreviations (FBCB, FHUC, FADU, etc.)
- Normalization rules are documented and version-controlled
- The explicit mapping table is maintained as a configuration file