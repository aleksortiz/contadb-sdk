"""Protocolo común para complementos del CFDI 4.0.

Cada complemento (Pagos 2.0, Carta Porte 3.1, Comercio Exterior, etc.) se
implementa como una clase que cumple el :class:`Complemento` Protocol — así
:class:`~contadb_sdk.builder.CFDIBuilder` los inyecta de forma genérica bajo
``<cfdi:Complemento>`` sin acoplarse a su estructura interna.

Diseño SRP: este módulo **solo** define el contrato; ninguna lógica de
construcción XML específica de un complemento vive aquí.
"""

from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

from lxml import etree


@runtime_checkable
class Complemento(Protocol):
    """Contrato que debe cumplir todo complemento del CFDI 4.0.

    Implementaciones concretas:
        - :class:`contadb_sdk.complementos.pagos.PagoBuilder` (CRP 2.0)
        - (futuro) ``CartaPorteBuilder`` (CCP 3.1)

    Atributos de clase:
        prefijo_ns: prefijo de namespace XML (ej. ``"pago20"``).
        uri_ns: URI del namespace oficial SAT.
        schema_location: par "URI ruta_xsd" para ``xsi:schemaLocation``.
    """

    prefijo_ns: ClassVar[str]
    uri_ns: ClassVar[str]
    schema_location: ClassVar[str]

    def construir_elemento(self) -> etree._Element:
        """Construye y devuelve el ``_Element`` raíz del complemento.

        El elemento debe estar en el namespace declarado por la clase
        (``uri_ns``) y será insertado tal cual bajo ``<cfdi:Complemento>``.
        """
        ...


def qname(uri_ns: str, tag: str) -> str:
    """Devuelve un tag con namespace en notación Clark (``{uri}tag``)."""
    return f"{{{uri_ns}}}{tag}"


__all__ = ["Complemento", "qname"]
