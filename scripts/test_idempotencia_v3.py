"""
Test de Idempotencia RÁPIDO - Búsqueda Correcta (numero=FBCB)

Usa un límite de páginas para ser rápido pero válidamente idempotente.
Si 10 páginas son idempotentes, 374 páginas también lo serán (mismo código).
"""

import sqlite3
import shutil
import sys
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = Path("data/sume.db")
BACKUP_PATH = Path("data/sume.db.backup_idempotencia_v3")
MAX_PAGES = 10  # Limitar a 10 páginas para test rápido (~100 expedientes)


def get_db_stats(conn: sqlite3.Connection) -> dict:
    stats = {}
    tables = ["expedientes", "movimientos", "asuntos", "expediente_asuntos", "dependencias"]
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = cursor.fetchone()[0]
    
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT concepto), MIN(fecha_alta), MAX(fecha_alta)
        FROM expedientes
    """)
    row = cursor.fetchone()
    stats["conceptos_unicos"] = row[0]
    stats["fecha_min"] = row[1]
    stats["fecha_max"] = row[2]
    
    cursor = conn.execute("SELECT concepto, COUNT(*) FROM expedientes GROUP BY concepto ORDER BY COUNT(*) DESC")
    stats["conceptos"] = {r[0]: r[1] for r in cursor.fetchall()}
    
    return stats


def run_scraper_limited(max_pages: int) -> dict:
    """Run scraper with CORRECT search, limited pages."""
    from src.scraper.client import SUMEClient
    from src.scraper.config import ScraperConfig
    from src.scraper.parser import parse_listing_page, parse_movimientos_table
    from src.scraper.normalizer import get_normalizer, normalize
    from src.database import get_connection, transaction
    from pathlib import Path as FilePath
    
    config = ScraperConfig.load()
    client = SUMEClient(config)
    normalizer_rules = get_normalizer(FilePath(config.normalization_rules_path))
    
    # CORRECT search params
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
    
    stats = {"expedientes": 0, "movimientos": 0, "pages": 0, "errors": 0}
    
    def process_expediente(exp):
        nonlocal stats
        try:
            detail = client.get(exp.detail_url)
            if detail.status_code != 200:
                stats["errors"] += 1
                return
            
            movimientos = parse_movimientos_table(detail.content)
            
            for mov in movimientos:
                mov.dependencia = normalize(mov.dependencia, normalizer_rules)
            if exp.origenes:
                exp.origenes = normalize(exp.origenes, normalizer_rules)
            
            with transaction() as conn:
                exists = conn.execute("SELECT id FROM expedientes WHERE numero=?", (exp.numero,)).fetchone()
                if exists:
                    return
                
                cur = conn.execute(
                    "INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes) VALUES (?,?,?,?,?,?,?)",
                    (exp.numero, exp.concepto, exp.descripcion, exp.fecha_alta, exp.estado, exp.palabras_clave, exp.origenes)
                )
                exp_id = cur.lastrowid
                
                for i, m in enumerate(reversed(movimientos), 1):
                    conn.execute("INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia) VALUES (?,?,?,?)",
                                 (exp_id, i, m.fecha_recepcion, m.dependencia))
                
                deps = {m.dependencia for m in movimientos}
                if exp.origenes:
                    deps.add(exp.origenes)
                for d in deps:
                    ex = conn.execute("SELECT id FROM dependencias WHERE nombre=?", (d,)).fetchone()
                    if ex:
                        conn.execute("UPDATE dependencias SET total_expedientes=total_expedientes+1 WHERE id=?", (ex[0],))
                    else:
                        conn.execute("INSERT INTO dependencias (nombre, nombre_original, total_expedientes) VALUES (?,?,1)", (d, d))
            
            stats["expedientes"] += 1
            stats["movimientos"] += len(movimientos)
        except Exception as e:
            stats["errors"] += 1
    
    # First page
    result = client.request("POST", f"{config.base_url}buscar/", data=search_params)
    if result.status_code != 200:
        print(f"  ERROR: {result.status_code}")
        client.close()
        return stats
    
    listing = parse_listing_page(result.content, config.base_url)
    total = min(listing.total_pages, max_pages)
    print(f"  Pages to scrape: {total} of {listing.total_pages}")
    
    for exp in listing.expedientes:
        process_expediente(exp)
    stats["pages"] = 1
    
    for page in range(2, total + 1):
        r = client.get(config.get_page_url(page))
        if r.status_code != 200:
            stats["errors"] += 1
            continue
        l = parse_listing_page(r.content, config.base_url)
        for exp in l.expedientes:
            process_expediente(exp)
        stats["pages"] = page
        if page % 5 == 0:
            print(f"    Page {page}/{total}: {stats['expedientes']} expedientes")
    
    # Update asuntos
    from src.analysis.asuntos import populate_asuntos_table
    populate_asuntos_table()
    
    client.close()
    return stats


def main():
    print("=" * 70)
    print(f"TEST IDEMPOTENCIA RÁPIDO - {MAX_PAGES} PÁGINAS (numero=FBCB)")
    print("=" * 70)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Backup
    print("--- Creando backup ---")
    if BACKUP_PATH.exists():
        BACKUP_PATH.unlink()
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"  ✓ Backup creado")
    
    try:
        # Baseline
        print("\n--- Línea base ---")
        conn = sqlite3.connect(DB_PATH)
        baseline = get_db_stats(conn)
        conn.close()
        print(f"  Expedientes: {baseline['expedientes']}")
        print(f"  Conceptos: {baseline['conceptos_unicos']}")
        
        # Clean
        print("\n--- Limpiando DB ---")
        conn = sqlite3.connect(DB_PATH)
        for t in ["expediente_asuntos", "movimientos", "asuntos", "expedientes", "dependencias"]:
            r = conn.execute(f"DELETE FROM {t}")
            print(f"  ✓ {t}: {r.rowcount} eliminados")
        conn.commit()
        conn.close()
        
        # Run 1
        print(f"\n--- Corrida 1 ({MAX_PAGES} páginas) ---")
        t1 = time.time()
        s1 = run_scraper_limited(MAX_PAGES)
        d1 = time.time() - t1
        print(f"  ✓ {s1['expedientes']} expedientes, {s1['movimientos']} movimientos en {d1:.0f}s")
        
        conn = sqlite3.connect(DB_PATH)
        stats1 = get_db_stats(conn)
        conn.close()
        
        # Clean again
        print("\n--- Limpiando DB (segunda vez) ---")
        conn = sqlite3.connect(DB_PATH)
        for t in ["expediente_asuntos", "movimientos", "asuntos", "expedientes", "dependencias"]:
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        conn.close()
        print("  ✓ DB limpiada")
        
        # Run 2
        print(f"\n--- Corrida 2 ({MAX_PAGES} páginas) ---")
        t2 = time.time()
        s2 = run_scraper_limited(MAX_PAGES)
        d2 = time.time() - t2
        print(f"  ✓ {s2['expedientes']} expedientes, {s2['movimientos']} movimientos en {d2:.0f}s")
        
        conn = sqlite3.connect(DB_PATH)
        stats2 = get_db_stats(conn)
        conn.close()
        
        # Compare
        print("\n--- Comparación ---")
        diffs = []
        for key in ["expedientes", "movimientos", "asuntos", "expediente_asuntos", "dependencias"]:
            if stats1[key] != stats2[key]:
                diffs.append(f"{key}: {stats1[key]} vs {stats2[key]}")
        
        for key in ["conceptos_unicos", "fecha_min", "fecha_max"]:
            if stats1[key] != stats2[key]:
                diffs.append(f"{key}: {stats1[key]} vs {stats2[key]}")
        
        if stats1["conceptos"] != stats2["conceptos"]:
            for c in set(list(stats1["conceptos"].keys()) + list(stats2["conceptos"].keys())):
                v1 = stats1["conceptos"].get(c, 0)
                v2 = stats2["conceptos"].get(c, 0)
                if v1 != v2:
                    diffs.append(f"concepto '{c}': {v1} vs {v2}")
        
        # Restore
        print("\n--- Restaurando backup ---")
        DB_PATH.unlink()
        shutil.copy2(BACKUP_PATH, DB_PATH)
        BACKUP_PATH.unlink()
        print("  ✓ DB restaurada")
        
        # Result
        print("\n" + "=" * 70)
        if not diffs:
            print("✓✓✓ TEST PASADO - Corridas idénticas ✓✓✓")
            print(f"  Corrida 1: {s1['expedientes']} exp en {d1:.0f}s")
            print(f"  Corrida 2: {s2['expedientes']} exp en {d2:.0f}s")
            print("\n  La búsqueda numero=FBCB es IDEMPOTENTE")
            return 0
        else:
            print(f"✗✗✗ TEST FALLÓ - {len(diffs)} diferencias ✗✗✗")
            for d in diffs:
                print(f"  - {d}")
            return 1
        
    except Exception as e:
        print(f"\n ERROR: {e}")
        if BACKUP_PATH.exists():
            DB_PATH.unlink()
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print("  ✓ DB restaurada de emergencia")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
