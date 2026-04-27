"""Fixtures locales para tests de Carta Porte 3.1."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from contadb_sdk import (
    Autotransporte,
    CartaPorteBuilder,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Seguros,
    TiposFigura,
    Ubicacion,
)


@pytest.fixture
def domicilio_mty() -> Domicilio:
    return Domicilio(
        calle="Av. Constitución",
        numero_exterior="100",
        colonia="Centro",
        municipio="019",
        estado="NLE",
        pais="MEX",
        codigo_postal="64000",
    )


@pytest.fixture
def domicilio_cdmx() -> Domicilio:
    return Domicilio(
        calle="Av. Insurgentes Sur",
        numero_exterior="2000",
        colonia="Del Valle",
        municipio="014",
        estado="CMX",
        pais="MEX",
        codigo_postal="03100",
    )


@pytest.fixture
def origen(domicilio_mty: Domicilio) -> Ubicacion:
    return Ubicacion(
        tipo_ubicacion="Origen",
        id_ubicacion="OR000001",
        rfc_remitente_destinatario="EKU9003173C9",
        nombre_remitente_destinatario="ESCUELA KEMPER URGATE",
        fecha_hora_salida_llegada=datetime(2026, 4, 26, 6, 0, 0),
        domicilio=domicilio_mty,
    )


@pytest.fixture
def destino(domicilio_cdmx: Domicilio) -> Ubicacion:
    return Ubicacion(
        tipo_ubicacion="Destino",
        id_ubicacion="DE000001",
        rfc_remitente_destinatario="URE180429TM6",
        nombre_remitente_destinatario="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        fecha_hora_salida_llegada=datetime(2026, 4, 27, 14, 0, 0),
        distancia_recorrida=Decimal("940"),
        domicilio=domicilio_cdmx,
    )


@pytest.fixture
def mercancia_acero() -> Mercancia:
    return Mercancia(
        bienes_transp="11161703",
        descripcion="Varilla corrugada 3/8 grado 42",
        cantidad=Decimal("5000"),
        clave_unidad="KGM",
        peso_en_kg=Decimal("5000"),
        material_peligroso="No",
    )


@pytest.fixture
def autotransporte() -> Autotransporte:
    iv = IdentificacionVehicular(
        config_vehicular="T3S2",
        peso_bruto_vehicular=Decimal("28.5"),
        placa_vm="NLF1234",
        anio_modelo_vm=2022,
    )
    seg = Seguros(
        asegura_resp_civil="QUALITAS",
        poliza_resp_civil="POL-RC-998877",
    )
    return Autotransporte(
        perm_sct="TPAF01",
        num_permiso_sct="A-12345-2025",
        identificacion_vehicular=iv,
        seguros=seg,
    )


@pytest.fixture
def operador() -> TiposFigura:
    return TiposFigura(
        tipo_figura="01",
        rfc_figura="VECJ880326XXX",
        num_licencia="A1234567",
        nombre_figura="JUAN VELASCO",
    )


@pytest.fixture
def figura_transporte(operador: TiposFigura) -> FiguraTransporte:
    ft = FiguraTransporte()
    ft.agregar_figura(operador)
    return ft


@pytest.fixture
def carta_porte_builder(
    origen: Ubicacion,
    destino: Ubicacion,
    mercancia_acero: Mercancia,
    autotransporte: Autotransporte,
    figura_transporte: FiguraTransporte,
) -> CartaPorteBuilder:
    cp = CartaPorteBuilder(transp_internac="No", total_dist_rec=Decimal("940"))
    cp.agregar_ubicacion(origen)
    cp.agregar_ubicacion(destino)
    cp.agregar_mercancia(mercancia_acero)
    cp.establecer_autotransporte(autotransporte)
    cp.agregar_figura_transporte(figura_transporte)
    return cp
