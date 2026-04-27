"""Literal types y constantes del Complemento de Recepción de Pagos 2.0.

Centraliza los valores admitidos por el catálogo SAT para que mypy
verifique en compile-time. Sin lógica — solo declaraciones de tipo.
"""

from __future__ import annotations

from typing import Final, Literal

# --- Versión y namespace --------------------------------------------------

#: Versión del complemento de pagos.
PAGOS_VERSION: Final[str] = "2.0"

#: Prefijo de namespace.
PAGOS_PREFIJO: Final[str] = "pago20"

#: URI del namespace oficial SAT para CRP 2.0.
PAGOS_NS: Final[str] = "http://www.sat.gob.mx/Pagos20"

#: Schema location oficial.
PAGOS_SCHEMA_LOCATION: Final[str] = (
    "http://www.sat.gob.mx/Pagos20 http://www.sat.gob.mx/sitio_internet/cfd/Pagos/Pagos20.xsd"
)

# --- Literals de catálogo -------------------------------------------------

#: TipoCadenaPago — solo aplica si el pago se hizo con SPEI y se incluye
#: comprobante de la operación.
TipoCadenaPagoStr = Literal["01"]

#: ObjetoImpDR — análogo a ObjetoImp del CFDI base, restringido en CRP.
ObjetoImpDRStr = Literal["01", "02", "03"]

#: TipoFactor de impuestos a nivel DR / P.
TipoFactorStr = Literal["Tasa", "Cuota", "Exento"]

# --- Constantes del Concepto placeholder requerido en CFDI tipo "P" -------

#: ClaveProdServ obligatoria del concepto único en un CFDI de tipo "P".
CLAVE_PROD_SERV_PAGO: Final[str] = "84111506"

#: ClaveUnidad obligatoria del concepto único en un CFDI de tipo "P".
CLAVE_UNIDAD_PAGO: Final[str] = "ACT"

#: Descripción canónica del concepto de pago.
DESCRIPCION_PAGO: Final[str] = "Pago"

#: Moneda obligatoria del Comprobante CFDI tipo "P".
MONEDA_COMPROBANTE_PAGO: Final[str] = "XXX"


__all__ = [
    "CLAVE_PROD_SERV_PAGO",
    "CLAVE_UNIDAD_PAGO",
    "DESCRIPCION_PAGO",
    "MONEDA_COMPROBANTE_PAGO",
    "PAGOS_NS",
    "PAGOS_PREFIJO",
    "PAGOS_SCHEMA_LOCATION",
    "PAGOS_VERSION",
    "ObjetoImpDRStr",
    "TipoCadenaPagoStr",
    "TipoFactorStr",
]
