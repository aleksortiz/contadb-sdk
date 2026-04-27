"""Tests de validación de los modelos Pydantic."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from contadb_sdk import Concepto, Emisor, InformacionGlobal, Receptor


class TestEmisor:
    def test_ok_persona_moral(self) -> None:
        e = Emisor(rfc="EKU9003173C9", nombre="EMPRESA SA", regimen_fiscal="601")
        assert e.rfc == "EKU9003173C9"

    def test_ok_persona_fisica(self) -> None:
        Emisor(rfc="VECJ880326XXX", nombre="Juan", regimen_fiscal="612")

    def test_rfc_corto_falla(self) -> None:
        with pytest.raises(ValidationError):
            Emisor(rfc="ABC", nombre="X", regimen_fiscal="601")

    def test_regimen_no_numerico_falla(self) -> None:
        with pytest.raises(ValidationError):
            Emisor(rfc="EKU9003173C9", nombre="X", regimen_fiscal="ABC")


class TestReceptor:
    def test_ok(self) -> None:
        r = Receptor(
            rfc="URE180429TM6",
            nombre="UNIVERSIDAD ROBOTICA",
            uso_cfdi="G03",
            domicilio_fiscal_receptor="65000",
            regimen_fiscal_receptor="601",
        )
        assert r.uso_cfdi == "G03"

    def test_publico_general(self) -> None:
        r = Receptor(
            rfc="XAXX010101000",
            nombre="PUBLICO EN GENERAL",
            uso_cfdi="S01",
            domicilio_fiscal_receptor="64000",
            regimen_fiscal_receptor="616",
        )
        assert r.rfc == "XAXX010101000"

    def test_cp_no_5_digitos(self) -> None:
        with pytest.raises(ValidationError):
            Receptor(
                rfc="URE180429TM6",
                nombre="X",
                uso_cfdi="G03",
                domicilio_fiscal_receptor="123",
                regimen_fiscal_receptor="601",
            )


class TestConcepto:
    def _base_kwargs(self) -> dict[str, object]:
        return {
            "clave_prod_serv": "43232408",
            "clave_unidad": "E48",
            "descripcion": "Servicios",
            "cantidad": Decimal("1"),
            "valor_unitario": Decimal("100.00"),
        }

    def test_ok_minimal(self) -> None:
        c = Concepto(**self._base_kwargs())
        assert c.objeto_imp == "02"

    def test_objeto_imp_01_no_admite_iva(self) -> None:
        with pytest.raises(ValidationError) as exc:
            Concepto(
                **self._base_kwargs(),
                objeto_imp="01",
                tasa_iva=Decimal("0.16"),
            )
        assert "objeto_imp" in str(exc.value).lower()

    def test_objeto_imp_01_no_admite_exento(self) -> None:
        with pytest.raises(ValidationError):
            Concepto(**self._base_kwargs(), objeto_imp="01", iva_exento=True)

    def test_cantidad_cero_falla(self) -> None:
        with pytest.raises(ValidationError):
            Concepto(
                clave_prod_serv="43232408",
                clave_unidad="E48",
                descripcion="X",
                cantidad=Decimal("0"),
                valor_unitario=Decimal("100"),
            )

    def test_tasa_iva_fuera_de_rango(self) -> None:
        with pytest.raises(ValidationError):
            Concepto(
                **self._base_kwargs(),
                tasa_iva=Decimal("1.5"),  # > 1.0
            )


class TestInformacionGlobal:
    def test_ok(self) -> None:
        ig = InformacionGlobal(periodicidad="04", meses="04", año=2026)
        assert ig.meses == "04"

    def test_meses_invalido(self) -> None:
        with pytest.raises(ValidationError):
            InformacionGlobal(periodicidad="04", meses="20", año=2026)
