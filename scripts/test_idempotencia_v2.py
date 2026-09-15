"""
Test de Idempotencia del Scraper SUME - Búsqueda Correcta

Usa la búsqueda con numero=FBCB (la que trae ~3,740 expedientes).
Verifica que limpiar la DB y volver a correr produce los mismos resultados.

COMPLETAMENTE REVERSIBLE.
"""

import sqlite3
import shutil
import sys
import time
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Paths
DB_PATH = Path("data/sume.db")
BACKUP_PATH = Path("data/sume.db.backup_idempotencia_v2")

# Rango de fechas del scraping actual
DATE_FROM = "2025-01-01"
DATE_TO = "2025-12-31"


def get_db_stats(conn: sqlite3.Connection) -> dict:
    """Obtener estadísticas de la DB para comparación."""
    stats = {}
    
    # Contar registros en cada tabla
    tables = ["expedientes", "movimientos", "asuntos", "expediente_asuntos", "dependencias"]
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = cursor.fetchone()[0]
    
    # Estadísticas adicionales de expedientes
    cursor = conn.execute("""
        SELECT 
            COUNT(DISTINCT concepto) as total_conceptos,
            COUNT(DISTINCT fecha_alta) as total_fechas_unicas,
            MIN(fecha_alta) as fecha_min,
            MAX(fecha_alta) as fecha_max
        FROM expedientes
    """)
    row = cursor.fetchone()
    stats["expedientes_conceptos_unicos"] = row[0]
    stats["expedientes_fechas_unicas"] = row[1]
    stats["expedientes_fecha_min"] = row[2]
    stats["expedientes_fecha_max"] = row[3]
    
    # Estadísticas de movimientos
    cursor = conn.execute("""
        SELECT 
            COUNT(DISTINCT dependencia) as dependencias_unicas,
            MIN(fecha_recepcion) as fecha_mov_min,
            MAX(fecha_recepcion) as fecha_mov_max
        FROM movimientos
    """)
    row = cursor.fetchone()
    stats["movimientos_dependencias_unicas"] = row[0]
    stats["movimientos_fecha_min"] = row[1]
    stats["movimientos_fecha_max"] = row[2]
    
    # Estadísticas de asuntos
    cursor = conn.execute("""
        SELECT 
            COUNT(DISTINCT concepto) as conceptos_con_asunto,
            COUNT(DISTINCT asunto) as asuntos_unicos
        FROM asuntos
    """)
    row = cursor.fetchone()
    stats["asuntos_conceptos"] = row[0]
    stats["asuntos_unicos"] = row[1]
    
    # Distribución por concepto
    cursor = conn.execute("""
        SELECT concepto, COUNT(*) as total 
        FROM expedientes 
        GROUP BY concepto 
        ORDER BY total DESC
    """)
    stats["conceptos_distribucion"] = {row[0]: row[1] for row in cursor.fetchall()}
    
    return stats


def compare_stats(baseline: dict, current: dict) -> list[str]:
    """Comparar estadísticas y retornar diferencias."""
    differences = []
    
    for key in baseline:
        if key == "conceptos_distribucion":
            continue  # Handle separately
        if key not in current:
            differences.append(f"MISSING: {key} existe en baseline pero no en current")
        elif baseline[key] != current[key]:
            differences.append(f"DIFF: {key} = {baseline[key]} → {current[key]}")
    
    for key in current:
        if key == "conceptos_distribucion":
            continue
        if key not in baseline:
            differences.append(f"NEW: {key} = {current[key]} (no existe en baseline)")
    
    # Compare concepto distribution
    if "conceptos_distribucion" in baseline and "conceptos_distribucion" in current:
        baseline_dist = baseline["conceptos_distribucion"]
        current_dist = current["conceptos_distribucion"]
        
        all_conceptos = set(list(baseline_dist.keys()) + list(current_dist.keys()))
        for concepto in all_conceptos:
            b_val = baseline_dist.get(concepto, 0)
            c_val = current_dist.get(concepto, 0)
            if b_val != c_val:
                differences.append(f"DIFF concepto '{concepto}': {b_val} → {c_val}")
    
    return differences


def run_correct_scraper():
    """
    Run scraper with the CORRECT search: numero=FBCB + date filters.
    This bypasses the orchestrator and uses the correct search params directly.
    """
    from src.scraper.client import SUMEClient
    from src.scraper.config import ScraperConfig
    from src.scraper.parser import parse_listing_page, parse_movimientos_table
    from src.scraper.normalizer import get_normalizer, normalize
    from src.database import get_connection, transaction
    from pathlib import Path as FilePath
    
    config = ScraperConfig.load()
    client = SUMEClient(config)
    normalizer_rules = get_normalizer(FilePath(config.normalization_rules_path))
    
    # CORRECT search params: numero=FBCB + date filters
    search_params = {
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
    
    stats = {
        "total_expedientes": 0,
        "total_movimientos": 0,
        "duplicate_expedientes": 0,
        "http_errors": 0,
        "pages_scraped": 0,
    }
    
    print("  Fetching first page...")
    result = client.request("POST", f"{config.base_url}buscar/", data=search_params)
    
    if result.status_code != 200:
        print(f"  ERROR: First page returned {result.status_code}")
        client.close()
        return stats
    
    listing = parse_listing_page(result.content, config.base_url)
    total_pages = listing.total_pages
    print(f"  Total pages detected: {total_pages}")
    
    # Process first page
    def process_page(expedientes, page_num):
        nonlocal stats
        
        for expediente in expedientes:
            # Fetch detail page
            try:
                detail_result = client.get(expediente.detail_url)
                if detail_result.status_code != 200:
                    stats["http_errors"] += 1
                    continue
                
                movimientos = parse_movimientos_table(detail_result.content)
                
                # Normalize
                for mov in movimientos:
                    mov.dependencia = normalize(mov.dependencia, normalizer_rules)
                
                if expediente.origenes:
                    expediente.origenes = normalize(expediente.origenes, normalizer_rules)
                
                # Persist
                with transaction() as conn:
                    existing = conn.execute(
                        "SELECT id FROM expedientes WHERE numero = ?",
                        (expediente.numero,),
                    ).fetchone()
                    
                    if existing:
                        stats["duplicate_expedientes"] += 1
                        continue
                    
                    cursor = conn.execute(
                        """INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (expediente.numero, expediente.concepto, expediente.descripcion,
                         expediente.fecha_alta, expediente.estado, expediente.palabras_clave, expediente.origenes),
                    )
                    expediente_id = cursor.lastrowid
                    
                    for i, mov in enumerate(reversed(movimientos), start=1):
                        conn.execute(
                            """INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                               VALUES (?, ?, ?, ?)""",
                            (expediente_id, i, mov.fecha_recepcion, mov.dependencia),
                        )
                    
                    # Update dependencias
                    all_deps = {mov.dependencia for mov in movimientos}
                    if expediente.origenes:
                        all_deps.add(expediente.origenes)
                    
                    for dep_name in all_deps:
                        existing_dep = conn.execute(
                            "SELECT id, total_expedientes FROM dependencias WHERE nombre = ?",
                            (dep_name,),
                        ).fetchone()
                        
                        if existing_dep:
                            conn.execute(
                                "UPDATE dependencias SET total_expedientes = total_expedientes + 1 WHERE id = ?",
                                (existing_dep[0],),
                            )
                        else:
                            conn.execute(
                                "INSERT INTO dependencias (nombre, nombre_original, total_expedientes) VALUES (?, ?, 1)",
                                (dep_name, dep_name),
                            )
                
                stats["total_expedientes"] += 1
                stats["total_movimientos"] += len(movimientos)
                
            except Exception as e:
                print(f"    Error processing {expediente.numero}: {e}")
                stats["http_errors"] += 1
    
    # Process first page
    process_page(listing.expedientes, 1)
    stats["pages_scraped"] = 1
    
    # Process remaining pages
    for page_num in range(2, total_pages + 1):
        if page_num % 50 == 0:
            print(f"  Processing page {page_num}/{total_pages}...")
        
        page_result = client.get(config.get_page_url(page_num))
        if page_result.status_code != 200:
            stats["http_errors"] += 1
            continue
        
        page_listing = parse_listing_page(page_result.content, config.base_url)
        process_page(page_listing.expedientes, page_num)
        stats["pages_scraped"] += 1
    
    # Update asuntos
    print("  Updating asuntos...")
    from src.analysis.asuntos import populate_asuntos_table
    populate_asuntos_table()
    
    client.close()
    return stats


def main():
    print("=" * 70)
    print("TEST DE IDEMPOTENCIA - BÚSQUEDA CORRECTA (numero=FBCB)")
    print("=" * 70)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DB: {DB_PATH}")
    print(f"Rango: {DATE_FROM} a {DATE_TO}")
    print()
    
    # ============================================================
    # PASO 1: Verificar que la DB existe
    # ============================================================
    if not DB_PATH.exists():
        print("ERROR: No se encuentra la DB en", DB_PATH)
        sys.exit(1)
    
    print("✓ DB encontrada")
    
    # ============================================================
    # PASO 2: Crear backup
    # ============================================================
    print("\n--- PASO 2: Creando backup ---")
    if BACKUP_PATH.exists():
        print(f"  Backup existente encontrado, eliminando...")
        BACKUP_PATH.unlink()
    
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"  ✓ Backup creado: {BACKUP_PATH}")
    print(f"  ✓ Tamaño: {BACKUP_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    
    try:
        # ============================================================
        # PASO 3: Guardar estadísticas de línea base
        # ============================================================
        print("\n--- PASO 3: Guardando estadísticas de línea base ---")
        conn = sqlite3.connect(DB_PATH)
        baseline_stats = get_db_stats(conn)
        conn.close()
        
        print(f"  Expedientes: {baseline_stats['expedientes']}")
        print(f"  Movimientos: {baseline_stats['movimientos']}")
        print(f"  Conceptos: {baseline_stats['expedientes_conceptos_unicos']}")
        print(f"  Rango fechas: {baseline_stats['expedientes_fecha_min']} a {baseline_stats['expedientes_fecha_max']}")
        
        # ============================================================
        # PASO 4: Limpiar la DB
        # ============================================================
        print("\n--- PASO 4: Limpiando la DB ---")
        conn = sqlite3.connect(DB_PATH)
        
        tables_to_clean = [
            "expediente_asuntos",
            "movimientos", 
            "asuntos",
            "expedientes",
            "dependencias",
        ]
        
        for table in tables_to_clean:
            cursor = conn.execute(f"DELETE FROM {table}")
            print(f"  ✓ {table}: {cursor.rowcount} registros eliminados")
        
        conn.commit()
        conn.close()
        print("  ✓ DB limpiada correctamente")
        
        # ============================================================
        # PASO 5: Correr scraper con búsqueda correcta
        # ============================================================
        print("\n--- PASO 5: Corriendo scraper (numero=FBCB) ---")
        print(f"  Búsqueda: numero=FBCB, fecha: {DATE_FROM} a {DATE_TO}")
        print("  Esto tomará varios minutos (estimado ~3,740 expedientes)...")
        print()
        
        start_time = time.time()
        scraper_stats = run_correct_scraper()
        duration = time.time() - start_time
        
        print(f"\n  ✓ Scraper completado en {duration:.1f}s")
        print(f"  Expedientes procesados: {scraper_stats['total_expedientes']}")
        print(f"  Movimientos extraídos: {scraper_stats['total_movimientos']}")
        print(f"  Duplicados skippeados: {scraper_stats['duplicate_expedientes']}")
        print(f"  Errores HTTP: {scraper_stats['http_errors']}")
        print(f"  Páginas scrapeadas: {scraper_stats['pages_scraped']}")
        
        # ============================================================
        # PASO 6: Obtener estadísticas post-scraping
        # ============================================================
        print("\n--- PASO 6: Obteniendo estadísticas post-scraping ---")
        conn = sqlite3.connect(DB_PATH)
        current_stats = get_db_stats(conn)
        conn.close()
        
        print(f"  Expedientes: {current_stats['expedientes']}")
        print(f"  Movimientos: {current_stats['movimientos']}")
        print(f"  Asuntos: {current_stats['asuntos']}")
        print(f"  Dependencias: {current_stats['dependencias']}")
        print(f"\n  Distribución por concepto:")
        for concepto, count in sorted(current_stats['conceptos_distribucion'].items(), 
                                       key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {concepto}: {count}")
        
        # ============================================================
        # PASO 7: Comparar con línea base
        # ============================================================
        print("\n--- PASO 7: Comparando con línea base ---")
        differences = compare_stats(baseline_stats, current_stats)
        
        if not differences:
            print("\n  ✓✓✓ TEST PASADO - Resultados idénticos ✓✓✓")
            print("  La búsqueda numero=FBCB es IDEMPOTENTE")
            result = "PASSED"
        else:
            print(f"\n  ✗✗✗ TEST FALLÓ - {len(differences)} diferencias encontradas ✗✗✗")
            for diff in differences[:20]:  # Show first 20
                print(f"    - {diff}")
            if len(differences) > 20:
                print(f"    ... y {len(differences) - 20} diferencias más")
            result = "FAILED"
        
        # ============================================================
        # PASO 8: Restaurar backup
        # ============================================================
        print("\n--- PASO 8: Restaurando backup original ---")
        DB_PATH.unlink()
        shutil.copy2(BACKUP_PATH, DB_PATH)
        BACKUP_PATH.unlink()
        print(f"  ✓ DB restaurada desde backup")
        
        # ============================================================
        # RESUMEN FINAL
        # ============================================================
        print("\n" + "=" * 70)
        print("RESUMEN DEL TEST")
        print("=" * 70)
        print(f"Resultado: {result}")
        print(f"Duración total: {duration:.1f}s")
        print(f"Expedientes scrapeados: {scraper_stats['total_expedientes']}")
        print(f"DB restaurada a estado original: SÍ")
        print()
        
        if result == "PASSED":
            print("CONCLUSIÓN:")
            print("La búsqueda numero=FBCB es idempotente.")
            print("Si limpiás la DB y volvés a correr, obtienes los mismos resultados.")
            print()
            print("NOTA: La DB actual tiene 1,833 expedientes, pero la búsqueda")
            print(f"correcta trae ~{scraper_stats['total_expedientes']}.")
            print("Esto confirma que la DB fue poblada incompletamente.")
        else:
            print("CONCLUSIÓN:")
            print("Hay diferencias entre las corridas.")
        
        print()
        print("=" * 70)
        
        return 0 if result == "PASSED" else 1
        
    except Exception as e:
        print(f"\n ERROR: {e}")
        print("\nRestaurando backup de emergencia...")
        
        if BACKUP_PATH.exists():
            DB_PATH.unlink()
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print("✓ DB restaurada desde backup de emergencia")
        
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
