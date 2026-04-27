"""Modelos Pydantic del Complemento Carta Porte 3.1 (Autotransporte).

Cada submódulo agrupa modelos por responsabilidad:
    - :mod:`.comun` — Domicilio (compartido)
    - :mod:`.ubicaciones` — Ubicacion (Origen/Destino)
    - :mod:`.mercancias` — Mercancia
    - :mod:`.autotransporte` — Autotransporte, IdentificacionVehicular,
      Seguros, Remolque
    - :mod:`.figura_transporte` — FiguraTransporte, TiposFigura
"""

from __future__ import annotations

from .autotransporte import Autotransporte, IdentificacionVehicular, Remolque, Seguros
from .comun import Domicilio
from .figura_transporte import FiguraTransporte, TiposFigura
from .mercancias import Mercancia
from .ubicaciones import Ubicacion

__all__ = [
    "Autotransporte",
    "Domicilio",
    "FiguraTransporte",
    "IdentificacionVehicular",
    "Mercancia",
    "Remolque",
    "Seguros",
    "TiposFigura",
    "Ubicacion",
]
