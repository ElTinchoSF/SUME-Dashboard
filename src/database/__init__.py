"""
Database package for SUME Dashboard.

Provides schema definitions, data models, and connection management
for the SQLite database used as the single source of truth.
"""

from src.database.connection import (
    get_connection,
    close_connection,
    transaction,
    _initialize_schema as init_database,
)
from src.database.models import (
    ExpedienteDict,
    MovimientoDict,
    DependenciaDict,
    CircuitoDict,
)
from src.database.schema import (
    SCHEMA_SQL,
    INDEXES_SQL,
    INIT_SQL,
)

__all__ = [
    # Connection management
    "get_connection",
    "close_connection",
    "transaction",
    "init_database",
    # Data models (TypedDicts)
    "ExpedienteDict",
    "MovimientoDict",
    "DependenciaDict",
    "CircuitoDict",
    # Schema SQL
    "SCHEMA_SQL",
    "INDEXES_SQL",
    "INIT_SQL",
]