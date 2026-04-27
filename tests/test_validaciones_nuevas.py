"""Tests para validaciones cruzadas (B1, B2, B3, B4) y normalización D9/D12."""

from __future__ import annotations

from decimal import Decimal

import pytest
from lxml import etree
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import (
    CFDIBuilder,
    Concepto,
    Emisor,
    Receptor,
    TimbradoResult,
)
from contadb_sdk.exceptions import ValidationError
from contadb_sdk.xml_utils import NS_CFDI

CFDI = f"{{{NS_CFDI}}}"


def _parse(xml: bytes) -> etree._Element:
    return etree.fromstring(xml)


class TestB1_BloqueImpuestosExento:
    """Cuando todos los traslados son Exento, el bloque global debe emitirse igual."""

    def test_solo_exento_emite_bloque_global(self, emisor: Emisor, receptor: Receptor) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(
            Concepto(
                clave_prod_serv="01010101",
                clave_unidad="E48",
                descripcion="Exento",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("500"),
                iva_exento=True,
            )
        )
        root = _parse(b.construir_xml())
        impuestos = root.find(f"{CFDI}Impuestos")
        assert impuestos is not None
        # No hay TotalImpuestosTrasladados porque el importe es 0.
        assert impuestos.get("TotalImpuestosTrasladados") is None
        traslado_global = impuestos.find(f"{CFDI}Traslados/{CFDI}Traslado")
        assert traslado_global is not None
        assert traslado_global.get("TipoFactor") == "Exento"
        assert traslado_global.get("Importe") is None


class TestB2_FormaPagoObligatoriaIE:
    def test_falta_forma_pago_en_tipo_I(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="forma_pago"):
            CFDIBuilder(emisor=emisor, receptor=receptor, lugar_expedicion="64000")

    def test_falta_forma_pago_en_tipo_E(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="forma_pago"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                lugar_expedicion="64000",
                tipo_comprobante="E",
            )

    def test_metodo_pago_obligatorio_en_I(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="metodo_pago"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                forma_pago="03",
                lugar_expedicion="64000",
                metodo_pago=None,
            )


class TestB3_TipoCambioConMXN:
    def test_tipo_cambio_con_mxn_falla(self, emisor: Emisor, receptor: Receptor) -> None:
        with pytest.raises(ValidationError, match="tipo_cambio"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                forma_pago="03",
                lugar_expedicion="64000",
                moneda="MXN",
                tipo_cambio=Decimal("1.0"),
            )


class TestB4_RFCGenerico:
    def test_xaxx_requiere_regimen_616(self) -> None:
        with pytest.raises(PydanticValidationError, match="616"):
            Receptor(
                rfc="XAXX010101000",
                nombre="PUBLICO EN GENERAL",
                uso_cfdi="S01",
                domicilio_fiscal_receptor="64000",
                regimen_fiscal_receptor="601",
            )

    def test_xaxx_requiere_uso_S01(self) -> None:
        with pytest.raises(PydanticValidationError, match="S01"):
            Receptor(
                rfc="XAXX010101000",
                nombre="PUBLICO EN GENERAL",
                uso_cfdi="G03",
                domicilio_fiscal_receptor="64000",
                regimen_fiscal_receptor="616",
            )

    def test_xexx_requiere_residencia_y_numregid(self) -> None:
        with pytest.raises(PydanticValidationError, match="residencia_fiscal"):
            Receptor(
                rfc="XEXX010101000",
                nombre="ACME",
                uso_cfdi="S01",
                domicilio_fiscal_receptor="64000",
                regimen_fiscal_receptor="616",
            )

    def test_xexx_completo_es_valido(self) -> None:
        Receptor(
            rfc="XEXX010101000",
            nombre="ACME",
            uso_cfdi="S01",
            domicilio_fiscal_receptor="64000",
            regimen_fiscal_receptor="616",
            residencia_fiscal="USA",
            num_reg_id_trib="123-45-6789",
        )


class TestD1_AtributosVaciosOmitidos:
    def test_construir_xml_sin_cert_omite_atributos_de_firma(self, builder: CFDIBuilder) -> None:
        root = _parse(builder.construir_xml())
        assert root.get("Sello") is None
        assert root.get("NoCertificado") is None
        assert root.get("Certificado") is None


class TestD9_ObjetoImpExoticos:
    def test_objeto_imp_04_con_iva_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="objeto_imp"):
            Concepto(
                clave_prod_serv="43232408",
                clave_unidad="E48",
                descripcion="X",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("100"),
                objeto_imp="04",
                tasa_iva=Decimal("0.16"),
            )

    def test_objeto_imp_05_con_exento_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="objeto_imp"):
            Concepto(
                clave_prod_serv="43232408",
                clave_unidad="E48",
                descripcion="X",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("100"),
                objeto_imp="05",
                iva_exento=True,
            )


class TestD12_UUIDValidacion:
    def test_uuid_valido_se_normaliza_a_minusculas(self) -> None:
        r = TimbradoResult(
            xml_timbrado="<x/>",
            uuid="550E8400-E29B-41D4-A716-446655440000",
            saldo_restante=10,
        )
        assert r.uuid == "550e8400-e29b-41d4-a716-446655440000"

    def test_uuid_invalido_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="UUID"):
            TimbradoResult(
                xml_timbrado="<x/>",
                uuid="no-es-uuid",
                saldo_restante=10,
            )

    def test_uuid_sin_guiones_falla(self) -> None:
        # uuid.UUID acepta hex puro de 32 chars; nuestra normalización lo
        # vuelve canónica con guiones, así que también es válido.
        r = TimbradoResult(
            xml_timbrado="<x/>",
            uuid="550e8400e29b41d4a716446655440000",
            saldo_restante=10,
        )
        assert r.uuid == "550e8400-e29b-41d4-a716-446655440000"
