"""Tests del modelo Domicilio."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import Domicilio


class TestDomicilio:
    def test_mexico_basico(self) -> None:
        d = Domicilio(estado="NLE", pais="MEX", codigo_postal="64000")
        assert d.pais == "MEX"
        assert d.codigo_postal == "64000"

    def test_codigo_postal_mx_no_5_digitos_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="codigo_postal para pais=MEX"):
            Domicilio(estado="NLE", pais="MEX", codigo_postal="640000")

    def test_codigo_postal_mx_con_letras_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="codigo_postal para pais=MEX"):
            Domicilio(estado="NLE", pais="MEX", codigo_postal="ABCDE")

    def test_pais_invalido_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="País inválido"):
            Domicilio(estado="NLE", pais="XYZ", codigo_postal="64000")

    def test_pais_extranjero_codigo_postal_libre(self) -> None:
        d = Domicilio(estado="CA", pais="USA", codigo_postal="90210")
        assert d.codigo_postal == "90210"

    def test_campos_opcionales_se_omiten(self) -> None:
        d = Domicilio(estado="NLE", pais="MEX", codigo_postal="64000")
        assert d.calle is None
        assert d.numero_exterior is None
        assert d.colonia is None
