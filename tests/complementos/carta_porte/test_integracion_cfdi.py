"""Tests end-to-end: CFDI tipo 'T' completo con complemento de Carta Porte."""

from __future__ import annotations

from datetime import datetime

import pytest
from lxml import etree

from contadb_sdk import (
    CartaPorteBuilder,
    Certificado,
    CFDIBuilder,
    Emisor,
    Receptor,
    ValidationError,
)
from contadb_sdk.cadena import cadena_original
from contadb_sdk.complementos.carta_porte.tipos import CARTA_PORTE_NS, CLAVE_PROD_SERV_TRASLADO
from contadb_sdk.xml_utils import NS_CFDI


class TestParaTrasladoFactory:
    def test_factory_aplica_defaults(self, emisor: Emisor, receptor: Receptor) -> None:
        cfdi = CFDIBuilder.para_traslado(emisor=emisor, receptor=receptor, lugar_expedicion="64000")
        xml_bytes = cfdi.construir_xml()
        root = etree.fromstring(xml_bytes)
        assert root.get("TipoDeComprobante") == "T"
        assert root.get("Moneda") == "XXX"
        assert root.get("FormaPago") is None
        assert root.get("MetodoPago") is None
        assert root.get("Total") == "0.00"
        assert root.get("SubTotal") == "0.00"

    def test_factory_inyecta_concepto_placeholder(self, emisor: Emisor, receptor: Receptor) -> None:
        cfdi = CFDIBuilder.para_traslado(emisor=emisor, receptor=receptor, lugar_expedicion="64000")
        xml_bytes = cfdi.construir_xml()
        root = etree.fromstring(xml_bytes)
        conceptos = root.xpath("//c:Concepto", namespaces={"c": NS_CFDI})
        assert len(conceptos) == 1
        assert conceptos[0].get("ClaveProdServ") == CLAVE_PROD_SERV_TRASLADO
        assert conceptos[0].get("ValorUnitario") == "0.00"


class TestValidacionTipoT:
    def test_tipo_t_con_moneda_mxn_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="moneda='XXX'"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                tipo_comprobante="T",
                moneda="MXN",
                metodo_pago=None,
            )

    def test_tipo_t_con_metodo_pago_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="metodo_pago"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                tipo_comprobante="T",
                moneda="XXX",
                metodo_pago="PUE",
            )


class TestCFDITrasladoIntegracion:
    def test_xml_incluye_complemento_carta_porte(
        self,
        emisor: Emisor,
        receptor: Receptor,
        carta_porte_builder: CartaPorteBuilder,
    ) -> None:
        cfdi = CFDIBuilder.para_traslado(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion="64000",
            serie="T",
            folio="2026-001",
            fecha=datetime(2026, 4, 26, 12, 0, 0),
        )
        cfdi.agregar_complemento(carta_porte_builder)
        xml_bytes = cfdi.construir_xml()
        root = etree.fromstring(xml_bytes)
        complementos = root.xpath(
            "c:Complemento/cp:CartaPorte",
            namespaces={"c": NS_CFDI, "cp": CARTA_PORTE_NS},
        )
        assert len(complementos) == 1
        assert complementos[0].get("Version") == "3.1"

    def test_schema_location_incluye_carta_porte(
        self,
        emisor: Emisor,
        receptor: Receptor,
        carta_porte_builder: CartaPorteBuilder,
    ) -> None:
        cfdi = CFDIBuilder.para_traslado(emisor=emisor, receptor=receptor, lugar_expedicion="64000")
        cfdi.agregar_complemento(carta_porte_builder)
        xml_bytes = cfdi.construir_xml()
        root = etree.fromstring(xml_bytes)
        schema_loc = root.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
        assert schema_loc is not None
        assert "CartaPorte31.xsd" in schema_loc

    def test_cadena_original_incluye_datos_carta_porte(
        self,
        emisor: Emisor,
        receptor: Receptor,
        carta_porte_builder: CartaPorteBuilder,
    ) -> None:
        cfdi = CFDIBuilder.para_traslado(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion="64000",
            serie="T",
            folio="2026-001",
            fecha=datetime(2026, 4, 26, 12, 0, 0),
        )
        cfdi.agregar_complemento(carta_porte_builder)
        xml_bytes = cfdi.construir_xml()
        cadena = cadena_original(xml_bytes)
        assert cadena.startswith("||4.0|")
        assert cadena.endswith("||")
        # Datos del complemento deben aparecer en la cadena
        assert "3.1" in cadena  # version del complemento
        assert "T3S2" in cadena  # ConfigVehicular
        assert "TPAF01" in cadena  # PermSCT
        assert "NLF1234" in cadena  # Placa

    def test_construir_y_firmar_cfdi_traslado(
        self,
        emisor: Emisor,
        receptor: Receptor,
        carta_porte_builder: CartaPorteBuilder,
        certificate: Certificado,
    ) -> None:
        cfdi = CFDIBuilder.para_traslado(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion="64000",
            serie="T",
            folio="2026-001",
            fecha=datetime(2026, 4, 26, 12, 0, 0),
        )
        cfdi.agregar_complemento(carta_porte_builder)
        xml = cfdi.construir_y_firmar(certificate)
        root = etree.fromstring(xml.encode("utf-8"))
        assert root.get("Sello")
        assert root.get("TipoDeComprobante") == "T"
