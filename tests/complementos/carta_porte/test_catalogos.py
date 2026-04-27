"""Tests del subpaquete de catálogos SAT."""

from __future__ import annotations

import pytest

from contadb_sdk.complementos.carta_porte.catalogos import (
    validar_config_autotransporte,
    validar_pais,
    validar_tipo_figura,
    validar_tipo_permiso,
)


class TestValidarPais:
    def test_pais_valido(self) -> None:
        assert validar_pais("MEX") == "MEX"
        assert validar_pais("USA") == "USA"

    def test_pais_invalido(self) -> None:
        with pytest.raises(ValueError, match="País inválido"):
            validar_pais("XYZ")


class TestValidarTipoPermiso:
    def test_tipos_validos(self) -> None:
        assert validar_tipo_permiso("TPAF01") == "TPAF01"
        assert validar_tipo_permiso("TPAF20") == "TPAF20"

    def test_invalido(self) -> None:
        with pytest.raises(ValueError, match="PermSCT"):
            validar_tipo_permiso("FAKE99")


class TestValidarConfigAutotransporte:
    def test_config_valida(self) -> None:
        assert validar_config_autotransporte("T3S2") == "T3S2"
        assert validar_config_autotransporte("VL") == "VL"

    def test_invalida(self) -> None:
        with pytest.raises(ValueError, match="ConfigVehicular"):
            validar_config_autotransporte("FAKEXX")


class TestValidarTipoFigura:
    def test_validos(self) -> None:
        for clave in ("01", "02", "03", "04"):
            assert validar_tipo_figura(clave) == clave

    def test_invalido(self) -> None:
        with pytest.raises(ValueError, match="TipoFigura"):
            validar_tipo_figura("99")
