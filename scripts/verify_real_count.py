"""
Verificar cuántos expedientes FBCB 2025 existen realmente en SUME.
Usar búsqueda avanzada sin filtro de oficina para traer todos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scraper.client import SUMEClient
from src.scraper.config import ScraperConfig
from src.scraper.parser import parse_listing_page

config = ScraperConfig.load()
client = SUMEClient(config)

print("=" * 70)
print("VERIFICACIÓN: ¿Cuántos expedientes FBCB 2025 existen en SUME?")
print("=" * 70)

# Búsqueda: solo filtro de número FBCB + fecha (sin mesa de entrada)
params = {
    "numero": "FBCB",
    "descripcion": "",
    "palabraClave": "",
    "selectOrigen": "interno",
    "mesaEntrada": "",
    "oficina": "",
    "concepto": "",
    "fechaCdesde": "01/01/2025",
    "fechaChasta": "31/12/2025",
    "tipoDR": "",
    "numeroDR": "",
}

result = client.request("POST", f"{config.base_url}buscar/", data=params)
print(f"Status: {result.status_code}")

if result.status_code == 200:
    listing = parse_listing_page(result.content, config.base_url)
    print(f"Total páginas: {listing.total_pages}")
    print(f"Expedientes en página 1: {len(listing.expedientes)}")
    print(f"Total estimado: {listing.total_pages * len(listing.expedientes)}")
    
    if listing.expedientes:
        print("\nPrimeros 5 expedientes:")
        for i, exp in enumerate(listing.expedientes[:5], 1):
            print(f"  {i}. {exp.numero} - {exp.concepto} ({exp.fecha_alta})")
else:
    print(f"Error: {result.error}")

# Búsqueda 2: sin filtro de número (solo fecha)
print("\n--- Búsqueda 2: Solo filtro de fecha (sin número) ---")
params2 = {
    "numero": "",
    "descripcion": "",
    "palabraClave": "",
    "selectOrigen": "interno",
    "mesaEntrada": "",
    "oficina": "",
    "concepto": "",
    "fechaCdesde": "01/01/2025",
    "fechaChasta": "31/12/2025",
    "tipoDR": "",
    "numeroDR": "",
}

result2 = client.request("POST", f"{config.base_url}buscar/", data=params2)
print(f"Status: {result2.status_code}")

if result2.status_code == 200:
    listing2 = parse_listing_page(result2.content, config.base_url)
    print(f"Total páginas: {listing2.total_pages}")
    print(f"Expedientes en página 1: {len(listing2.expedientes)}")
    print(f"Total estimado: {listing2.total_pages * len(listing2.expedientes)}")
else:
    print(f"Error: {result2.error}")

client.close()
