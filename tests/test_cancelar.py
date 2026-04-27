"""Tests del flujo de cancelación: client.cancelar + Retry-After + exports."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest
from pytest_httpx import HTTPXMock

from contadb_sdk import (
    APIError,
    CancelacionResult,
    Certificado,
    ContaDBClient,
    MotivoInvalidoError,
    RateLimitError,
    UUIDNoEncontradoError,
    excepcion_para_codigo,
)
from contadb_sdk.client import CANCELAR_PATH, TIMBRAR_PATH
from contadb_sdk.exceptions import ValidationError

BASE = "https://api.contadb.test"
CANCELAR_URL = f"{BASE}{CANCELAR_PATH}"
TIMBRAR_URL = f"{BASE}{TIMBRAR_PATH}"

UUID_OK = "550e8400-e29b-41d4-a716-446655440000"
UUID_SUSTITUTO = "660e8400-e29b-41d4-a716-446655440111"

CANCEL_OK = {
    "success": True,
    "uuid": UUID_OK,
    "aceptada": True,
    "estatus_uuid": "201",
    "mensaje": "Cancelación aceptada",
    "xml_acuse": "<acuse/>",
}


@pytest.fixture
def client() -> ContaDBClient:
    return ContaDBClient(api_token="cdb_TEST", base_url=BASE)


class TestCancelarHappyPath:
    def test_devuelve_cancelacion_result(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        certificate: Certificado,
    ) -> None:
        httpx_mock.add_response(method="POST", url=CANCELAR_URL, json=CANCEL_OK)
        result = client.cancelar(
            uuid_cfdi=UUID_OK,
            motivo="02",
            certificado=certificate,
        )
        assert isinstance(result, CancelacionResult)
        assert result.aceptada is True
        assert result.uuid == UUID_OK
        assert result.estatus_uuid == "201"

    def test_envia_cer_key_y_password(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        certificate: Certificado,
    ) -> None:
        httpx_mock.add_response(method="POST", url=CANCELAR_URL, json=CANCEL_OK)
        client.cancelar(uuid_cfdi=UUID_OK, motivo="03", certificado=certificate)
        req = httpx_mock.get_request()
        assert req is not None
        body = req.read()
        # El payload debe contener cer/key/password en base64.
        assert b'"cer"' in body
        assert b'"key"' in body
        assert b'"password"' in body
        assert b'"motivo":"03"' in body

    def test_motivo_01_envia_folio_sustitucion(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        certificate: Certificado,
    ) -> None:
        httpx_mock.add_response(method="POST", url=CANCELAR_URL, json=CANCEL_OK)
        client.cancelar(
            uuid_cfdi=UUID_OK,
            motivo="01",
            folio_sustitucion=UUID_SUSTITUTO,
            certificado=certificate,
        )
        req = httpx_mock.get_request()
        assert req is not None
        assert UUID_SUSTITUTO.encode() in req.read()

    def test_idempotency_key_se_envia(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        certificate: Certificado,
    ) -> None:
        httpx_mock.add_response(method="POST", url=CANCELAR_URL, json=CANCEL_OK)
        client.cancelar(
            uuid_cfdi=UUID_OK,
            motivo="02",
            certificado=certificate,
            idempotency_key="mi-key-123",
        )
        req = httpx_mock.get_request()
        assert req is not None
        assert req.headers["idempotency-key"] == "mi-key-123"


class TestCancelarValidaciones:
    def test_motivo_invalido_local(self, client: ContaDBClient, certificate: Certificado) -> None:
        with pytest.raises(ValidationError, match="motivo"):
            client.cancelar(
                uuid_cfdi=UUID_OK,
                motivo="99",  # type: ignore[arg-type]
                certificado=certificate,
            )

    def test_motivo_01_sin_folio_sustitucion(
        self, client: ContaDBClient, certificate: Certificado
    ) -> None:
        with pytest.raises(ValidationError, match="folio_sustitucion"):
            client.cancelar(uuid_cfdi=UUID_OK, motivo="01", certificado=certificate)

    def test_motivo_02_con_folio_sustitucion_falla(
        self, client: ContaDBClient, certificate: Certificado
    ) -> None:
        with pytest.raises(ValidationError, match="solo aplica para motivo='01'"):
            client.cancelar(
                uuid_cfdi=UUID_OK,
                motivo="02",
                folio_sustitucion=UUID_SUSTITUTO,
                certificado=certificate,
            )

    def test_uuid_invalido_local(self, client: ContaDBClient, certificate: Certificado) -> None:
        with pytest.raises(ValueError, match="UUID"):
            client.cancelar(
                uuid_cfdi="no-es-uuid",
                motivo="02",
                certificado=certificate,
            )

    def test_certificado_no_es_instancia(self, client: ContaDBClient) -> None:
        with pytest.raises(ValidationError, match="Certificado"):
            client.cancelar(
                uuid_cfdi=UUID_OK,
                motivo="02",
                certificado="no-soy-un-cert",  # type: ignore[arg-type]
            )


class TestCancelarErroresAPI:
    def test_uuid_no_encontrado(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        certificate: Certificado,
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=CANCELAR_URL,
            status_code=404,
            json={
                "success": False,
                "error": "no existe",
                "code": "UUID_NO_ENCONTRADO",
            },
        )
        with pytest.raises(UUIDNoEncontradoError):
            client.cancelar(uuid_cfdi=UUID_OK, motivo="02", certificado=certificate)

    def test_motivo_invalido_remoto(
        self,
        client: ContaDBClient,
        httpx_mock: HTTPXMock,
        certificate: Certificado,
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=CANCELAR_URL,
            status_code=400,
            json={
                "success": False,
                "error": "motivo malo",
                "code": "MOTIVO_INVALIDO",
            },
        )
        with pytest.raises(MotivoInvalidoError):
            client.cancelar(uuid_cfdi=UUID_OK, motivo="02", certificado=certificate)


class TestRetryAfter:
    def test_retry_after_int_segundos(self, client: ContaDBClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=429,
            json={"success": False, "error": "rate", "code": "RATE_LIMIT_EXCEEDED"},
            headers={"Retry-After": "5"},
        )
        with pytest.raises(RateLimitError) as info:
            client.timbrar("<xml/>")
        assert info.value.retry_after == 5

    def test_retry_after_float_string(self, client: ContaDBClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=429,
            json={
                "success": False,
                "error": "rate",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": "2.7",
            },
        )
        with pytest.raises(RateLimitError) as info:
            client.timbrar("<xml/>")
        assert info.value.retry_after == 2

    def test_retry_after_http_date(self, client: ContaDBClient, httpx_mock: HTTPXMock) -> None:
        future = datetime.now(timezone.utc) + timedelta(seconds=120)
        http_date = format_datetime(future, usegmt=True)
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=429,
            json={"success": False, "error": "rate", "code": "RATE_LIMIT_EXCEEDED"},
            headers={"Retry-After": http_date},
        )
        with pytest.raises(RateLimitError) as info:
            client.timbrar("<xml/>")
        assert info.value.retry_after is not None
        assert 100 < info.value.retry_after <= 120

    def test_retry_after_seconds_alias_payload(
        self, client: ContaDBClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=TIMBRAR_URL,
            status_code=429,
            json={
                "success": False,
                "error": "rate",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after_seconds": 15,
            },
        )
        with pytest.raises(RateLimitError) as info:
            client.timbrar("<xml/>")
        assert info.value.retry_after == 15


class TestExportes:
    def test_excepcion_para_codigo_es_publico(self) -> None:
        cls = excepcion_para_codigo("UUID_NO_ENCONTRADO")
        assert cls is UUIDNoEncontradoError

    def test_excepcion_para_codigo_desconocido(self) -> None:
        cls = excepcion_para_codigo("INVENTADO")
        assert cls is APIError


class TestPKCS12:
    def test_cargar_pfx_desde_bytes(self, certificate: Certificado, cert_password: str) -> None:
        from cryptography.hazmat.primitives.serialization import (
            BestAvailableEncryption,
            pkcs12,
        )

        # Empaquetar el cert + key existentes en un PKCS#12 con la misma password.
        pfx_bytes = pkcs12.serialize_key_and_certificates(
            name=b"test",
            key=certificate._private_key,
            cert=certificate._x509,
            cas=None,
            encryption_algorithm=BestAvailableEncryption(cert_password.encode("utf-8")),
        )
        cargado = Certificado.desde_bytes_pfx(pfx_bytes, cert_password)
        assert cargado.no_certificado == certificate.no_certificado
        # firma reproduce el flujo completo
        sello = cargado.firmar("||4.0|test||")
        assert len(base64.b64decode(sello)) > 0
