"""
TypedDict models for SUME Dashboard database rows.

These provide type-safe access to database rows when using sqlite3.Row
or when converting to/from pandas DataFrames.
"""

from typing import TypedDict, NotRequired
from datetime import date, datetime


class ExpedienteDict(TypedDict):
    """Row from expedientes table."""

    id: int
    numero: str
    concepto: str
    descripcion: str | None
    fecha_alta: date | str
    estado: str | None
    palabras_clave: str | None
    origenes: str | None
    fecha_extraccion: datetime | str


class ExpedienteInputDict(TypedDict):
    """Input for inserting a new expediente (excludes auto-generated fields)."""

    numero: str
    concepto: str
    descripcion: NotRequired[str | None]
    fecha_alta: date | str
    estado: NotRequired[str | None]
    palabras_clave: NotRequired[str | None]
    origenes: NotRequired[str | None]


class MovimientoDict(TypedDict):
    """Row from movimientos table."""

    id: int
    expediente_id: int
    orden: int
    fecha_recepcion: date | str
    dependencia: str


class MovimientoInputDict(TypedDict):
    """Input for inserting a new movimiento."""

    expediente_id: int
    orden: int
    fecha_recepcion: date | str
    dependencia: str


class DependenciaDict(TypedDict):
    """Row from dependencias table."""

    id: int
    nombre: str
    nombre_original: str
    total_expedientes: int


class DependenciaInputDict(TypedDict):
    """Input for inserting/updating a dependencia."""

    nombre: str
    nombre_original: str
    total_expedientes: NotRequired[int]


class CircuitoDict(TypedDict):
    """Row from circuitos table."""

    id: int
    circuito: str  # JSON array of dependency names
    concepto: str
    frecuencia: int
    es_mas_frecuente: bool


class CircuitoInputDict(TypedDict):
    """Input for inserting a new circuito."""

    circuito: str
    concepto: str
    frecuencia: int
    es_mas_frecuente: NotRequired[bool]


# Type aliases for common query results
ExpedienteWithMovimientos = tuple[ExpedienteDict, list[MovimientoDict]]
CircuitFrequencyRow = tuple[str, str, int, bool]  # circuito_json, concepto, frecuencia, es_mas_frecuente