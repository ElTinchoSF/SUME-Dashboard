"""
Script rápido para verificar cuántas páginas tiene SUME.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scraper.client import SUMEClient
from src.scraper.config import ScraperConfig
from src.scraper.parser import parse_listing_page

config = ScraperConfig.load()
client = SUMEClient(config)

# Fetch first page with date filters
search_params = config.get_search_params(
    date_from="2025-01-01",
    date_to="2025-12-31"
)
result = client.search(search_params)

if result.error:
    print(f"Error: {result.error}")
    sys.exit(1)

print(f"Status: {result.status_code}")
print(f"Content length: {len(result.content)} chars")

# Parse listing
listing = parse_listing_page(result.content, config.base_url)
print(f"Total pages detected: {listing.total_pages}")
print(f"Expedientes on first page: {len(listing.expedientes)}")
print(f"Next page: {listing.next_page_num}")

# Show first 3 expedientes
for i, exp in enumerate(listing.expedientes[:3], 1):
    print(f"  {i}. {exp.numero} - {exp.concepto} ({exp.fecha_alta})")

client.close()
