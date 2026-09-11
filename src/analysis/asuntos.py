"""
Asuntos extraction module for SUME Dashboard.

Extracts 'asuntos' (subjects) from expediente descriptions using regex patterns.
Each concepto has its own set of patterns that map to asuntos.

Usage:
    from src.analysis.asuntos import extract_asuntos, populate_asuntos_table

    # Extract asuntos for a single description
    asunto = extract_asunto("Solicita CERTIFICADO ANALITICO de la carrera Bioquímica", "Gestión Alumno")

    # Populate asuntos table from all expedientes
    populate_asuntos_table()
"""

import re
import sqlite3
from typing import Optional
from dataclasses import dataclass

from src.database import get_connection


@dataclass
class AsuntoPattern:
    """A regex pattern that maps to an asunto."""
    asunto: str
    pattern: str
    priority: int = 0  # Higher = checked first


# ============================================================
# Patterns by concepto
# ============================================================

ASUNTO_PATTERNS: dict[str, list[AsuntoPattern]] = {
    # ===========================================================
    # Gestión Alumno - Certificados (diferenciados)
    # ===========================================================
    "Gestión Alumno": [
        # Certificados - orden de prioridad
        AsuntoPattern(
            asunto="Certificado Analítico",
            pattern=r"CERTIFICADO\s+ANAL[IÍ]TICO",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Historia Académica",
            pattern=r"HISTORIA\s+ACAD[EÉ]MICA",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Materias Aprobadas",
            pattern=r"MATERIAS?\s+APROBADAS?",
            priority=85,
        ),
        AsuntoPattern(
            asunto="Finalización de Carrera y Título en Trámite",
            pattern=r"FINALIZACI[OÓ]N\s+DE\s+CARRERA",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Sanciones Disciplinarias",
            pattern=r"SANCIONES?\s+DISCIPLINARIAS?",
            priority=75,
        ),
        # Trámites académicos
        AsuntoPattern(
            asunto="Extensión de regularidad",
            pattern=r"EXTENSI[OÓ]N\s+DE\s+REGULARIDAD",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Plan de estudios",
            pattern=r"PLAN\s+DE\s+ESTUDIOS",
            priority=65,
        ),
        AsuntoPattern(
            asunto="Inscripción a materia",
            pattern=r"INSCRIPCI[OÓ]N\s+A\s+(?:LA\s+)?MATERIA",
            priority=60,
        ),
        AsuntoPattern(
            asunto="Inscripción a tesina",
            pattern=r"INSCRIPCI[OÓ]N\s+(?:A\s+)?(?:LA\s+)?TESINA",
            priority=55,
        ),
        AsuntoPattern(
            asunto="Solicitud de equivalencia",
            pattern=r"EQUIVALENCIA",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Solicitud de regularización",
            pattern=r"REGULARIZACI[OÓ]N",
            priority=45,
        ),
        AsuntoPattern(
            asunto="Constancia de alumno regular",
            pattern=r"CONSTANCIA\s+(?:DE\s+)?ALUMNO\s+REGULAR",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Constancia de no haber sido pasible de sanciones",
            pattern=r"NO\s+HABER\s+SIDO\s+PASIBLE\s+DE\s+SANCIONES",
            priority=35,
        ),
    ],

    # ===========================================================
    # Gestión de Cargos Docentes
    # ===========================================================
    "Gestión de Cargos Docentes": [
        AsuntoPattern(asunto="Solicitud de cargo Jefe de Trabajos Prácticos", pattern=r"JEFE\s+TRAB(?:AJOS)?\.?\s+PR[AÁ]CTICOS?"),
        AsuntoPattern(asunto="Solicitud de cargo Ayudante de 1ra", pattern=r"AYUDANTE\s+DE\s+1RA"),
        AsuntoPattern(asunto="Solicitud de cargo Ayudante de Cátedra", pattern=r"AYUDANTE\s+DE\s+C[AÁ]TEDRA"),
        AsuntoPattern(asunto="Solicitud de cargo Profesor Adjunto", pattern=r"PROFESOR\s+ADJUNTO"),
        AsuntoPattern(asunto="Solicitud de cargo Profesor Asociado", pattern=r"PROFESOR\s+ASOCIADO"),
        AsuntoPattern(asunto="Solicitud de cargo Profesor Titular", pattern=r"PROFESOR\s+TITULAR"),
        AsuntoPattern(asunto="Solicitud de cargo Horas de Cátedra", pattern=r"HORAS?\s+DE\s+C[AÁ]TEDRA"),
        AsuntoPattern(asunto="Designación de cargo", pattern=r"DESIGNACI[OÓ]N\s+DE\s+CARGO"),
        AsuntoPattern(asunto="Renuncia a cargo", pattern=r"RENUNCIA\s+(?:AL\s+)?CARGO"),
    ],

    # ===========================================================
    # Gestión de Diplomas
    # ===========================================================
    "Gestión de Diplomas": [
        AsuntoPattern(asunto="Solicitud de diploma Licenciatura", pattern=r"DIPLOMA\s+(?:DE\s+)?(?:LA\s+)?LIC(?:\.|ENCIATURA)"),
        AsuntoPattern(asunto="Solicitud de diploma Doctorado", pattern=r"DIPLOMA\s+(?:DE\s+)?(?:EL\s+)?DOCTORADO"),
        AsuntoPattern(asunto="Solicitud de diploma Tecnicatura", pattern=r"DIPLOMA\s+(?:DE\s+)?(?:LA\s+)?TECNICATURA"),
        AsuntoPattern(asunto="Envío de diploma", pattern=r"ENV[IÍ]O\s+DE\s+DIPLOMA"),
        AsuntoPattern(asunto="Entrega de diploma", pattern=r"ENTREGA\s+DE\s+DIPLOMA"),
    ],

    # ===========================================================
    # Gestión de Pago a Proveedores
    # ===========================================================
    "Gestion de Pago a Proveedores": [
        AsuntoPattern(asunto="Liquidación y pago a proveedores", pattern=r"LIQUIDACI[OÓ]N\s+Y\s+PAGO\s+A\s+PROVEEDORES?"),
        AsuntoPattern(asunto="Pago al exterior", pattern=r"PAGO\s+AL\s+EXTERIOR"),
        AsuntoPattern(asunto="Transferencia de fondos", pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Devolución de cobros", pattern=r"DEVOLUCI[OÓ]N\s+DE\s+COBROS?"),
    ],

    # ===========================================================
    # Gestión de Viáticos
    # ===========================================================
    "Gestión de Viaticos": [
        AsuntoPattern(asunto="Solicitud de viáticos", pattern=r"VI[AÁ]TICOS?"),
    ],

    # ===========================================================
    # Gestión de Fondos con cargo a rendición
    # ===========================================================
    "Gestión de Fondos con cargo a rendición": [
        AsuntoPattern(asunto="Solicitud de adelanto a responsable", pattern=r"ADELANTO\s+A\s+RESPONSABLE"),
        AsuntoPattern(asunto="Solicitud de caja chica", pattern=r"CAJA\s+CHICA"),
        AsuntoPattern(asunto="Rendición de cuentas", pattern=r"RENDICI[OÓ]N\s+DE\s+CUENTAS?"),
        AsuntoPattern(asunto="Comprobantes de gastos", pattern=r"COMPROBANTES?\s+DE\s+GASTOS?"),
        AsuntoPattern(asunto="Conciliación bancaria", pattern=r"CONCILIACI[OÓ]N\s+BANCARIA"),
        AsuntoPattern(asunto="Libro banco", pattern=r"LIBRO\s+BANCO"),
    ],

    # ===========================================================
    # Gestión de Bienes Patrimoniales
    # ===========================================================
    "Gestión de Bienes Patrimoniales": [
        AsuntoPattern(asunto="Alta de bienes", pattern=r"ALTA\s+(?:DE\s+)?BIENES?"),
        AsuntoPattern(asunto="Baja de bienes", pattern=r"BAJA\s+(?:DE\s+)?BIENES?"),
        AsuntoPattern(asunto="Incorporación al patrimonio", pattern=r"INCORPORACI[OÓ]N\s+(?:AL\s+)?PATRIMONIO"),
        AsuntoPattern(asunto="Transferencia de bienes", pattern=r"TRANSFERENCIA\s+DE\s+BIENES?"),
        AsuntoPattern(asunto="Inventario de bienes", pattern=r"INVENTARIO\s+DE\s+BIENES?"),
    ],

    # ===========================================================
    # Gestión de Compras y Contrataciones
    # ===========================================================
    "Gestión de Compras y Contrataciones": [
        AsuntoPattern(asunto="Compra directa", pattern=r"COMPRA\s+DIRECTA"),
        AsuntoPattern(asunto="Compra directa simplificada", pattern=r"COMPRA\s+DIRECTA\s+SIMPLIFICADA"),
        AsuntoPattern(asunto="Licitación pública", pattern=r"LICITACI[OÓ]N\s+[PÚP]UBLICA"),
        AsuntoPattern(asunto="Adquisición de equipamiento", pattern=r"ADQUISICI[OÓ]N\s+DE\s+EQUIPAMIENTO"),
        AsuntoPattern(asunto="Adquisición de insumos", pattern=r"ADQUISICI[OÓ]N\s+DE\s+INSUMOS?"),
        AsuntoPattern(asunto="Mantenimiento de equipos", pattern=r"MANTENIMIENTO\s+DE\s+EQUIPOS?"),
    ],

    # ===========================================================
    # Gestión de Becas
    # ===========================================================
    "Gestión de Becas": [
        AsuntoPattern(asunto="Solicitud de beca", pattern=r"SOLICITUD\s+DE\s+BECA"),
        AsuntoPattern(asunto="Prórroga de beca", pattern=r"PR[OÓ]RROGA\s+DE\s+BECA"),
        AsuntoPattern(asunto="Suspensión de beca", pattern=r"SUSPENSI[OÓ]N\s+DE\s+BECA"),
        AsuntoPattern(asunto="Renuncia a beca", pattern=r"RENUNCIA\s+(?:A\s+)?(?:LA\s+)?BECA"),
        AsuntoPattern(asunto="Beca de comisión de servicios", pattern=r"BECA\s+DE\s+COMISI[OÓ]N\s+DE\s+SERVICIOS"),
        AsuntoPattern(asunto="Beca de integración académica", pattern=r"BECA\s+DE\s+INTEGRACI[OÓ]N\s+ACAD[EÉ]MICA"),
        AsuntoPattern(asunto="Cientibeca", pattern=r"SCIENTIBECA|CIENTIBECA"),
    ],

    # ===========================================================
    # Gestión de Particulares
    # ===========================================================
    "Gestión de Particulares": [
        AsuntoPattern(asunto="Certificación de servicios", pattern=r"CERTIFICACI[OÓ]N\s+DE\s+SERVICIOS"),
        AsuntoPattern(asunto="Certificación de servicios y remuneraciones", pattern=r"CERTIFICACI[OÓ]N\s+DE\s+SERVICIOS\s+Y\s+REMUNERACIONES"),
        AsuntoPattern(asunto="Solicitud de subsidio", pattern=r"SOLICITUD\s+DE\s+SUBSIDIO"),
        AsuntoPattern(asunto="Renuncia al cargo", pattern=r"RENUNCIA\s+(?:AL\s+)?CARGO"),
        AsuntoPattern(asunto="Plan de estudios", pattern=r"PLAN\s+DE\s+ESTUDIOS"),
        AsuntoPattern(asunto="Solicitud de licencia", pattern=r"SOLICITUD\s+DE\s+LICENCIA"),
    ],

    # ===========================================================
    # Gestión Personal Docente
    # ===========================================================
    "Gestión Personal Docente": [
        AsuntoPattern(asunto="Licencia por maternidad", pattern=r"LICENCIA\s+POR\s+MATERNIDAD"),
        AsuntoPattern(asunto="Licencia por enfermedad", pattern=r"LICENCIA\s+POR\s+ENFERMEDAD"),
        AsuntoPattern(asunto="Licencia con goce de haberes", pattern=r"LICENCIA\s+CON\s+GOCE\s+DE\s+HABERES"),
        AsuntoPattern(asunto="Licencia sin goce de sueldo", pattern=r"LICENCIA\s+SIN\s+GOCE\s+DE\s+SUENDO"),
        AsuntoPattern(asunto="Certificación de servicios", pattern=r"CERTIFICACI[OÓ]N\s+DE\s+SERVICIOS"),
        AsuntoPattern(asunto="Designación de jurado", pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO"),
        AsuntoPattern(asunto="Nómina de jurados", pattern=r"N[OÓ]MINA\s+DE\s+JURADOS?"),
        AsuntoPattern(asunto="Planificación", pattern=r"PLANIFICACI[OÓ]N"),
        AsuntoPattern(asunto="Horas extras", pattern=r"HORAS?\s+EXTRAS?"),
    ],

    # ===========================================================
    # Gestión Personal No Docente
    # ===========================================================
    "Gestión Personal No Docente": [
        AsuntoPattern(asunto="Licencia por enfermedad", pattern=r"LICENCIA\s+POR\s+ENFERMEDAD"),
        AsuntoPattern(asunto="Inasistencia injustificada", pattern=r"INASISTENCIA\s+INJUSTIFICADA"),
        AsuntoPattern(asunto="Permiso de lactancia", pattern=r"PERMISO\s+DE\s+LACTANCIA"),
        AsuntoPattern(asunto="Renuncia al cargo", pattern=r"RENUNCIA\s+(?:AL\s+)?CARGO"),
        AsuntoPattern(asunto="Designación de jurado", pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO"),
        AsuntoPattern(asunto="Situación de revista", pattern=r"SITUACI[OÓ]N\s+DE\s+REVISTA"),
        AsuntoPattern(asunto="Horas extras", pattern=r"HORAS?\s+EXTRAS?"),
    ],

    # ===========================================================
    # Actas de exámenes y de regularización
    # ===========================================================
    "Actas de exámenes y de regularización": [
        AsuntoPattern(asunto="Acta de examen", pattern=r"ACTA\s+DE\s+EX[AÁ]MEN"),
        AsuntoPattern(asunto="Acta de promoción", pattern=r"ACTA\s+DE\s+PROMOCI[OÓ]N"),
        AsuntoPattern(asunto="Nómina de alumnos", pattern=r"N[OÓ]MINA\s+DE\s+ALUMNOS?"),
        AsuntoPattern(asunto="Rectificación de acta", pattern=r"RECTIFICACI[OÓ]N\s+DE\s+ACTA"),
        AsuntoPattern(asunto="Acta de alumnos externos", pattern=r"ACTA\s+DE\s+ALUMNOS?\s+EXTERNOS?"),
    ],

    # ===========================================================
    # Gestión de Convenios y Acuerdos
    # ===========================================================
    "Gestión de Convenios y Acuerdos": [
        AsuntoPattern(asunto="Certificado de cumplimiento fiscal", pattern=r"CERTIFICADO\s+DE\s+CUMPLIMIENTO\s+FISCAL"),
        AsuntoPattern(asunto="Certificado de deudores morosos", pattern=r"CERTIFICADO\s+DE\s+DEUDORES?\s+MOROSOS"),
        AsuntoPattern(asunto="Rectificativa SAT", pattern=r"RECTIFICATIVA\s+SAT"),
        AsuntoPattern(asunto="Transferencia de fondos", pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Convenio marco", pattern=r"CONVENIO\s+MARCO"),
    ],

    # ===========================================================
    # Gestión de Ingresos de Fondos
    # ===========================================================
    "Gestión de Ingresos de Fondos": [
        AsuntoPattern(asunto="Elevación de orden de trabajo", pattern=r"ELEVACI[OÓ]N\s+DE\s+OT|ELEVACI[OÓ]N\s+OT|ELEVAR\s+(?:LA\s+)?OT"),
        AsuntoPattern(asunto="Aprobación de movimientos bancarios", pattern=r"APROBACI[OÓ]N\s+DE\s+MOVIMIENTOS?\s+BANCARIOS?"),
        AsuntoPattern(asunto="Solicitud de documentación", pattern=r"SOLICITUD\s+DE\s+DOCUMENTACI[OÓ]N"),
    ],

    # ===========================================================
    # Gestión de Órganos de Gobierno y Autoridades
    # ===========================================================
    "Gestión de Órganos de Gobierno y Autoridades": [
        AsuntoPattern(asunto="Designación de autoridades", pattern=r"DESIGNACI[OÓ]N\s+DE\s+AUTORIDADES?"),
        AsuntoPattern(asunto="Prórroga de beca", pattern=r"PR[OÓ]RROGA\s+DE\s+BECA"),
        AsuntoPattern(asunto="Renovación de comité", pattern=r"RENOVACI[OÓ]N\s+DE\s+COMIT[EÉ]"),
        AsuntoPattern(asunto="Habilitación de laboratorio", pattern=r"HABILITACI[OÓ]N\s+DE\s+LABORATORIO"),
        AsuntoPattern(asunto="Resolución de CD", pattern=r"RESOLUCI[OÓ]N\s+(?:DEL\s+)?CD|RES\.?\s+CD"),
    ],

    # ===========================================================
    # SAT - SET
    # ===========================================================
    "SAT - SET": [
        AsuntoPattern(asunto="Solicitud de formulario 931", pattern=r"FORMULARIO\s+931|F931"),
        AsuntoPattern(asunto="Solicitud de documentación", pattern=r"SOLICITUD\s+DE\s+DOCUMENTACI[OÓ]N"),
        AsuntoPattern(asunto="Transferencia de fondos", pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Rendición de fondos", pattern=r"RENDICI[OÓ]N\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Adenda a convenio", pattern=r"ADENDA\s+AL\s+CONVENIO"),
    ],
}


def extract_asunto(descripcion: str, concepto: str) -> Optional[str]:
    """
    Extract asunto from a description using regex patterns.

    Args:
        descripcion: The expediente description.
        concepto: The expediente concepto.

    Returns:
        The matched asunto, or None if no pattern matches.
    """
    if not descripcion:
        return None

    patterns = ASUNTO_PATTERNS.get(concepto, [])
    desc_upper = descripcion.upper()

    # Sort by priority (higher first)
    sorted_patterns = sorted(patterns, key=lambda p: p.priority, reverse=True)

    for ap in sorted_patterns:
        if re.search(ap.pattern, desc_upper):
            return ap.asunto

    return None


def get_all_asuntos() -> dict[str, list[str]]:
    """
    Get all defined asuntos by concepto.

    Returns:
        Dictionary mapping concepto to list of asunto names.
    """
    result = {}
    for concepto, patterns in ASUNTO_PATTERNS.items():
        result[concepto] = [p.asunto for p in patterns]
    return result


def populate_asuntos_table() -> dict[str, int]:
    """
    Populate the asuntos table from patterns and link to expedientes.

    Returns:
        Dictionary with counts: {concepto: num_asuntos}
    """
    conn = get_connection()
    counts = {}

    # Insert asuntos from patterns
    for concepto, patterns in ASUNTO_PATTERNS.items():
        count = 0
        for p in patterns:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO asuntos (concepto, asunto, patron_regex) VALUES (?, ?, ?)",
                    (concepto, p.asunto, p.pattern),
                )
                count += 1
            except Exception as e:
                print(f"Error inserting asunto {p.asunto}: {e}")
        counts[concepto] = count

    conn.commit()

    # Link expedientes to asuntos
    _link_expedientes_to_asuntos(conn)

    return counts


def _link_expedientes_to_asuntos(conn: sqlite3.Connection) -> int:
    """
    Link expedientes to their extracted asuntos.

    Returns:
        Number of links created.
    """
    # Get all expedientes with descriptions
    cursor = conn.execute(
        "SELECT id, descripcion, concepto FROM expedientes WHERE descripcion IS NOT NULL AND descripcion != ''"
    )

    linked = 0
    batch = []

    for exp_id, descripcion, concepto in cursor:
        asunto = extract_asunto(descripcion, concepto)
        if asunto:
            # Get asunto_id
            asunto_row = conn.execute(
                "SELECT id FROM asuntos WHERE concepto = ? AND asunto = ?",
                (concepto, asunto),
            ).fetchone()

            if asunto_row:
                batch.append((exp_id, asunto_row[0]))

                # Batch insert every 1000 rows
                if len(batch) >= 1000:
                    conn.executemany(
                        "INSERT OR IGNORE INTO expediente_asuntos (expediente_id, asunto_id) VALUES (?, ?)",
                        batch,
                    )
                    linked += len(batch)
                    batch = []

    # Insert remaining
    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO expediente_asuntos (expediente_id, asunto_id) VALUES (?, ?)",
            batch,
        )
        linked += len(batch)

    conn.commit()
    return linked


def get_asuntos_for_concepto(concepto: str) -> list[str]:
    """
    Get available asuntos for a concepto.

    Args:
        concepto: The concepto name.

    Returns:
        List of asunto names.
    """
    conn = get_connection()
    cursor = conn.execute(
        "SELECT DISTINCT asunto FROM asuntos WHERE concepto = ? ORDER BY asunto",
        (concepto,),
    )
    return [row[0] for row in cursor.fetchall()]


def get_expedientes_by_asunto(concepto: str, asunto: str) -> list[int]:
    """
    Get expediente IDs matching a specific asunto.

    Args:
        concepto: The concepto name.
        asunto: The asunto name.

    Returns:
        List of expediente IDs.
    """
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT e.id FROM expedientes e
        JOIN expediente_asuntos ea ON e.id = ea.expediente_id
        JOIN asuntos a ON ea.asunto_id = a.id
        WHERE e.concepto = ? AND a.asunto = ?
        """,
        (concepto, asunto),
    )
    return [row[0] for row in cursor.fetchall()]
