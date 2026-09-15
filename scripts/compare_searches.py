"""
Comparar búsquedas: original (numero=FBCB) vs actual (mesaEntrada=5)
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
print("COMPARACIÓN DE BÚSQUEDAS EN SUME")
print("=" * 70)

# ============================================================
# BÚSQUEDA ORIGINAL (commit 8e501c7)
# ============================================================
print("\n--- BÚSQUEDA ORIGINAL (numero=FBCB) ---")
original_params = {
    "numero": "FBCB",
    "fecha_desde": "01/01/2025",
    "fecha_hasta": "31/12/2025",
    "buscar": "Buscar",
}

result1 = client.request("POST", f"{config.base_url}buscar/", data=original_params)
print(f"Status: {result1.status_code}")

if result1.status_code == 200:
    listing1 = parse_listing_page(result1.content, config.base_url)
    print(f"Total páginas: {listing1.total_pages}")
    print(f"Expedientes en página 1: {len(listing1.expedientes)}")
    print(f"Total estimado: {listing1.total_pages * len(listing1.expedientes)}")
    
    # Show first 3
    for i, exp in enumerate(listing1.expedientes[:3], 1):
        print(f"  {i}. {exp.numero} - {exp.concepto} ({exp.fecha_alta})")
else:
    print(f"Error: {result1.error}")

# ============================================================
# BÚSQUEDA ACTUAL (mesaEntrada=5)
# ============================================================
print("\n--- BÚSQUEDA ACTUAL (mesaEntrada=5, oficina=5) ---")
actual_params = {
    "numero": "",
    "descripcion": "",
    "palabraClave": "",
    "selectOrigen": "interno",
    "mesaEntrada": "5",
    "oficina": "5",
    "concepto": "",
    "fechaCdesde": "01/01/2025",
    "fechaChasta": "31/12/2025",
    "tipoDR": "",
    "numeroDR": "",
}

result2 = client.request("POST", f"{config.base_url}buscar/", data=actual_params)
print(f"Status: {result2.status_code}")

if result2.status_code == 200:
    listing2 = parse_listing_page(result2.content, config.base_url)
    print(f"Total páginas: {listing2.total_pages}")
    print(f"Expedientes en página 1: {len(listing2.expedientes)}")
    print(f"Total estimado: {listing2.total_pages * len(listing2.expedientes)}")
    
    # Show first 3
    for i, exp in enumerate(listing2.expedientes[:3], 1):
        print(f"  {i}. {exp.numero} - {exp.concepto} ({exp.fecha_alta})")
else:
    print(f"Error: {result2.error}")

# ============================================================
# COMPARACIÓN
# ============================================================
print("\n" + "=" * 70)
print("RESUMEN")
print("=" * 70)

if result1.status_code == 200 and result2.status_code == 200:
    total_original = listing1.total_pages * len(listing1.expedientes) if listing1.expedientes else 0
    total_actual = listing2.total_pages * len(listing2.expedientes) if listing2.expedientes else 0
    
    print(f"Búsqueda original (numero=FBCB): ~{total_original} expedientes")
    print(f"Búsqueda actual (mesaEntrada=5): ~{total_actual} expedientes")
    print(f"DB actual: 1,833 expedientes")
    print()
    
    if total_original > total_actual:
        print("✓ La búsqueda ORIGINAL trae MÁS expedientes")
        print("  Esto explica por qué la DB tiene 1,833 y el scraper actual solo trae ~730")
    elif total_actual > total_original:
        print("✓ La búsqueda ACTUAL trae MÁS expedientes")
    else:
        print("✓ Ambas búsquedas traen la misma cantidad")

client.close()
