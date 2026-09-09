"""
HTML parser for SUME pages.

Extracts structured data from SUME listing pages, detail pages,
and movimientos tables using robust CSS selectors.
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scraper.config import SelectorConfig


@dataclass
class ExpedienteDict:
    """Parsed expediente data from detail page."""

    numero: str
    concepto: str
    descripcion: Optional[str]
    fecha_alta: str
    estado: Optional[str]
    palabras_clave: Optional[str]
    origenes: Optional[str]
    detail_url: str


@dataclass
class MovimientoDict:
    """Parsed movimiento (pase) data."""

    orden: int
    fecha_recepcion: str
    dependencia: str


@dataclass
class ListingResult:
    """Result of parsing a listing page."""

    detail_urls: list[str]
    next_page_url: Optional[str]


def parse_listing_page(html: str, base_url: str, selectors: Optional[SelectorConfig] = None) -> ListingResult:
    """
    Parse a SUME listing page to extract detail URLs and pagination.

    Args:
        html: Raw HTML content of the listing page
        base_url: Base URL for resolving relative links
        selectors: CSS selector configuration (uses defaults if None)

    Returns:
        ListingResult with detail URLs and next page URL.
    """
    selectors = selectors or SelectorConfig()
    soup = BeautifulSoup(html, "lxml")

    detail_urls = []

    # Find the expedientes table
    table = soup.select_one(selectors.listing_table)
    if table:
        # Try tbody tr first, then fallback to direct tr children
        rows = table.select(selectors.listing_rows)
        if not rows:
            rows = table.select("tr")
        for row in rows:
            link = row.select_one(selectors.listing_detail_link)
            if link and link.get("href"):
                href = link["href"]
                full_url = urljoin(base_url, href)
                detail_urls.append(full_url)

    # Find next page URL
    next_page_url = None
    pagination = soup.select_one(selectors.pagination_container)
    if pagination:
        links = pagination.select(selectors.pagination_links)
        for link in links:
            text = link.get_text(strip=True)
            # Look for "Siguiente" or "Next" or page number > current
            if text.lower() in ("siguiente", "next", "»"):
                href = link.get("href")
                if href:
                    next_page_url = urljoin(base_url, href)
                    break
            # Also check for numeric pagination - find the current page and get next
            elif text.isdigit():
                # This is a simple approach - in reality we'd need to know current page
                pass

    return ListingResult(detail_urls=detail_urls, next_page_url=next_page_url)


def parse_detail_page(html: str, url: str, selectors: Optional[SelectorConfig] = None) -> ExpedienteDict:
    """
    Parse a SUME expediente detail page.

    Args:
        html: Raw HTML content of the detail page
        url: Source URL of the detail page
        selectors: CSS selector configuration (uses defaults if None)

    Returns:
        ExpedienteDict with all extracted fields.

    Raises:
        ValueError: If required fields (numero, concepto, fecha_alta) are missing.
    """
    selectors = selectors or SelectorConfig()
    soup = BeautifulSoup(html, "lxml")

    # Extract numero
    numero_elem = soup.select_one(selectors.detail_numero)
    numero = numero_elem.get_text(strip=True) if numero_elem else ""
    if not numero:
        # Fallback: try to extract from URL
        match = re.search(r"id=(\d+)", url)
        if match:
            numero = f"EXP-{match.group(1)}"
        else:
            raise ValueError(f"Could not extract numero from detail page: {url}")

    # Extract concepto
    concepto_elem = soup.select_one(selectors.detail_concepto)
    concepto = concepto_elem.get_text(strip=True) if concepto_elem else ""
    if not concepto:
        raise ValueError(f"Missing required field 'concepto' in detail page: {url}")

    # Extract info fields from the info container
    info_container = soup.select_one(selectors.detail_info_container)
    descripcion = None
    fecha_alta = ""
    estado = None
    palabras_clave = None
    origenes = None

    if info_container:
        # Find all paragraphs with strong labels
        for p in info_container.select("p"):
            strong = p.select_one("strong")
            if strong:
                label = strong.get_text(strip=True).rstrip(":")
                # Get the text after the strong element
                value = p.get_text(strip=True)[len(label):].strip().lstrip(":").strip()

                if label.lower() in ("descripción", "descripcion"):
                    descripcion = value if value else None
                elif label.lower() in ("fecha alta", "fecha de alta"):
                    fecha_alta = _normalize_date(value)
                elif label.lower() == "estado":
                    estado = value if value else None
                elif label.lower() in ("palabras clave", "palabras-clave"):
                    palabras_clave = value if value else None
                elif label.lower() in ("orígenes", "origenes", "origen"):
                    origenes = value if value else None

    if not fecha_alta:
        raise ValueError(f"Missing required field 'fecha_alta' in detail page: {url}")

    return ExpedienteDict(
        numero=numero,
        concepto=concepto,
        descripcion=descripcion,
        fecha_alta=fecha_alta,
        estado=estado,
        palabras_clave=palabras_clave,
        origenes=origenes,
        detail_url=url,
    )


def parse_movimientos_table(html: str, selectors: Optional[SelectorConfig] = None) -> list[MovimientoDict]:
    """
    Parse the movimientos (pases) table from a detail page.

    Args:
        html: Raw HTML content (can be full page or just table)
        selectors: CSS selector configuration (uses defaults if None)

    Returns:
        List of MovimientoDict with orden, fecha_recepcion, dependencia.
    """
    selectors = selectors or SelectorConfig()
    soup = BeautifulSoup(html, "lxml")

    movimientos = []

    table = soup.select_one(selectors.movimientos_table)
    if not table:
        return movimientos

    rows = table.select(selectors.movimientos_rows)
    for i, row in enumerate(rows, start=1):
        cells = row.select(selectors.movimientos_cells)
        if len(cells) >= 3:
            # Expected columns: Orden, Fecha Recepción, Dependencia
            orden_text = cells[0].get_text(strip=True)
            fecha_text = cells[1].get_text(strip=True)
            dependencia = cells[2].get_text(strip=True)

            try:
                orden = int(orden_text) if orden_text.isdigit() else i
            except ValueError:
                orden = i

            fecha_recepcion = _normalize_date(fecha_text)

            if dependencia:
                movimientos.append(MovimientoDict(
                    orden=orden,
                    fecha_recepcion=fecha_recepcion,
                    dependencia=dependencia,
                ))

    return movimientos


def _normalize_date(date_str: str) -> str:
    """
    Normalize date string to YYYY-MM-DD format.

    Handles formats like:
    - DD/MM/YYYY
    - DD-MM-YYYY
    - YYYY-MM-DD (already normalized)
    """
    date_str = date_str.strip()

    # Already in ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # DD/MM/YYYY or DD-MM-YYYY
    match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # Try to parse with dateutil if available, otherwise return as-is
    try:
        from dateutil import parser as date_parser
        parsed = date_parser.parse(date_str, dayfirst=True)
        return parsed.strftime("%Y-%m-%d")
    except (ImportError, ValueError):
        return date_str  # Return as-is if unable to parse