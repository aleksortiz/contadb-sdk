"""Cálculos puros del Complemento de Recepción de Pagos 2.0.

Funciones sin side-effects que agregan información derivada a partir de
los modelos Pydantic — específicamente:

- :func:`calcular_impuestos_p`: agrega los TrasladosDR/RetencionesDR de
  cada DR de un Pago al bloque ``pago20:ImpuestosP`` (en MonedaP).
- :func:`calcular_totales`: agrega todos los Pagos al bloque ``pago20:Totales``
  del comprobante (en MXN, aplicando ``TipoCambioP`` por pago).

Mantener estas funciones puras facilita testearlas sin instanciar lxml ni
construir XML, y respeta SRP separando "qué se calcula" de "cómo se serializa".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ...catalogs import IMPUESTO_IVA
from ...xml_utils import cuantizar_dinero
from .modelos import Pago


@dataclass(frozen=True, slots=True)
class _ClaveTrasladoP:
    """Llave de agregación para TrasladosP — tasa formateada como string
    para evitar colisiones por equivalencia de Decimals (0.16 vs 0.160000)."""

    impuesto: str
    tipo_factor: str
    tasa_str: str  # vacío para Exento


@dataclass(slots=True)
class TrasladoP:
    """Traslado agregado a nivel Pago (``pago20:TrasladoP``)."""

    base: Decimal
    impuesto: str
    tipo_factor: str
    tasa_o_cuota: Decimal | None
    importe: Decimal | None


@dataclass(slots=True)
class RetencionP:
    """Retención agregada a nivel Pago (``pago20:RetencionP``)."""

    impuesto: str
    importe: Decimal


@dataclass(slots=True)
class ImpuestosP:
    """Resultado de :func:`calcular_impuestos_p`."""

    traslados: list[TrasladoP] = field(default_factory=list)
    retenciones: list[RetencionP] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.traslados and not self.retenciones


@dataclass(slots=True)
class Totales:
    """Resultado de :func:`calcular_totales` — todos los importes en MXN.

    Los campos opcionales (``None``) no se serializan en el XML.
    """

    monto_total_pagos: Decimal
    total_retenciones_iva: Decimal | None = None
    total_retenciones_isr: Decimal | None = None
    total_retenciones_ieps: Decimal | None = None
    total_traslados_base_iva_16: Decimal | None = None
    total_traslados_impuesto_iva_16: Decimal | None = None
    total_traslados_base_iva_8: Decimal | None = None
    total_traslados_impuesto_iva_8: Decimal | None = None
    total_traslados_base_iva_0: Decimal | None = None
    total_traslados_impuesto_iva_0: Decimal | None = None
    total_traslados_base_iva_exento: Decimal | None = None


# --- Cálculos a nivel Pago ------------------------------------------------


def calcular_impuestos_p(pago: Pago) -> ImpuestosP:
    """Agrega los impuestos de los DRs al bloque ImpuestosP del Pago.

    Los importes se convierten a MonedaP multiplicando por
    ``EquivalenciaDR`` cuando MonedaDR difiere; si coincide se asume 1.
    """
    traslados_acc: dict[_ClaveTrasladoP, tuple[Decimal, Decimal | None]] = {}
    # value: (base_acumulada, importe_acumulado_o_None_si_exento)
    retenciones_acc: dict[str, Decimal] = {}

    for dr in pago.documentos:
        if dr.objeto_imp_dr != "02":
            continue
        equiv = _equivalencia(pago, dr.moneda_dr, dr.equivalencia_dr)

        for t in dr.traslados:
            tasa_str = _fmt_tasa(t.tasa_o_cuota) if t.tasa_o_cuota is not None else ""
            key = _ClaveTrasladoP(t.impuesto, t.tipo_factor, tasa_str)
            base_p = t.base * equiv
            importe_p = t.importe * equiv if t.importe is not None else None

            base_prev, importe_prev = traslados_acc.get(key, (Decimal("0"), None))
            new_base = base_prev + base_p
            new_importe: Decimal | None
            if importe_p is None:
                new_importe = importe_prev  # exento permanece sin importe
            else:
                new_importe = (importe_prev or Decimal("0")) + importe_p
            traslados_acc[key] = (new_base, new_importe)

        for r in dr.retenciones:
            importe_p = r.importe * equiv
            retenciones_acc[r.impuesto] = retenciones_acc.get(r.impuesto, Decimal("0")) + importe_p

    traslados = [
        TrasladoP(
            base=cuantizar_dinero(base),
            impuesto=k.impuesto,
            tipo_factor=k.tipo_factor,
            tasa_o_cuota=Decimal(k.tasa_str) if k.tasa_str else None,
            importe=cuantizar_dinero(importe) if importe is not None else None,
        )
        for k, (base, importe) in sorted(
            traslados_acc.items(),
            key=lambda kv: (kv[0].impuesto, kv[0].tipo_factor, kv[0].tasa_str),
        )
    ]
    retenciones = [
        RetencionP(impuesto=imp, importe=cuantizar_dinero(importe))
        for imp, importe in sorted(retenciones_acc.items())
    ]
    return ImpuestosP(traslados=traslados, retenciones=retenciones)


# --- Cálculos a nivel Totales (XML completo) ------------------------------


def calcular_totales(pagos: list[Pago]) -> Totales:
    """Agrega los Pagos al bloque ``pago20:Totales`` (todo en MXN)."""
    monto_total = Decimal("0")
    ret_iva = Decimal("0")
    ret_isr = Decimal("0")
    ret_ieps = Decimal("0")
    base_iva_16 = Decimal("0")
    imp_iva_16 = Decimal("0")
    base_iva_8 = Decimal("0")
    imp_iva_8 = Decimal("0")
    base_iva_0 = Decimal("0")
    imp_iva_0 = Decimal("0")
    base_iva_exento = Decimal("0")

    huellas: dict[str, bool] = {
        "ret_iva": False,
        "ret_isr": False,
        "ret_ieps": False,
        "iva_16": False,
        "iva_8": False,
        "iva_0": False,
        "iva_exento": False,
    }

    for pago in pagos:
        factor_mxn = _factor_a_mxn(pago)
        monto_total += pago.monto * factor_mxn

        impuestos_p = calcular_impuestos_p(pago)

        for r in impuestos_p.retenciones:
            importe_mxn = r.importe * factor_mxn
            if r.impuesto == "002":
                ret_iva += importe_mxn
                huellas["ret_iva"] = True
            elif r.impuesto == "001":
                ret_isr += importe_mxn
                huellas["ret_isr"] = True
            elif r.impuesto == "003":
                ret_ieps += importe_mxn
                huellas["ret_ieps"] = True

        for t in impuestos_p.traslados:
            if t.impuesto != IMPUESTO_IVA:
                # Totales solo agrega IVA — los traslados de IEPS no figuran.
                continue
            base_mxn = t.base * factor_mxn
            importe_mxn = t.importe * factor_mxn if t.importe is not None else Decimal("0")
            if t.tipo_factor == "Exento":
                base_iva_exento += base_mxn
                huellas["iva_exento"] = True
            elif t.tasa_o_cuota == Decimal("0.16"):
                base_iva_16 += base_mxn
                imp_iva_16 += importe_mxn
                huellas["iva_16"] = True
            elif t.tasa_o_cuota == Decimal("0.08"):
                base_iva_8 += base_mxn
                imp_iva_8 += importe_mxn
                huellas["iva_8"] = True
            elif t.tasa_o_cuota == Decimal("0"):
                base_iva_0 += base_mxn
                imp_iva_0 += importe_mxn
                huellas["iva_0"] = True

    def _opt(presente: bool, valor: Decimal) -> Decimal | None:
        return cuantizar_dinero(valor) if presente else None

    return Totales(
        monto_total_pagos=cuantizar_dinero(monto_total),
        total_retenciones_iva=_opt(huellas["ret_iva"], ret_iva),
        total_retenciones_isr=_opt(huellas["ret_isr"], ret_isr),
        total_retenciones_ieps=_opt(huellas["ret_ieps"], ret_ieps),
        total_traslados_base_iva_16=_opt(huellas["iva_16"], base_iva_16),
        total_traslados_impuesto_iva_16=_opt(huellas["iva_16"], imp_iva_16),
        total_traslados_base_iva_8=_opt(huellas["iva_8"], base_iva_8),
        total_traslados_impuesto_iva_8=_opt(huellas["iva_8"], imp_iva_8),
        total_traslados_base_iva_0=_opt(huellas["iva_0"], base_iva_0),
        total_traslados_impuesto_iva_0=_opt(huellas["iva_0"], imp_iva_0),
        total_traslados_base_iva_exento=_opt(huellas["iva_exento"], base_iva_exento),
    )


# --- Helpers privados -----------------------------------------------------


def _equivalencia(pago: Pago, moneda_dr: str, equivalencia_dr: Decimal | None) -> Decimal:
    """Factor para convertir importes de MonedaDR a MonedaP."""
    if moneda_dr == pago.moneda:
        return Decimal("1")
    if equivalencia_dr is None:
        raise ValueError(
            f"DR en moneda {moneda_dr} con Pago en {pago.moneda} requiere equivalencia_dr"
        )
    return equivalencia_dr


def _factor_a_mxn(pago: Pago) -> Decimal:
    """Factor para convertir importes de MonedaP a MXN."""
    if pago.moneda == "MXN":
        return Decimal("1")
    if pago.tipo_cambio is None:  # pragma: no cover — Pydantic ya lo valida
        raise ValueError(f"Pago en {pago.moneda} sin tipo_cambio")
    return pago.tipo_cambio


def _fmt_tasa(tasa: Decimal) -> str:
    """Llave estable de tasa para usar en dicts (6 decimales fijos)."""
    return format(tasa.quantize(Decimal("0.000001")), "f")


__all__ = [
    "ImpuestosP",
    "RetencionP",
    "Totales",
    "TrasladoP",
    "calcular_impuestos_p",
    "calcular_totales",
]
