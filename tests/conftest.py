"""
Pytest configuration and fixtures for SUME Dashboard tests.

Provides:
- Temporary database fixture
- Sample HTML fixtures for scraper testing
- Mock HTTP client fixture
- Test settings override
"""

import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest
import sqlite3

from src.config import Settings, DatabaseConfig
from src.database.connection import get_connection, close_connection, set_connection_factory
from src.database.schema import INIT_SQL


# ============================================================================
# Test Settings
# ============================================================================

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sume.db"
        settings = Settings(
            database=DatabaseConfig(path=str(db_path)),
            sume=Settings.model_fields["sume"].default,
            scraper=Settings.model_fields["scraper"].default,
            normalizer=Settings.model_fields["normalizer"].default,
            analyzer=Settings.model_fields["analyzer"].default,
            dashboard=Settings.model_fields["dashboard"].default,
            reporter=Settings.model_fields["reporter"].default,
        )
        yield settings


@pytest.fixture(autouse=True)
def override_settings(test_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override global settings for all tests."""
    # Patch the get_settings function to return test settings
    import src.config
    monkeypatch.setattr(src.config, "get_settings", lambda: test_settings)
    monkeypatch.setattr(src.config, "_settings", test_settings)


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        yield db_path
    finally:
        db_path.unlink(missing_ok=True)


@pytest.fixture
def db_connection(temp_db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """
    Provide a clean database connection for each test.

    Creates a new connection to a temporary database with schema initialized.
    The connection is closed after the test.
    """
    def factory() -> sqlite3.Connection:
        conn = sqlite3.connect(temp_db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    # Override connection factory
    set_connection_factory(factory)

    # Get connection and initialize schema
    conn = get_connection()
    conn.executescript(INIT_SQL)
    conn.commit()

    try:
        yield conn
    finally:
        close_connection()
        set_connection_factory(None)


@pytest.fixture
def initialized_db(db_connection: sqlite3.Connection) -> sqlite3.Connection:
    """Alias for db_connection with explicit name for clarity."""
    return db_connection


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_expediente() -> dict:
    """Sample expediente data for testing."""
    return {
        "numero": "EXP-2025-00001",
        "concepto": "Gestión Alumno",
        "descripcion": "Trámite de inscripción a cursadas",
        "fecha_alta": "2025-03-15",
        "estado": "En trámite",
        "palabras_clave": "inscripción,cursadas,alumno",
        "origenes": "Mesa de Entradas FBCB",
    }


@pytest.fixture
def sample_movimientos() -> list[dict]:
    """Sample movimientos for an expediente."""
    return [
        {"orden": 1, "fecha_recepcion": "2025-03-15", "dependencia": "Mesa de Entradas FBCB"},
        {"orden": 2, "fecha_recepcion": "2025-03-16", "dependencia": "Departamento Alumnos"},
        {"orden": 3, "fecha_recepcion": "2025-03-18", "dependencia": "Secretaría Académica"},
        {"orden": 4, "fecha_recepcion": "2025-03-20", "dependencia": "Departamento Alumnos"},
    ]


@pytest.fixture
def sample_html_listing() -> str:
    """Sample SUME listing page HTML for parser testing."""
    return """
    <html>
    <body>
        <table class="tabla_expedientes">
            <thead>
                <tr>
                    <th>Número</th>
                    <th>Concepto</th>
                    <th>Fecha Alta</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>EXP-2025-00001</td>
                    <td>Gestión Alumno</td>
                    <td>15/03/2025</td>
                    <td>En trámite</td>
                    <td><a href="ver_expediente.php?id=12345">Ver</a></td>
                </tr>
                <tr>
                    <td>EXP-2025-00002</td>
                    <td>Gestión de Becas</td>
                    <td>16/03/2025</td>
                    <td>Finalizado</td>
                    <td><a href="ver_expediente.php?id=12346">Ver</a></td>
                </tr>
            </tbody>
        </table>
        <div class="pagination">
            <a href="busqueda_avanzada.php?page=1">1</a>
            <a href="busqueda_avanzada.php?page=2">2</a>
            <a href="busqueda_avanzada.php?page=3">3</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_detail() -> str:
    """Sample SUME detail page HTML for parser testing."""
    return """
    <html>
    <body>
        <div class="expediente-header">
            <h1>EXP-2025-00001</h1>
            <span class="concepto">Gestión Alumno</span>
        </div>
        <div class="expediente-info">
            <p><strong>Descripción:</strong> Trámite de inscripción a cursadas</p>
            <p><strong>Fecha Alta:</strong> 15/03/2025</p>
            <p><strong>Estado:</strong> En trámite</p>
            <p><strong>Palabras Clave:</strong> inscripción, cursadas, alumno</p>
            <p><strong>Orígenes:</strong> Mesa de Entradas FBCB</p>
        </div>
        <table class="tabla_movimientos">
            <thead>
                <tr>
                    <th>Orden</th>
                    <th>Fecha Recepción</th>
                    <th>Dependencia</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1</td>
                    <td>15/03/2025</td>
                    <td>Mesa de Entradas FBCB</td>
                </tr>
                <tr>
                    <td>2</td>
                    <td>16/03/2025</td>
                    <td>Departamento Alumnos</td>
                </tr>
                <tr>
                    <td>3</td>
                    <td>18/03/2025</td>
                    <td>Secretaría Académica</td>
                </tr>
                <tr>
                    <td>4</td>
                    <td>20/03/2025</td>
                    <td>Departamento Alumnos</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_http_session() -> MagicMock:
    """Create a mock requests.Session for testing HTTP client."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = ""
    response.raise_for_status = MagicMock()
    session.get.return_value = response
    session.post.return_value = response
    return session


@pytest.fixture
def mock_response_factory():
    """Factory for creating mock HTTP responses."""

    def _create(status_code: int = 200, text: str = "", headers: dict = None) -> MagicMock:
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        response.headers = headers or {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            from requests.exceptions import HTTPError
            response.raise_for_status.side_effect = HTTPError(f"{status_code} Error")
        return response

    return _create


# ============================================================================
# Test Utilities
# ============================================================================

def insert_test_expediente(conn: sqlite3.Connection, expediente: dict) -> int:
    """Helper to insert a test expediente and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            expediente["numero"],
            expediente["concepto"],
            expediente.get("descripcion"),
            expediente["fecha_alta"],
            expediente.get("estado"),
            expediente.get("palabras_clave"),
            expediente.get("origenes"),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_test_movimientos(conn: sqlite3.Connection, expediente_id: int, movimientos: list[dict]) -> None:
    """Helper to insert test movimientos for an expediente."""
    for mov in movimientos:
        conn.execute(
            """
            INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
            VALUES (?, ?, ?, ?)
            """,
            (expediente_id, mov["orden"], mov["fecha_recepcion"], mov["dependencia"]),
        )
    conn.commit()


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests (e.g., performance benchmarks)")
    config.addinivalue_line("markers", "scraper: Scraper-related tests")
    config.addinivalue_line("markers", "analysis: Analysis-related tests")
    config.addinivalue_line("markers", "dashboard: Dashboard-related tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark tests based on their path."""
    for item in items:
        if "test_scraper" in item.nodeid:
            item.add_marker(pytest.mark.scraper)
        if "test_normalizer" in item.nodeid:
            item.add_marker(pytest.mark.scraper)
        if "test_circuits" in item.nodeid or "test_statistics" in item.nodeid:
            item.add_marker(pytest.mark.analysis)
        if "test_dashboard" in item.nodeid:
            item.add_marker(pytest.mark.dashboard)
        if "test_integration" in item.nodeid or "test_performance" in item.nodeid:
            item.add_marker(pytest.mark.integration)