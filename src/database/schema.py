"""
SQL Schema definitions for SUME Dashboard database.

Contains DDL for the 4 core tables plus indexes, matching the design specification exactly.
"""

# Table creation SQL statements (in dependency order)
EXPEDIENTES_SQL = """
CREATE TABLE IF NOT EXISTS expedientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT UNIQUE NOT NULL,
    concepto TEXT NOT NULL,
    descripcion TEXT,
    fecha_alta DATE NOT NULL,
    estado TEXT,
    palabras_clave TEXT,
    origenes TEXT,
    fecha_extraccion DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

MOVIMIENTOS_SQL = """
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expediente_id INTEGER NOT NULL REFERENCES expedientes(id),
    orden INTEGER NOT NULL,
    fecha_recepcion DATE NOT NULL,
    dependencia TEXT NOT NULL,
    UNIQUE(expediente_id, orden)
);
"""

DEPENDENCIAS_SQL = """
CREATE TABLE IF NOT EXISTS dependencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    nombre_original TEXT NOT NULL,
    total_expedientes INTEGER DEFAULT 0
);
"""

CIRCUITOS_SQL = """
CREATE TABLE IF NOT EXISTS circuitos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    circuito TEXT NOT NULL,  -- JSON array of dependency names
    concepto TEXT NOT NULL,
    frecuencia INTEGER NOT NULL,
    es_mas_frecuente BOOLEAN DEFAULT FALSE,
    UNIQUE(circuito, concepto)
);
"""

# Combined schema for easy execution
SCHEMA_SQL = "\n".join([
    EXPEDIENTES_SQL,
    MOVIMIENTOS_SQL,
    DEPENDENCIAS_SQL,
    CIRCUITOS_SQL,
])

# Index creation SQL statements
INDEXES_SQL = "\n".join([
    "CREATE INDEX IF NOT EXISTS idx_expedientes_concepto ON expedientes(concepto);",
    "CREATE INDEX IF NOT EXISTS idx_expedientes_fecha_alta ON expedientes(fecha_alta);",
    "CREATE INDEX IF NOT EXISTS idx_movimientos_expediente ON movimientos(expediente_id);",
    "CREATE INDEX IF NOT EXISTS idx_movimientos_dependencia ON movimientos(dependencia);",
    "CREATE INDEX IF NOT EXISTS idx_circuitos_concepto ON circuitos(concepto);",
])

# Complete initialization SQL (schema + indexes)
INIT_SQL = SCHEMA_SQL + "\n" + INDEXES_SQL

# Migration/version tracking (for future use)
MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
"""

# Current schema version
SCHEMA_VERSION = 1


def init_db(conn) -> None:
    """
    Initialize database schema on an existing connection.
    
    Creates all tables and indexes if they don't exist.
    
    Args:
        conn: SQLite connection to initialize.
    """
    conn.executescript(INIT_SQL)