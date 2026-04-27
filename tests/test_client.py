"""Tests del ContaDBClient (HTTP) — usa pytest-httpx para mockear httpx."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from contadb_sdk import (
    ConfigurationError,
    ContaDBClient,
    PACError,
    RateLimitError,
    SaldoInsuficienteError,
    ServerError,
    TimbradoResult,
    TokenInvalidoError,
    TokenRevocadoError,
    XMLDemasiadoGrandeError,
    XMLInvalidoError,
)
from contadb_sdk.client import TIMBRAR_PATH
from contadb_sdk.exceptions import APIError, CuentaBloqueadaError, InternalError

BASE = "https://api.contadb.test"
TIMBRAR_URL = f"{BASE}{TIMBRAR_PATH}"

SUCCESS_PAYLOAD = {
    "success": True,
    "xml_timbrado": "<cfdi:Comprobante>...</cfdi:Comprobante>",
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "saldo_restante": 999,
    "fecha_vencimiento": "2027-04-26T00:00:00Z",
}


@pytest.fixture
def client() -> ContaDBClient:
    return ContaDBClient(api_token="cdb_TEST", base_url=BASE)


class TestConfiguracion:
    def test_token_vacio_falla(self) -> None:
        with pytest.raises(ConfigurationError):
            ContaDBClient(api_token="")

    def test_token_solo_espacios_falla(self) -> None:
        with pytest.raises(ConfigurationError):
            ContaDBClient(api_token="   ")

    def test_base_url_invalida_falla(self) -> None:
        with pytest.raises(ConfigurationError, match="http"):
            ContaDBClient(api_token="cdb_x", base_url="ftp://x.com")

    def test_base_url_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CONTADB_BASE_URL", raising=False)
        c = ContaDBClient(api_token="cdb_x")
        assert c._base_url == "https://api.contadb.com"

    def test_base_url_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONTADB_BASE_URL", "https://staging.contadb.com")
        c = ContaDBClient(api_token="cdb_x")
        assert c._base_url == "https://staging.contadb.com"


class TestTimbrarExito:
    def test_devuelve_timbrado_result(self, client: ContaDBClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        result = client.timbrar("<xml/>")
        assert isinstance(result, TimbradoResult)
        assert result.uuid == "550e8400-e29b-41d4-a716-446655440000"
        assert result.saldo_restante == 999
        assert result.fecha_vencimiento is not None

    def test_envia_authorization_header(self, client: ContaDBClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        client.timbrar("<xml/>")
        req = httpx_mock.get_request()
        assert req is not None
        assert req.headers["authorization"] == "Bearer cdb_TEST"
        assert req.headers["user-agent"].startswith("contadb-sdk-python/")

    def test_genera_idempotency_key_automatico(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        client.timbrar("<xml/>")
        req = httpx_mock.get_request()
        assert req is not None
        assert "idempotency-key" in req.headers
        assert len(req.headers["idempotency-key"]) == 36  # UUID v4

    def test_idempotency_key_custom_se_respeta(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        client.timbrar("<xml/>", idempotency_key="my-key-123")
        req = httpx_mock.get_request()
        assert req is not None
        assert req.headers["idempotency-key"] == "my-key-123"

    def test_acepta_xml_bytes(self, client: ContaDBClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        result = client.timbrar(b"<xml/>")
        assert result.uuid


class TestErrores:
    @pytest.mark.parametrize(
        ("code", "status", "exc_cls"),
        [
            ("TOKEN_INVALIDO", 401, TokenInvalidoError),
            ("TOKEN_REVOCADO", 401, TokenRevocadoError),
            ("XML_INVALIDO", 400, XMLInvalidoError),
            ("XML_DEMASIADO_GRANDE", 413, XMLDemasiadoGrandeError),
            ("SALDO_INSUFICIENTE", 402, SaldoInsuficienteError),
            ("PAC_ERROR", 502, PACError),
            ("INTERNAL_ERROR", 500, InternalError),
        ],
    )
    def test_codigo_mapea_a_excepcion(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        code: str,
        status: int,
        exc_cls: type[APIError],
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=status,
            json={"success": False, "error": "boom", "code": code},
        )
        with pytest.raises(exc_cls) as info:
            client.timbrar("<xml/>")
        assert info.value.code == code
        assert info.value.status_code == status
        assert info.value.message == "boom"

    def test_rate_limit_extrae_retry_after(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=429,
            json={
                "success": False,
                "error": "rate exceeded",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": 3,
            },
        )
        with pytest.raises(RateLimitError) as info:
            client.timbrar("<xml/>")
        assert info.value.retry_after == 3

    def test_cuenta_bloqueada_extrae_blocked_until(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=403,
            json={
                "success": False,
                "error": "blocked",
                "code": "CUENTA_BLOQUEADA",
                "blocked_until": "2026-07-25T00:00:00Z",
            },
        )
        with pytest.raises(CuentaBloqueadaError) as info:
            client.timbrar("<xml/>")
        assert info.value.blocked_until is not None
        assert info.value.blocked_until.year == 2026

    def test_codigo_desconocido_lanza_apierror(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=400,
            json={"success": False, "error": "weird", "code": "UNKNOWN_FUTURE_CODE"},
        )
        with pytest.raises(APIError) as info:
            client.timbrar("<xml/>")
        assert info.value.code == "UNKNOWN_FUTURE_CODE"

    def test_respuesta_no_json_lanza_servererror(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST", url=TIMBRAR_URL, status_code=500, content=b"not json"
        )
        with pytest.raises(ServerError):
            client.timbrar("<xml/>")


class TestContextManager:
    def test_close_se_invoca(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(method="POST", url=TIMBRAR_URL, json=SUCCESS_PAYLOAD)
        with ContaDBClient(api_token="cdb_X", base_url=BASE) as client:
            client.timbrar("<xml/>")
        assert client._http.is_closed
