"""
Configuración del SUME Scraper.

Proporciona configuración tipada con Pydantic para el scraping de
expedientes de diferentes unidades académicas de la UNL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ScraperConfig:
    """
    Configuración para el SUME Scraper.
    
    Attributes:
        faculty_code: Código de la unidad académica (ej: "FBCB", "FCA", "FCV")
        date_from: Fecha de inicio del rango (YYYY-MM-DD o DD/MM/YYYY)
        date_to: Fecha de fin del rango (YYYY-MM-DD o DD/MM/YYYY)
        base_url: URL base de SUME
        delay_seconds: Delay entre requests HTTP (segundos)
        timeout_seconds: Timeout para requests HTTP (segundos)
        max_retries: Número máximo de reintentos
        backoff_base: Base para backoff exponencial (segundos)
        rate_limit_wait: Espera en respuesta 429 (segundos)
        raw_html_dir: Directorio para HTML crudo
        db_path: Ruta a la base de datos SQLite
        user_agent: User-Agent para requests HTTP
    """
    
    faculty_code: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    base_url: str = "https://servicios.unl.edu.ar/expedientes/"
    delay_seconds: float = 0.5
    timeout_seconds: int = 30
    max_retries: int = 3
    backoff_base: float = 1.0
    rate_limit_wait: int = 60
    raw_html_dir: str = "data/raw"
    db_path: str = "data/sume.db"
    user_agent: str = "SUME-Scraper/1.0 (Universidad Nacional del Litoral)"
    
    def __post_init__(self):
        """Validar y normalizar configuración después de la inicialización."""
        # Validar faculty_code
        if not self.faculty_code or not self.faculty_code.strip():
            raise ValueError("faculty_code no puede estar vacío")
        self.faculty_code = self.faculty_code.strip().upper()
        
        # Normalizar fechas
        if self.date_from:
            self.date_from = self._normalize_date(self.date_from)
        if self.date_to:
            self.date_to = self._normalize_date(self.date_to)
        
        # Validar rango de fechas
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError(
                    f"date_from ({self.date_from}) debe ser anterior a date_to ({self.date_to})"
                )
    
    def _normalize_date(self, date_str: str) -> str:
        """
        Normalizar fecha a formato YYYY-MM-DD.
        
        Acepta:
        - YYYY-MM-DD (ISO)
        - DD/MM/YYYY (formato SUME)
        
        Returns:
            Fecha en formato YYYY-MM-DD
        """
        date_str = date_str.strip()
        
        # Ya está en formato ISO
        if "-" in date_str and len(date_str) == 10:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                return date_str
            except ValueError:
                pass
        
        # Formato DD/MM/YYYY
        if "/" in date_str:
            try:
                dt = datetime.strptime(date_str, "%d/%m/%Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        raise ValueError(
            f"Formato de fecha inválido: '{date_str}'. "
            f"Use YYYY-MM-DD o DD/MM/YYYY"
        )
    
    def get_search_params(self) -> dict:
        """
        Construir parámetros de búsqueda para SUME.
        
        Returns:
            Dict con parámetros para POST a buscar/
        """
        params = {
            "numero": self.faculty_code,
            "descripcion": "",
            "palabraClave": "",
            "selectOrigen": "interno",
            "mesaEntrada": "",
            "oficina": "",
            "concepto": "",
            "fechaCdesde": "",
            "fechaChasta": "",
            "tipoDR": "",
            "numeroDR": "",
        }
        
        # Formatear fechas para SUME (DD/MM/YYYY)
        if self.date_from:
            dt = datetime.strptime(self.date_from, "%Y-%m-%d")
            params["fechaCdesde"] = dt.strftime("%d/%m/%Y")
        
        if self.date_to:
            dt = datetime.strptime(self.date_to, "%Y-%m-%d")
            params["fechaChasta"] = dt.strftime("%d/%m/%Y")
        
        return params
    
    def get_page_url(self, page: int) -> str:
        """
        Construir URL de paginación.
        
        Args:
            page: Número de página
            
        Returns:
            URL completa de la página
        """
        return f"{self.base_url.rstrip('/')}/buscar/{page}/"
    
    def get_detail_url(self, numero: str) -> str:
        """
        Construir URL de detalle de expediente.
        
        Args:
            numero: Número del expediente
            
        Returns:
            URL completa del detalle
        """
        return f"{self.base_url.rstrip('/')}/expediente/{numero}"
    
    def get_raw_html_path(self, filename: str) -> Path:
        """
        Obtener ruta para guardar HTML crudo.
        
        Args:
            filename: Nombre del archivo (sin extensión)
            
        Returns:
            Path completo con extensión .html
        """
        raw_dir = Path(self.raw_html_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir / f"{filename}.html"
    
    def get_db_connection_string(self) -> str:
        """
        Obtener cadena de conexión a la base de datos.
        
        Returns:
            Ruta a la base de datos SQLite
        """
        return self.db_path
