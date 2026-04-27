"""Complemento Carta Porte 3.1 — Autotransporte (Fase 3a).

Públicos:
    - :class:`CartaPorteBuilder` — constructor del bloque ``<cartaporte31:CartaPorte>``.
    - Modelos: :class:`Domicilio`, :class:`Ubicacion`, :class:`Mercancia`,
      :class:`Autotransporte`, :class:`IdentificacionVehicular`,
      :class:`Seguros`, :class:`Remolque`, :class:`FiguraTransporte`,
      :class:`TiposFigura`.

Limitaciones Fase 3a:
    - Solo soporta autotransporte (no marítimo/aéreo/ferroviario).
    - Sub-elementos avanzados de Mercancia (DocumentacionAduanera,
      Pedimentos, etc.) diferidos a Fase 3b.
    - Catálogos validados: TipoPermiso, ConfigAutotransporte, TipoFigura,
      Pais. Estado/Municipio/Colonia se aceptan como string libre.
"""

from __future__ import annotations

from .builder import CartaPorteBuilder
from .modelos import (
    Autotransporte,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Remolque,
    Seguros,
    TiposFigura,
    Ubicacion,
)

__all__ = [
    "Autotransporte",
    "CartaPorteBuilder",
    "Domicilio",
    "FiguraTransporte",
    "IdentificacionVehicular",
    "Mercancia",
    "Remolque",
    "Seguros",
    "TiposFigura",
    "Ubicacion",
]
