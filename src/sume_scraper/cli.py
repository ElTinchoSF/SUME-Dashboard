"""
SUME Scraper - Interfaz de línea de comandos.

Proporciona una CLI para ejecutar el scraping de SUME con diferentes
opciones de configuración.
"""

import argparse
import sys
import logging
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    """Configurar logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Punto de entrada principal para la CLI."""
    parser = argparse.ArgumentParser(
        description="SUME Scraper - Extraer expedientes de SUME",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Scraping completo de FBCB para 2025
  python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31

  # Scraping con validación
  python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --validate

  # Scraping incremental (actualiza existentes)
  python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-06-30

  # Limpiar DB antes de scraping
  python -m src.sume_scraper --faculty FBCB --date-from 2025-01-01 --date-to 2025-12-31 --clean

  # Scraping limitado (testing)
  python -m src.sume_scraper --faculty FBCB --max-pages 5

  # Scraping de otra facultad
  python -m src.sume_scraper --faculty FCA --date-from 2025-01-01 --date-to 2025-12-31
        """,
    )
    
    parser.add_argument(
        "--faculty",
        required=True,
        help="Código de la unidad académica (ej: FBCB, FCA, FCV)",
    )
    parser.add_argument(
        "--date-from",
        help="Fecha de inicio (YYYY-MM-DD o DD/MM/YYYY)",
    )
    parser.add_argument(
        "--date-to",
        help="Fecha de fin (YYYY-MM-DD o DD/MM/YYYY)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Ejecutar validaciones después del scraping",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Limpiar DB antes de scraping (cuidado: elimina todos los datos)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Número máximo de páginas a procesar (para testing)",
    )
    parser.add_argument(
        "--db-path",
        default="data/sume.db",
        help="Ruta a la base de datos (default: data/sume.db)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Habilitar logging detallado",
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    setup_logging(args.verbose)
    
    # Importar aquí para evitar importaciones circulares
    from .config import ScraperConfig
    from .scraper import SUMEScraper
    from .validator import ScrapingValidator
    
    try:
        # Crear configuración
        config = ScraperConfig(
            faculty_code=args.faculty,
            date_from=args.date_from,
            date_to=args.date_to,
            db_path=args.db_path,
        )
        
        # Limpiar DB si se solicita
        if args.clean:
            print(f"⚠️  Limpiando base de datos: {config.db_path}")
            response = input("¿Estás seguro? (s/N): ")
            if response.lower() != "s":
                print("Operación cancelada.")
                return 0
            
            _clean_database(config.db_path)
            print("✓ Base de datos limpiada")
        
        # Crear y ejecutar scraper
        scraper = SUMEScraper(config)
        
        # Si hay max_pages, limitar el scraping
        if args.max_pages:
            print(f"⚠️  Modo limitado: máximo {args.max_pages} páginas")
        
        print(f"\n🚀 Iniciando scraping de {config.faculty_code}...")
        if config.date_from or config.date_to:
            print(f"   Período: {config.date_from or '...'} a {config.date_to or '...'}")
        
        result = scraper.run()
        
        # Imprimir resultado
        result.print_summary()
        
        # Ejecutar validaciones si se solicita
        if args.validate:
            print("\n🔍 Ejecutando validaciones...")
            validator = ScrapingValidator(config.db_path)
            validation = validator.validate()
            validation.print_summary()
            
            if validation.has_errors():
                print("\n❌ Se encontraron errores en la validación")
                return 1
        
        if result.success:
            print("\n✅ Scraping completado exitosamente")
            return 0
        else:
            print("\n❌ Scraping completado con errores")
            return 1
    
    except ValueError as e:
        print(f"❌ Error de configuración: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrumpido por el usuario")
        return 130
    except Exception as e:
        print(f"❌ Error inesperado: {e}", file=sys.stderr)
        logging.exception("Error durante el scraping")
        return 1


def _clean_database(db_path: str) -> None:
    """
    Limpiar la base de datos.
    
    Elimina todos los datos de las tablas principales
    pero mantiene el esquema.
    """
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    
    # Eliminar datos en orden correcto (respetar foreign keys)
    tables_to_clean = [
        "expediente_asuntos",
        "movimientos",
        "asuntos",
        "expedientes",
        "dependencias",
    ]
    
    for table in tables_to_clean:
        conn.execute(f"DELETE FROM {table}")
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
