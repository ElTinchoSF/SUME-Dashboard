"""
SUME Scraper - Lógica principal de scraping.

Proporciona la clase SUMEScraper que maneja el scraping completo de
expedientes y movimientos de SUME para diferentes unidades académicas.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .client import SUMEClient, RequestResult
from .config import ScraperConfig
from .normalizer import get_normalizer, normalize
from .parser import parse_listing_page, parse_movimientos_table, ExpedienteDict, MovimientoDict

logger = logging.getLogger(__name__)


@dataclass
class ScrapingStats:
    """Estadísticas del scraping."""
    total_expedientes: int = 0
    total_movimientos: int = 0
    expedientes_inserted: int = 0
    expedientes_updated: int = 0
    expedientes_skipped: int = 0
    duplicate_expedientes: int = 0
    http_errors: int = 0
    parse_errors: int = 0
    pages_scraped: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def duration_seconds(self) -> float:
        """Duración total en segundos."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def to_dict(self) -> dict:
        """Convertir a diccionario para reporting."""
        return {
            "total_expedientes": self.total_expedientes,
            "total_movimientos": self.total_movimientos,
            "expedientes_inserted": self.expedientes_inserted,
            "expedientes_updated": self.expedientes_updated,
            "expedientes_skipped": self.expedientes_skipped,
            "duplicate_expedientes": self.duplicate_expedientes,
            "http_errors": self.http_errors,
            "parse_errors": self.parse_errors,
            "pages_scraped": self.pages_scraped,
            "duration_seconds": round(self.duration_seconds, 2),
        }


@dataclass
class ScrapingResult:
    """Resultado del scraping."""
    stats: ScrapingStats
    success: bool = True
    errors: list[str] = field(default_factory=list)
    
    def print_summary(self) -> None:
        """Imprimir resumen formateado."""
        print("\n" + "=" * 60)
        print("RESUMEN DEL SCRAPING")
        print("=" * 60)
        print(f"Expedientes procesados: {self.stats.total_expedientes}")
        print(f"  - Insertados: {self.stats.expedientes_inserted}")
        print(f"  - Actualizados: {self.stats.expedientes_updated}")
        print(f"  - Saltados: {self.stats.expedientes_skipped}")
        print(f"Movimientos extraídos: {self.stats.total_movimientos}")
        print(f"Páginas scrapeadas: {self.stats.pages_scraped}")
        print(f"Duración: {self.stats.duration_seconds:.1f}s")
        
        if self.stats.http_errors > 0:
            print(f"Errores HTTP: {self.stats.http_errors}")
        if self.stats.parse_errors > 0:
            print(f"Errores de parseo: {self.stats.parse_errors}")
        
        if self.errors:
            print(f"\nErrores ({len(self.errors)}):")
            for error in self.errors[:10]:
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... y {len(self.errors) - 10} errores más")
        
        print("=" * 60)


class SUMEScraper:
    """
    Scraper principal para SUME.
    
    Maneja el scraping completo de expedientes y movimientos de SUME
    para diferentes unidades académicas de la UNL.
    
    Características:
    - Scraping por rangos de fecha
    - Actualización incremental (insert + update)
    - Validaciones post-scraping
    - Reutilizable para diferentes facultades
    """
    
    def __init__(self, config: ScraperConfig):
        """
        Inicializar el scraper.
        
        Args:
            config: Configuración del scraper
        """
        self.config = config
        self.client = SUMEClient(config)
        self.normalizer_rules = get_normalizer()
        self.stats = ScrapingStats()
    
    def run(self) -> ScrapingResult:
        """
        Ejecutar el scraping completo.
        
        Returns:
            Resultado del scraping con estadísticas
        """
        self.stats.start_time = time.time()
        result = ScrapingResult(stats=self.stats)
        
        logger.info(
            f"Iniciando scraping para {self.config.faculty_code} "
            f"({self.config.date_from or 'sin inicio'} a {self.config.date_to or 'sin fin'})"
        )
        
        try:
            # 1. Fetch primera página para obtener total de páginas
            first_page = self._fetch_listing_page(1)
            if not first_page:
                result.success = False
                result.errors.append("No se pudo obtener la primera página")
                return result
            
            listing = parse_listing_page(first_page, self.config.base_url)
            total_pages = listing.total_pages
            logger.info(f"Total de páginas: {total_pages}")
            
            # 2. Procesar primera página
            self._process_listing_expedientes(listing.expedientes, 1)
            
            # 3. Procesar páginas restantes
            for page_num in range(2, total_pages + 1):
                if page_num % 10 == 0:
                    logger.info(f"Procesando página {page_num}/{total_pages}")
                
                page_html = self._fetch_listing_page(page_num)
                if not page_html:
                    self.stats.http_errors += 1
                    continue
                
                listing = parse_listing_page(page_html, self.config.base_url)
                self._process_listing_expedientes(listing.expedientes, page_num)
            
            # 4. Actualizar asuntos (solo si hay expedientes nuevos)
            if self.stats.expedientes_inserted > 0:
                self._update_asuntos()
            
        except Exception as e:
            logger.exception(f"Error durante el scraping: {e}")
            result.success = False
            result.errors.append(str(e))
        
        finally:
            self.stats.end_time = time.time()
            self.client.close()
        
        return result
    
    def _fetch_listing_page(self, page_num: int) -> Optional[str]:
        """
        Obtener una página de listado.
        
        Args:
            page_num: Número de página
            
        Returns:
            HTML de la página o None en caso de error
        """
        if page_num == 1:
            # Primera página: usar búsqueda con filtros
            search_params = self.config.get_search_params()
            result = self.client.request("POST", f"{self.config.base_url}buscar/", data=search_params)
        else:
            # Páginas subsiguientes: usar URL de paginación
            page_url = self.config.get_page_url(page_num)
            result = self.client.get(page_url)
        
        if result.error:
            logger.error(f"Error HTTP en página {page_num}: {result.error}")
            return None
        
        if result.status_code != 200:
            logger.error(f"Status {result.status_code} en página {page_num}")
            return None
        
        # Guardar HTML crudo
        self.client.save_raw_html(result.content, f"listing_page_{page_num}")
        
        return result.content
    
    def _process_listing_expedientes(self, expedientes: list[ExpedienteDict], page_num: int) -> None:
        """
        Procesar expedientes de una página de listado.
        
        Para cada expediente:
        1. Fetch detail page para movimientos
        2. Normalizar dependencias
        3. Insertar o actualizar en la DB
        
        Args:
            expedientes: Lista de ExpedienteDict del listado
            page_num: Número de página actual
        """
        for i, expediente in enumerate(expedientes, 1):
            logger.debug(f"Procesando {expediente.numero} ({i}/{len(expedientes)} en página {page_num})")
            
            try:
                # Fetch movimientos del detalle
                movimientos = self._fetch_and_parse_movimientos(expediente)
                
                # Normalizar dependencias
                for mov in movimientos:
                    mov.dependencia = normalize(mov.dependencia, self.normalizer_rules)
                
                if expediente.origenes:
                    expediente.origenes = normalize(expediente.origenes, self.normalizer_rules)
                
                # Insertar o actualizar
                self._upsert_expediente(expediente, movimientos)
                
                # Actualizar estadísticas
                self.stats.total_expedientes += 1
                self.stats.total_movimientos += len(movimientos)
                
            except Exception as e:
                logger.exception(f"Error procesando {expediente.numero}: {e}")
                self.stats.parse_errors += 1
    
    def _fetch_and_parse_movimientos(self, expediente: ExpedienteDict) -> list[MovimientoDict]:
        """
        Obtener y parsear movimientos de un expediente.
        
        Args:
            expediente: ExpedienteDict con detail_url
            
        Returns:
            Lista de MovimientoDict
        """
        numero = expediente.numero
        
        # Fetch página de detalle
        result = self.client.get(expediente.detail_url)
        
        if result.error:
            logger.warning(f"Error obteniendo detalle para {numero}: {result.error}")
            self.stats.http_errors += 1
            return []
        
        if result.status_code != 200:
            logger.warning(f"Detalle retornó {result.status_code} para {numero}")
            self.stats.http_errors += 1
            return []
        
        # Guardar HTML crudo
        self.client.save_raw_html(result.content, f"detail_{numero}")
        
        # Parsear movimientos
        movimientos = parse_movimientos_table(result.content)
        
        return movimientos
    
    def _upsert_expediente(self, expediente: ExpedienteDict, movimientos: list[MovimientoDict]) -> None:
        """
        Insertar o actualizar un expediente y sus movimientos.
        
        Si el expediente no existe, lo inserta con todos sus movimientos.
        Si ya existe, reemplaza TODOS los movimientos.
        
        Args:
            expediente: Datos del expediente
            movimientos: Lista de movimientos
        """
        from src.database import get_connection, transaction
        
        with transaction() as conn:
            # Verificar si el expediente ya existe
            existing = conn.execute(
                "SELECT id FROM expedientes WHERE numero = ?",
                (expediente.numero,),
            ).fetchone()
            
            if existing:
                # Actualizar: eliminar movimientos viejos y agregar nuevos
                expediente_id = existing[0]
                
                # Eliminar movimientos viejos
                conn.execute(
                    "DELETE FROM movimientos WHERE expediente_id = ?",
                    (expediente_id,),
                )
                
                # Insertar movimientos nuevos
                for i, mov in enumerate(reversed(movimientos), start=1):
                    conn.execute(
                        """INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                           VALUES (?, ?, ?, ?)""",
                        (expediente_id, i, mov.fecha_recepcion, mov.dependencia),
                    )
                
                self.stats.expedientes_updated += 1
                logger.debug(f"Actualizado expediente {expediente.numero} con {len(movimientos)} movimientos")
            
            else:
                # Insertar nuevo expediente
                cursor = conn.execute(
                    """INSERT INTO expedientes (numero, concepto, descripcion, fecha_alta, estado, palabras_clave, origenes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        expediente.numero,
                        expediente.concepto,
                        expediente.descripcion,
                        expediente.fecha_alta,
                        expediente.estado,
                        expediente.palabras_clave,
                        expediente.origenes,
                    ),
                )
                expediente_id = cursor.lastrowid
                
                # Insertar movimientos
                for i, mov in enumerate(reversed(movimientos), start=1):
                    conn.execute(
                        """INSERT INTO movimientos (expediente_id, orden, fecha_recepcion, dependencia)
                           VALUES (?, ?, ?, ?)""",
                        (expediente_id, i, mov.fecha_recepcion, mov.dependencia),
                    )
                
                # Actualizar dependencias
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
                
                self.stats.expedientes_inserted += 1
                logger.debug(f"Insertado expediente {expediente.numero} con {len(movimientos)} movimientos")
    
    def _update_asuntos(self) -> None:
        """Actualizar asuntos para expedientes nuevos."""
        try:
            from src.analysis.asuntos import populate_asuntos_table
            logger.info("Actualizando asuntos...")
            counts = populate_asuntos_table()
            total = sum(counts.values())
            logger.info(f"Asuntos actualizados: {total} en {len(counts)} conceptos")
        except Exception as e:
            logger.warning(f"Error actualizando asuntos (no crítico): {e}")
