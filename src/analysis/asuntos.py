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
        # =====================================================
        # PRIORIDAD ALTA (100-80): Certificados y trámites críticos
        # =====================================================
        AsuntoPattern(
            asunto="Certificado Analítico",
            pattern=r"CERTIFICADO\s+ANAL[IÍ]TICO",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Historia Académica",
            pattern=r"HISTORIA\s+ACAD[EÉ]MICA",
            priority=95,
        ),
        AsuntoPattern(
            asunto="Certificado de Sanciones Disciplinarias",
            pattern=r"(?:CERTIFICADO|CONSTANCIA)\s+(?:DE\s+)?(?:NO\s+)?SANC(?:IONES?|IÓN(?:ES)?)\s+DISCIPLINARI[AO]?S?|(?:CERTIFICADO|CONSTANCIA)\s+(?:DE\s+)?(?:NO\s+)?SANC(?:IONES?|IÓN(?:ES)?)|SANC(?:IONES?|IÓN(?:ES)?)\s+DISCIPLINARIAS?|SANCION\s+DICIPLINARIA",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Diplomas",
            pattern=r"DIPLOMA|ENV[IÍ]O\s+DE\s+DIPLOMA|ENTREGA\s+DE\s+DIPLOMA",
            priority=85,
        ),
        AsuntoPattern(
            asunto="Materias Aprobadas",
            pattern=r"MATERIAS?\s+APROBADAS?",
            priority=80,
        ),
        # =====================================================
        # PRIORIDAD MEDIA-ALTA (79-60): Trámites académicos
        # =====================================================
        AsuntoPattern(
            asunto="Plan de Estudios y Programas",
            pattern=r"PLAN\s+DE\s+ESTUDIOS?|SOLICITUD.*PROGRAMAS|SOLICITUD.*PROGRAMA\s+DE|PROGRAMA\s+(?:DE\s+)?MATERIAS?|PROGRAMAS?\s+DE\s+ASIGNATURA|SOLICITUD.*PROGRAMA.*MATERIA|SOLICITUD.*PROGRAMA.*ASIGNATURA|COPIA.*PROGRAMAS|CERTIFICACI[OÓ]N.*PROGRAMAS|LEGALIZACI[OÓ]N.*PROGRAMAS|LEGALIZACI[OÓ]N.*PROGRAMA|PLAN\s+ESTUDIO|PLAN\s+DE\s+MATERIA|PROGRAMAS?\s+CERTIFICADOS?|ENV[IÍ]O.*PROGRAMAS|PLAN\s+POLAN|POLAN\s+DE\s+ESTUDIOS",
            priority=75,
        ),
        AsuntoPattern(
            asunto="Extensión de regularidad",
            pattern=r"EXTENSI[OÓ]N\s+DE\s+REGULARIDAD|EXTENSI[OÓ]N\s+DE\s+LAS?\s+REGULARIDAD|EXTENCI[OÓ]N\s+DE\s+REGULARIDAD|EXTENSI[OÓ]N\s+DE\s+MI\s+REGULARIDAD|EXTENDER\s+LA\s+REGULARIDAD|EXTENCI[OÓ]N.*REGULARIDAD",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Admisión a Carrera de Posgrado",
            pattern=r"INSCRIPCI[OÓ]N\s+A\s+LA\s+CARRERA\s+DE\s+POSGRADO|INSCRIPCI[OÓ]N.*POSGRADO|ADMISI[OÓ]N.*POSGRADO|ADMISI[OÓ]N.*DOCTORADO|ADMISI[OÓ]N.*MAESTR|ADMISI[OÓ]N.*ESPECIALIZACI[OÓ]N|ADMISI[OÓ]N.*CARRERA.*POSGRADO|INSCRIPCI[OÓ]N.*CARRERA.*POSGRADO|INSCRIPCI[OÓ]N.*POSGRADO",
            priority=65,
        ),
        AsuntoPattern(
            asunto="Rectificación de Actas",
            pattern=r"RECTIFICACI[OÓ]N\s+DEL?\s+ACTA|RECTIFICACI[OÓ]N\s+DE\s+NOTA|RECTIFICAR\s+ACTA|RECTIFICA.*ACTA|RECTIFICACI[OÓ]N\s+DE\s+EXAMEN",
            priority=60,
        ),
        # =====================================================
        # PRIORIDAD MEDIA (59-40): Trámites frecuentes
        # =====================================================
        AsuntoPattern(
            asunto="Uso de Instalaciones",
            pattern=r"USO\s+DE\s+INSTALACIONES|USO\s+DE\s+LA\s+FACULTAD|PERMITAN\s+EL\s+USO|SOLICITUD.*USO.*INSTALACIONES|SOLICITUD.*USO.*FACULTAD|USO\s+DE\s+UN\s+AULA|USO\s+DE\s+AULA|SOLICITUD\s+DE\s+AULA|SOLICITUD\s+UN\s+AULA|SOLICITUD.*AULA|SOLICITA.*AULA|PARA\s+\d+\s+PERSONAS|CAPACIDAD\s+PARA|USO\s+DE\s+LAS\s+INSTALACIONES|ACTIVIDADES?\s+CON\s+FINES?\s+ACAD[ÉE]MICOS?",
            priority=55,
        ),
        AsuntoPattern(
            asunto="Homologación de materias",
            pattern=r"HOMOLOGACI[OÓ]N|HOMOLOGAR|EQUIVALENCIA|HOMOLOGACI6N",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Cancelación de Matrícula",
            pattern=r"CANCELACI[OÓ]N\s+DE\s+MATR[IÍ]CULA|CANCELACI[OÓ]N\s+DE\s+LA\s+MATR[IÍ]CULA|BAJA\s+DE\s+LA\s+MATR[IÍ]CULA|CANCELACI[OÓ]N\s+DE\s+MI\s+MATR[IÍ]CULA",
            priority=45,
        ),
        AsuntoPattern(
            asunto="Inscripción a Concurso Alumno",
            pattern=r"INSCRIPCI[OÓ]N.*CONCURSO.*AYUDANTE\s+ALUMNO|INSCRIPCI[OÓ]N.*CONCURSO.*ALUMNO|CONCURSO.*AYUDANTE\s+ALUMNO|POSTULARME.*CONCURSO.*ALUMNO|CUBRIR.*CARGO.*AYUDANTE\s+ALUMNO|INSCRIPCI[OÓ]N.*AL\s+CONCURSO.*ALUMNO|CONCURSO\s+PARA\s+LA\s+VACANTE|INSCRIPCI[OÓ]N.*CONCURSO.*PROFESOR|INSCRIPCI[OÓ]N.*CONCURSO.*ADJUNTO",
            priority=42,
        ),
        AsuntoPattern(
            asunto="Prórrogas/Extensión de Plazos",
            pattern=r"PR[OÓ]RROGA|EXTENSI[OÓ]N\s+DE\s+PLAZO|EXTENSI[OÓ]N.*A[ÑN]O|PLAZO\s+ADICIONAL|SUSPENSI[OÓ]N\s+DE\s+PLAZOS|SUSPENSI[OÓ]N\s+DE\s+PLAZO",
            priority=40,
        ),
        # =====================================================
        # PRIORIDAD MEDIA-BAJA (39-20): Trámites puntuales
        # =====================================================
        AsuntoPattern(
            asunto="Trabajo Final de Grado",
            pattern=r"TRABAJO\s+FINAL\s+DE\s+GRADO|TRABAJO\s+FINAL|TESIS\s+DE\s+GRADO|TRABAJO\s+FINAL/TESINA|TFI|TRABAJO\s+FINAL\s+INTEGRADOR|PROYECTO\s+(?:DE\s+)?TFI",
            priority=38,
        ),
        AsuntoPattern(
            asunto="Trabajo Final de Posgrado",
            pattern=r"TESIS\s+DE\s+(?:DOCTORADO|MAESTR|POSGRADO)|MANUSCRITO.*TESIS|TESIS.*DOCTORADO|TESIS.*MAESTR|PROYECTO\s+DE\s+VINCULACI[OÓ]N.*GESTI[OÓ]N",
            priority=36,
        ),
        AsuntoPattern(
            asunto="Mal Cargados",
            pattern=r"LICENCIA\s+POSTMATERNIDAD|CAMBIOS?\s+EN\s+LA\s+LISTA\s+DE\s+PRECIOS|LISTA\s+DE\s+NECESIDADES\s+DE\s+MATERIAL|COMPRA\s+DE\s+MATERIAL\s+DE\s+LIBRER[IÍ]A|ESTANCIA\s+DE\s+INVESTIGACI[OÓ]N|NO\s+CONTINUAR[ÉE]\s+EN\s+MIS\s+FUNCIONES|RENUNCIO\s+A\s+MIS\s+CARGOS\s+DE\s+DOCENTE",
            priority=1,
        ),
        AsuntoPattern(
            asunto="Cursado Condicional",
            pattern=r"CURSADO\s+CONDICIONAL|INSCRIPCI[OÓ]N\s+CONDICIONAL|CURSADO\s+EXCEPCIONAL|EXCEPCI[OÓ]N\s+QUE\s+ME\s+PERMITA\s+CONTINUAR",
            priority=34,
        ),
        AsuntoPattern(
            asunto="Conformación de jurado",
            pattern=r"CONFORMAR\s+JURADO|CONFORMACI[OÓ]N\s+(?:DE\s+)?JURADO|CREACI[OÓ]N\s+DE\s+JURADO|SOLICITUD.*JURADO|JURADO\s+DE\s+TESINA|JURADO.*TESINA|TRIBUNAL\s+EVALUADOR|NOMINA.*JURADO",
            priority=32,
        ),
        AsuntoPattern(
            asunto="Renuncia a Regularidad",
            pattern=r"RENUNCIA\s+A\s+LA\s+REGULARIDAD|RENUNCIA\s+A\s+LA\s+REGULARI|RENUNCIA\s+DE\s+LA\s+REGULARIDAD|BAJA\s+COMO\s+ALUMNO|BAJA\s+COMO\s+ALUMNA|BAJA\s+DEL\s+DOCTORADO|BAJA\s+DE\s+LA\s+CARRERA|RENUNCIA.*REGULARIDAD|RENUNCIA\s+(?:AL|DEL)\s+CARGO|NO\s+CONTINUAR[ÉE]\s+EN\s+MIS\s+FUNCIONES|RENUNCIO\s+A\s+MIS\s+CARGOS|LICENCIA\s+POSTMATERNIDAD|RENUNCIA\s+AL\s+CONTRATO",
            priority=30,
        ),
        AsuntoPattern(
            asunto="Licencia Sin Goce de Sueldo",
            pattern=r"LICENCIA\s+SIN\s+GOCE\s+DE\s+SU[EL]DO|EXTENSI[OÓ]N.*LICENCIA\s+SIN\s+GOCE",
            priority=29,
        ),
        AsuntoPattern(
            asunto="Readmisión",
            pattern=r"READMISI[OÓ]N|REINSCRIPCI[OÓ]N|REINSCRIPCION",
            priority=28,
        ),
        AsuntoPattern(
            asunto="Inscripción Fuera de Término",
            pattern=r"INSCRIPCI[OÓ]N\s+FUERA\s+DE\s+T[ÉE]RMINO|INSCRIPCI[OÓ]N\s+FUERA\s+DE\s+PLAZO",
            priority=26,
        ),
        AsuntoPattern(
            asunto="Baja de Alumnos",
            pattern=r"BAJA\s+A\s+LOS\s+ALUMNOS?|BAJA\s+DE\s+ALUMNOS?|OTORGAR\s+LA\s+BAJA.*ALUMNO",
            priority=24,
        ),
        AsuntoPattern(
            asunto="Constancias",
            pattern=r"CONSTANCIA\s+DE\s+CARGA\s+HORARIA|CONSTANCIA\s+DE\s+ALUMNO\s+REGULAR|CONSTANCIA\s+(?:DE\s+)?NO\s+POSEER|CONSTANCIA\s+(?:DE\s+)?NO\s+SANC(?:ION|IÓN)(?:ES)?|CONSTANCIA\s+(?:DE\s+)?(?:NO\s+)?SANC(?:ION|IÓN)(?:ES)?|CONSTANCIA\s+DE\s+NO\s+TENER|CONSTANCIA\s+DE\s+CARGA\s+HORARIA.*AÑOS|CORROBORAR.*EGRES[ÓO]",
            priority=22,
        ),
        AsuntoPattern(
            asunto="Revisión de Expedientes",
            pattern=r"REVEA\s+EL\s+EXP|REVISI[OÓ]N\s+DE\s+EXPEDIENTE|SE\s+REVEA.*EXPEDIENTE",
            priority=20,
        ),
        # =====================================================
        # PRIORIDAD BAJA (19-10): Trámites menos frecuentes
        # =====================================================
        AsuntoPattern(
            asunto="Inscripción a materia",
            pattern=r"INSCRIPCI[OÓ]N\s+A\s+(?:LA\s+)?MATERIA|INSCRIPCI[OÓ]N\s+A\s+LAS?\s+MATERIAS|INSCRIBIRME\s+AL\s+CURSADO",
            priority=18,
        ),
        AsuntoPattern(
            asunto="Inscripción a tesina",
            pattern=r"INSCRIPCI[OÓ]N\s+(?:A\s+)?(?:LA\s+)?TESINA|INSCRIPCI[OÓ]N.*TESINA",
            priority=16,
        ),
        AsuntoPattern(
            asunto="Solicitud de regularización",
            pattern=r"REGULARIZACI[OÓ]N",
            priority=14,
        ),
        AsuntoPattern(
            asunto="Certificado de incumbencias",
            pattern=r"CERTIFICADO\s+DE\s+INCUMBENCIAS",
            priority=12,
        ),
        AsuntoPattern(
            asunto="Finalización de Carrera y Título en Trámite",
            pattern=r"FINALIZACI[OÓ]N\s+DE\s+CARRERA",
            priority=10,
        ),
        # =====================================================
        # PRIORIDAD MUY BAJA (9-1): Trámites poco frecuentes
        # =====================================================
        AsuntoPattern(
            asunto="Cambio de horario",
            pattern=r"CAMBIO\s+DE\s+HORARIO|CAMBIO\s+DE\s+HORA",
            priority=9,
        ),
        AsuntoPattern(
            asunto="Propuesta de cátedra abierta",
            pattern=r"C[AÁ]TEDRA\s+ABIERTA",
            priority=8,
        ),
        AsuntoPattern(
            asunto="Renuncia a beneficio",
            pattern=r"RENUNCI[OÓ]\s+BENEFICIO|RENUNCI[OÓ]\s+.*JUBILACI[OÓ]N|RENUNCIA.*BENEFICIO|RENUNCIA.*JUBILACI[OÓ]N",
            priority=7,
        ),
        AsuntoPattern(
            asunto="Designación de auxiliar docente",
            pattern=r"DESIGNACI[OÓ]N.*AUXILIAR\s+DOCENTE",
            priority=6,
        ),
        AsuntoPattern(
            asunto="Certificación complementaria",
            pattern=r"CERTIFICACI[OÓ]N\s+COMPLEMENTARIA",
            priority=5,
        ),
        AsuntoPattern(
            asunto="Propuesta de comisión especial",
            pattern=r"COMISI[OÓ]N\s+ESPECIAL|PROPUESTA.*COMISI[OÓ]N\s+ESPECIAL",
            priority=4,
        ),
        AsuntoPattern(
            asunto="Justificación de Inasistencias",
            pattern=r"JUSTIFICACI[OÓ]N\s+DE\s+INASISTENCIAS?|JUSTIFICACI[OÓ]N.*INASISTENCIAS?|JUSTIFICAR.*INASISTENCIAS?",
            priority=3,
        ),
        AsuntoPattern(
            asunto="Acreditación de Créditos/Cursos/Publicaciones Posgrado",
            pattern=r"ACREDITACI[OÓ]N\s+DE\s+CR[ÉE]DITOS|ACREDITACI[OÓ]N\s+DE\s+CURSO|ACREDITACI[OÓ]N\s+DE\s+PUBLICACI[OÓ]N|ACREDITAR\s+CURSO|ACREDITAR\s+CR[ÉE]DITO",
            priority=35,
        ),
        AsuntoPattern(
            asunto="Otro",
            pattern=r".+",
            priority=0,
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
        AsuntoPattern(asunto="Solicitud de cargo FBCB", pattern=r"SOLICITUD\s+DE\s+CARGO\s+DE\s+FBCB"),
    ],

    # ===========================================================
    # Gestión de Pago a Proveedores
    # ===========================================================
    "Gestion de Pago a Proveedores": [
        AsuntoPattern(asunto="Liquidación y pago a proveedores", pattern=r"LIQUIDACI[OÓ]N\s+Y\s+PAGO\s+A\s+PROVEEDORES?"),
        AsuntoPattern(asunto="Pago al exterior", pattern=r"PAGO\s+AL\s+EXTERIOR"),
        AsuntoPattern(asunto="Transferencia de fondos", pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Devolución de cobros", pattern=r"DEVOLUCI[OÓ]N\s+DE\s+COBROS?"),
        AsuntoPattern(asunto="Liquidación de pagos", pattern=r"LIQUIDACI[OÓ]N\s+DE\s+PAGO"),
        AsuntoPattern(asunto="Contratación", pattern=r"CONTRATACI[OÓ]N"),
        AsuntoPattern(asunto="CCE", pattern=r"CCE\s+\d|CCE\s*\d"),
        AsuntoPattern(asunto="CDSD", pattern=r"CDSD\s+\d|CDSD\s*\d"),
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
        AsuntoPattern(asunto="Baja de bienes", pattern=r"BAJA\s+(?:DE\s+)?BIENES?|BAJA\s+PATRIMONIAL|BAJA\s+DE\s+ELEMENTOS"),
        AsuntoPattern(asunto="Incorporación al patrimonio", pattern=r"INCORPORACI[OÓ]N\s+(?:AL\s+)?PATRIMONIO|INCORPORAR\s+AL\s+PATRIMONIO"),
        AsuntoPattern(asunto="Transferencia de bienes", pattern=r"TRANSFERENCIA\s+DE\s+BIENES?"),
        AsuntoPattern(asunto="Inventario de bienes", pattern=r"INVENTARIO\s+DE\s+BIENES?|INVENTARIADO"),
        AsuntoPattern(asunto="Donación", pattern=r"DONACI[OÓ]N|DONAR"),
        AsuntoPattern(asunto="Pedido de bienes", pattern=r"PEDIDO\s+DE\s+BIENES|SOLICITUD\s+DE\s+BIENES"),
        AsuntoPattern(asunto="Adquisición de bienes", pattern=r"ADQUISICI[OÓ]N"),
        AsuntoPattern(asunto="Plan de mantenimiento", pattern=r"PLAN.*MENAJE|MENAJE"),
        AsuntoPattern(asunto="Ampliación de espacio", pattern=r"AMPLIAR\s+(?:UNA\s+)?OFICINA|AMPLIACI[OÓ]N"),
        AsuntoPattern(asunto="Baja de elementos inventariados", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+INVENTARIADOS"),
        AsuntoPattern(asunto="Incorporación de libros", pattern=r"INCORPORACI[OÓ]N\s+DE\s+LIBROS"),
        AsuntoPattern(asunto="Incorporación de elementos", pattern=r"INCORPORACI[OÓ]N\s+DE\s+ELEMENTOS"),
        AsuntoPattern(asunto="Baja por deterioro", pattern=r"BAJA\s+POR\s+DETERIORO|DETERIORO"),
        AsuntoPattern(asunto="Baja por obsolescencia", pattern=r"BAJA\s+POR\s+OBSOLESCENCIA|OBSOLESCENCIA"),
        AsuntoPattern(asunto="Baja por antigüedad", pattern=r"BAJA\s+POR\s+ANTIG[ÜU]EDAD|ANTIG[ÜU]EDAD"),
        AsuntoPattern(asunto="Baja por siniestro", pattern=r"BAJA\s+POR\s+SINIESTRO|SINIESTRO"),
        AsuntoPattern(asunto="Baja por daño", pattern=r"BAJA\s+POR\s+DA[ÑN]O|DA[ÑN]O"),
        AsuntoPattern(asunto="Baja por pérdida", pattern=r"BAJA\s+POR\s+[PÉP]RDIDA|[PÉP]RDIDA"),
        AsuntoPattern(asunto="Baja por robo", pattern=r"BAJA\s+POR\s+ROBO|ROBO"),
        AsuntoPattern(asunto="Baja por deterioro de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+DETERIORO"),
        AsuntoPattern(asunto="Baja por obsolescencia de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+OBSOLESCENCIA"),
        AsuntoPattern(asunto="Baja por antigüedad de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+ANTIG[ÜU]EDAD"),
        AsuntoPattern(asunto="Baja por siniestro de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+SINIESTRO"),
        AsuntoPattern(asunto="Baja por daño de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+DA[ÑN]O"),
        AsuntoPattern(asunto="Baja por pérdida de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+[PÉP]RDIDA"),
        AsuntoPattern(asunto="Baja por robo de elementos", pattern=r"BAJA\s+DE\s+ELEMENTOS\s+POR\s+ROBO"),
    ],

    # ===========================================================
    # Gestión de Compras y Contrataciones
    # ===========================================================
    "Gestión de Compras y Contrataciones": [
        AsuntoPattern(asunto="Solicitud SBS", pattern=r"SOLICITUD\s+SBS|SBS\s+\d"),
        AsuntoPattern(asunto="Compra", pattern=r"COMPRA"),
        AsuntoPattern(asunto="Adquisición", pattern=r"ADQUISICI[OÓ]N"),
        AsuntoPattern(asunto="Mantenimiento", pattern=r"MANTENIMIENTO"),
        AsuntoPattern(asunto="Licitación pública", pattern=r"LICITACI[OÓ]N\s+[PÚP]UBLICA"),
        AsuntoPattern(asunto="Desarchivo", pattern=r"DESARCHIVO"),
        AsuntoPattern(asunto="CCE", pattern=r"CCE\s+\d|CCE\s*\d"),
        AsuntoPattern(asunto="CDSD", pattern=r"CDSD\s+\d|CDSD\s*\d"),
        AsuntoPattern(asunto="Contratación", pattern=r"CONTRATACI[OÓ]N"),
        AsuntoPattern(asunto="Residuos", pattern=r"RESIDUOS"),
        AsuntoPattern(asunto="Rectificativa", pattern=r"RECTIFICATIVA"),
    ],

    # ===========================================================
    # Gestión de Becas
    # ===========================================================
    "Gestión de Becas": [
        AsuntoPattern(asunto="Solicitud de beca", pattern=r"SOLICITUD\s+DE\s+BECA"),
        AsuntoPattern(asunto="Prórroga de beca", pattern=r"PR[OÓ]RROGA\s+DE\s+BECA|PR[OÓ]RROGA.*BCSI"),
        AsuntoPattern(asunto="Suspensión de beca", pattern=r"SUSPENSI[OÓ]N\s+DE\s+BECA"),
        AsuntoPattern(asunto="Renuncia a beca", pattern=r"RENUNCIA\s+(?:A\s+)?(?:LA\s+)?BECA"),
        AsuntoPattern(asunto="Beca de comisión de servicios", pattern=r"BECA\s+DE\s+COMISI[OÓ]N\s+DE\s+SERVICIOS"),
        AsuntoPattern(asunto="Beca de integración académica", pattern=r"BECA\s+DE\s+INTEGRACI[OÓ]N\s+ACAD[EÉ]MICA"),
        AsuntoPattern(asunto="Cientibeca", pattern=r"SCIENTIBECA|CIENTIBECA"),
        AsuntoPattern(asunto="Levantamiento de incompatibilidad", pattern=r"LEVANTAMIENTO\s+DE\s+INCOMPATIBILIDAD|LEVANTAMIENTO\s+INCOMPATIBILIDAD"),
        AsuntoPattern(asunto="Orden de prioridad institucional", pattern=r"ORDEN\s+DE\s+PRIORIDAD\s+INSTITUCIONAL"),
        AsuntoPattern(asunto="BCSI", pattern=r"BCSI"),
        AsuntoPattern(asunto="Beca por comisión de servicios", pattern=r"BECA\s+DE\s+COMISI[OÓ]N"),
        AsuntoPattern(asunto="Inscripción a tesina", pattern=r"INSCRIPCI[OÓ]N\s+(?:A\s+)?(?:LA\s+)?TESINA"),
        AsuntoPattern(asunto="Inscripción a materia", pattern=r"INSCRIPCI[OÓ]N\s+(?:A\s+)?(?:LA\s+)?MATERIA"),
        AsuntoPattern(asunto="Dictamen de comisión", pattern=r"DICTAMEN.*COMISI[OÓ]N"),
        AsuntoPattern(asunto="Evaluación de informe", pattern=r"EVALUACI[OÓ]N.*INFORME"),
        AsuntoPattern(asunto="Incorporación como codirector", pattern=r"INCORPORACI[OÓ]N.*CODIRECTOR"),
        AsuntoPattern(asunto="Solicitud de beca de inicio", pattern=r"BIA|BECA\s+DE\s+INICIACI[OÓ]N"),
        AsuntoPattern(asunto="Renuncia de beca EVC-CIN", pattern=r"RENUNCIA.*EVC-CIN|RENUNCIA.*BECAS?\s+EVC"),
        AsuntoPattern(asunto="Prórroga de beca por comisión", pattern=r"PR[OÓ]RROGA.*BECA\s+POR\s+COMISI[OÓ]N"),
        AsuntoPattern(asunto="Solicitud de inscripción a tesina", pattern=r"SOLICITUD.*INSCRIPCI[OÓ]N.*TESINA"),
        AsuntoPattern(asunto="Solicitud de beca por comisión", pattern=r"SOLICITUD.*BECA\s+POR\s+COMISI[OÓ]N"),
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
        AsuntoPattern(asunto="Actualización de haberes", pattern=r"ACTUALIZACI[OÓ]N\s+DE\s+HABERES|ACTUALIZACI[OÓ]N\s+DE\s+REMUNERACIONES|ACTUALI[ZC]EN\s+(?:LOS\s+)?HABERES|ACTUALIZACI[OÓ]N\s+HABERES"),
        AsuntoPattern(asunto="Certificación de haberes", pattern=r"CERTIFICACI[OÓ]N\s+DE\s+HABERES|CERTIFICACI[OÓ]N\s+DE\s+REMUNERACIONES"),
        AsuntoPattern(asunto="Desarchivo", pattern=r"DESARCHIVO"),
        AsuntoPattern(asunto="Invitación", pattern=r"INVITACI[OÓ]N"),
        AsuntoPattern(asunto="Aval", pattern=r"\bAVAL\b"),
        AsuntoPattern(asunto="Certificación ampliada", pattern=r"CERTIFICACI[OÓ]N\s+AMPLIADA"),
        AsuntoPattern(asunto="Certificación complementaria", pattern=r"CERTIFICACI[OÓ]N\s+COMPLEMENTARIA"),
        AsuntoPattern(asunto="Rectificación de remuneración", pattern=r"RECTIFICACI[OÓ]N.*REMUNERACI[OÓ]N|RECTIFICACI[OÓ]N.*HABERES"),
        AsuntoPattern(asunto="Inscripción al concurso", pattern=r"INSCRIPCI[OÓ]N\s+(?:AL\s+)?CONCURSO"),
        AsuntoPattern(asunto="Suspensión de concurso", pattern=r"SUSPENSI[OÓ]N\s+DE\s+CONCURSO"),
        AsuntoPattern(asunto="Lista de precios", pattern=r"LISTA\s+DE\s+PRECIOS"),
        AsuntoPattern(asunto="Rescisión de convenio", pattern=r"RESCISI[OÓ]N\s+DE\s+CONVENIO|RESCINDIR.*CONVENIO"),
        AsuntoPattern(asunto="Renuncia condicionada", pattern=r"RENUNCIA\s+CONDICIONADA"),
        AsuntoPattern(asunto="Uso de opción previsional", pattern=r"OPCI[OÓ]N.*ART.*19|OPCI[OÓ]N.*LEY\s+24241"),
        AsuntoPattern(asunto="Solicitud de representante", pattern=r"SOLICITUD\s+DE\s+REPRESENTANTE"),
        AsuntoPattern(asunto="Solicitud de certificación actualizada", pattern=r"SOLICITUD\s+DE\s+CERTIFICACI[OÓ]N\s+ACTUALIZADA|SOLICITUD.*CERTIFICACI[OÓ]N.*ACTUALIZADA"),
        AsuntoPattern(asunto="Certificación para ANSES", pattern=r"CERTIFICACI[OÓ]N.*ANSES"),
        AsuntoPattern(asunto="Actualización de haberes jubilatorios", pattern=r"ACTUALIZACI[OÓ]N.*HABERES.*JUBILATORIOS|ACTUALIZAR.*HABERES.*JUBILATORIOS"),
        AsuntoPattern(asunto="Solicitud de certificación", pattern=r"SOLICITUD\s+DE\s+CERTIFICACI[OÓ]N"),
        AsuntoPattern(asunto="Confirmación de persona", pattern=r"CONFIRME.*PERSONA|CONFIRMAR.*PERSONA"),
    ],

    # ===========================================================
    # Gestión Personal Docente
    # ===========================================================
    "Gestión Personal Docente": [
        AsuntoPattern(
            asunto="Licencia sin goce de sueldo",
            pattern=r"LICENCIA\s+SIN\s+GOCE\s+DE\s+SUELDO|LICENCIA\s+SIN\s+GOCE\s+DE\s+HABERES|LICENCIA\s+CON\s+GOCE\s+DE\s+SUELDO|LICENCIA\s+EN\s+MI\s+CARGO",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Licencia postmaternidad",
            pattern=r"LICENCIA\s+(?:POR\s+)?(?:POST)?MATERNIDAD|POST\s*MATERNIDAD|EXCEDENCIA.*LICENCIA.*POSMATERNIDAD|EXTENSI[OÓ]N.*LICENCIA.*POSMATERNIDAD|LICENCIA.*POSMATERNIDAD\s+POR\s+\d+\s+D[IÍ]AS",
            priority=95,
        ),
        AsuntoPattern(
            asunto="Acreditación de Créditos/Cursos/Publicaciones Posgrado",
            pattern=r"ACREDITACI[OÓ]N\s+DE\s+CR[ÉE]DITOS|ACREDITACI[OÓ]N\s+DE\s+CURSO|ACREDITACI[OÓ]N\s+DE\s+PUBLICACI[OÓ]N|ACREDITAR\s+CURSO|ACREDITAR\s+CR[ÉE]DITO|ACREDITACI[OÓ]N\s+DE\s+LA\s+MATERIA",
            priority=87,
        ),
        AsuntoPattern(
            asunto="Planificación",
            pattern=r"PLANIFICACI[OÓ]N|ELEVANDO\s+PLANIFICACI[OÓ]N|PRESENTACI[OÓ]N.*PLANIFICACI[OÓ]N",
            priority=86,
        ),
        AsuntoPattern(
            asunto="Rectificación de acta",
            pattern=r"RECTIFICACI[OÓ]N\s+DE\s+ACTA|CORRECCI[OÓ]N\s+DE\s+ACTA|RECTIFICACI[OÓ]N\s+DEL?\s+ACTA",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Resolución de CD",
            pattern=r"RESOLUCI[OÓ]N\s+(?:DEL?\s+)?CD|RESOLUCI[OÓ]N\s+DONDE\s+SE\s+ESTABLEZCA",
            priority=88,
        ),
        AsuntoPattern(
            asunto="Inscripción al concurso",
            pattern=r"INSCRIPCI[OÓ]N\s+(?:AL\s+)?CONCURSO|INSCRIPCI[OÓ]N.*CONCURSO|PARTICIPAR.*CONCURSO|CONVOCATORIA\s+PARA.*PASANT[IÍ]A",
            priority=85,
        ),
        AsuntoPattern(
            asunto="Renuncia",
            pattern=r"RENUNCIA|FINALIZAR.*RELACI[OÓ]N\s+DE\s+EMPLEO",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Autorización",
            pattern=r"AUTORIZACI[OÓ]N|INVITAR.*PARTICIPAR|INVITAR.*FORMAR\s+PARTE|CONFORMIDAD.*PARA\s+INICIAR|FIRMA.*NOTA.*AUTORIZA",
            priority=75,
        ),
        AsuntoPattern(
            asunto="Curso de posgrado",
            pattern=r"CURSO\s+DE\s+POSGRADO|DIPLOMATURA|RE-?EDICI[OÓ]N.*CURSO|CAPACITACI[OÓ]N",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Plan y programa de materias",
            pattern=r"PLAN\s+Y\s+PROGRAMA\s+DE\s+MATERIAS|SOLICITAR\s+EL\s+PLAN\s+Y\s+PROGRAMA",
            priority=25,
        ),
        AsuntoPattern(
            asunto="Estancia de investigación",
            pattern=r"ESTANCIA\s+DE\s+INVESTIGACI[OÓ]N|ESTANCIA\s+ACAD[EÉ]MICA",
            priority=60,
        ),
        AsuntoPattern(
            asunto="Certificación de servicios",
            pattern=r"CERTIFICACI[OÓ]N\s+DE\s+SERVICIOS",
            priority=55,
        ),
        AsuntoPattern(
            asunto="Solicitud de material",
            pattern=r"SOLICITUD\s+DE\s+MATERIAL|SOLICITUD.*MATERIAL|MATERIALES?\s+DE\s+LIBRER[IÍ]A|INSUMOS?\s+DE\s+OFICINA|ELEMENTOS?\s+E\s+INSUMOS?|COMPRA\s+DEL?\s+SIGUIENTE\s+MATERIAL|PROVISI[OÓ]N\s+DE\s+INSUMOS|PROVISI[OÓ]N.*LIBRER[IÍ]A",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Autorización de viaje",
            pattern=r"AUTORIZACI[OÓ]N\s+(?:PARA\s+)?VIAJE|VIAJE\s+DE\s+C[AÁ]TEDRA|LICENCIA.*VIAJE",
            priority=45,
        ),
        AsuntoPattern(
            asunto="Incorporación al patrimonio",
            pattern=r"INCORPORACI[OÓ]N\s+(?:AL\s+)?PATRIMONIO|INCORPORACI[OÓ]N\s+DOCENTE",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Designación de jurado",
            pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO|DESIGNACI[OÓ]N\s+DE\s+DOCENTE|DESIGNACI[OÓ]N\s+DE\s+LA\s+DRA",
            priority=35,
        ),
        AsuntoPattern(
            asunto="Trabajo Final de Posgrado",
            pattern=r"TRABAJO\s+FINAL\s+INTEGRADOR|TESIS\s+DOCTORAL|PROYECTO\s+DE\s+VINCULACI[OÓ]N",
            priority=30,
        ),
        AsuntoPattern(
            asunto="Constancia de deseo de continuar",
            pattern=r"CONSTANCIA\s+DE\s+DESEO\s+DE\s+CONTINUAR|DESEO\s+DE\s+CONTINUAR\s+COMO\s+DOCENTE",
            priority=25,
        ),
        AsuntoPattern(
            asunto="Alta y baja de personal",
            pattern=r"ALTA\s+Y\s+BAJA|ALTA.*Y.*BAJA|ALTA\s+DRA|BAJA\s+PROF",
            priority=24,
        ),
        AsuntoPattern(
            asunto="Aval",
            pattern=r"\bAVAL\b",
            priority=20,
        ),
        AsuntoPattern(
            asunto="Recurso de apelación",
            pattern=r"RECURSO\s+DE\s+APELACI[OÓ]N",
            priority=15,
        ),
        AsuntoPattern(
            asunto="Rescisión de contrato",
            pattern=r"RESCISI[OÓ]N\s+DE\s+CONTRATO|RESCINDO",
            priority=10,
        ),
        AsuntoPattern(
            asunto="Movilidad académica",
            pattern=r"MOVILIDAD\s+ACAD[EÉ]MICA|MOVILIDAD\s+DE\s+POSGRADO",
            priority=5,
        ),
        AsuntoPattern(
            asunto="Dictado de seminario",
            pattern=r"SEMINARIO",
            priority=4,
        ),
        AsuntoPattern(
            asunto="Permiso",
            pattern=r"PERMISO",
            priority=3,
        ),
        AsuntoPattern(
            asunto="Afectación de cargo",
            pattern=r"AFECTACI[OÓ]N\s+DE\s+CARGO|AFECTACI[OÓ]N.*CARGO.*PARA\s+CUMPLIR",
            priority=22,
        ),
        AsuntoPattern(
            asunto="Días pendientes de licencia",
            pattern=r"D[IÍ]AS?\s+PENDIENTES?\s+DE\s+LICENCIA|BENEFICIO.*D[IÍ]AS|LICENCIA\s+ANUAL\s+ORDINARIA",
            priority=20,
        ),
        AsuntoPattern(
            asunto="Prórroga de cargo",
            pattern=r"PR[OÓ]RROGA\s+DE\s+CARGO|PR[OÓ]RROGA.*CARGO",
            priority=1,
        ),
    ],

    # ===========================================================
    # Gestión Personal No Docente
    # ===========================================================
    "Gestión Personal No Docente": [
        AsuntoPattern(
            asunto="Licencia por enfermedad",
            pattern=r"LICENCIA\s+POR\s+ENFERMEDAD",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Inasistencia injustificada",
            pattern=r"INASISTENCI[AO]S?\s+INJUSTIFICADA[SO]?|NO\s+JUSTIFICAR|INASISTENCIA\s+INJUSTIFICADA",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Permiso de lactancia",
            pattern=r"PERMISO\s+DE\s+LACTANCIA|LACTANCIA",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Renuncia al cargo",
            pattern=r"RENUNCIA\s+(?:AL\s+)?CARGO",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Designación de jurado",
            pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO",
            priority=60,
        ),
        AsuntoPattern(
            asunto="Situación de revista",
            pattern=r"SITUACI[OÓ]N\s+DE\s+REVISTA",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Horas extras",
            pattern=r"HORAS?\s+EXTRAS?",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Certificación de servicios y haberes",
            pattern=r"CERTIFICACI[OÓ]N\s+DE\s+SERVICIOS\s+Y\s+HABERES",
            priority=30,
        ),
        AsuntoPattern(
            asunto="Licencia postmaternidad",
            pattern=r"POST[\s-]MATERNIDAD",
            priority=25,
        ),
        AsuntoPattern(
            asunto="Baja de asociación",
            pattern=r"BAJA\s+DE\s+ASOCIACI[OÓ]N",
            priority=20,
        ),
        AsuntoPattern(
            asunto="Ingreso no docente",
            pattern=r"INGRESO\s+NO\s+DOCENTE",
            priority=15,
        ),
        AsuntoPattern(
            asunto="Solicitud de licencia",
            pattern=r"SOLICITUD\s+DE\s+LICENCIA|SOLICITA\s+LICENCIA",
            priority=10,
        ),
        AsuntoPattern(
            asunto="Información de horarios",
            pattern=r"HORARIOS?\s+DE\s+CURSADO|HORARIOS?\s+DE\s+MATERIA|INFORMANDO\s+LOS\s+HORARIOS",
            priority=5,
        ),
        AsuntoPattern(
            asunto="Prórroga de beca por comisión de servicios",
            pattern=r"PR[OÓ]RROGA.*BCSI|BCSI",
            priority=4,
        ),
        AsuntoPattern(
            asunto="Beca por comisión de servicios",
            pattern=r"BECA\s+DE\s+COMISI[OÓ]N\s+DE\s+SERVICIOS",
            priority=3,
        ),
        AsuntoPattern(
            asunto="Solicitud de permiso",
            pattern=r"SOLICITUD\s+DE\s+PERMISO|SOLICITA\s+PERMISO",
            priority=2,
        ),
        AsuntoPattern(
            asunto="Concurso no docente",
            pattern=r"CONCURSO\s+NO\s+DOCENTE|CONCURSO.*CATEGOR[ÍI]A\s+4",
            priority=1,
        ),
    ],

    # ===========================================================
    # Actas de exámenes y de regularización
    # ===========================================================
    "Actas de exámenes y de regularización": [
        AsuntoPattern(asunto="Acta de examen", pattern=r"ACTA\s+DE\s+EX[AÁ]MEN"),
        AsuntoPattern(asunto="Acta de promoción", pattern=r"ACTA\s+DE\s+PROMOCI[OÓ]N"),
        AsuntoPattern(asunto="Nómina de alumnos", pattern=r"N[OÓ]MINA\s+DE\s+ALUMNOS?"),
        AsuntoPattern(asunto="Rectificación de acta", pattern=r"RECTIFICACI[OÓ]N\s+DE\s+ACTA|RECTIFICATIVA"),
        AsuntoPattern(asunto="Acta de alumnos externos", pattern=r"ACTA\s+DE\s+ALUMNOS?\s+EXTERNOS?"),
        AsuntoPattern(asunto="Acta de electivas", pattern=r"ACTA\s+DE\s+ELECTIVAS"),
        AsuntoPattern(asunto="Designación de jurado", pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO"),
        AsuntoPattern(asunto="Envío de acta", pattern=r"ENVI[OÓ]\s+DE\s+ACTA|REMITA?\s+ACTA|REMITE\s+ACTA|ENVIAR\s+ACTA"),
        AsuntoPattern(asunto="Acta de examen", pattern=r"ACTAS?\s+DE\s+EX[AÁ]MEN"),
        AsuntoPattern(asunto="Rectificación de acta", pattern=r"RECTIFICAR\s+ACTA|RECTIFICA.*ACTA"),
        AsuntoPattern(asunto="Remite acta a facultad", pattern=r"REMITE\s+ACTA|REMITE\s+A\s+FACULTAD|REMITIDAS?\s+A\s+FA"),
    ],

    # ===========================================================
    # Gestión de Convenios y Acuerdos
    # ===========================================================
    "Gestión de Convenios y Acuerdos": [
        AsuntoPattern(
            asunto="Certificado de cumplimiento fiscal",
            pattern=r"CERTIFICADO\s+DE\s+CUMPLIMIENTO\s+FISCAL",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Certificado de deudores morosos",
            pattern=r"CERTIFICADO\s+DE\s+DEUDORES?\s+MOROSOS",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Rectificativa",
            pattern=r"RECTIFICATIVA",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Actualización de valores",
            pattern=r"ACTUALIZACI[OÓ]N\s+DE\s+VALORES|ACTUALIZACI[OÓ]N.*VALORES|CUOTA\s+SOCIAL",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Transferencia de fondos",
            pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?",
            priority=60,
        ),
        AsuntoPattern(
            asunto="Convenio marco",
            pattern=r"CONVENIO\s+MARCO",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Prórroga de convenio",
            pattern=r"PR[OÓ]RROGA\s+DE\s+CONVENIO|PR[OÓ]RROGA.*CONVENIO",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Resolución de convenio",
            pattern=r"RESOLUCI[OÓ]N.*CONVENIO",
            priority=30,
        ),
        AsuntoPattern(
            asunto="Convenio",
            pattern=r"CONVENIO",
            priority=20,
        ),
    ],

    # ===========================================================
    # Gestión de Ingresos de Fondos
    # ===========================================================
    "Gestión de Ingresos de Fondos": [
        AsuntoPattern(
            asunto="Elevación de OT",
            pattern=r"ELEVACI[OÓ]N\s+DE\s+OT|ELEVACI[OÓ]N\s+OT|ELEVAR\s+(?:LA\s+)?OT|NOTA\s+OT|EL[ÉE]VEN(?:SE|LAS?\s+OT)|EL[ÉE]VES(?:E|LA?\s+OT)|ELEV[AÁ]\s+OT|OTs?\s+N[º°]|ELEVAR\s+LAS?\s+OT",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Liquidación divisas",
            pattern=r"LIQUIDACI[OÓ]N\s+DIVISAS|LIQUIDACI[OÓ]N.*DIVISAS|LIQUIDACI[OÓ]N\s+\d+",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Rendición de fondos",
            pattern=r"RENDICI[OÓ]N\s+DE\s+FONDOS?|RENDICI[OÓ]N\s+DE\s+FONDOS\s+POR\s+\$",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Claus Andermatt",
            pattern=r"CLAUS\s+ANDERMATT",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Desarchivo",
            pattern=r"DESARCHIVO",
            priority=60,
        ),
        AsuntoPattern(
            asunto="Aprobación de movimientos bancarios",
            pattern=r"APROBACI[OÓ]N\s+DE\s+MOVIMIENTOS?\s+BANCARIOS?",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Solicitud de documentación",
            pattern=r"SOLICITUD\s+DE\s+DOCUMENTACI[OÓ]N",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Solicitud de copias",
            pattern=r"SOLICITUD\s+DE\s+COPIAS|SOLICITUD.*COPIAS",
            priority=30,
        ),
    ],

    # ===========================================================
    # Gestión de Órganos de Gobierno y Autoridades
    # ===========================================================
    "Gestión de Órganos de Gobierno y Autoridades": [
        AsuntoPattern(asunto="Designación de autoridades", pattern=r"DESIGNACI[OÓ]N\s+DE\s+AUTORIDADES?|PROCLAMACI[OÓ]N"),
        AsuntoPattern(asunto="Prórroga de beca", pattern=r"PR[OÓ]RROGA\s+DE\s+BECA"),
        AsuntoPattern(asunto="Resolución de CD", pattern=r"RESOLUCI[OÓ]N\s+(?:DEL\s+)?CD|RES\.?\s+CD"),
        AsuntoPattern(asunto="Contrato de locación", pattern=r"CONTRATO\s+DE\s+LOCACI[OÓ]N"),
        AsuntoPattern(asunto="Protocolo", pattern=r"PROTOCOLO"),
        AsuntoPattern(asunto="No renovación de contrato", pattern=r"NO\s+RENOVACI[OÓ]N\s+(?:DEL?\s+)?CONTRATO|NO\s+RENOVAR"),
        AsuntoPattern(asunto="Taller", pattern=r"TALLER"),
        AsuntoPattern(asunto="Prórroga de beca por comisión de servicios", pattern=r"PR[OÓ]RROGA.*BCSI|BCSI|PR[OÓ]RROGA.*BECA\s+POR\s+COMISI[OÓ]N"),
        AsuntoPattern(asunto="Diplomatura", pattern=r"DIPLOMATURA"),
        AsuntoPattern(asunto="Estructura de gestión", pattern=r"ESTRUCTURA\s+DE\s+GESTI[OÓ]N"),
        AsuntoPattern(asunto="Renovación de comité", pattern=r"RENOVACI[OÓ]N\s+DE\s+COMIT[EÉ]"),
        AsuntoPattern(asunto="Aval institucional", pattern=r"AVAL\s+INSTITUCIONAL|\bAVAL\b"),
        AsuntoPattern(asunto="Toma de posesión", pattern=r"TOMA\s+DE\s+POSESI[OÓ]N"),
        AsuntoPattern(asunto="Convocatoria", pattern=r"CONVOCATORIA"),
        AsuntoPattern(asunto="Prórroga CL", pattern=r"PR[OÓ]RROGA\s+CL|PR[OÓ]RROGA\s+CONTRATO"),
        AsuntoPattern(asunto="Inicio de expediente", pattern=r"INICIO\s+DE\s+(?:UN\s+)?EXPEDIENTE"),
        AsuntoPattern(asunto="Memoria", pattern=r"MEMORIA"),
        AsuntoPattern(asunto="Creación de cargos", pattern=r"CREACI[OÓ]N\s+DE\s+CARGOS"),
        AsuntoPattern(asunto="Designación de representante", pattern=r"DESIGNACI[OÓ]N\s+DE\s+REPRESENTANTE"),
        AsuntoPattern(asunto="Designación de coordinador", pattern=r"DESIGNACI[OÓ]N\s+DE\s+COORDINADOR"),
        AsuntoPattern(asunto="Cursado de asignatura", pattern=r"CURSADO\s+DE\s+ASIGNATURA|CURSADO\s+DE\s+MATERIA"),
        AsuntoPattern(asunto="Propuesta de renovación", pattern=r"PROPUESTA\s+DE\s+RENOVACI[OÓ]N"),
        AsuntoPattern(asunto="Solicitud de aula", pattern=r"SOLICITUD\s+DE\s+AULA|SOLICITA\s+AULA"),
        AsuntoPattern(asunto="Solicitud de jurado", pattern=r"SOLICITA.*JURADO|JURADO"),
        AsuntoPattern(asunto="Propuesta de designación", pattern=r"PROPUESTA\s+DE\s+DESIGNACI[OÓ]N|PROPUESTA.*DESIGNAR"),
        AsuntoPattern(asunto="Eleva propuesta", pattern=r"ELEVA\s+PROPUESTA|ELEVACI[OÓ]N\s+DE\s+PROPUESTA"),
        AsuntoPattern(asunto="Informa integración", pattern=r"INFORMA.*INTEGRACI[OÓ]N|INFORMA.*COMISI[OÓ]N"),
        AsuntoPattern(asunto="Jefe de emergencia", pattern=r"JEFE\s+DE\s+EMERGENCIA"),
        AsuntoPattern(asunto="Profesor Consulto", pattern=r"PROFESOR\s+CONSULTO"),
        AsuntoPattern(asunto="Cubrimiento de vacante", pattern=r"CUBRIMIENTO\s+DE\s+VACANTE|CUBRIR\s+VACANTE"),
        AsuntoPattern(asunto="Prórroga de Beca de Integración Académica", pattern=r"PR[OÓ]RROGA.*BECA\s+DE\s+INTEGRACI[OÓ]N"),
        AsuntoPattern(asunto="Designación de profesor", pattern=r"DESIGNACI[OÓ]N.*PROFESOR|DESIGNAR.*PROFESOR"),
        AsuntoPattern(asunto="Informa horarios", pattern=r"INFORMA.*HORARIO"),
        AsuntoPattern(asunto="Propuesta de pautas", pattern=r"PROPUESTA\s+DE\s+PAUTAS"),
        AsuntoPattern(asunto="Cubrimiento de cargo", pattern=r"CUBRIMIENTO\s+DE\s+CARGO|CUBRIR.*CARGO"),
        AsuntoPattern(asunto="Sistema de formación extracurricular", pattern=r"SISTEMA\s+DE\s+FORMACI[OÓ]N\s+EXTRACURRICULAR"),
        AsuntoPattern(asunto="Propuesta de pautas", pattern=r"PROPUESTA\s+DE\s+PAUTAS"),
        AsuntoPattern(asunto="Cubrimiento de cargo", pattern=r"CUBRIMIENTO\s+DE\s+CARGO|CUBRIR.*CARGO"),
        AsuntoPattern(asunto="Informa horarios", pattern=r"INFORMA.*HORARIO"),
        AsuntoPattern(asunto="Designación de profesor", pattern=r"DESIGNACI[OÓ]N.*PROFESOR|DESIGNAR.*PROFESOR"),
        AsuntoPattern(asunto="Prórroga de Beca de Integración Académica", pattern=r"PR[OÓ]RROGA.*BECA\s+DE\s+INTEGRACI[OÓ]N"),
        AsuntoPattern(asunto="Solicitud de jurado", pattern=r"SOLICITA.*JURADO|JURADO"),
        AsuntoPattern(asunto="Propuesta de renovación", pattern=r"PROPUESTA\s+DE\s+RENOVACI[OÓ]N"),
        AsuntoPattern(asunto="Solicitud de aula", pattern=r"SOLICITUD\s+DE\s+AULA|SOLICITA\s+AULA"),
        AsuntoPattern(asunto="Promedio histórico", pattern=r"PROMEDIO\s+HIST[OÓ]RICO"),
        AsuntoPattern(asunto="Informa integración de comisiones", pattern=r"INFORMA.*INTEGRACI[OÓ]N.*COMISI[OÓ]N"),
        AsuntoPattern(asunto="Propuesta de designación de profesor", pattern=r"PROPUESTA.*DESIGNACI[OÓ]N.*PROFESOR"),
        AsuntoPattern(asunto="Designación de jefe de emergencia", pattern=r"JEFE\s+DE\s+EMERGENCIA"),
        AsuntoPattern(asunto="Propuesta de pautas para designación", pattern=r"PROPUESTA.*PAUTAS.*DESIGNACI[OÓ]N"),
        AsuntoPattern(asunto="Vacante en formación extracurricular", pattern=r"VACANTE.*FORMACI[OÓ]N\s+EXTRACURRICULAR"),
        AsuntoPattern(asunto="Solicitud de autorización para cubrimiento", pattern=r"SOLICITUD.*AUTORIZACI[OÓ]N.*CUBRIMIENTO"),
    ],

    # ===========================================================
    # SAT - SET
    # ===========================================================
    "SAT - SET": [
        AsuntoPattern(
            asunto="Solicitud de formulario 931",
            pattern=r"FORMULARIO\s+F?\s*931|F931",
            priority=100,
        ),
        AsuntoPattern(
            asunto="Desarchivo",
            pattern=r"DESARCHIVO",
            priority=90,
        ),
        AsuntoPattern(
            asunto="Transferencia del 20%",
            pattern=r"TRANSFERENCIA\s+DEL\s+20\s*%",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Transferencia de fondos",
            pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?|TRANSFERENCIA",
            priority=70,
        ),
        AsuntoPattern(
            asunto="Solicitud de documentación",
            pattern=r"DOCUMENTACI[OÓ]N",
            priority=60,
        ),
        AsuntoPattern(
            asunto="Rendición de fondos",
            pattern=r"RENDICI[OÓ]N\s+DE\s+FONDOS?",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Adenda a convenio",
            pattern=r"ADENDA\s+AL\s+CONVENIO",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Dictamen de jurado",
            pattern=r"DICTAMEN.*JURADO",
            priority=30,
        ),
        AsuntoPattern(
            asunto="Designación de jurado",
            pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO",
            priority=20,
        ),
    ],

    # ===========================================================
    # Proyecto y Propuestas curriculares, extensión e investigación
    # ===========================================================
    "Proyecto y Propuestas curriculares, extensión e investigación": [
        # AFE (Actividades de Formación Específica) - todos los tipos
        AsuntoPattern(
            asunto="AFE",
            pattern=r"\bAFE(?:\s+INV(?:ESTIGACI[OÓ]N)?|\s+DESIGNACI[OÓ]N)?\b",
            priority=100,
        ),
        # CAI+D
        AsuntoPattern(
            asunto="Proyecto CAI+D",
            pattern=r"CAI\+D",
            priority=90,
        ),
        # Cursos
        AsuntoPattern(
            asunto="Curso de extensión",
            pattern=r"CURSO\s+(?:DE\s+)?(?:ACTUALIZACI[OÓ]N|PERFECCIONAMIENTO|EXTENSI[OÓ]N)",
            priority=80,
        ),
        AsuntoPattern(
            asunto="Curso",
            pattern=r"\bCURSO\b",
            priority=70,
        ),
        # Planificación
        AsuntoPattern(
            asunto="Solicitud de planificación",
            pattern=r"PLANIFICACI[OÓ]N",
            priority=60,
        ),
        # Propuestas de extensión
        AsuntoPattern(
            asunto="Propuesta de extensión",
            pattern=r"PROPUESTA\s+(?:DE\s+)?EXTENSI[OÓ]N",
            priority=50,
        ),
        AsuntoPattern(
            asunto="Propuesta curricular",
            pattern=r"PROPUESTA\s+CURRICULAR",
            priority=45,
        ),
        # Talleres
        AsuntoPattern(
            asunto="Taller de extensión",
            pattern=r"TALLER(?:ES)?\s+(?:COLABORATIVO|DE\s+EXTENSI[OÓ]N)",
            priority=40,
        ),
        AsuntoPattern(
            asunto="Taller",
            pattern=r"\bTALLER(?:ES)?\b",
            priority=35,
        ),
        # Aval
        AsuntoPattern(
            asunto="Solicitud de aval",
            pattern=r"SOLICITUD\s+DE\s+AVAL",
            priority=30,
        ),
        AsuntoPattern(
            asunto="Aval",
            pattern=r"\bAVAL\b",
            priority=25,
        ),
        # Designación de alumnos
        AsuntoPattern(
            asunto="Designación de alumno",
            pattern=r"DESIGNACI[OÓ]N\s+DE\s+(?:ALUMNO|ESTUDIANTE|SRTA?\.?)",
            priority=20,
        ),
        # Práctica profesional
        AsuntoPattern(
            asunto="Práctica profesional",
            pattern=r"PR[AÁ]CTICA\s+(?:PRE-?PROFESIONAL|PROFESIONAL)",
            priority=15,
        ),
        # Práctica de extensión
        AsuntoPattern(
            asunto="Práctica de extensión",
            pattern=r"PR[AÁ]CTICA\s+DE\s+EXTENSI[OÓ]N|PR[AÁ]CTICAS?\s+DE\s+EXTENSI[OÓ]N",
            priority=10,
        ),
        AsuntoPattern(
            asunto="Educación experiencial",
            pattern=r"EDUCACI[OÓ]N\s+EXPERIENCIAL",
            priority=5,
        ),
        # Designación en SAyPG
        AsuntoPattern(
            asunto="Designación en SAyPG",
            pattern=r"SAyPG|SAYPG",
            priority=4,
        ),
        # Solicitud de reserva de aula
        AsuntoPattern(
            asunto="Reserva de aula",
            pattern=r"RESERVA\s+DE\s+EL\s+AULA|MAGNA|RESERVA\s+DE\s+AULA",
            priority=3,
        ),
        # Solicitud de cobertura
        AsuntoPattern(
            asunto="Solicitud de cobertura de investigación",
            pattern=r"COBERTURA.*INVESTIGACI[OÓ]N",
            priority=2,
        ),
        # Vinculación con la sociedad
        AsuntoPattern(
            asunto="Vinculación con la sociedad",
            pattern=r"VINCULACI[OÓ]N",
            priority=1,
        ),
        # Propuesta de extensión
        AsuntoPattern(
            asunto="Propuesta de práctica",
            pattern=r"PROPUESTA\s+DE\s+PR[AÁ]CTICA",
            priority=0,
        ),
    ],

    # ===========================================================
    # Conceptos sin patrones (agregados para completar cobertura)
    # ===========================================================

    # Migración
    "Migración": [
        AsuntoPattern(asunto="Inscripción", pattern=r"INSCRIPCI[OÓ]N"),
        AsuntoPattern(asunto="Maestría", pattern=r"MAESTR[IÍ]A"),
        AsuntoPattern(asunto="Transferencia", pattern=r"TRANSFERENCIA"),
        AsuntoPattern(asunto="Evaluación", pattern=r"EVALUACI[OÓ]N"),
        AsuntoPattern(asunto="Designación de jurado", pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO"),
        AsuntoPattern(asunto="Plan de tesina", pattern=r"PLAN\s+DE\s+TESINA|PLAN DE TESINA"),
        AsuntoPattern(asunto="Nómina de alumnos", pattern=r"N[OÓ]MINA\s+DE\s+ALUMNOS?"),
        AsuntoPattern(asunto="Acreditación de UCA", pattern=r"ACREDITACI[OÓ]N.*UCA|ACREDITE.*UCAS"),
        AsuntoPattern(asunto="Subsidio", pattern=r"SUBSIDIO|PROMAC"),
        AsuntoPattern(asunto="Pasantía", pattern=r"PASANTIA"),
        AsuntoPattern(asunto="Certificado de finalización", pattern=r"CERTIFICADO\s+DE\s+FINALIZACI[OÓ]N"),
        AsuntoPattern(asunto="Seguro estudiantil", pattern=r"SEGURO.*ESTUDIANTE"),
        AsuntoPattern(asunto="Designación", pattern=r"DESIGNACI[OÓ]N"),
        AsuntoPattern(asunto="Autorización", pattern=r"AUTORIZACI[OÓ]N"),
        AsuntoPattern(asunto="Cubrimiento de cargo", pattern=r"CUBRIMIENTO\s+DE\s+CARGO|CUBRIR\s+UN\s+CARGO"),
        AsuntoPattern(asunto="Cursado", pattern=r"CURSADO"),
        AsuntoPattern(asunto="Concurso", pattern=r"CONCURSO"),
        AsuntoPattern(asunto="Jurado", pattern=r"JURADO"),
        AsuntoPattern(asunto="Situación de revista", pattern=r"SITUACI[OÓ]N\s+DE\s+REVISTA"),
        AsuntoPattern(asunto="Facturación y depósitos", pattern=r"FACTURACI[OÓ]N|DEP[OÓ]SITOS"),
    ],

    # Adhesiones, Homenajes, Declaraciones y Acontecimientos
    "Adhesiones, Homenajes, Declaraciones y Acontecimientos": [
        AsuntoPattern(asunto="Aval institucional", pattern=r"AVAL\s+INSTITUCIONAL|\bAVAL\b"),
        AsuntoPattern(asunto="Adhesión", pattern=r"ADHESI[OÓ]N"),
        AsuntoPattern(asunto="Homenaje", pattern=r"HOMENAJE"),
        AsuntoPattern(asunto="Solicitud de auspicio", pattern=r"AUSPICIO"),
        AsuntoPattern(asunto="Invitación", pattern=r"INVITACI[OÓ]N"),
    ],

    # Reservas para uso de espacios Institucionales
    "Reservas para uso de espacios Institucionales": [
        AsuntoPattern(asunto="Solicitud de aula", pattern=r"AULA"),
        AsuntoPattern(asunto="Solicitud de Aula Magna", pattern=r"AULA\s+MAGNA"),
        AsuntoPattern(asunto="Uso de espacio", pattern=r"USO\s+DE\s+ESPACIO"),
        AsuntoPattern(asunto="Reserva", pattern=r"RESERVA"),
        AsuntoPattern(asunto="Solicitud de espacio", pattern=r"SOLICITUD\s+DE\s+ESPACIO"),
        AsuntoPattern(asunto="Solicitud de salón", pattern=r"SAL[OÓ]N"),
        AsuntoPattern(asunto="Uso de salón", pattern=r"USO\s+DE\s+SAL[OÓ]N"),
    ],

    # Normativa Institucional y externa
    "Normativa Institucional y externa": [
        AsuntoPattern(asunto="Resolución", pattern=r"RESOLUCI[OÓ]N"),
        AsuntoPattern(asunto="Reglamento", pattern=r"REGLAMENTO"),
        AsuntoPattern(asunto="Plan de estudios", pattern=r"PLAN\s+DE\s+ESTUDIOS"),
        AsuntoPattern(asunto="Memoria anual", pattern=r"MEMORIA\s+ANUAL|MEMORIA"),
        AsuntoPattern(asunto="Protocolo", pattern=r"PROTOCOLO"),
        AsuntoPattern(asunto="Convocatoria a sesión", pattern=r"CONVOCANDO\s+AL\s+CONSEJO|CONVOCATORIA.*SESI[OÓ]N|REUNI[OÓ]N\s+ORDINARIA"),
        AsuntoPattern(asunto="Propuesta curricular", pattern=r"PROPUESTA\s+CURRICULAR|MODIFICACIONES"),
        AsuntoPattern(asunto="Simulacro de emergencia", pattern=r"SIMULACRO"),
        AsuntoPattern(asunto="Programa de movilidad", pattern=r"PROGRAMA\s+DE\s+MOVILIDAD"),
        AsuntoPattern(asunto="Colección publicación", pattern=r"COLECCI[OÓ]N|PUBLICACI[OÓ]N"),
        AsuntoPattern(asunto="Promedio histórico", pattern=r"PROMEDIO\s+HIST[OÓ]RICO"),
        AsuntoPattern(asunto="Renuncia aceptada", pattern=r"ACEPTANDO.*RENUNCIA|RENUNCIA.*ACEPTA"),
        AsuntoPattern(asunto="Renuncia de autoridad", pattern=r"RENUNCIA\s+DEL|RENUNCIA\s+DE\s+LA"),
        AsuntoPattern(asunto="Dictamen de jurado", pattern=r"DICTAMEN.*JURADO"),
        AsuntoPattern(asunto="Calendario académico", pattern=r"CALENDARIO\s+ACAD[EÉ]MICO"),
        AsuntoPattern(asunto="Res C.D.", pattern=r"RES\.?\s+C\.D\.|RES\.?\s+CD"),
    ],

    # Elecciones
    "Elecciones": [
        AsuntoPattern(asunto="Designación de autoridades", pattern=r"DESIGNACI[OÓ]N\s+DE\s+AUTORIDADES"),
        AsuntoPattern(asunto="Junta electoral", pattern=r"JUNTA\s+ELECTORAL"),
        AsuntoPattern(asunto="Cronograma electoral", pattern=r"CRONOGRAMA\s+ELECTORAL"),
        AsuntoPattern(asunto="Resultado electoral", pattern=r"RESULTADO\s+ELECTORAL"),
        AsuntoPattern(asunto="Elección de autoridades", pattern=r"ELECCI[OÓ]N\s+DE\s+AUTORIDADES|ELECCI[OÓ]N"),
        AsuntoPattern(asunto="Designación de jurado", pattern=r"DESIGNACI[OÓ]N\s+DE\s+JURADO"),
        AsuntoPattern(asunto="Propuesta curricular", pattern=r"PROPUESTA\s+CURRICULAR"),
        AsuntoPattern(asunto="Convocatoria a sesión", pattern=r"CONVOCANDO\s+AL\s+CONSEJO|CONVOCATORIA.*SESI[OÓ]N|REUNI[OÓ]N\s+ORDINARIA"),
    ],

    # Gestión de fondos SPU
    "Gestión de fondos SPU": [
        AsuntoPattern(asunto="Liquidación y pago a proveedores", pattern=r"LIQUIDACI[OÓ]N\s+Y\s+PAGO\s+A\s+PROVEEDORES?"),
        AsuntoPattern(asunto="Transferencia de fondos", pattern=r"TRANSFERENCIA\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Rendición de fondos", pattern=r"RENDICI[OÓ]N\s+DE\s+FONDOS?"),
        AsuntoPattern(asunto="Solicitud de fondos", pattern=r"SOLICITUD\s+DE\s+FONDOS"),
    ],

    # Gestión de reintegros
    "Gestión de reintegros": [
        AsuntoPattern(asunto="Rendición de gastos", pattern=r"RENDICI[OÓ]N\s+DE\s+GASTOS"),
        AsuntoPattern(asunto="Reintegro", pattern=r"REINTEGRO"),
        AsuntoPattern(asunto="Devolución", pattern=r"DEVOLUCI[OÓ]N"),
        AsuntoPattern(asunto="Solicitud de reintegro", pattern=r"SOLICITUD\s+DE\s+REINTEGRO"),
        AsuntoPattern(asunto="Rendición de fondos", pattern=r"RENDICI[OÓ]N\s+DE\s+FONDOS?"),
    ],

    # Notificaciones Judiciales
    "Notificaciones Judiciales": [
        AsuntoPattern(asunto="Oficio judicial", pattern=r"OFICIO\s+JUDICIAL|OFICIO\s+JUD"),
        AsuntoPattern(asunto="Notificación judicial", pattern=r"NOTIFICACI[OÓ]N\s+JUDICIAL"),
        AsuntoPattern(asunto="Oficio del Ministerio", pattern=r"MINISTERIO"),
        AsuntoPattern(asunto="Oficio", pattern=r"OFICIO"),
        AsuntoPattern(asunto="Judicial", pattern=r"JUDICIAL"),
    ],

    # Accidentes y siniestros
    "Accidentes y siniestros": [
        AsuntoPattern(asunto="Accidente", pattern=r"ACCIDENTE"),
        AsuntoPattern(asunto="Incidente", pattern=r"INCIDENTE"),
        AsuntoPattern(asunto="Daño", pattern=r"DA[ÑN]O"),
        AsuntoPattern(asunto="Licencia por enfermedad", pattern=r"LICENCIA\s+POR\s+ENFERMEDAD"),
        AsuntoPattern(asunto="Simulacro de evacuación", pattern=r"SIMULACRO\s+DE\s+EVACUACI[OÓ]N|SIMULACRO"),
        AsuntoPattern(asunto="Siniestro", pattern=r"SINIESTRO"),
        AsuntoPattern(asunto="Vandalismo", pattern=r"VANDALISMO|ACTO\s+VAND[AÁ]LICO"),
    ],

    # Gestión Obra Pública
    "Gestión Obra Pública": [
        AsuntoPattern(asunto="Reparación", pattern=r"REPARACI[OÓ]N"),
        AsuntoPattern(asunto="Ampliación", pattern=r"AMPLIACI[OÓ]N"),
        AsuntoPattern(asunto="Mantenimiento edilicio", pattern=r"MANTENIMIENTO\s+EDILICIO"),
        AsuntoPattern(asunto="Puesta en valor", pattern=r"PUESTA\s+EN\s+VALOR"),
        AsuntoPattern(asunto="Reacondicionamiento", pattern=r"REACONDICIONAMIENTO"),
        AsuntoPattern(asunto="Arreglo", pattern=r"ARREGLO"),
    ],

    # Presupuesto
    "Presupuesto": [
        AsuntoPattern(asunto="Libro banco", pattern=r"LIBRO\s+BANCO"),
        AsuntoPattern(asunto="Conciliación bancaria", pattern=r"CONCILIACI[OÓ]N\s+BANCARIA"),
        AsuntoPattern(asunto="Presupuesto", pattern=r"PRESUPUESTO"),
        AsuntoPattern(asunto="Solicitud de presupuesto", pattern=r"SOLICITUD\s+DE\s+PRESUPUESTO"),
        AsuntoPattern(asunto="Aprobación de presupuesto", pattern=r"APROBACI[OÓ]N\s+DE\s+PRESUPUESTO"),
    ],

    # Denuncia y Sumario
    "Denuncia y Sumario": [
        AsuntoPattern(asunto="Falta de ética", pattern=r"FALTA\s+DE\s+[EÉ]TICA"),
        AsuntoPattern(asunto="Denuncia", pattern=r"DENUNCIA"),
        AsuntoPattern(asunto="Informe de infraestructura", pattern=r"INFRAESTRUCTURA"),
        AsuntoPattern(asunto="Sumario", pattern=r"SUMARIO"),
        AsuntoPattern(asunto="Expediente disciplinario", pattern=r"EXPEDIENTE\s+DISCIPLINARIO"),
    ],

    # Pasantías y Adscripciones
    "Pasantias y Adscripciones": [
        AsuntoPattern(asunto="Oferta de vacante", pattern=r"OFERTA\s+(?:DE\s+)?VACANTE"),
        AsuntoPattern(asunto="Formación extracurricular", pattern=r"FORMACI[OÓ]N\s+EXTRACURRICULAR"),
        AsuntoPattern(asunto="Propuesta de formación", pattern=r"PROPUESTA\s+DE\s+FORMACI[OÓ]N"),
        AsuntoPattern(asunto="Oferta de pasantía", pattern=r"OFERTA\s+DE\s+PASANTIA"),
        AsuntoPattern(asunto="Solicitud de pasantía", pattern=r"SOLICITUD\s+DE\s+PASANTIA"),
        AsuntoPattern(asunto="Propuesta de pasantía", pattern=r"PROPUESTA\s+DE\s+PASANTIA"),
    ],
}


def extract_asunto(descripcion: str, concepto: str) -> Optional[str]:
    """
    Extract asunto from a description using regex patterns.

    Args:
        descripcion: The expediente description.
        concepto: The expediente concepto.

    Returns:
        The matched asunto, or "Trámite" if no pattern matches.
    """
    if not descripcion:
        return "Otro"

    patterns = ASUNTO_PATTERNS.get(concepto, [])
    desc_upper = descripcion.upper()

    # Sort by priority (higher first)
    sorted_patterns = sorted(patterns, key=lambda p: p.priority, reverse=True)

    for ap in sorted_patterns:
        if re.search(ap.pattern, desc_upper, re.DOTALL):
            return ap.asunto

    # Return catch-all for unmatched descriptions
    return "Otro"


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

        # Add catch-all "Otro" asunto for this concepto
        try:
            conn.execute(
                "INSERT OR IGNORE INTO asuntos (concepto, asunto, patron_regex) VALUES (?, ?, ?)",
                (concepto, "Otro", ".+"),
            )
            count += 1
        except Exception:
            pass

        counts[concepto] = count

    conn.commit()

    # Link expedientes to asuntos
    _link_expedientes_to_asuntos(conn)

    # Clean up orphaned asuntos (asuntos with no linked expedientes)
    cursor = conn.execute(
        """DELETE FROM asuntos WHERE id NOT IN (
            SELECT DISTINCT asunto_id FROM expediente_asuntos
        )"""
    )
    orphaned_deleted = cursor.rowcount
    if orphaned_deleted > 0:
        print(f"Cleaned up {orphaned_deleted} orphaned asuntos")
    conn.commit()

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
