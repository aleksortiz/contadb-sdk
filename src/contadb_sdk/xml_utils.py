"""Helpers de bajo nivel para construir XML CFDI 4.0 con lxml.

Centraliza el uso de namespaces oficiales del SAT y el formato decimal
estándar (2 decimales para importes, 6 para tasas con escala extendida).
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

# --- Namespaces oficiales SAT --------------------------------------------

NS_CFDI: Final[str] = "http://www.sat.gob.mx/cfd/4"
NS_TFD: Final[str] = "http://www.sat.gob.mx/TimbreFiscalDigital"
NS_XSI: Final[str] = "http://www.w3.org/2001/XMLSchema-instance"

SCHEMA_LOCATION: Final[str] = (
    "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"
)

NSMAP: Final[dict[str, str]] = {
    "cfdi": NS_CFDI,
    "xsi": NS_XSI,
}


def cfdi(tag: str) -> str:
    """Devuelve un tag con el namespace cfdi en formato Clark notation."""
    return f"{{{NS_CFDI}}}{tag}"


# --- Formato decimal SAT --------------------------------------------------

#: Cuantizador estándar para importes monetarios (2 decimales).
_Q2 = Decimal("0.01")

#: Cuantizador para tasas (6 decimales — escala máxima del SAT).
_Q6 = Decimal("0.000001")


def fmt_dinero(value: Decimal | int | float) -> str:
    """Formatea un valor monetario a string con 2 decimales (banker's rounding).

    El SAT acepta hasta 6 decimales pero la convención de facturación es 2.
    Usamos ROUND_HALF_EVEN (banker's rounding) que es el default de Python
    Decimal y matemáticamente más estable.
    """
    return str(_a_decimal(value).quantize(_Q2, rounding=ROUND_HALF_EVEN))


def fmt_tasa(value: Decimal | int | float) -> str:
    """Formatea una tasa (TasaOCuota) a string con 6 decimales."""
    return str(_a_decimal(value).quantize(_Q6, rounding=ROUND_HALF_EVEN))


def fmt_cantidad(value: Decimal | int | float) -> str:
    """Formatea cantidad (preserva hasta 6 decimales pero remueve trailing zeros)."""
    d = _a_decimal(value).quantize(_Q6, rounding=ROUND_HALF_EVEN)
    # Normalizar: 1.500000 → 1.5, pero 1.000000 → 1
    normalized = d.normalize()
    _sign, _digits, exponent = normalized.as_tuple()
    if isinstance(exponent, int) and exponent > 0:
        # Forzar al menos 0 decimales (no notación científica)
        return f"{normalized:f}"
    return str(normalized)


def cuantizar_dinero(value: Decimal | int | float) -> Decimal:
    """Cuantiza a 2 decimales (sin convertir a string)."""
    return _a_decimal(value).quantize(_Q2, rounding=ROUND_HALF_EVEN)


def _a_decimal(value: Decimal | int | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    # float → str → Decimal evita errores de representación binaria.
    return Decimal(str(value))


__all__ = [
    "NSMAP",
    "NS_CFDI",
    "NS_TFD",
    "NS_XSI",
    "SCHEMA_LOCATION",
    "cfdi",
    "cuantizar_dinero",
    "fmt_cantidad",
    "fmt_dinero",
    "fmt_tasa",
]
