"""Complementos del CFDI 4.0.

Cada sub-paquete implementa un complemento oficial del SAT como clase que
cumple el :class:`~contadb_sdk.complementos.base.Complemento` Protocol.

Sub-paquetes disponibles:
    - :mod:`contadb_sdk.complementos.pagos` — Recepción de Pagos 2.0 (CRP)
    - :mod:`contadb_sdk.complementos.carta_porte` — Carta Porte 3.1 (autotransporte)
"""

from __future__ import annotations

from .base import Complemento, qname
from .carta_porte import (
    Autotransporte,
    CartaPorteBuilder,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Remolque,
    Seguros,
    TiposFigura,
    Ubicacion,
)
from .pagos import (
    DoctoRelacionado,
    Pago,
    PagoBuilder,
    RetencionDR,
    TrasladoDR,
)

__all__ = [
    "Autotransporte",
    "CartaPorteBuilder",
    "Complemento",
    "DoctoRelacionado",
    "Domicilio",
    "FiguraTransporte",
    "IdentificacionVehicular",
    "Mercancia",
    "Pago",
    "PagoBuilder",
    "Remolque",
    "RetencionDR",
    "Seguros",
    "TiposFigura",
    "TrasladoDR",
    "Ubicacion",
    "qname",
]
