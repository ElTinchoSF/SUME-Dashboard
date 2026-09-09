"""
SQLite connection management for SUME Dashboard.

Provides a singleton connection with:
- Thread-safe access
- Row factory for dict-like access
- Transaction context manager
- Foreign key enforcement
- WAL mode for better concurrency
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.config import get_settings
from src.database.schema import INIT_SQL, SCHEMA_VERSION, MIGRATIONS_TABLE_SQL


# Thread-local storage for connection
_local = threading.local()
_connection_lock = threading.Lock()
_initialized = False


def _get_db_path() -> Path:
    """Get the database path from settings."""
    settings = get_settings()
    db_path = Path(settings.database.path)
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _create_connection() -> sqlite3.Connection:
    """Create a new SQLite connection with proper configuration."""
    db_path = _get_db_path()
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,  # Allow multi-threaded access (we manage thread safety)
        timeout=30.0,  # 30 second busy timeout
    )

    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL;")

    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys=ON;")

    # Return rows as sqlite3.Row objects (dict-like access)
    conn.row_factory = sqlite3.Row

    # Busy timeout in milliseconds
    conn.execute("PRAGMA busy_timeout=30000;")

    return conn


def get_connection() -> sqlite3.Connection:
    """
    Get the thread-local database connection.

    Creates a new connection for the current thread if one doesn't exist.
    The connection is configured with WAL mode, foreign keys, and row factory.

    Returns:
        sqlite3.Connection: Thread-local database connection.
    """
    global _initialized

    if not hasattr(_local, "connection") or _local.connection is None:
        with _connection_lock:
            # Double-check after acquiring lock
            if not hasattr(_local, "connection") or _local.connection is None:
                _local.connection = _create_connection()

                # Initialize schema on first connection (once per process)
                if not _initialized:
                    _initialize_schema(_local.connection)
                    _initialized = True

    return _local.connection


def _initialize_schema(conn: sqlite3.Connection) -> None:
    """
    Initialize the database schema if not already present.

    Args:
        conn: Database connection to initialize.
    """
    # Create migrations table first
    conn.execute(MIGRATIONS_TABLE_SQL)

    # Check current schema version
    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
    row = cursor.fetchone()
    current_version = row[0] if row else 0

    if current_version < SCHEMA_VERSION:
        # Apply schema
        conn.executescript(INIT_SQL)

        # Record migration
        conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
            (SCHEMA_VERSION, "Initial schema: expedientes, movimientos, dependencias, circuitos"),
        )
        conn.commit()


def close_connection() -> None:
    """Close the thread-local database connection if it exists."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


def close_all_connections() -> None:
    """Close all thread-local connections (for testing/cleanup)."""
    close_connection()
    # Note: Other threads' connections are in their thread-local storage
    # and will be closed when those threads call close_connection()


@contextmanager
def transaction(conn: Optional[sqlite3.Connection] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database transactions.

    Commits on success, rolls back on exception.
    If no connection is provided, uses the thread-local connection.

    Args:
        conn: Optional connection to use. Defaults to thread-local connection.

    Yields:
        sqlite3.Connection: The connection with an active transaction.

    Example:
        with transaction() as conn:
            conn.execute("INSERT INTO ...")
            conn.execute("INSERT INTO ...")
        # Auto-commits here
    """
    if conn is None:
        conn = get_connection()

    # Check if we're already in a transaction
    in_transaction = conn.in_transaction

    try:
        if not in_transaction:
            conn.execute("BEGIN")
        yield conn
        if not in_transaction:
            conn.commit()
    except Exception:
        if not in_transaction:
            conn.rollback()
        raise


def execute_script(sql: str) -> None:
    """
    Execute a multi-statement SQL script.

    Args:
        sql: SQL script to execute.
    """
    conn = get_connection()
    conn.executescript(sql)
    conn.commit()


def vacuum() -> None:
    """Run VACUUM to reclaim space and defragment the database."""
    conn = get_connection()
    conn.execute("VACUUM")


def get_table_row_count(table: str) -> int:
    """
    Get the row count for a table.

    Args:
        table: Table name.

    Returns:
        int: Number of rows in the table.
    """
    conn = get_connection()
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


def check_integrity() -> bool:
    """
    Run SQLite integrity check.

    Returns:
        bool: True if database is healthy, False otherwise.
    """
    conn = get_connection()
    cursor = conn.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    return result == "ok"


# For testing: allow replacing the connection factory
_override_connection_factory: Optional[callable] = None


def set_connection_factory(factory: Optional[callable]) -> None:
    """
    Override the connection factory (for testing).

    Args:
        factory: Callable that returns a sqlite3.Connection, or None to reset.
    """
    global _override_connection_factory
    _override_connection_factory = factory


def _create_connection_for_test() -> sqlite3.Connection:
    """Create connection using override factory if set."""
    if _override_connection_factory is not None:
        return _override_connection_factory()
    return _create_connection()


# Patch get_connection for testing
_original_get_connection = get_connection


def _test_get_connection() -> sqlite3.Connection:
    """Test version of get_connection that uses override factory."""
    if not hasattr(_local, "connection") or _local.connection is None:
        with _connection_lock:
            if not hasattr(_local, "connection") or _local.connection is None:
                _local.connection = _create_connection_for_test()
    return _local.connection