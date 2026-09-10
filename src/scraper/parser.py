"""
HTML parser for SUME pages.

Extracts structured data from SUME listing pages, detail pages,
and movimientos tables using robust CSS selectors.

Updated for new SUME structure (2026):
- Listing page: table with onclick handlers (numero, descripcion, concepto, origen, fecha_alta, ultimo_movimiento)
- Detail page: movimientos table (fecha_envio, fecha_recepcion, dependencia_destino)
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scraper.config import SelectorConfig


@dataclass
class ExpedienteDict:
    """Parsed expediente data from listing page."""

    numero: str
    concepto: str
    descripcion: Optional[str]
    fecha_alta: str
    estado: Optional[str]
    palabras_clave: Optional[str]
    origenes: Optional[str]
    detail_url: str
    ultimo_movimiento: Optional[str] = None


@dataclass
class MovimientoDict:
    """Parsed movimiento (pase) data."""

    orden: int
    fecha_envio: str
    fecha_recepcion: str
    dependencia: str


@dataclass
class ListingResult:
    """Result of parsing a listing page."""

    expedientes: list[ExpedienteDict]
    next_page_num: Optional[int]
    total_pages: int


def parse_listing_page(html: str, base_url: str, selectors: Optional[SelectorConfig] = None) -> ListingResult:
    """
    Parse a SUME listing page to extract expedientes and pagination.

    Args:
        html: Raw HTML content of the listing page
        base_url: Base URL for resolving relative links
        selectors: CSS selector configuration (uses defaults if None)

    Returns:
        ListingResult with expedientes data and pagination info.
    """
    selectors = selectors or SelectorConfig()
    soup = BeautifulSoup(html, "lxml")

    expedientes = []

    # Find the expedientes table
    table = soup.select_one(selectors.listing_table)
    if table:
        rows = table.select(selectors.listing_rows)
        if not rows:
            rows = table.select("tr")

        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue

            # Extract onclick URL
            onclick = row.get("onclick", "")
            match = re.search(r"location\.href='([^']+)'", onclick)
            if not match:
                continue

            detail_path = match.group(1)
            detail_url = urljoin(base_url, detail_path)

            # Extract numero (first cell)
            numero = cells[0].get_text(strip=True)
            # Clean up numero (remove extra info like (92001))
            numero = re.sub(r"\s*\(\d+\)\s*$", "", numero)

            # Extract other fields
            descripcion = cells[1].get_text(strip=True) or None
            concepto = cells[2].get_text(strip=True)
            origen = cells[3].get_text(strip=True) or None
            fecha_alta = _normalize_date(cells[4].get_text(strip=True))
            ultimo_movimiento = _normalize_date(cells[5].get_text(strip=True)) if cells[5].get_text(strip=True) else None

            if numero and concepto:
                expedientes.append(ExpedienteDict(
                    numero=numero,
                    concepto=concepto,
                    descripcion=descripcion,
                    fecha_alta=fecha_alta,
                    estado=None,
                    palabras_clave=None,
                    origenes=origen,
                    detail_url=detail_url,
                    ultimo_movimiento=ultimo_movimiento,
                ))

    # Parse pagination
    next_page_num = None
    total_pages = 1

    pagination = soup.select_one(selectors.pagination_container)
    if pagination:
        links = pagination.select(selectors.pagination_links)

        # Find total pages (last numeric page link)
        max_page = 1
        current_page = 1
        for link in links:
            text = link.get_text(strip=True)
            if text.isdigit():
                page_num = int(text)
                max_page = max(max_page, page_num)
                # Check if this link is active (current page)
                if "active" in " ".join(link.get("class", [])):
                    current_page = page_num

        total_pages = max_page

        # Find "Siguiente" link
        for link in links:
            text = link.get_text(strip=True)
            if text == "Siguiente":
                href = link.get("href", "")
                page_match = re.search(r"buscar/(\d+)/", href)
                if page_match:
                    next_page_num = int(page_match.group(1))
                break

    return ListingResult(
        expedientes=expedientes,
        next_page_num=next_page_num,
        total_pages=total_pages,
    )


def parse_detail_page(html: str, url: str, selectors: Optional[SelectorConfig] = None) -> ExpedienteDict:
    """
    Parse a SUME expediente detail page.

    Note: The new SUME detail page is minimal - it only shows the expediente
    number and movements table. Most data comes from the listing page.

    Args:
        html: Raw HTML content of the detail page
        url: Source URL of the detail page
        selectors: CSS selector configuration (uses defaults if None)

    Returns:
        ExpedienteDict with extracted fields.

    Raises:
        ValueError: If required fields (numero) are missing.
    """
    selectors = selectors or SelectorConfig()
    soup = BeautifulSoup(html, "lxml")

    # Extract numero from the page
    numero = ""

    # Try the label element
    numero_elem = soup.select_one(selectors.detail_numero)
    if numero_elem:
        numero = numero_elem.get_text(strip=True)

    # Fallback: extract from URL
    if not numero:
        match = re.search(r"expediente/([^/]+)$", url)
        if match:
            numero = match.group(1)

    if not numero:
        raise ValueError(f"Could not extract numero from detail page: {url}")

    # The detail page doesn't have concepto, descripcion, etc.
    # These should come from the listing page
    return ExpedienteDict(
        numero=numero,
        concepto="",  # Will be filled from listing page
        descripcion=None,
        fecha_alta="",  # Will be filled from listing page
        estado=None,
        palabras_clave=None,
        origenes=None,
        detail_url=url,
    )


def parse_movimientos_table(html: str, selectors: Optional[SelectorConfig] = None) -> list[MovimientoDict]:
    """
    Parse the movimientos (pases) table from a detail page.

    Args:
        html: Raw HTML content (can be full page or just table)
        selectors: CSS selector configuration (uses defaults if None)

    Returns:
        List of MovimientoDict with orden, fecha_envio, fecha_recepcion, dependencia.
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
            # New table columns: Fecha de envío, Fecha de recepción, Dependencia destino
            fecha_envio = _normalize_date(cells[0].get_text(strip=True))
            fecha_recepcion = _normalize_date(cells[1].get_text(strip=True))
            dependencia = cells[2].get_text(strip=True)

            if dependencia:
                movimientos.append(MovimientoDict(
                    orden=i,
                    fecha_envio=fecha_envio,
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

    if not date_str:
        return ""

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
