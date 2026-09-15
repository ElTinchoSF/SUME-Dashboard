"""
Punto de entrada para ejecutar el módulo como script.

Permite ejecutar el scraper con:
    python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31
"""

from .cli import main

if __name__ == "__main__":
    main()
