"""Tests de las validaciones cruzadas multi-modelo."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from contadb_sdk import (
    Autotransporte,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Seguros,
    TiposFigura,
    Ubicacion,
    ValidationError,
)
from contadb_sdk.complementos.carta_porte import validadores


class TestValidarUbicaciones:
    def test_ok(self, origen: Ubicacion, destino: Ubicacion) -> None:
        validadores.validar_ubicaciones([origen, destino])

    def test_sin_origen(self, destino: Ubicacion) -> None:
        with pytest.raises(ValidationError, match=r"exactamente una.*Origen"):
            validadores.validar_ubicaciones([destino])

    def test_sin_destino(self, origen: Ubicacion) -> None:
        with pytest.raises(ValidationError, match=r"al menos.*Destino"):
            validadores.validar_ubicaciones([origen])

    def test_dos_origenes_falla(
        self, origen: Ubicacion, destino: Ubicacion, domicilio_mty: Domicilio
    ) -> None:
        otro_origen = Ubicacion(
            tipo_ubicacion="Origen",
            rfc_remitente_destinatario="EKU9003173C9",
            fecha_hora_salida_llegada=datetime(2026, 4, 26, 7, 0, 0),
            domicilio=domicilio_mty,
        )
        with pytest.raises(ValidationError, match="a lo más 1 'Origen'"):
            validadores.validar_ubicaciones([origen, otro_origen, destino])


class TestValidarDistanciaTotal:
    def test_dentro_de_tolerancia(self, origen: Ubicacion, destino: Ubicacion) -> None:
        # destino tiene distancia=940, total=945 → diferencia 5, margen=9.45 → OK
        validadores.validar_distancia_total(Decimal("945"), [origen, destino])

    def test_fuera_de_tolerancia(self, origen: Ubicacion, destino: Ubicacion) -> None:
        with pytest.raises(ValidationError, match="inconsistente"):
            validadores.validar_distancia_total(Decimal("1500"), [origen, destino])


class TestValidarMercancias:
    def test_consistente(self, mercancia_acero: Mercancia) -> None:
        validadores.validar_mercancias([mercancia_acero], Decimal("5000"), 1)

    def test_peso_inconsistente(self, mercancia_acero: Mercancia) -> None:
        with pytest.raises(ValidationError, match="peso_bruto_total"):
            validadores.validar_mercancias([mercancia_acero], Decimal("9999"), 1)

    def test_count_inconsistente(self, mercancia_acero: Mercancia) -> None:
        with pytest.raises(ValidationError, match="num_total_mercancias"):
            validadores.validar_mercancias([mercancia_acero], Decimal("5000"), 5)

    def test_lista_vacia(self) -> None:
        with pytest.raises(ValidationError, match="al menos una Mercancia"):
            validadores.validar_mercancias([], Decimal("0"), 0)


class TestValidarSegurosMaterialPeligroso:
    def test_no_peligroso_sin_seguro_med_ambiente(
        self, mercancia_acero: Mercancia, autotransporte: Autotransporte
    ) -> None:
        # mercancia_acero es no peligrosa; auto sin seguro med ambiente — debe pasar.
        validadores.validar_seguros_material_peligroso([mercancia_acero], autotransporte)

    def test_peligroso_sin_seguro_falla(self) -> None:
        peligroso = Mercancia(
            bienes_transp="11161703",
            descripcion="Materiales corrosivos",
            cantidad=Decimal("1"),
            clave_unidad="KGM",
            peso_en_kg=Decimal("1"),
            material_peligroso="Sí",
            cve_material_peligroso="UN1234",
            embalaje="4G",
            descrip_embalaje="Caja",
        )
        iv = IdentificacionVehicular(
            config_vehicular="T3S2",
            peso_bruto_vehicular=Decimal("10"),
            placa_vm="ABC123",
            anio_modelo_vm=2022,
        )
        seg = Seguros(asegura_resp_civil="QUALITAS", poliza_resp_civil="POL-1")
        auto = Autotransporte(
            perm_sct="TPAF01",
            num_permiso_sct="A-12345-2025",
            identificacion_vehicular=iv,
            seguros=seg,
        )
        with pytest.raises(ValidationError, match="material peligroso"):
            validadores.validar_seguros_material_peligroso([peligroso], auto)


class TestValidarFiguraTransporte:
    def test_con_figura(self, figura_transporte: FiguraTransporte) -> None:
        validadores.validar_figura_transporte(figura_transporte)

    def test_vacia_falla(self) -> None:
        ft = FiguraTransporte()
        with pytest.raises(ValidationError, match="al menos una figura"):
            validadores.validar_figura_transporte(ft)

    def test_multiples_figuras(self, operador: TiposFigura) -> None:
        propietario = TiposFigura(tipo_figura="02", rfc_figura="EKU9003173C9")
        ft = FiguraTransporte()
        ft.agregar_figura(operador)
        ft.agregar_figura(propietario)
        validadores.validar_figura_transporte(ft)
