"""Loader lazy de los catálogos SAT para Carta Porte 3.1.

Lee los archivos JSON de ``_datos/`` solo en el primer uso y mantiene
una caché module-level. Los archivos se distribuyen en el wheel vía
``[tool.hatch.build.targets.wheel.force-include]``.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Final

_CACHE: dict[str, frozenset[str]] = {}


def _cargar(nombre_archivo: str) -> frozenset[str]:
    """Carga las claves de un catálogo (sin valores descriptivos).

    Retorna ``frozenset`` para lookups O(1) y ahorrar memoria.
    """
    if nombre_archivo in _CACHE:
        return _CACHE[nombre_archivo]

    recurso = files("contadb_sdk.complementos.carta_porte.catalogos._datos") / nombre_archivo
    contenido = json.loads(recurso.read_text(encoding="utf-8"))
    claves = frozenset(contenido["claves"].keys())
    _CACHE[nombre_archivo] = claves
    return claves


# Wrappers tipados — un getter por catálogo para que la API pública sea
# explícita y mypy detecte typos en el nombre del catálogo.

_TIPO_PERMISO: Final[str] = "tipo_permiso.json"
_CONFIG_AUTOTRANSPORTE: Final[str] = "config_autotransporte.json"
_TIPO_FIGURA: Final[str] = "tipo_figura.json"
_PAIS: Final[str] = "pais.json"


def tipos_permiso() -> frozenset[str]:
    return _cargar(_TIPO_PERMISO)


def configuraciones_autotransporte() -> frozenset[str]:
    return _cargar(_CONFIG_AUTOTRANSPORTE)


def tipos_figura() -> frozenset[str]:
    return _cargar(_TIPO_FIGURA)


def paises() -> frozenset[str]:
    return _cargar(_PAIS)


__all__ = [
    "configuraciones_autotransporte",
    "paises",
    "tipos_figura",
    "tipos_permiso",
]
