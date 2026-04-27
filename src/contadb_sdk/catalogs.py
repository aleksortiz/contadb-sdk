"""Constantes y enums de los catálogos SAT más usados.

Este módulo NO incluye los catálogos completos del SAT (ProductoServicio,
ClaveUnidad, etc.) — esos contienen miles de entradas y deben consultarse
directamente al SAT o a un endpoint de búsqueda. Aquí solo proveemos
enums para los catálogos pequeños y de uso constante.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class TipoComprobante(str, Enum):
    """Catálogo c_TipoDeComprobante."""

    INGRESO = "I"
    EGRESO = "E"
    TRASLADO = "T"
    PAGO = "P"
    NOMINA = "N"


class MetodoPago(str, Enum):
    """Catálogo c_MetodoPago."""

    PUE = "PUE"  # Pago en una sola exhibición
    PPD = "PPD"  # Pago en parcialidades o diferido


class Exportacion(str, Enum):
    """Catálogo c_Exportacion."""

    NO_APLICA = "01"
    DEFINITIVA = "02"
    TEMPORAL = "03"
    DEFINITIVA_NO_RETORNO = "04"


class ObjetoImp(str, Enum):
    """Catálogo c_ObjetoImp."""

    NO_OBJETO = "01"
    SI_OBJETO = "02"
    SI_OBJETO_NO_DESGLOSE = "03"


class Periodicidad(str, Enum):
    """Catálogo c_Periodicidad (para CFDI globales)."""

    DIARIO = "01"
    SEMANAL = "02"
    QUINCENAL = "03"
    MENSUAL = "04"
    BIMESTRAL = "05"


class FormaPago(str, Enum):
    """Catálogo c_FormaPago — claves más comunes (no exhaustivo)."""

    EFECTIVO = "01"
    CHEQUE_NOMINATIVO = "02"
    TRANSFERENCIA = "03"
    TARJETA_CREDITO = "04"
    MONEDERO_ELECTRONICO = "05"
    DINERO_ELECTRONICO = "06"
    VALES_DESPENSA = "08"
    DACION_PAGO = "12"
    SUBROGACION = "13"
    CONSIGNACION = "14"
    CONDONACION = "15"
    COMPENSACION = "17"
    NOVACION = "23"
    CONFUSION = "24"
    REMISION_DEUDA = "25"
    PRESCRIPCION_CADUCIDAD = "26"
    SATISFACCION_ACREEDOR = "27"
    TARJETA_DEBITO = "28"
    TARJETA_SERVICIOS = "29"
    APLICACION_ANTICIPOS = "30"
    INTERMEDIARIO_PAGOS = "31"
    POR_DEFINIR = "99"


# Constantes de referencia comunes ----------------------------------------

#: RFC genérico para "Público en general" (CFDI globales).
RFC_PUBLICO_GENERAL: Final[str] = "XAXX010101000"

#: Nombre genérico para el receptor "Público en general".
NOMBRE_PUBLICO_GENERAL: Final[str] = "PUBLICO EN GENERAL"

#: RFC genérico para receptor extranjero.
RFC_EXTRANJERO: Final[str] = "XEXX010101000"

#: Régimen fiscal "Sin obligaciones fiscales" (usado para receptor genérico).
REGIMEN_SIN_OBLIGACIONES: Final[str] = "616"

#: UsoCFDI "Sin efectos fiscales" (S01) — apropiado para CFDI globales.
USO_PUBLICO_GENERAL: Final[str] = "S01"

#: Código del impuesto IVA según c_Impuesto.
IMPUESTO_IVA: Final[str] = "002"

#: Código del impuesto ISR según c_Impuesto.
IMPUESTO_ISR: Final[str] = "001"

#: Código del impuesto IEPS según c_Impuesto.
IMPUESTO_IEPS: Final[str] = "003"

#: Versión del CFDI generado por este SDK.
CFDI_VERSION: Final[str] = "4.0"

#: Moneda mexicana (default).
MONEDA_MXN: Final[str] = "MXN"


__all__ = [
    "CFDI_VERSION",
    "IMPUESTO_IEPS",
    "IMPUESTO_ISR",
    "IMPUESTO_IVA",
    "MONEDA_MXN",
    "NOMBRE_PUBLICO_GENERAL",
    "REGIMEN_SIN_OBLIGACIONES",
    "RFC_EXTRANJERO",
    "RFC_PUBLICO_GENERAL",
    "USO_PUBLICO_GENERAL",
    "Exportacion",
    "FormaPago",
    "MetodoPago",
    "ObjetoImp",
    "Periodicidad",
    "TipoComprobante",
]
