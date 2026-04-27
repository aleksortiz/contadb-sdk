"""Constructor del XML del Complemento de Recepción de Pagos 2.0.

Este módulo **solo** ensambla ``lxml._Element``s — la lógica de validación
vive en :mod:`.modelos` y los cálculos agregados en :mod:`._calculos`.

API pública: :class:`PagoBuilder` cumple el Protocol
:class:`~contadb_sdk.complementos.base.Complemento`, así que se inserta en
un CFDI vía ``CFDIBuilder.agregar_complemento(pago_builder)``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from lxml import etree

from ...exceptions import ValidationError
from ...xml_utils import fmt_dinero, fmt_tasa
from ..base import qname
from ._calculos import (
    ImpuestosP,
    RetencionP,
    Totales,
    TrasladoP,
    calcular_impuestos_p,
    calcular_totales,
)
from .modelos import DoctoRelacionado, Pago
from .tipos import (
    PAGOS_NS,
    PAGOS_PREFIJO,
    PAGOS_SCHEMA_LOCATION,
    PAGOS_VERSION,
)


def _p(tag: str) -> str:
    """Tag con namespace de Pagos 2.0 en notación Clark."""
    return qname(PAGOS_NS, tag)


class PagoBuilder:
    """Constructor del bloque ``<pago20:Pagos>`` del CFDI 4.0.

    Uso típico::

        builder = (
            PagoBuilder()
            .agregar_pago(Pago(...))
            .agregar_pago(Pago(...))
        )
        cfdi = CFDIBuilder.para_pago(emisor=..., receptor=..., lugar_expedicion="64000")
        cfdi.agregar_complemento(builder)
        xml = cfdi.construir_y_firmar(cert)

    El builder calcula automáticamente:
        - El bloque ``pago20:ImpuestosP`` por cada Pago, agregando los
          TrasladosDR/RetencionesDR de sus DRs (en MonedaP).
        - El bloque ``pago20:Totales`` del comprobante (en MXN).
    """

    # Cumplimiento del Protocol Complemento -------------------------------
    prefijo_ns: ClassVar[str] = PAGOS_PREFIJO
    uri_ns: ClassVar[str] = PAGOS_NS
    schema_location: ClassVar[str] = PAGOS_SCHEMA_LOCATION

    def __init__(self) -> None:
        self._pagos: list[Pago] = []

    # -- API fluida --------------------------------------------------------

    def agregar_pago(self, pago: Pago) -> PagoBuilder:
        if not isinstance(pago, Pago):
            raise ValidationError("pago debe ser una instancia de Pago")
        self._pagos.append(pago)
        return self

    def agregar_pagos(self, pagos: Iterable[Pago]) -> PagoBuilder:
        for p in pagos:
            self.agregar_pago(p)
        return self

    # -- Construcción del elemento ----------------------------------------

    def construir_elemento(self) -> etree._Element:
        if not self._pagos:
            raise ValidationError("PagoBuilder requiere al menos un Pago")

        for pago in self._pagos:
            self._validar_consistencia_monedas(pago)

        nsmap = {PAGOS_PREFIJO: PAGOS_NS}
        root = etree.Element(_p("Pagos"), nsmap=nsmap)
        root.set("Version", PAGOS_VERSION)

        totales = calcular_totales(self._pagos)
        self._construir_totales(root, totales)

        for pago in self._pagos:
            self._construir_pago(root, pago)

        return root

    # -- Internos ----------------------------------------------------------

    @staticmethod
    def _validar_consistencia_monedas(pago: Pago) -> None:
        for dr in pago.documentos:
            if dr.moneda_dr != pago.moneda and dr.equivalencia_dr is None:
                raise ValidationError(
                    f"DoctoRelacionado {dr.id_documento}: moneda_dr={dr.moneda_dr} "
                    f"difiere de moneda del Pago ({pago.moneda}) — equivalencia_dr "
                    "es obligatorio"
                )

    @staticmethod
    def _construir_totales(parent: etree._Element, t: Totales) -> None:
        el = etree.SubElement(parent, _p("Totales"))
        # SAT define un orden estricto de atributos en Totales — respetarlo
        # ayuda a que el XSLT canonice de forma reproducible.
        if t.total_retenciones_iva is not None:
            el.set("TotalRetencionesIVA", fmt_dinero(t.total_retenciones_iva))
        if t.total_retenciones_isr is not None:
            el.set("TotalRetencionesISR", fmt_dinero(t.total_retenciones_isr))
        if t.total_retenciones_ieps is not None:
            el.set("TotalRetencionesIEPS", fmt_dinero(t.total_retenciones_ieps))
        if t.total_traslados_base_iva_16 is not None:
            el.set("TotalTrasladosBaseIVA16", fmt_dinero(t.total_traslados_base_iva_16))
        if t.total_traslados_impuesto_iva_16 is not None:
            el.set("TotalTrasladosImpuestoIVA16", fmt_dinero(t.total_traslados_impuesto_iva_16))
        if t.total_traslados_base_iva_8 is not None:
            el.set("TotalTrasladosBaseIVA8", fmt_dinero(t.total_traslados_base_iva_8))
        if t.total_traslados_impuesto_iva_8 is not None:
            el.set("TotalTrasladosImpuestoIVA8", fmt_dinero(t.total_traslados_impuesto_iva_8))
        if t.total_traslados_base_iva_0 is not None:
            el.set("TotalTrasladosBaseIVA0", fmt_dinero(t.total_traslados_base_iva_0))
        if t.total_traslados_impuesto_iva_0 is not None:
            el.set("TotalTrasladosImpuestoIVA0", fmt_dinero(t.total_traslados_impuesto_iva_0))
        if t.total_traslados_base_iva_exento is not None:
            el.set("TotalTrasladosBaseIVAExento", fmt_dinero(t.total_traslados_base_iva_exento))
        el.set("MontoTotalPagos", fmt_dinero(t.monto_total_pagos))

    def _construir_pago(self, parent: etree._Element, pago: Pago) -> None:
        el = etree.SubElement(parent, _p("Pago"))
        el.set("FechaPago", pago.fecha_pago.strftime("%Y-%m-%dT%H:%M:%S"))
        el.set("FormaDePagoP", pago.forma_pago)
        el.set("MonedaP", pago.moneda)
        if pago.tipo_cambio is not None:
            el.set("TipoCambioP", fmt_tasa(pago.tipo_cambio))
        el.set("Monto", fmt_dinero(pago.monto))
        if pago.num_operacion is not None:
            el.set("NumOperacion", pago.num_operacion)
        if pago.rfc_emisor_cta_ord is not None:
            el.set("RfcEmisorCtaOrd", pago.rfc_emisor_cta_ord)
        if pago.nom_banco_ord_ext is not None:
            el.set("NomBancoOrdExt", pago.nom_banco_ord_ext)
        if pago.cta_ordenante is not None:
            el.set("CtaOrdenante", pago.cta_ordenante)
        if pago.rfc_emisor_cta_ben is not None:
            el.set("RfcEmisorCtaBen", pago.rfc_emisor_cta_ben)
        if pago.cta_beneficiario is not None:
            el.set("CtaBeneficiario", pago.cta_beneficiario)
        if pago.tipo_cad_pago is not None:
            el.set("TipoCadPago", pago.tipo_cad_pago)
        if pago.cert_pago is not None:
            el.set("CertPago", pago.cert_pago)
        if pago.cad_pago is not None:
            el.set("CadPago", pago.cad_pago)
        if pago.sello_pago is not None:
            el.set("SelloPago", pago.sello_pago)

        for dr in pago.documentos:
            self._construir_docto_relacionado(el, dr, pago.moneda)

        impuestos_p = calcular_impuestos_p(pago)
        if not impuestos_p.vacio:
            self._construir_impuestos_p(el, impuestos_p)

    def _construir_docto_relacionado(
        self,
        parent: etree._Element,
        dr: DoctoRelacionado,
        moneda_pago: str,
    ) -> None:
        el = etree.SubElement(parent, _p("DoctoRelacionado"))
        el.set("IdDocumento", dr.id_documento)
        if dr.serie is not None:
            el.set("Serie", dr.serie)
        if dr.folio is not None:
            el.set("Folio", dr.folio)
        el.set("MonedaDR", dr.moneda_dr)
        if dr.equivalencia_dr is not None:
            el.set("EquivalenciaDR", fmt_tasa(dr.equivalencia_dr))
        elif dr.moneda_dr != moneda_pago:  # pragma: no cover — _validar_consistencia_monedas
            raise ValidationError("EquivalenciaDR requerido por divergencia de moneda")
        el.set("NumParcialidad", str(dr.num_parcialidad))
        el.set("ImpSaldoAnt", fmt_dinero(dr.imp_saldo_ant))
        el.set("ImpPagado", fmt_dinero(dr.imp_pagado))
        el.set("ImpSaldoInsoluto", fmt_dinero(dr.imp_saldo_insoluto))
        el.set("ObjetoImpDR", dr.objeto_imp_dr)

        if dr.objeto_imp_dr == "02" and (dr.traslados or dr.retenciones):
            self._construir_impuestos_dr(el, dr)

    def _construir_impuestos_dr(self, parent: etree._Element, dr: DoctoRelacionado) -> None:
        imp_el = etree.SubElement(parent, _p("ImpuestosDR"))
        # SAT exige primero RetencionesDR, luego TrasladosDR.
        if dr.retenciones:
            ret_el = etree.SubElement(imp_el, _p("RetencionesDR"))
            for r in dr.retenciones:
                rel = etree.SubElement(ret_el, _p("RetencionDR"))
                rel.set("BaseDR", fmt_dinero(r.base))
                rel.set("ImpuestoDR", r.impuesto)
                rel.set("TipoFactorDR", r.tipo_factor)
                rel.set("TasaOCuotaDR", fmt_tasa(r.tasa_o_cuota))
                rel.set("ImporteDR", fmt_dinero(r.importe))
        if dr.traslados:
            tras_el = etree.SubElement(imp_el, _p("TrasladosDR"))
            for t in dr.traslados:
                tel = etree.SubElement(tras_el, _p("TrasladoDR"))
                tel.set("BaseDR", fmt_dinero(t.base))
                tel.set("ImpuestoDR", t.impuesto)
                tel.set("TipoFactorDR", t.tipo_factor)
                if t.tasa_o_cuota is not None:
                    tel.set("TasaOCuotaDR", fmt_tasa(t.tasa_o_cuota))
                if t.importe is not None:
                    tel.set("ImporteDR", fmt_dinero(t.importe))

    def _construir_impuestos_p(self, parent: etree._Element, ip: ImpuestosP) -> None:
        imp_el = etree.SubElement(parent, _p("ImpuestosP"))
        if ip.retenciones:
            ret_el = etree.SubElement(imp_el, _p("RetencionesP"))
            for r in ip.retenciones:
                self._construir_retencion_p(ret_el, r)
        if ip.traslados:
            tras_el = etree.SubElement(imp_el, _p("TrasladosP"))
            for t in ip.traslados:
                self._construir_traslado_p(tras_el, t)

    @staticmethod
    def _construir_retencion_p(parent: etree._Element, r: RetencionP) -> None:
        el = etree.SubElement(parent, _p("RetencionP"))
        el.set("ImpuestoP", r.impuesto)
        el.set("ImporteP", fmt_dinero(r.importe))

    @staticmethod
    def _construir_traslado_p(parent: etree._Element, t: TrasladoP) -> None:
        el = etree.SubElement(parent, _p("TrasladoP"))
        el.set("BaseP", fmt_dinero(t.base))
        el.set("ImpuestoP", t.impuesto)
        el.set("TipoFactorP", t.tipo_factor)
        if t.tasa_o_cuota is not None:
            el.set("TasaOCuotaP", fmt_tasa(t.tasa_o_cuota))
        if t.importe is not None:
            el.set("ImporteP", fmt_dinero(t.importe))


__all__ = ["PagoBuilder"]
