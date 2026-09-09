"""
Performance benchmarks for SUME Dashboard.

Benchmarks:
- Scraper: 2K expedientes < 2hr (mock HTTP)
- Analyzer: 4K expedientes < 10s
- Dashboard initial load < 3s
"""

import json
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.analysis.circuits import run_full_circuit_analysis
from src.analysis.statistics import run_full_statistics_analysis
from src.analysis.reports import generate_main_report
from src.database.connection import get_connection, close_connection, set_connection_factory
from src.database.schema import INIT_SQL
from src.config import Settings, DatabaseConfig
from src.scraper.client import SUMEClient
from src.scraper.config import ScraperConfig


# ============================================================================
# Benchmark Database Fixtures
# ============================================================================

def create_benchmark_db(num_expedientes: int, db_path: str) -> sqlite3.Connection:
    """Create a database with synthetic expedientes for benchmarking."""
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000;")

    conn.executescript(INIT_SQL)
    conn.commit()

    import random
    random.seed(42)

    conceptos = ["Gestión Alumno", "Gestión de Becas", "Trámites Docentes", "Administración General"]
    concept_weights = [0.4, 0.3, 0.2, 0.1]

    deps_by_concepto = {
        "Gestión Alumno": [
            "Mesa de Entradas - FBCB",
            "Departamento Alumnos",
            "Secretaría Académica",
            "Dirección de Carreras",
            "Consejo Directivo",
        ],
        "Gestión de Becas": [
            "Mesa de Entradas - FBCB",
            "Departamento Becas",
            "Comité Evaluador",
            "Secretaría de Bienestar",
            "Tesorería",
        ],
        "Trámites Docentes": [
            "Mesa de Entradas - FBCB",
            "Departamento Docentes",
            "Secretaría Académica",
            "Consejo Directivo",
            "Dirección de Carreras",
        ],
        "Administración General": [
            "Mesa de Entradas - FBCB",
            "Secretaría Administrativa",
            "Dirección General",
            "Asesoría Legal",
        ],
    }

    circuits_by_concepto = {
        "Gestión Alumno": [
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica"], 0.5),
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Dirección de Carreras", "Secretaría Académica"], 0.25),
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica", "Consejo Directivo"], 0.15),
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica", "Dirección de Carreras", "Consejo Directivo"], 0.05),
            (["Mesa de Entradas - FBCB", "Departamento Alumnos", "Secretaría Académica", "Departamento Alumnos"], 0.05),
        ],
        "Gestión de Becas": [
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Comité Evaluador"], 0.5),
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Secretaría de Bienestar", "Comité Evaluador"], 0.3),
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Tesorería", "Secretaría de Bienestar", "Comité Evaluador"], 0.15),
            (["Mesa de Entradas - FBCB", "Departamento Becas", "Comité Evaluador", "Departamento Becas"], 0.05),
        ],
        "Trámites Docentes": [
            (["Mesa de Entradas - FBCB", "Departamento Docentes", "Secretaría Académica"], 0.6),
            (["Mesa de Entradas - FBCB", "Departamento Docentes", "Dirección de Carreras", "Secretaría Académica"], 0.25),
            (["Mesa de Entradas - FBCB", "Departamento Docentes", "Secretaría Académica", "Consejo Directivo"], 0.15),
        ],
        "Administración General": [
            (["Mesa de Entradas - FBCB", "Secretaría Administrativa", "Dirección General"], 0.6),
            (["Mesa de Entradas - FBCB", "Secretaría Administrativa", "Asesoría Legal", "Dirección General"], 0.4),
        ],
    }

    from datetime import date, timedelta

    expediente_id = 0
    for i in range(num_expedientes):
        expediente_id += 1
        concepto = random.choices(conceptos, weights=concept_weights)[0]
        circuits = circuits_by_concepto[concepto]
        circuit_pattern = random.choices(
            [c[0] for c in circuits],
            weights=[c[1] for c in circuits]
        )[0]

        numero = f"EXP-2025-{expediente_id:06d}"
        start_date = date(2025, 1, 1)
        random_days = random.randint(0, 364)
        fecha_alta = start_date + timedelta(days=random_days)
        estado = random.choice(["En trámite", "Finalizado", "Archivado"])

        conn.execute(
            """INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                numero,
                concepto,
                f"Trámite de {concepto.lower()} - Expediente {expediente_id}",
                fecha_alta.isoformat(),
                estado,
                f"{concepto.lower().replace(' ', ',')}, tramite",
                "Mesa de Entradas - FBCB",
            ),
        )

        for orden, dep in enumerate(circuit_pattern, 1):
            mov_fecha = fecha_alta + timedelta(days=orden * random.randint(1, 5))
            conn.execute(
                """INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                   VALUES (?, ?, ?, ?)""",
                (expediente_id, orden, mov_fecha.isoformat(), dep),
            )

    all_deps = set()
    for deps in deps_by_concepto.values():
        all_deps.update(deps)

    for dep in all_deps:
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT expediente_id) FROM movimientos WHERE dependencia = ?",
            (dep,),
        )
        total = cursor.fetchone()[0]
        if total > 0:
            conn.execute(
                "INSERT INTO dependencias (nombre, nombre_original, total_expedientes) VALUES (?, ?, ?)",
                (dep, dep, total),
            )

    conn.commit()
    return conn


@pytest.fixture
def benchmark_db_2k() -> Generator[sqlite3.Connection, None, None]:
    """Create a database with 2000 expedientes for scraper/analyzer benchmarks."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = create_benchmark_db(2000, db_path)

    def factory():
        c = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000;")
        return c

    set_connection_factory(factory)

    import src.config
    original_get_settings = src.config.get_settings

    def test_get_settings():
        return Settings(
            database=DatabaseConfig(path=db_path),
            sume=Settings.model_fields["sume"].default,
            scraper=Settings.model_fields["scraper"].default,
            normalizer=Settings.model_fields["normalizer"].default,
            analyzer=Settings.model_fields["analyzer"].default,
            dashboard=Settings.model_fields["dashboard"].default,
            reporter=Settings.model_fields["reporter"].default,
        )

    src.config.get_settings = test_get_settings

    try:
        yield conn
    finally:
        close_connection()
        set_connection_factory(None)
        src.config.get_settings = original_get_settings
        conn.close()
        Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def benchmark_db_4k() -> Generator[sqlite3.Connection, None, None]:
    """Create a database with 4000 expedientes for analyzer benchmarks."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = create_benchmark_db(4000, db_path)

    def factory():
        c = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000;")
        return c

    set_connection_factory(factory)

    import src.config
    original_get_settings = src.config.get_settings

    def test_get_settings():
        return Settings(
            database=DatabaseConfig(path=db_path),
            sume=Settings.model_fields["sume"].default,
            scraper=Settings.model_fields["scraper"].default,
            normalizer=Settings.model_fields["normalizer"].default,
            analyzer=Settings.model_fields["analyzer"].default,
            dashboard=Settings.model_fields["dashboard"].default,
            reporter=Settings.model_fields["reporter"].default,
        )

    src.config.get_settings = test_get_settings

    try:
        yield conn
    finally:
        close_connection()
        set_connection_factory(None)
        src.config.get_settings = original_get_settings
        conn.close()
        Path(db_path).unlink(missing_ok=True)


# ============================================================================
# Scraper Benchmarks (Mock HTTP)
# ============================================================================

class TestScraperPerformance:
    """Performance benchmarks for scraper with mock HTTP."""

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_scraper_2k_mock_http_under_2hr(self, benchmark_db_2k):
        """
        Benchmark: Scraper processes 2K expedientes in < 2 hours with mock HTTP.

        This simulates the HTTP client layer with mocked responses to test
        the parsing, normalization, and persistence throughput.
        """
        config = ScraperConfig.load()
        client = SUMEClient(config)

        # Mock the HTTP responses to simulate fast local processing
        # We'll test the parsing + normalization + DB write pipeline directly
        # by measuring the scraper orchestrator's _process_expediente equivalent

        from src.scraper.parser import parse_detail_page, parse_movimientos_table
        from src.scraper.normalizer import get_normalizer, normalize
        from src.database import get_connection, transaction

        normalizer_rules = get_normalizer(Path(config.normalization_rules_path))

        # Create mock HTML for a typical detail page
        mock_html = """
        <html>
        <body>
            <div class="expediente-header">
                <h1>EXP-2025-000001</h1>
                <span class="concepto">Gestão Alumno</span>
            </div>
            <div class="expediente-info">
                <p><strong>Descrição:</strong> Trámite de inscrição a cursadas</p>
                <p><strong>Data Alta:</strong> 15/03/2025</p>
                <p><strong>Estado:</strong> En trámite</p>
                <p><strong>Palavras Chave:</strong> inscrição, cursadas, alumno</p>
                <p><strong>Orígenes:</strong> Mesa de Entradas FBCB</p>
            </div>
            <table class="tabla_movimientos">
                <thead>
                    <tr><th>Orden</th><th>Fecha Recepção</th><th>Dependencia</th></tr>
                </thead>
                <tbody>
                    <tr><td>1</td><td>15/03/2025</td><td>Mesa de Entradas FBCB</td></tr>
                    <tr><td>2</td><td>16/03/2025</td><td>Alumnado (Mesa de Entradas - FBCB)</td></tr>
                    <tr><td>3</td><td>18/03/2025</td><td>Departamento Alumnos</td></tr>
                    <tr><td>4</td><td>20/03/2025</td><td>Secretaría Académica</td></tr>
                </tbody>
            </table>
        </body>
        </html>
        """

        # Benchmark parsing + normalization + DB write for 2000 expedientes
        start_time = time.time()

        with transaction() as conn:
            for i in range(2000):
                # Parse
                expediente = parse_detail_page(mock_html, f"http://test.com/detail?id={i}")
                movimientos = parse_movimientos_table(mock_html)

                # Normalize
                for mov in movimientos:
                    mov.dependencia = normalize(mov.dependencia, normalizer_rules)
                if expediente.origenes:
                    expediente.origenes = normalize(expediente.origenes, normalizer_rules)

                # Persist (simplified - just measure the operations)
                cursor = conn.execute(
                    """INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origemes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"EXP-2025-{i:06d}",
                        expediente.concepto,
                        expediente.descripcion,
                        expediente.fecha_alta,
                        expediente.estado,
                        expediente.palabras_clave,
                        expediente.origenes,
                    ),
                )
                expediente_id = cursor.lastrowid

                for mov in movimientos:
                    conn.execute(
                        """INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                           VALUES (?, ?, ?, ?)""",
                        (expediente_id, mov.orden, mov.fecha_recepcion, mov.dependencia),
                    )

        elapsed = time.time() - start_time

        # 2 hours = 7200 seconds
        # With mock HTTP, this should complete in well under 2 hours
        # We set a generous threshold of 300 seconds (5 minutes) for the mocked pipeline
        max_allowed_seconds = 300  # 5 minutes for mocked pipeline
        assert elapsed < max_allowed_seconds, \
            f"Scraper mock pipeline took {elapsed:.1f}s, expected < {max_allowed_seconds}s (2hr budget for real HTTP)"

        print(f"\nScraper mock pipeline (2K expedientes): {elapsed:.2f}s")
        print(f"  Throughput: {2000/elapsed:.1f} expedientes/sec")
        print(f"  Extrapolated real HTTP (0.5s delay): ~{2000 * 0.5 / 3600:.1f} hours")

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_scraper_client_mock_latency(self):
        """Test HTTP client latency with mocked responses."""
        config = ScraperConfig.load()
        client = SUMEClient(config)

        # Mock session to return immediately
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_response):
            start_time = time.time()
            for _ in range(100):
                client.get("http://test.com/test")
            elapsed = time.time() - start_time

            # 100 requests should complete very fast with mock
            assert elapsed < 1.0, f"100 mock requests took {elapsed:.2f}s, expected < 1s"
            print(f"\n100 mock HTTP requests: {elapsed*1000:.1f}ms")


# ============================================================================
# Analyzer Benchmarks
# ============================================================================

class TestAnalyzerPerformance:
    """Performance benchmarks for analyzer."""

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_analyzer_4k_under_10s(self, benchmark_db_4k):
        """
        Benchmark: Analyzer processes 4K expedientes in < 10 seconds.

        Tests the full circuit analysis + statistics analysis pipeline.
        """
        # Warm up (first run may have overhead)
        run_full_circuit_analysis(benchmark_db_4k)

        # Benchmark circuit analysis
        start_time = time.time()
        result = run_full_circuit_analysis(benchmark_db_4k)
        circuit_time = time.time() - start_time

        # Benchmark statistics analysis
        start_time = time.time()
        stats = run_full_statistics_analysis(benchmark_db_4k)
        stats_time = time.time() - start_time

        total_time = circuit_time + stats_time

        print(f"\nAnalyzer benchmark (4K expedientes):")
        print(f"  Circuit analysis: {circuit_time:.2f}s")
        print(f"  Statistics analysis: {stats_time:.2f}s")
        print(f"  Total: {total_time:.2f}s")

        # Budget: 10 seconds for 4K expedientes
        assert total_time < 10.0, \
            f"Analyzer took {total_time:.2f}s for 4K expedientes, expected < 10s"

        # Verify correctness
        assert result["frecuencia"].sum() == 4000
        assert len(stats["step_statistics"]) == 4
        assert len(stats["concept_distribution"]) == 4

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_analyzer_2k_under_5s(self, benchmark_db_2k):
        """Benchmark: Analyzer processes 2K expedientes in < 5 seconds."""
        run_full_circuit_analysis(benchmark_db_2k)

        start_time = time.time()
        result = run_full_circuit_analysis(benchmark_db_2k)
        circuit_time = time.time() - start_time

        start_time = time.time()
        stats = run_full_statistics_analysis(benchmark_db_2k)
        stats_time = time.time() - start_time

        total_time = circuit_time + stats_time

        print(f"\nAnalyzer benchmark (2K expedientes):")
        print(f"  Circuit analysis: {circuit_time:.2f}s")
        print(f"  Statistics analysis: {stats_time:.2f}s")
        print(f"  Total: {total_time:.2f}s")

        assert total_time < 5.0, \
            f"Analyzer took {total_time:.2f}s for 2K expedientes, expected < 5s"

    @pytest.mark.benchmark
    def test_circuit_analysis_scalability(self):
        """Test that circuit analysis scales roughly linearly."""
        import random
        random.seed(42)

        times = []
        sizes = [500, 1000, 2000]

        for size in sizes:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name

            conn = create_benchmark_db(size, db_path)

            def factory():
                c = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
                c.execute("PRAGMA journal_mode=WAL;")
                c.execute("PRAGMA foreign_keys=ON;")
                c.row_factory = sqlite3.Row
                c.execute("PRAGMA busy_timeout=30000;")
                return c

            set_connection_factory(factory)

            import src.config
            original_get_settings = src.config.get_settings

            def test_get_settings():
                return Settings(
                    database=DatabaseConfig(path=db_path),
                    sume=Settings.model_fields["sume"].default,
                    scraper=Settings.model_fields["scraper"].default,
                    normalizer=Settings.model_fields["normalizer"].default,
                    analyzer=Settings.model_fields["analyzer"].default,
                    dashboard=Settings.model_fields["dashboard"].default,
                    reporter=Settings.model_fields["reporter"].default,
                )

            src.config.get_settings = test_get_settings

            run_full_circuit_analysis(conn)

            start_time = time.time()
            result = run_full_circuit_analysis(conn)
            elapsed = time.time() - start_time
            times.append(elapsed)

            close_connection()
            set_connection_factory(None)
            src.config.get_settings = original_get_settings
            conn.close()
            Path(db_path).unlink(missing_ok=True)

            print(f"  {size} expedientes: {elapsed:.2f}s")

        # Check roughly linear scaling (ratio should be ~2x for 2x data)
        if len(times) >= 2:
            ratio = times[-1] / times[0]
            size_ratio = sizes[-1] / sizes[0]
            # Allow some overhead, but should not be quadratic
            assert ratio < size_ratio * 1.5, \
                f"Scaling ratio {ratio:.2f}x for {size_ratio}x data suggests super-linear complexity"


# ============================================================================
# Dashboard Benchmarks
# ============================================================================

class TestDashboardPerformance:
    """Performance benchmarks for dashboard data loading."""

    @pytest.mark.slow
    @pytest.mark.benchmark
    def test_dashboard_initial_load_under_3s(self, benchmark_db_2k):
        """
        Benchmark: Dashboard initial data load < 3 seconds.

        Tests all cached data loading functions that run on initial page load.
        """
        from src.dashboard.data import (
            load_expedientes,
            load_circuitos,
            load_step_stats,
            load_permanence,
            load_dependencias,
            load_conceptos,
            load_dependency_traffic,
            load_concept_distribution,
            load_monthly_trend,
            FilterState,
            invalidate_cache,
        )

        # Ensure analysis is done first
        run_full_circuit_analysis(benchmark_db_2k)
        run_full_statistics_analysis(benchmark_db_2k)

        # Clear cache to simulate cold start
        invalidate_cache()

        start_time = time.time()

        # Load all data needed for initial dashboard render
        expedientes_df = load_expedientes(FilterState())
        circuitos_df = load_circuitos()
        step_stats_df = load_step_stats()
        permanence_df = load_permanence()
        dependencias_df = load_dependencias()
        conceptos_df = load_conceptos()
        dep_traffic_df = load_dependency_traffic(FilterState())
        conc_dist_df = load_concept_distribution(FilterState())
        monthly_df = load_monthly_trend(FilterState())

        elapsed = time.time() - start_time

        print(f"\nDashboard initial load benchmark (2K expedientes):")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  expedientes: {len(expedientes_df)} rows")
        print(f"  circuitos: {len(circuitos_df)} rows")
        print(f"  step_stats: {len(step_stats_df)} rows")
        print(f"  permanence: {len(permanence_df)} rows")
        print(f"  dependencias: {len(dependencias_df)} rows")
        print(f"  conceptos: {len(conceptos_df)} rows")
        print(f"  dependency_traffic: {len(dep_traffic_df)} rows")
        print(f"  concept_distribution: {len(conc_dist_df)} rows")
        print(f"  monthly_trend: {len(monthly_df)} rows")

        # Budget: 3 seconds for initial load
        assert elapsed < 3.0, \
            f"Dashboard initial load took {elapsed:.2f}s, expected < 3s"

        # Verify data integrity
        assert len(expedientes_df) == 2000
        assert len(circuitos_df) > 0
        assert len(step_stats_df) == 4

    @pytest.mark.benchmark
    def test_dashboard_cached_load_fast(self, benchmark_db_2k):
        """Test that cached dashboard loads are very fast (< 500ms)."""
        from src.dashboard.data import (
            load_expedientes,
            load_circuitos,
            load_step_stats,
            FilterState,
            invalidate_cache,
        )

        run_full_circuit_analysis(benchmark_db_2k)
        run_full_statistics_analysis(benchmark_db_2k)

        # First load (populates cache)
        _ = load_expedientes(FilterState())
        _ = load_circuitos()
        _ = load_step_stats()

        # Second load (should hit cache)
        start_time = time.time()
        _ = load_expedientes(FilterState())
        _ = load_circuitos()
        _ = load_step_stats()
        elapsed = time.time() - start_time

        print(f"\nDashboard cached load: {elapsed*1000:.1f}ms")

        # Cached loads should be very fast
        assert elapsed < 0.5, f"Cached load took {elapsed*1000:.1f}ms, expected < 500ms"


# ============================================================================
# Report Generation Benchmarks
# ============================================================================

class TestReportPerformance:
    """Performance benchmarks for report generation."""

    @pytest.mark.benchmark
    def test_report_generation_under_5s(self, benchmark_db_2k):
        """Test that report generation completes in reasonable time."""
        run_full_circuit_analysis(benchmark_db_2k)
        run_full_statistics_analysis(benchmark_db_2k)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "benchmark_report.md"

            start_time = time.time()
            generate_main_report(
                output_path=output_path,
                format_type="markdown",
                db=benchmark_db_2k,
                templates_dir="templates",
            )
            elapsed = time.time() - start_time

            print(f"\nReport generation (2K expedientes): {elapsed:.2f}s")

            assert elapsed < 5.0, f"Report generation took {elapsed:.2f}s, expected < 5s"
            assert output_path.exists()
            assert output_path.stat().st_size > 0


# ============================================================================
# Summary
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark"])