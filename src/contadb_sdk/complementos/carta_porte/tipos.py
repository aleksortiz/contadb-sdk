"""Literal types y constantes del Complemento Carta Porte 3.1.

Centraliza los valores admitidos por el catálogo SAT para que mypy
verifique en compile-time. Sin lógica — solo declaraciones de tipo.
"""

from __future__ import annotations

from typing import Final, Literal

# --- Versión y namespace --------------------------------------------------

#: Versión del complemento Carta Porte.
CARTA_PORTE_VERSION: Final[str] = "3.1"

#: Prefijo de namespace.
CARTA_PORTE_PREFIJO: Final[str] = "cartaporte31"

#: URI del namespace oficial SAT para CCP 3.1.
CARTA_PORTE_NS: Final[str] = "http://www.sat.gob.mx/CartaPorte31"

#: Schema location oficial.
CARTA_PORTE_SCHEMA_LOCATION: Final[str] = (
    "http://www.sat.gob.mx/CartaPorte31 "
    "http://www.sat.gob.mx/sitio_internet/cfd/CartaPorte/CartaPorte31.xsd"
)

# --- Literals de catálogo -------------------------------------------------

#: TipoUbicacion del nodo cartaporte31:Ubicacion.
TipoUbicacionStr = Literal["Origen", "Destino"]

#: TipoFigura del nodo TiposFigura.
TipoFiguraStr = Literal["01", "02", "03", "04"]

#: Sí/No de los atributos booleanos textuales del SAT.
SiNoStr = Literal["Sí", "No"]

#: TranspInternac — indica si el traslado cruza frontera.
TranspInternacStr = SiNoStr

#: MaterialPeligroso a nivel Mercancia.
MaterialPeligrosoStr = SiNoStr

# --- Constantes para CFDI tipo "T" (Traslado) ----------------------------

#: ClaveProdServ obligatoria del concepto único en un CFDI tipo "T" con
#: complemento de Carta Porte (catálogo c_ClaveProdServCP).
CLAVE_PROD_SERV_TRASLADO: Final[str] = "78101803"

#: ClaveUnidad obligatoria del concepto único en un CFDI tipo "T".
CLAVE_UNIDAD_TRASLADO: Final[str] = "ACT"

#: Descripción canónica del concepto único de traslado.
DESCRIPCION_TRASLADO: Final[str] = "Traslado"


__all__ = [
    "CARTA_PORTE_NS",
    "CARTA_PORTE_PREFIJO",
    "CARTA_PORTE_SCHEMA_LOCATION",
    "CARTA_PORTE_VERSION",
    "CLAVE_PROD_SERV_TRASLADO",
    "CLAVE_UNIDAD_TRASLADO",
    "DESCRIPCION_TRASLADO",
    "MaterialPeligrosoStr",
    "SiNoStr",
    "TipoFiguraStr",
    "TipoUbicacionStr",
    "TranspInternacStr",
]
