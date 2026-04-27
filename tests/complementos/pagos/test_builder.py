"""Tests del PagoBuilder — construcción del bloque <pago20:Pagos>."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from lxml import etree

from contadb_sdk import (
    DoctoRelacionado,
    Pago,
    PagoBuilder,
    TrasladoDR,
    ValidationError,
)
from contadb_sdk.complementos.pagos.tipos import PAGOS_NS


def _xpath(el: etree._Element, path: str) -> list[etree._Element]:
    """XPath helper con el namespace de Pagos 2.0."""
    return el.xpath(path, namespaces={"p": PAGOS_NS})


class TestPagoBuilderBasico:
    def test_construir_genera_elemento_pagos(self, pago_builder: PagoBuilder) -> None:
        el = pago_builder.construir_elemento()
        assert el.tag == f"{{{PAGOS_NS}}}Pagos"
        assert el.get("Version") == "2.0"

    def test_genera_un_pago(self, pago_builder: PagoBuilder) -> None:
        el = pago_builder.construir_elemento()
        pagos = _xpath(el, "p:Pago")
        assert len(pagos) == 1
        pago_el = pagos[0]
        assert pago_el.get("MonedaP") == "MXN"
        assert pago_el.get("Monto") == "1160.00"
        assert pago_el.get("FormaDePagoP") == "03"

    def test_totales_iva_16(self, pago_builder: PagoBuilder) -> None:
        el = pago_builder.construir_elemento()
        totales = _xpath(el, "p:Totales")[0]
        assert totales.get("TotalTrasladosBaseIVA16") == "1000.00"
        assert totales.get("TotalTrasladosImpuestoIVA16") == "160.00"
        assert totales.get("MontoTotalPagos") == "1160.00"
        assert totales.get("TotalRetencionesIVA") is None

    def test_genera_docto_relacionado(self, pago_builder: PagoBuilder, docto_uuid: str) -> None:
        el = pago_builder.construir_elemento()
        drs = _xpath(el, "p:Pago/p:DoctoRelacionado")
        assert len(drs) == 1
        dr = drs[0]
        assert dr.get("IdDocumento") == docto_uuid
        assert dr.get("Serie") == "A"
        assert dr.get("Folio") == "1"
        assert dr.get("ObjetoImpDR") == "02"
        assert dr.get("ImpPagado") == "1160.00"

    def test_genera_impuestos_dr(self, pago_builder: PagoBuilder) -> None:
        el = pago_builder.construir_elemento()
        traslados = _xpath(el, "p:Pago/p:DoctoRelacionado/p:ImpuestosDR/p:TrasladosDR/p:TrasladoDR")
        assert len(traslados) == 1
        t = traslados[0]
        assert t.get("BaseDR") == "1000.00"
        assert t.get("ImpuestoDR") == "002"
        assert t.get("TasaOCuotaDR") == "0.160000"
        assert t.get("ImporteDR") == "160.00"

    def test_genera_impuestos_p(self, pago_builder: PagoBuilder) -> None:
        el = pago_builder.construir_elemento()
        traslados = _xpath(el, "p:Pago/p:ImpuestosP/p:TrasladosP/p:TrasladoP")
        assert len(traslados) == 1
        t = traslados[0]
        assert t.get("BaseP") == "1000.00"
        assert t.get("ImpuestoP") == "002"
        assert t.get("TipoFactorP") == "Tasa"
        assert t.get("ImporteP") == "160.00"


class TestPagoBuilderValidaciones:
    def test_sin_pagos_falla(self) -> None:
        with pytest.raises(ValidationError, match="al menos un Pago"):
            PagoBuilder().construir_elemento()

    def test_agregar_no_pago_falla(self) -> None:
        with pytest.raises(ValidationError):
            PagoBuilder().agregar_pago("not a pago")  # type: ignore[arg-type]

    def test_dr_distinta_moneda_sin_equivalencia_falla(self, docto_uuid: str) -> None:
        # Construimos un DR en USD pero el Pago será MXN, sin EquivalenciaDR.
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="USD",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("100"),
            imp_pagado=Decimal("100"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="01",
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("2000"),
            documentos=[dr],
        )
        with pytest.raises(ValidationError, match="equivalencia_dr"):
            PagoBuilder().agregar_pago(pago).construir_elemento()


class TestProtocolCompliance:
    def test_cumple_protocol_complemento(self, pago_builder: PagoBuilder) -> None:
        from contadb_sdk import Complemento

        assert isinstance(pago_builder, Complemento)
        assert PagoBuilder.prefijo_ns == "pago20"
        assert PagoBuilder.uri_ns == PAGOS_NS


class TestMultiplesPagos:
    def test_dos_pagos_se_serializan_en_orden(self, pago_basico: Pago, docto_uuid: str) -> None:
        otro_dr = DoctoRelacionado(
            id_documento="99999999-8888-7777-6666-555555555555",
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("232"),
            imp_pagado=Decimal("232"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[
                TrasladoDR(
                    base=Decimal("200"),
                    impuesto="002",
                    tipo_factor="Tasa",
                    tasa_o_cuota=Decimal("0.16"),
                    importe=Decimal("32"),
                )
            ],
        )
        otro_pago = Pago(
            fecha_pago=datetime(2026, 4, 27),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("232"),
            documentos=[otro_dr],
        )
        builder = PagoBuilder().agregar_pagos([pago_basico, otro_pago])
        el = builder.construir_elemento()
        pagos = _xpath(el, "p:Pago")
        assert len(pagos) == 2

        totales = _xpath(el, "p:Totales")[0]
        # 1160 + 232 = 1392
        assert totales.get("MontoTotalPagos") == "1392.00"
        # IVA 16 base: 1000 + 200 = 1200
        assert totales.get("TotalTrasladosBaseIVA16") == "1200.00"
        # IVA 16 impuesto: 160 + 32 = 192
        assert totales.get("TotalTrasladosImpuestoIVA16") == "192.00"
