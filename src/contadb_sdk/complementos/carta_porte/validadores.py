"""Validaciones cruzadas multi-modelo del Complemento Carta Porte 3.1.

Funciones puras que verifican coherencia *entre* modelos (peso bruto vs
suma de mercancías, seguros vs material peligroso, etc.). Cada función
lanza :class:`~contadb_sdk.exceptions.ValidationError` si encuentra un
problema; en caso exitoso no retorna nada.

Las validaciones intra-modelo (un solo modelo) viven en los respectivos
``@model_validator`` de cada Pydantic.
"""

from __future__ import annotations

from decimal import Decimal

from ...exceptions import ValidationError
from .modelos import (
    Autotransporte,
    FiguraTransporte,
    Mercancia,
    Ubicacion,
)


def validar_ubicaciones(ubicaciones: list[Ubicacion]) -> None:
    """Mínimo 1 Origen + 1 Destino; máximo 1 Origen."""
    origenes = [u for u in ubicaciones if u.tipo_ubicacion == "Origen"]
    destinos = [u for u in ubicaciones if u.tipo_ubicacion == "Destino"]
    if len(origenes) == 0:
        raise ValidationError("CartaPorte requiere exactamente una Ubicacion 'Origen'")
    if len(origenes) > 1:
        raise ValidationError(f"CartaPorte admite a lo más 1 'Origen', recibidos {len(origenes)}")
    if len(destinos) == 0:
        raise ValidationError("CartaPorte requiere al menos una Ubicacion 'Destino'")


def validar_distancia_total(
    total_dist_rec: Decimal,
    ubicaciones: list[Ubicacion],
    tolerancia: Decimal = Decimal("0.01"),
) -> None:
    """``total_dist_rec`` debe coincidir con la suma de distancias de los Destinos
    dentro de la tolerancia (1% por default)."""
    suma = sum(
        (u.distancia_recorrida for u in ubicaciones if u.distancia_recorrida is not None),
        Decimal("0"),
    )
    if total_dist_rec <= 0:
        return  # ya validado por el modelo principal
    diferencia = abs(total_dist_rec - suma)
    margen = total_dist_rec * tolerancia
    if diferencia > margen:
        raise ValidationError(
            f"total_dist_rec ({total_dist_rec}) inconsistente con la suma de "
            f"distancia_recorrida de los Destinos ({suma}); diferencia={diferencia}, "
            f"margen={margen}"
        )


def validar_mercancias(
    mercancias: list[Mercancia],
    peso_bruto_total: Decimal,
    num_total_mercancias: int,
    tolerancia_peso: Decimal = Decimal("0.01"),
) -> None:
    """``peso_bruto_total`` ≈ Σ ``peso_en_kg`` y ``num_total_mercancias`` = len(mercancias)."""
    if not mercancias:
        raise ValidationError("CartaPorte requiere al menos una Mercancia")
    if num_total_mercancias != len(mercancias):
        raise ValidationError(
            f"num_total_mercancias ({num_total_mercancias}) no coincide con la "
            f"cantidad real de mercancías ({len(mercancias)})"
        )
    suma_peso = sum((m.peso_en_kg for m in mercancias), Decimal("0"))
    diferencia = abs(peso_bruto_total - suma_peso)
    margen = suma_peso * tolerancia_peso
    if diferencia > margen:
        raise ValidationError(
            f"peso_bruto_total ({peso_bruto_total}) inconsistente con la suma de "
            f"peso_en_kg de mercancías ({suma_peso}); diferencia={diferencia}, "
            f"margen={margen}"
        )


def validar_seguros_material_peligroso(
    mercancias: list[Mercancia],
    autotransporte: Autotransporte,
) -> None:
    """Si hay alguna mercancía peligrosa, el autotransporte debe declarar
    seguro de medio ambiente."""
    hay_peligroso = any(m.material_peligroso == "Sí" for m in mercancias)
    if hay_peligroso and autotransporte.seguros.asegura_med_ambiente is None:
        raise ValidationError(
            "Mercancía con material peligroso requiere Seguros.asegura_med_ambiente"
        )


def validar_figura_transporte(figura: FiguraTransporte) -> None:
    """``FiguraTransporte`` debe contener al menos una :class:`TiposFigura`."""
    if not figura.figuras:
        raise ValidationError("FiguraTransporte requiere al menos una figura")


__all__ = [
    "validar_distancia_total",
    "validar_figura_transporte",
    "validar_mercancias",
    "validar_seguros_material_peligroso",
    "validar_ubicaciones",
]
