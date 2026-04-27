"""Tests de los modelos del autotransporte."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import (
    Autotransporte,
    IdentificacionVehicular,
    Remolque,
    Seguros,
)


class TestIdentificacionVehicular:
    def test_basico(self) -> None:
        iv = IdentificacionVehicular(
            config_vehicular="T3S2",
            peso_bruto_vehicular=Decimal("28.5"),
            placa_vm="NLF1234",
            anio_modelo_vm=2022,
        )
        assert iv.config_vehicular == "T3S2"

    def test_config_invalida_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="ConfigVehicular"):
            IdentificacionVehicular(
                config_vehicular="FAKEXX",
                peso_bruto_vehicular=Decimal("10"),
                placa_vm="ABC123",
                anio_modelo_vm=2022,
            )


class TestSeguros:
    def test_solo_resp_civil(self) -> None:
        s = Seguros(asegura_resp_civil="QUALITAS", poliza_resp_civil="POL-1")
        assert s.asegura_med_ambiente is None

    def test_med_ambiente_sin_poliza_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="medio ambiente"):
            Seguros(
                asegura_resp_civil="QUALITAS",
                poliza_resp_civil="POL-1",
                asegura_med_ambiente="GNP",
            )

    def test_carga_completa(self) -> None:
        s = Seguros(
            asegura_resp_civil="QUALITAS",
            poliza_resp_civil="POL-1",
            asegura_carga="GNP",
            poliza_carga="POL-2",
            prima_seguro=Decimal("500"),
        )
        assert s.prima_seguro == Decimal("500")


class TestRemolque:
    def test_basico(self) -> None:
        r = Remolque(sub_tipo_rem="CTR01", placa="REM1234")
        assert r.sub_tipo_rem == "CTR01"

    def test_subtipo_invalido(self) -> None:
        with pytest.raises(PydanticValidationError):
            Remolque(sub_tipo_rem="X1", placa="REM1234")


class TestAutotransporte:
    def test_basico(
        self,
    ) -> None:
        iv = IdentificacionVehicular(
            config_vehicular="T3S2",
            peso_bruto_vehicular=Decimal("28.5"),
            placa_vm="NLF1234",
            anio_modelo_vm=2022,
        )
        seg = Seguros(asegura_resp_civil="QUALITAS", poliza_resp_civil="POL-1")
        a = Autotransporte(
            perm_sct="TPAF01",
            num_permiso_sct="A-12345",
            identificacion_vehicular=iv,
            seguros=seg,
        )
        assert a.perm_sct == "TPAF01"

    def test_perm_sct_invalido(self) -> None:
        iv = IdentificacionVehicular(
            config_vehicular="T3S2",
            peso_bruto_vehicular=Decimal("28.5"),
            placa_vm="NLF1234",
            anio_modelo_vm=2022,
        )
        seg = Seguros(asegura_resp_civil="QUALITAS", poliza_resp_civil="POL-1")
        with pytest.raises(PydanticValidationError, match="PermSCT"):
            Autotransporte(
                perm_sct="FAKE99",
                num_permiso_sct="A-12345",
                identificacion_vehicular=iv,
                seguros=seg,
            )
