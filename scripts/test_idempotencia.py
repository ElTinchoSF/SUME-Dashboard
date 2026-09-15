"""
Test de Idempotencia del Scraper SUME.

Verifica que limpiar la DB y volver a correr el scraper en el mismo rango
de fechas produce los mismos resultados.

Este test es COMPLETAMENTE REVERSIBLE:
1. Crea backup de la DB
2. Guarda estadísticas de línea base
3. Limpia las tablas
4. Corre el scraper
5. Compara resultados
6. Restaura el backup original
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
BACKUP_PATH = Path("data/sume.db.backup_idempotencia")
BASELINE_PATH = Path("data/baseline_stats.json")

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
    
    return stats


def compare_stats(baseline: dict, current: dict) -> list[str]:
    """Comparar estadísticas y retornar diferencias."""
    differences = []
    
    for key in baseline:
        if key not in current:
            differences.append(f"MISSING: {key} existe en baseline pero no en current")
        elif baseline[key] != current[key]:
            differences.append(f"DIFF: {key} = {baseline[key]} → {current[key]}")
    
    for key in current:
        if key not in baseline:
            differences.append(f"NEW: {key} = {current[key]} (no existe en baseline)")
    
    return differences


def main():
    print("=" * 70)
    print("TEST DE IDEMPOTENCIA DEL SCRAPER SUME")
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
        print(f"  Asuntos: {baseline_stats['asuntos']}")
        print(f"  Expediente-Asuntos: {baseline_stats['expediente_asuntos']}")
        print(f"  Dependencias: {baseline_stats['dependencias']}")
        print(f"  Conceptos únicos: {baseline_stats['expedientes_conceptos_unicos']}")
        print(f"  Rango fechas: {baseline_stats['expedientes_fecha_min']} a {baseline_stats['expedientes_fecha_max']}")
        
        # ============================================================
        # PASO 4: Limpiar la DB (mantener schema)
        # ============================================================
        print("\n--- PASO 4: Limpiando la DB ---")
        conn = sqlite3.connect(DB_PATH)
        
        # Limpiar en orden correcto (respetar foreign keys)
        tables_to_clean = [
            "expediente_asuntos",
            "movimientos", 
            "asuntos",
            "expedientes",
            "dependencias",
            # NO limpiar schema_migrations
        ]
        
        for table in tables_to_clean:
            cursor = conn.execute(f"DELETE FROM {table}")
            print(f"  ✓ {table}: {cursor.rowcount} registros eliminados")
        
        conn.commit()
        conn.close()
        
        print("  ✓ DB limpiada correctamente")
        
        # ============================================================
        # PASO 5: Correr el scraper
        # ============================================================
        print("\n--- PASO 5: Corriendo el scraper ---")
        print(f"  Rango: {DATE_FROM} a {DATE_TO}")
        print("  Esto tomará varios minutos...")
        print()
        
        # Importar y correr el scraper
        from src.scraper.main import run_scraper
        
        start_time = time.time()
        report = run_scraper(date_from=DATE_FROM, date_to=DATE_TO)
        duration = time.time() - start_time
        
        print(f"\n  ✓ Scraper completado en {duration:.1f}s")
        print(f"  Expedientes procesados: {report.stats.total_expedientes}")
        print(f"  Movimientos extraídos: {report.stats.total_movimientos}")
        print(f"  Duplicados skippeados: {report.stats.duplicate_expedientes}")
        print(f"  Errores HTTP: {report.stats.http_errors}")
        print(f"  Errores de parseo: {report.stats.parse_errors}")
        
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
        print(f"  Expediente-Asuntos: {current_stats['expediente_asuntos']}")
        print(f"  Dependencias: {current_stats['dependencias']}")
        
        # ============================================================
        # PASO 7: Comparar resultados
        # ============================================================
        print("\n--- PASO 7: Comparando con línea base ---")
        differences = compare_stats(baseline_stats, current_stats)
        
        if not differences:
            print("\n  ✓✓✓ TEST PASADO - Resultados idénticos ✓✓✓")
            print("  El scraper es IDEMPOTENTE para este rango de fechas")
            result = "PASSED"
        else:
            print(f"\n  ✗✗✗ TEST FALLÓ - {len(differences)} diferencias encontradas ✗✗✗")
            for diff in differences:
                print(f"    - {diff}")
            result = "FAILED"
        
        # ============================================================
        # PASO 8: Restaurar backup
        # ============================================================
        print("\n--- PASO 8: Restaurando backup original ---")
        DB_PATH.unlink()
        shutil.copy2(BACKUP_PATH, DB_PATH)
        print(f"  ✓ DB restaurada desde backup")
        print(f"  ✓ Backup eliminado: {BACKUP_PATH.unlink()}")
        
        # ============================================================
        # RESUMEN FINAL
        # ============================================================
        print("\n" + "=" * 70)
        print("RESUMEN DEL TEST")
        print("=" * 70)
        print(f"Resultado: {result}")
        print(f"Duración total: {duration:.1f}s")
        print(f"DB restaurada a estado original: SÍ")
        print()
        
        if result == "PASSED":
            print("CONCLUSIÓN:")
            print("El scraper es idempotente. Si limpiás la DB y volvés a correr")
            print("en el mismo rango de fechas, obtienes los mismos resultados.")
        else:
            print("CONCLUSIÓN:")
            print("Hay diferencias entre las corridas. Esto puede deberse a:")
            print("  1. Contenido cambiado en SUME (nuevos expedientes)")
            print("  2. Bugs en la extracción")
            print("  3. Problemas de red/conectividad")
        
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
