"""API pública de catálogos SAT para Carta Porte 3.1.

Cada función ``validar_*`` regresa el valor recibido si es válido; lanza
:class:`ValueError` si no figura en el catálogo SAT correspondiente. Se
usa ``ValueError`` (no nuestra ``ValidationError``) para que Pydantic lo
envuelva automáticamente cuando se invoca desde un ``@model_validator``;
los callers externos pueden capturar igualmente con ``ValueError``.

Los catálogos cargan de forma lazy en el primer uso (ver :mod:`._carga`).
"""

from __future__ import annotations

from . import _carga


def validar_tipo_permiso(clave: str) -> str:
    if clave not in _carga.tipos_permiso():
        raise ValueError(f"PermSCT inválido según catálogo SAT: {clave!r}")
    return clave


def validar_config_autotransporte(clave: str) -> str:
    if clave not in _carga.configuraciones_autotransporte():
        raise ValueError(f"ConfigVehicular inválido según catálogo SAT: {clave!r}")
    return clave


def validar_tipo_figura(clave: str) -> str:
    if clave not in _carga.tipos_figura():
        raise ValueError(f"TipoFigura inválido según catálogo SAT: {clave!r}")
    return clave


def validar_pais(clave: str) -> str:
    if clave not in _carga.paises():
        raise ValueError(f"País inválido (esperado código ISO 3166-1 alpha-3): {clave!r}")
    return clave


__all__ = [
    "validar_config_autotransporte",
    "validar_pais",
    "validar_tipo_figura",
    "validar_tipo_permiso",
]
