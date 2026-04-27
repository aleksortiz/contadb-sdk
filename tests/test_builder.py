"""Tests del CFDIBuilder: cálculo de impuestos, estructura XML, firma."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from lxml import etree

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    Concepto,
    Emisor,
    Receptor,
)
from contadb_sdk.exceptions import ValidationError
from contadb_sdk.xml_utils import NS_CFDI

CFDI = f"{{{NS_CFDI}}}"


def parse(xml: bytes | str) -> etree._Element:
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    return etree.fromstring(xml)


class TestEstructuraBasica:
    def test_root_es_comprobante(self, builder: CFDIBuilder) -> None:
        root = parse(builder.construir_xml())
        assert root.tag == f"{CFDI}Comprobante"
        assert root.get("Version") == "4.0"

    def test_atributos_basicos(self, builder: CFDIBuilder) -> None:
        root = parse(builder.construir_xml())
        assert root.get("Serie") == "A"
        assert root.get("Folio") == "1"
        assert root.get("FormaPago") == "03"
        assert root.get("MetodoPago") == "PUE"
        assert root.get("LugarExpedicion") == "64000"
        assert root.get("Exportacion") == "01"
        assert root.get("TipoDeComprobante") == "I"
        assert root.get("Moneda") == "MXN"

    def test_tiene_emisor_y_receptor(self, builder: CFDIBuilder) -> None:
        root = parse(builder.construir_xml())
        assert root.find(f"{CFDI}Emisor") is not None
        assert root.find(f"{CFDI}Receptor") is not None

    def test_emisor_attrs(self, builder: CFDIBuilder) -> None:
        root = parse(builder.construir_xml())
        em = root.find(f"{CFDI}Emisor")
        assert em is not None
        assert em.get("Rfc") == "EKU9003173C9"
        assert em.get("RegimenFiscal") == "601"


class TestCalculos:
    def test_subtotal_y_total_basico(self, builder: CFDIBuilder) -> None:
        root = parse(builder.construir_xml())
        assert root.get("SubTotal") == "1000.00"
        assert root.get("Total") == "1160.00"  # 1000 + 16% IVA

    def test_descuento_se_resta(self, emisor: Emisor, receptor: Receptor) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            serie="A",
            folio="2",
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(
            Concepto(
                clave_prod_serv="43232408",
                clave_unidad="E48",
                descripcion="X",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("1000"),
                descuento=Decimal("100"),
                tasa_iva=Decimal("0.16"),
            )
        )
        root = parse(b.construir_xml())
        assert root.get("Descuento") == "100.00"
        # Base = 900, IVA = 144, Total = 1044
        assert root.get("Total") == "1044.00"

    def test_retenciones_isr_iva(self, emisor: Emisor, receptor: Receptor) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            serie="A",
            folio="3",
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(
            Concepto(
                clave_prod_serv="80111501",
                clave_unidad="E48",
                descripcion="Honorarios profesionales",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("10000"),
                tasa_iva=Decimal("0.16"),
                tasa_retencion_isr=Decimal("0.10"),
                tasa_retencion_iva=Decimal("0.106667"),
            )
        )
        root = parse(b.construir_xml())
        # Sub=10000, IVA trasladado=1600, ISR ret=1000, IVA ret=1066.67
        # Total = 10000 + 1600 - 1000 - 1066.67 = 9533.33
        assert root.get("Total") == "9533.33"
        impuestos = root.find(f"{CFDI}Impuestos")
        assert impuestos is not None
        assert impuestos.get("TotalImpuestosTrasladados") == "1600.00"
        assert impuestos.get("TotalImpuestosRetenidos") == "2066.67"

    def test_iva_exento_no_genera_importe(self, emisor: Emisor, receptor: Receptor) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(
            Concepto(
                clave_prod_serv="01010101",
                clave_unidad="E48",
                descripcion="Producto exento",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("500"),
                iva_exento=True,
            )
        )
        root = parse(b.construir_xml())
        traslado = root.find(f".//{CFDI}Traslado")
        assert traslado is not None
        assert traslado.get("TipoFactor") == "Exento"
        assert traslado.get("Importe") is None
        assert traslado.get("TasaOCuota") is None
        # Total = SubTotal (sin impuestos)
        assert root.get("Total") == "500.00"


class TestFirma:
    def test_construir_y_firmar_inyecta_sello(
        self, builder: CFDIBuilder, certificate: Certificado
    ) -> None:
        xml = builder.construir_y_firmar(certificate)
        root = parse(xml)
        sello = root.get("Sello")
        assert sello and len(sello) > 100
        assert root.get("NoCertificado") == "30001000000400002434"
        assert root.get("Certificado")

    def test_rfc_certificado_no_coincide_con_emisor(
        self, certificate: Certificado, receptor: Receptor
    ) -> None:
        otro = Emisor(rfc="VECJ880326XXX", nombre="OTRO", regimen_fiscal="612")
        b = CFDIBuilder(
            emisor=otro,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(
            Concepto(
                clave_prod_serv="43232408",
                clave_unidad="E48",
                descripcion="X",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("100"),
                tasa_iva=Decimal("0.16"),
            )
        )
        with pytest.raises(ValidationError, match="RFC del certificado"):
            b.construir_y_firmar(certificate)


class TestErroresDeConstruccion:
    def test_sin_conceptos_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
        )
        with pytest.raises(ValidationError, match="al menos un concepto"):
            b.construir_xml()

    def test_lugar_expedicion_invalido(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="lugar_expedicion"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                forma_pago="03",
                lugar_expedicion="123",  # 3 dígitos, no 5
            )

    def test_moneda_distinta_de_mxn_requiere_tipo_cambio(
        self, emisor: Emisor, receptor: Receptor
    ) -> None:
        with pytest.raises(ValidationError, match="tipo_cambio"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                forma_pago="03",
                lugar_expedicion="64000",
                moneda="USD",
            )

    def test_fecha_se_serializa_iso(
        self, emisor: Emisor, receptor: Receptor, concepto_basico: Concepto
    ) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            fecha=datetime(2026, 1, 15, 9, 30, 45),
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(concepto_basico)
        root = parse(b.construir_xml())
        assert root.get("Fecha") == "2026-01-15T09:30:45"
