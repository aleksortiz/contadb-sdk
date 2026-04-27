"""Tests para las funcionalidades agregadas en v1.1.0:

- CfdiRelacionados (modelo + emisión XML + validaciones).
- Validación cruzada InformacionGlobal ↔ receptor genérico.
- Límites SAT (max conceptos, max importe).
- Reintentos automáticos con backoff y respeto de Retry-After.
- Validación de Content-Type en respuestas HTTP.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from lxml import etree
from pydantic import ValidationError as PydanticValidationError
from pytest_httpx import HTTPXMock

from contadb_sdk import (
    RETRY_POLICY_NINGUNO,
    CFDIBuilder,
    CfdiRelacionados,
    Concepto,
    ContaDBClient,
    Emisor,
    InformacionGlobal,
    Receptor,
    RetryPolicy,
    ServerError,
    TimbradoResult,
)
from contadb_sdk.client import TIMBRAR_PATH
from contadb_sdk.exceptions import ValidationError
from contadb_sdk.xml_utils import NS_CFDI

CFDI = f"{{{NS_CFDI}}}"

BASE = "https://api.contadb.test"
TIMBRAR_URL = f"{BASE}{TIMBRAR_PATH}"

UUID_PREVIO_1 = "550e8400-e29b-41d4-a716-446655440000"
UUID_PREVIO_2 = "660e8400-e29b-41d4-a716-446655440111"

SUCCESS_PAYLOAD = {
    "success": True,
    "xml_timbrado": "<x/>",
    "uuid": UUID_PREVIO_1,
    "saldo_restante": 100,
}


def _parse(xml: bytes | str) -> etree._Element:
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    return etree.fromstring(xml)


# --- CfdiRelacionados modelo ---------------------------------------------


class TestCfdiRelacionadosModelo:
    def test_construye_un_uuid(self) -> None:
        rel = CfdiRelacionados(tipo_relacion="04", uuids=[UUID_PREVIO_1])
        assert rel.tipo_relacion == "04"
        assert rel.uuids == [UUID_PREVIO_1]

    def test_normaliza_uuids_a_minusculas(self) -> None:
        rel = CfdiRelacionados(tipo_relacion="04", uuids=[UUID_PREVIO_1.upper()])
        assert rel.uuids == [UUID_PREVIO_1]

    def test_uuids_duplicados_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="duplicados"):
            CfdiRelacionados(tipo_relacion="04", uuids=[UUID_PREVIO_1, UUID_PREVIO_1])

    def test_uuids_vacios_falla(self) -> None:
        with pytest.raises(PydanticValidationError):
            CfdiRelacionados(tipo_relacion="04", uuids=[])

    def test_tipo_relacion_invalido_falla(self) -> None:
        with pytest.raises(PydanticValidationError):
            CfdiRelacionados(tipo_relacion="99", uuids=[UUID_PREVIO_1])  # type: ignore[arg-type]

    def test_uuid_malformado_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="UUID"):
            CfdiRelacionados(tipo_relacion="04", uuids=["no-es-uuid"])


# --- CfdiRelacionados en el builder --------------------------------------


class TestCfdiRelacionadosEnBuilder:
    def test_emite_bloque_xml(
        self, emisor: Emisor, receptor: Receptor, concepto_basico: Concepto
    ) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
            cfdi_relacionados=[
                CfdiRelacionados(tipo_relacion="04", uuids=[UUID_PREVIO_1]),
            ],
        ).agregar_concepto(concepto_basico)
        root = _parse(b.construir_xml())
        bloques = root.findall(f"{CFDI}CfdiRelacionados")
        assert len(bloques) == 1
        assert bloques[0].get("TipoRelacion") == "04"
        hijos = bloques[0].findall(f"{CFDI}CfdiRelacionado")
        assert len(hijos) == 1
        assert hijos[0].get("UUID") == UUID_PREVIO_1

    def test_emite_multiples_bloques(
        self, emisor: Emisor, receptor: Receptor, concepto_basico: Concepto
    ) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
            cfdi_relacionados=[
                CfdiRelacionados(tipo_relacion="04", uuids=[UUID_PREVIO_1]),
                CfdiRelacionados(tipo_relacion="01", uuids=[UUID_PREVIO_2]),
            ],
        ).agregar_concepto(concepto_basico)
        root = _parse(b.construir_xml())
        bloques = root.findall(f"{CFDI}CfdiRelacionados")
        assert len(bloques) == 2
        assert {b.get("TipoRelacion") for b in bloques} == {"04", "01"}

    def test_metodo_fluido_funciona(
        self, emisor: Emisor, receptor: Receptor, concepto_basico: Concepto
    ) -> None:
        b = (
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                forma_pago="03",
                lugar_expedicion="64000",
            )
            .agregar_concepto(concepto_basico)
            .agregar_cfdi_relacionado(tipo_relacion="04", uuids=[UUID_PREVIO_1])
        )
        root = _parse(b.construir_xml())
        bloque = root.find(f"{CFDI}CfdiRelacionados")
        assert bloque is not None
        assert bloque.get("TipoRelacion") == "04"

    def test_orden_xml_relacionados_antes_de_emisor(
        self, emisor: Emisor, receptor: Receptor, concepto_basico: Concepto
    ) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
            cfdi_relacionados=[CfdiRelacionados(tipo_relacion="04", uuids=[UUID_PREVIO_1])],
        ).agregar_concepto(concepto_basico)
        root = _parse(b.construir_xml())
        # En el orden del schema CFDI 4.0 el primer hijo debe ser CfdiRelacionados
        hijos = list(root)
        assert hijos[0].tag == f"{CFDI}CfdiRelacionados"
        # Y Emisor debe ir después
        tags = [h.tag for h in hijos]
        assert tags.index(f"{CFDI}CfdiRelacionados") < tags.index(f"{CFDI}Emisor")


# --- Validación cruzada InformacionGlobal ↔ XAXX ------------------------


class TestInformacionGlobalCruzada:
    def _receptor_publico_general(self) -> Receptor:
        return Receptor(
            rfc="XAXX010101000",
            nombre="PUBLICO EN GENERAL",
            uso_cfdi="S01",
            domicilio_fiscal_receptor="64000",
            regimen_fiscal_receptor="616",
        )

    def test_xaxx_sin_informacion_global_falla(
        self, emisor: Emisor, concepto_basico: Concepto
    ) -> None:
        with pytest.raises(ValidationError, match="informacion_global"):
            CFDIBuilder(
                emisor=emisor,
                receptor=self._receptor_publico_general(),
                forma_pago="03",
                lugar_expedicion="64000",
            )

    def test_informacion_global_con_receptor_no_generico_falla(
        self, emisor: Emisor, receptor: Receptor
    ) -> None:
        with pytest.raises(ValidationError, match="XAXX010101000"):
            CFDIBuilder(
                emisor=emisor,
                receptor=receptor,
                forma_pago="03",
                lugar_expedicion="64000",
                informacion_global=InformacionGlobal(periodicidad="04", meses="04", año=2026),
            )

    def test_xaxx_con_informacion_global_ok(
        self, emisor: Emisor, concepto_basico: Concepto
    ) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=self._receptor_publico_general(),
            forma_pago="03",
            lugar_expedicion="64000",
            informacion_global=InformacionGlobal(periodicidad="04", meses="04", año=2026),
        ).agregar_concepto(concepto_basico)
        b.construir_xml()  # no debe levantar


# --- Límites SAT ---------------------------------------------------------


class TestLimitesSAT:
    def test_max_conceptos(self, emisor: Emisor, receptor: Receptor) -> None:
        from contadb_sdk.models import MAX_CONCEPTOS_POR_CFDI

        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
        )
        for _ in range(MAX_CONCEPTOS_POR_CFDI + 1):
            b.agregar_concepto(
                Concepto(
                    clave_prod_serv="43232408",
                    clave_unidad="E48",
                    descripcion="X",
                    cantidad=Decimal("1"),
                    valor_unitario=Decimal("1"),
                    objeto_imp="01",
                )
            )
        with pytest.raises(ValidationError, match="máximo"):
            b.construir_xml()

    def test_importe_excede_tope_sat(self, emisor: Emisor, receptor: Receptor) -> None:
        b = CFDIBuilder(
            emisor=emisor,
            receptor=receptor,
            forma_pago="03",
            lugar_expedicion="64000",
        ).agregar_concepto(
            Concepto(
                clave_prod_serv="43232408",
                clave_unidad="E48",
                descripcion="X",
                cantidad=Decimal("1"),
                valor_unitario=Decimal("9999999999.99"),
                objeto_imp="01",
            )
        )
        with pytest.raises(ValidationError, match="tope SAT"):
            b.construir_xml()


# --- Reintentos ----------------------------------------------------------


class TestReintentos:
    def test_reintenta_en_500_y_eventualmente_exito(self, httpx_mock: HTTPXMock) -> None:
        # 2 fallos transitorios, después éxito → debe devolver el resultado final.
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, status_code=500, json={})
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, status_code=502, json={})
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        client = ContaDBClient(
            api_token="cdb_x",
            base_url=BASE,
            retry_policy=RetryPolicy(max_intentos=3, backoff_factor=0.0),
        )
        result = client.timbrar("<x/>")
        assert isinstance(result, TimbradoResult)
        assert len(httpx_mock.get_requests()) == 3

    def test_reintenta_en_429_respeta_retry_after(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=429,
            headers={"retry-after": "0"},
            json={"success": False, "code": "RATE_LIMIT_EXCEEDED", "error": "x"},
        )
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        client = ContaDBClient(
            api_token="cdb_x",
            base_url=BASE,
            retry_policy=RetryPolicy(max_intentos=2, backoff_factor=0.0),
        )
        result = client.timbrar("<x/>")
        assert result.uuid == UUID_PREVIO_1

    def test_no_reintenta_en_4xx_no_transitorio(self, httpx_mock: HTTPXMock) -> None:
        # 401 no está en la lista de retry — debe fallar al primer intento.
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=401,
            json={"success": False, "code": "TOKEN_INVALIDO", "error": "x"},
        )
        client = ContaDBClient(
            api_token="cdb_x",
            base_url=BASE,
            retry_policy=RetryPolicy(max_intentos=3, backoff_factor=0.0),
        )
        from contadb_sdk import TokenInvalidoError

        with pytest.raises(TokenInvalidoError):
            client.timbrar("<x/>")
        # Verificar que solo hubo 1 request (no se reintentó)
        assert len(httpx_mock.get_requests()) == 1

    def test_agota_reintentos_y_levanta_ultimo_error(self, httpx_mock: HTTPXMock) -> None:
        # Tres 500 seguidos: agota intentos y lanza ServerError del último.
        for _ in range(3):
            httpx_mock.add_response(
                method="POST",
                url=TIMBRAR_URL,
                status_code=500,
                json={"success": False, "code": "INTERNAL_ERROR", "error": "x"},
            )
        client = ContaDBClient(
            api_token="cdb_x",
            base_url=BASE,
            retry_policy=RetryPolicy(max_intentos=3, backoff_factor=0.0),
        )
        from contadb_sdk import InternalError

        with pytest.raises(InternalError):
            client.timbrar("<x/>")
        assert len(httpx_mock.get_requests()) == 3

    def test_red_caida_se_reintenta(self, httpx_mock: HTTPXMock) -> None:
        # Primer intento: error de red. Segundo: éxito.
        httpx_mock.add_exception(httpx.ConnectError("conexión rechazada"))
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        client = ContaDBClient(
            api_token="cdb_x",
            base_url=BASE,
            retry_policy=RetryPolicy(max_intentos=2, backoff_factor=0.0),
        )
        result = client.timbrar("<x/>")
        assert result.uuid == UUID_PREVIO_1


# --- Content-Type --------------------------------------------------------


class TestContentType:
    def test_html_en_lugar_de_json_levanta_servererror(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=502,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><body>Bad Gateway</body></html>",
        )
        client = ContaDBClient(api_token="cdb_x", base_url=BASE, retry_policy=RETRY_POLICY_NINGUNO)
        with pytest.raises(ServerError, match="Content-Type"):
            client.timbrar("<x/>")
