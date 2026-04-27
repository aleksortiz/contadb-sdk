"""Generación de la cadena original del CFDI 4.0 vía XSLT oficial del SAT.

La cadena original es la representación canónica del comprobante que se
firma con la llave privada para producir el atributo ``Sello``. El SAT
publica el stylesheet oficial; este módulo lo aplica usando lxml.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Union

from lxml import etree

from .exceptions import BuildError

# typing.Union usado intencionalmente: lxml._Element / _ElementTree son
# tipos de C y no soportan PEP 604 (`A | B`) en runtime con `from __future__`.
XmlInput = Union[bytes, str, etree._Element, etree._ElementTree]  # noqa: UP007

_XSLT_TRANSFORM: etree.XSLT | None = None


def _cargar_xslt() -> etree.XSLT:
    """Carga (lazy + cached) el XSLT oficial del SAT desde los recursos del paquete."""
    global _XSLT_TRANSFORM
    if _XSLT_TRANSFORM is not None:
        return _XSLT_TRANSFORM

    xslt_dir = files("contadb_sdk._xslt")
    cadena_path = xslt_dir / "cadenaoriginal_4_0.xslt"

    # `parse` necesita una ruta de filesystem para resolver el include relativo
    # a utilerias.xslt — usamos `as_file` para obtener una ruta concreta.
    from importlib.resources import as_file

    with as_file(cadena_path) as concrete_path:
        try:
            xslt_tree = etree.parse(str(concrete_path))
            _XSLT_TRANSFORM = etree.XSLT(xslt_tree)
        except etree.XMLSyntaxError as exc:  # pragma: no cover
            raise BuildError(f"XSLT del SAT corrupto: {exc}") from exc
        except etree.XSLTParseError as exc:  # pragma: no cover
            raise BuildError(f"No se pudo compilar el XSLT del SAT: {exc}") from exc

    return _XSLT_TRANSFORM


def cadena_original(xml: XmlInput) -> str:
    """Genera la cadena original del comprobante CFDI 4.0.

    Args:
        xml: el XML del comprobante (sin sello). Acepta bytes, str, o un
            elemento/árbol lxml ya parseado.

    Returns:
        La cadena original como string (typically empieza con ``||4.0|...``).

    Raises:
        BuildError: si el XML no es válido o el XSLT falla al transformarlo.
    """
    transform = _cargar_xslt()

    try:
        if isinstance(xml, etree._ElementTree):
            tree = xml
        elif isinstance(xml, etree._Element):
            tree = etree.ElementTree(xml)
        elif isinstance(xml, str):
            tree = etree.ElementTree(etree.fromstring(xml.encode("utf-8")))
        else:
            tree = etree.ElementTree(etree.fromstring(xml))
    except etree.XMLSyntaxError as exc:
        raise BuildError(f"XML mal formado: {exc}") from exc

    try:
        result = transform(tree)
    except etree.XSLTApplyError as exc:
        raise BuildError(f"Falló la aplicación del XSLT: {exc}") from exc

    return str(result).strip()


__all__ = ["cadena_original"]
