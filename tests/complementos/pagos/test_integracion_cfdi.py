"""Tests end-to-end: CFDI tipo 'P' completo con complemento de pagos.

Verifica:
    1. ``CFDIBuilder.para_pago()`` aplica los defaults SAT.
    2. El XML resultante contiene ``<cfdi:Complemento><pago20:Pagos>``.
    3. La cadena original procesa el complemento (XSLT del SAT).
    4. La firma se aplica correctamente.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from lxml import etree

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    Emisor,
    PagoBuilder,
    Receptor,
    ValidationError,
)
from contadb_sdk.cadena import cadena_original
from contadb_sdk.complementos.pagos.tipos import (
    CLAVE_PROD_SERV_PAGO,
    PAGOS_NS,
)
from contadb_sdk.xml_utils import NS_CFDI


class TestParaPagoFactory:
    def test_factory_aplica_defaults(self, emisor: Emisor, receptor: Receptor) -> None:
        builder = CFDIBuilder.para_pago(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion="64000",
            serie="P",
            folio="1",
        )
        xml_bytes = builder.construir_xml()  # construir_xml falla porque agregar_pago vacío
        # Pero construir_xml solo valida estructuralmente — debe pasar con el concepto placeholder.
        root = etree.fromstring(xml_bytes)
        assert root.get("TipoDeComprobante") == "P"
        assert root.get("Moneda") == "XXX"
        assert root.get("FormaPago") is None
        assert root.get("MetodoPago") is None
        assert root.get("Total") == "0.00"
        assert root.get("SubTotal") == "0.00"

    def test_factory_inyecta_concepto_placeholder(self, emisor: Emisor, receptor: Receptor) -> None:
        builder = CFDIBuilder.para_pago(emisor=emisor, receptor=receptor, lugar_expedicion="64000")
        xml_bytes = builder.construir_xml()
        root = etree.fromstring(xml_bytes)
        conceptos = root.xpath("//c:Concepto", namespaces={"c": NS_CFDI})
        assert len(conceptos) == 1
        c = conceptos[0]
        assert c.get("ClaveProdServ") == CLAVE_PROD_SERV_PAGO
        assert c.get("ValorUnitario") == "0.00"
        assert c.get("ObjetoImp") == "01"


class TestValidacionTipoP:
    def test_tipo_p_con_moneda_mxn_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="moneda='XXX'"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                tipo_comprobante="P",
                moneda="MXN",
                metodo_pago=None,
            )

    def test_tipo_p_con_metodo_pago_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="metodo_pago"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                tipo_comprobante="P",
                moneda="XXX",
                metodo_pago="PUE",
            )

    def test_tipo_p_con_forma_pago_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="forma_pago"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                tipo_comprobante="P",
                moneda="XXX",
                metodo_pago=None,
                forma_pago="03",
            )


class TestCFDIPagoIntegracion:
    def test_xml_incluye_complemento_pagos(
        self,
        emisor: Emisor,
        receptor: Receptor,
        pago_builder: PagoBuilder,
    ) -> None:
        cfdi_builder = CFDIBuilder.para_pago(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion="64000",
            serie="P",
            folio="1",
            fecha=datetime(2026, 4, 26, 12, 0, 0),
        ).agregar_complemento(pago_builder)

        xml_bytes = cfdi_builder.construir_xml()
        root = etree.fromstring(xml_bytes)

        # cfdi:Complemento → pago20:Pagos
        complementos = root.xpath(
            "c:Complemento/p:Pagos",
            namespaces={"c": NS_CFDI, "p": PAGOS_NS},
        )
        assert len(complementos) == 1
        assert complementos[0].get("Version") == "2.0"

    def test_schema_location_incluye_pagos(
        self,
        emisor: Emisor,
        receptor: Receptor,
        pago_builder: PagoBuilder,
    ) -> None:
        cfdi_builder = CFDIBuilder.para_pago(
            emisor=emisor, receptor=receptor, lugar_expedicion="64000"
        ).agregar_complemento(pago_builder)
        xml_bytes = cfdi_builder.construir_xml()
        root = etree.fromstring(xml_bytes)
        schema_loc = root.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
        assert schema_loc is not None
        assert "Pagos20.xsd" in schema_loc
        assert "cfdv40.xsd" in schema_loc

    def test_cadena_original_procesa_complemento(
        self,
        emisor: Emisor,
        receptor: Receptor,
        pago_builder: PagoBuilder,
    ) -> None:
        cfdi_builder = CFDIBuilder.para_pago(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion="64000",
            serie="P",
            folio="1",
            fecha=datetime(2026, 4, 26, 12, 0, 0),
        ).agregar_complemento(pago_builder)

        xml_bytes = cfdi_builder.construir_xml()
        cadena = cadena_original(xml_bytes)
        assert cadena.startswith("||4.0|")
        assert cadena.endswith("||")
        # Datos del comprobante base.
        assert "EKU9003173C9" in cadena
        assert "URE180429TM6" in cadena
        # Datos del complemento de Pagos (Version + Totales + Pago + DR + impuestos).
        assert "|2.0|" in cadena  # Version del complemento
        assert "1160.00" in cadena  # Monto del pago
        assert "11111111-2222-3333-4444-555555555555" in cadena  # IdDocumento
        assert "0.160000" in cadena  # Tasa IVA
        assert "160.00" in cadena  # Importe traslado

    def test_construir_y_firmar_cfdi_pago(
        self,
        emisor: Emisor,
        receptor: Receptor,
        pago_builder: PagoBuilder,
        certificate: Certificado,
    ) -> None:
        xml = (
            CFDIBuilder.para_pago(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                serie="P",
                folio="1",
                fecha=datetime(2026, 4, 26, 12, 0, 0),
            )
            .agregar_complemento(pago_builder)
            .construir_y_firmar(certificate)
        )
        root = etree.fromstring(xml.encode("utf-8"))
        assert root.get("Sello")
        assert root.get("Certificado")
        assert root.get("NoCertificado")
        assert root.get("TipoDeComprobante") == "P"


class TestComplementoNoP:
    """Un complemento se puede agregar también a un CFDI tipo 'I' (Ingreso),
    aunque para Pagos 2.0 normalmente no aplica — el integration smoke test
    aquí solo confirma que el mecanismo es genérico."""

    def test_cfdi_ingreso_acepta_complemento(
        self,
        builder: CFDIBuilder,
        pago_builder: PagoBuilder,
    ) -> None:
        # No es semánticamente válido en SAT (tipo I no debería tener Pagos),
        # pero el SDK no debe bloquear el mecanismo genérico de plug-in.
        builder.agregar_complemento(pago_builder)
        xml_bytes = builder.construir_xml()
        root = etree.fromstring(xml_bytes)
        complementos = root.xpath(
            "c:Complemento/p:Pagos",
            namespaces={"c": NS_CFDI, "p": PAGOS_NS},
        )
        assert len(complementos) == 1
