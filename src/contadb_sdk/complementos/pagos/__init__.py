"""Complemento de Recepción de Pagos 2.0 (CRP / REP).

Públicos:
    - :class:`PagoBuilder` — constructor del bloque ``<pago20:Pagos>``.
    - :class:`Pago`, :class:`DoctoRelacionado`, :class:`TrasladoDR`,
      :class:`RetencionDR` — modelos Pydantic.
"""

from __future__ import annotations

from .builder import PagoBuilder
from .modelos import DoctoRelacionado, Pago, RetencionDR, TrasladoDR

__all__ = [
    "DoctoRelacionado",
    "Pago",
    "PagoBuilder",
    "RetencionDR",
    "TrasladoDR",
]
