"""Tests de FiguraTransporte y TiposFigura."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import Domicilio, FiguraTransporte, TiposFigura


class TestTiposFigura:
    def test_operador_basico(self) -> None:
        f = TiposFigura(
            tipo_figura="01",
            rfc_figura="VECJ880326XXX",
            num_licencia="A1234567",
            nombre_figura="JUAN VELASCO",
        )
        assert f.tipo_figura == "01"

    def test_operador_sin_licencia_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="num_licencia"):
            TiposFigura(tipo_figura="01", rfc_figura="VECJ880326XXX")

    def test_operador_con_domicilio_falla(self) -> None:
        dom = Domicilio(estado="NLE", pais="MEX", codigo_postal="64000")
        with pytest.raises(PydanticValidationError, match="no admite domicilio"):
            TiposFigura(
                tipo_figura="01",
                rfc_figura="VECJ880326XXX",
                num_licencia="A1234567",
                domicilio=dom,
            )

    def test_propietario_con_domicilio_ok(self) -> None:
        dom = Domicilio(estado="NLE", pais="MEX", codigo_postal="64000")
        f = TiposFigura(tipo_figura="02", rfc_figura="EKU9003173C9", domicilio=dom)
        assert f.domicilio is not None

    def test_tipo_invalido_no_pasa_pydantic(self) -> None:
        with pytest.raises(PydanticValidationError):
            TiposFigura(tipo_figura="99", rfc_figura="EKU9003173C9")  # type: ignore[arg-type]


class TestFiguraTransporte:
    def test_agregar_figura(self, operador: TiposFigura) -> None:
        ft = FiguraTransporte()
        ft.agregar_figura(operador)
        assert len(ft.figuras) == 1

    def test_agregar_no_figura_falla(self) -> None:
        ft = FiguraTransporte()
        with pytest.raises(TypeError):
            ft.agregar_figura("not a figura")  # type: ignore[arg-type]
