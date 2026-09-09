"""
Unit tests for SUME HTML parser.

Tests cover:
- Listing page parsing (detail URLs + pagination)
- Detail page parsing (all fields)
- Movimientos table parsing
- Edge cases (missing fields, empty tables)
"""

import pytest
from bs4 import BeautifulSoup

from src.scraper.parser import (
    parse_listing_page,
    parse_detail_page,
    parse_movimientos_table,
    ExpedienteDict,
    MovimientoDict,
    ListingResult,
)
from src.scraper.config import SelectorConfig


# ============================================================================
# HTML Fixtures
# ============================================================================

SAMPLE_LISTING_HTML = """
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
            <tr>
                <td>EXP-2025-00003</td>
                <td>Certificación de Estudios</td>
                <td>17/03/2025</td>
                <td>En trámite</td>
                <td><a href="ver_expediente.php?id=12347">Ver</a></td>
            </tr>
        </tbody>
    </table>
    <div class="pagination">
        <a href="busqueda_avanzada.php?page=1">1</a>
        <a href="busqueda_avanzada.php?page=2">2</a>
        <a href="busqueda_avanzada.php?page=3">3</a>
        <a href="busqueda_avanzada.php?page=2">Siguiente</a>
    </div>
</body>
</html>
"""

SAMPLE_LISTING_EMPTY_HTML = """
<html>
<body>
    <table class="tabla_expedientes">
        <thead>
            <tr><th>Número</th><th>Concepto</th><th>Fecha Alta</th><th>Estado</th><th>Acciones</th></tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <div class="pagination"></div>
</body>
</html>
"""

SAMPLE_LISTING_NO_PAGINATION_HTML = """
<html>
<body>
    <table class="tabla_expedientes">
        <tbody>
            <tr>
                <td>EXP-2025-00001</td>
                <td>Gestión Alumno</td>
                <td>15/03/2025</td>
                <td>En trámite</td>
                <td><a href="ver_expediente.php?id=12345">Ver</a></td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""

SAMPLE_DETAIL_HTML = """
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

SAMPLE_DETAIL_MINIMAL_HTML = """
<html>
<body>
    <div class="expediente-header">
        <h1>EXP-2025-00002</h1>
        <span class="concepto">Gestión de Becas</span>
    </div>
    <div class="expediente-info">
        <p><strong>Fecha Alta:</strong> 16/03/2025</p>
    </div>
    <table class="tabla_movimientos">
        <tbody></tbody>
    </table>
</body>
</html>
"""

SAMPLE_DETAIL_MISSING_REQUIRED_HTML = """
<html>
<body>
    <div class="expediente-header">
        <h1>EXP-2025-00003</h1>
    </div>
    <div class="expediente-info">
        <p><strong>Fecha Alta:</strong> 17/03/2025</p>
    </div>
</body>
</html>
"""

SAMPLE_MOVIMIENTOS_HTML = """
<table class="tabla_movimientos">
    <thead>
        <tr><th>Orden</th><th>Fecha Recepción</th><th>Dependencia</th></tr>
    </thead>
    <tbody>
        <tr><td>1</td><td>15/03/2025</td><td>Mesa de Entradas FBCB</td></tr>
        <tr><td>2</td><td>16/03/2025</td><td>Departamento Alumnos</td></tr>
        <tr><td>3</td><td>18/03/2025</td><td>Secretaría Académica</td></tr>
    </tbody>
</table>
"""

SAMPLE_MOVIMIENTOS_EMPTY_HTML = """
<table class="tabla_movimientos">
    <thead><tr><th>Orden</th><th>Fecha Recepción</th><th>Dependencia</th></tr></thead>
    <tbody></tbody>
</table>
"""

SAMPLE_MOVIMIENTOS_MALFORMED_HTML = """
<table class="tabla_movimientos">
    <tbody>
        <tr><td>1</td><td>15/03/2025</td></tr>
        <tr><td>2</td></tr>
        <tr><td></td><td></td><td>Solo dependencia</td></tr>
    </tbody>
</table>
"""

BASE_URL = "https://servicios.unl.edu.ar/expedientes/"


# ============================================================================
# Listing Page Tests
# ============================================================================

class TestParseListingPage:
    """Tests for parse_listing_page function."""

    def test_parse_listing_happy_path(self):
        """Test parsing a standard listing page with results and pagination."""
        result = parse_listing_page(SAMPLE_LISTING_HTML, BASE_URL)

        assert isinstance(result, ListingResult)
        assert len(result.detail_urls) == 3
        assert result.detail_urls[0] == "https://servicios.unl.edu.ar/expedientes/ver_expediente.php?id=12345"
        assert result.detail_urls[1] == "https://servicios.unl.edu.ar/expedientes/ver_expediente.php?id=12346"
        assert result.detail_urls[2] == "https://servicios.unl.edu.ar/expedientes/ver_expediente.php?id=12347"
        assert result.next_page_url is not None
        assert "page=2" in result.next_page_url

    def test_parse_listing_empty_results(self):
        """Test parsing a listing page with zero results."""
        result = parse_listing_page(SAMPLE_LISTING_EMPTY_HTML, BASE_URL)

        assert len(result.detail_urls) == 0
        assert result.next_page_url is None

    def test_parse_listing_no_pagination(self):
        """Test parsing a listing page without pagination controls."""
        result = parse_listing_page(SAMPLE_LISTING_NO_PAGINATION_HTML, BASE_URL)

        assert len(result.detail_urls) == 1
        assert result.next_page_url is None

    def test_parse_listing_relative_urls(self):
        """Test that relative URLs are resolved against base_url."""
        html = """
        <table class="tabla_expedientes">
            <tbody>
                <tr><td>EXP-1</td><td>Concepto</td><td>01/01/2025</td><td>Estado</td>
                <td><a href="/expedientes/ver_expediente.php?id=999">Ver</a></td></tr>
            </tbody>
        </table>
        """
        result = parse_listing_page(html, "https://servicios.unl.edu.ar/")
        assert result.detail_urls[0] == "https://servicios.unl.edu.ar/expedientes/ver_expediente.php?id=999"

    def test_parse_listing_custom_selectors(self):
        """Test parsing with custom selector configuration."""
        custom_html = """
        <div class="custom-table">
            <div class="custom-row">
                <a class="custom-link" href="detail.php?id=1">Link</a>
            </div>
        </div>
        <div class="custom-pager">
            <a href="page2.php">Next</a>
        </div>
        """
        selectors = SelectorConfig(
            listing_table="div.custom-table",
            listing_rows="div.custom-row",
            listing_detail_link="a.custom-link",
            pagination_container="div.custom-pager",
            pagination_links="a",
        )
        result = parse_listing_page(custom_html, BASE_URL, selectors)
        assert len(result.detail_urls) == 1
        assert result.next_page_url is not None


# ============================================================================
# Detail Page Tests
# ============================================================================

class TestParseDetailPage:
    """Tests for parse_detail_page function."""

    def test_parse_detail_happy_path(self):
        """Test parsing a complete detail page with all fields."""
        expediente = parse_detail_page(SAMPLE_DETAIL_HTML, "https://example.com/ver_expediente.php?id=12345")

        assert isinstance(expediente, ExpedienteDict)
        assert expediente.numero == "EXP-2025-00001"
        assert expediente.concepto == "Gestión Alumno"
        assert expediente.descripcion == "Trámite de inscripción a cursadas"
        assert expediente.fecha_alta == "2025-03-15"
        assert expediente.estado == "En trámite"
        assert expediente.palabras_clave == "inscripción, cursadas, alumno"
        assert expediente.origenes == "Mesa de Entradas FBCB"
        assert expediente.detail_url == "https://example.com/ver_expediente.php?id=12345"

    def test_parse_detail_minimal_fields(self):
        """Test parsing a detail page with only required fields."""
        expediente = parse_detail_page(SAMPLE_DETAIL_MINIMAL_HTML, "https://example.com/detail?id=2")

        assert expediente.numero == "EXP-2025-00002"
        assert expediente.concepto == "Gestión de Becas"
        assert expediente.fecha_alta == "2025-03-16"
        assert expediente.descripcion is None
        assert expediente.estado is None
        assert expediente.palabras_clave is None
        assert expediente.origenes is None

    def test_parse_detail_missing_concepto_raises(self):
        """Test that missing concepto raises ValueError."""
        with pytest.raises(ValueError, match="concepto"):
            parse_detail_page(SAMPLE_DETAIL_MISSING_REQUIRED_HTML, "https://example.com/detail?id=3")

    def test_parse_detail_missing_fecha_alta_raises(self):
        """Test that missing fecha_alta raises ValueError."""
        html = """
        <div class="expediente-header">
            <h1>EXP-1</h1>
            <span class="concepto">Test</span>
        </div>
        <div class="expediente-info">
            <p><strong>Descripción:</strong> Test</p>
        </div>
        """
        with pytest.raises(ValueError, match="fecha_alta"):
            parse_detail_page(html, "https://example.com/detail?id=1")

    def test_parse_detail_missing_numero_fallback(self):
        """Test numero extraction falls back to URL when missing from HTML."""
        html = """
        <div class="expediente-header">
            <span class="concepto">Test</span>
        </div>
        <div class="expediente-info">
            <p><strong>Fecha Alta:</strong> 01/01/2025</p>
        </div>
        """
        expediente = parse_detail_page(html, "https://example.com/ver_expediente.php?id=99999")
        assert expediente.numero == "EXP-99999"

    def test_parse_detail_date_normalization(self):
        """Test various date formats are normalized to YYYY-MM-DD."""
        test_cases = [
            ("15/03/2025", "2025-03-15"),
            ("15-03-2025", "2025-03-15"),
            ("2025-03-15", "2025-03-15"),
            ("1/3/2025", "2025-03-01"),
        ]

        for input_date, expected in test_cases:
            html = f"""
            <div class="expediente-header">
                <h1>EXP-1</h1>
                <span class="concepto">Test</span>
            </div>
            <div class="expediente-info">
                <p><strong>Fecha Alta:</strong> {input_date}</p>
            </div>
            """
            expediente = parse_detail_page(html, "https://example.com/detail?id=1")
            assert expediente.fecha_alta == expected, f"Failed for input: {input_date}"

    def test_parse_detail_empty_optional_fields(self):
        """Test empty optional fields become None."""
        html = """
        <div class="expediente-header">
            <h1>EXP-1</h1>
            <span class="concepto">Test</span>
        </div>
        <div class="expediente-info">
            <p><strong>Fecha Alta:</strong> 01/01/2025</p>
            <p><strong>Descripción:</strong> </p>
            <p><strong>Estado:</strong> </p>
        </div>
        """
        expediente = parse_detail_page(html, "https://example.com/detail?id=1")
        assert expediente.descripcion is None
        assert expediente.estado is None


# ============================================================================
# Movimientos Table Tests
# ============================================================================

class TestParseMovimientosTable:
    """Tests for parse_movimientos_table function."""

    def test_parse_movimientos_happy_path(self):
        """Test parsing a complete movimientos table."""
        movimientos = parse_movimientos_table(SAMPLE_MOVIMIENTOS_HTML)

        assert len(movimientos) == 3
        assert all(isinstance(m, MovimientoDict) for m in movimientos)

        assert movimientos[0].orden == 1
        assert movimientos[0].fecha_recepcion == "2025-03-15"
        assert movimientos[0].dependencia == "Mesa de Entradas FBCB"

        assert movimientos[1].orden == 2
        assert movimientos[1].fecha_recepcion == "2025-03-16"
        assert movimientos[1].dependencia == "Departamento Alumnos"

        assert movimientos[2].orden == 3
        assert movimientos[2].fecha_recepcion == "2025-03-18"
        assert movimientos[2].dependencia == "Secretaría Académica"

    def test_parse_movimientos_empty_table(self):
        """Test parsing an empty movimientos table."""
        movimientos = parse_movimientos_table(SAMPLE_MOVIMIENTOS_EMPTY_HTML)
        assert len(movimientos) == 0

    def test_parse_movimientos_malformed_rows(self):
        """Test parsing handles malformed rows gracefully."""
        movimientos = parse_movimientos_table(SAMPLE_MOVIMIENTOS_MALFORMED_HTML)
        # Only rows with at least 3 cells should be parsed
        assert len(movimientos) == 1
        assert movimientos[0].dependencia == "Solo dependencia"

    def test_parse_movimientos_from_full_page(self):
        """Test parsing movimientos from a full detail page HTML."""
        movimientos = parse_movimientos_table(SAMPLE_DETAIL_HTML)
        assert len(movimientos) == 4

    def test_parse_movimientos_orden_fallback(self):
        """Test orden falls back to row index when not numeric."""
        html = """
        <table class="tabla_movimientos">
            <tbody>
                <tr><td>Primero</td><td>01/01/2025</td><td>Dep A</td></tr>
                <tr><td>Segundo</td><td>02/01/2025</td><td>Dep B</td></tr>
            </tbody>
        </table>
        """
        movimientos = parse_movimientos_table(html)
        assert len(movimientos) == 2
        assert movimientos[0].orden == 1
        assert movimientos[1].orden == 2

    def test_parse_movimientos_date_normalization(self):
        """Test date normalization in movimientos."""
        html = """
        <table class="tabla_movimientos">
            <tbody>
                <tr><td>1</td><td>15/03/2025</td><td>Dep A</td></tr>
                <tr><td>2</td><td>2025-03-16</td><td>Dep B</td></tr>
            </tbody>
        </table>
        """
        movimientos = parse_movimientos_table(html)
        assert movimientos[0].fecha_recepcion == "2025-03-15"
        assert movimientos[1].fecha_recepcion == "2025-03-16"


# ============================================================================
# Integration Tests
# ============================================================================

class TestParserIntegration:
    """Integration tests combining listing and detail parsing."""

    def test_full_listing_to_detail_flow(self):
        """Test the flow from listing page to detail pages."""
        # Parse listing
        listing = parse_listing_page(SAMPLE_LISTING_HTML, BASE_URL)
        assert len(listing.detail_urls) == 3

        # Parse each detail (simulated - would normally fetch)
        for detail_url in listing.detail_urls:
            # In real usage, you'd fetch the detail page
            # Here we just verify URL format
            assert "ver_expediente.php?id=" in detail_url
            assert detail_url.startswith(BASE_URL)


# ============================================================================
# Edge Cases
# ============================================================================

class TestParserEdgeCases:
    """Edge case tests for parser robustness."""

    def test_parse_with_malformed_html(self):
        """Test parser handles malformed HTML gracefully."""
        html = """
        <html><body>
        <table class="tabla_expedientes">
        <tr><td>EXP-1</td><td>Concepto</td><td>01/01/2025</td><td>Estado</td>
        <td><a href="detail?id=1">Ver</a></td></tr>
        </table>
        </body></html>
        """
        # Missing tbody, thead - should still work
        result = parse_listing_page(html, BASE_URL)
        assert len(result.detail_urls) == 1

    def test_parse_detail_with_special_characters(self):
        """Test parsing handles special characters in fields."""
        html = """
        <div class="expediente-header">
            <h1>EXP-2025-00001</h1>
            <span class="concepto">Gestión Alumño & "Becas"</span>
        </div>
        <div class="expediente-info">
            <p><strong>Fecha Alta:</strong> 15/03/2025</p>
            <p><strong>Descripción:</strong> Trámite con "comillas" y <tags></p>
        </div>
        """
        expediente = parse_detail_page(html, "https://example.com/detail?id=1")
        assert "Alumño" in expediente.concepto
        assert "comillas" in expediente.descripcion

    def test_parse_movimientos_with_special_chars(self):
        """Test parsing movimientos with special characters in dependency names."""
        html = """
        <table class="tabla_movimientos">
            <tbody>
                <tr><td>1</td><td>15/03/2025</td><td>Mesa de Entradas FBCB (Of. Central)</td></tr>
                <tr><td>2</td><td>16/03/2025</td><td>Dpto. Alumnos & Becas</td></tr>
            </tbody>
        </table>
        """
        movimientos = parse_movimientos_table(html)
        assert len(movimientos) == 2
        assert "Of. Central" in movimientos[0].dependencia
        assert "Becas" in movimientos[1].dependencia


if __name__ == "__main__":
    pytest.main([__file__, "-v"])