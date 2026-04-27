"""Cliente HTTP síncrono para los endpoints /api/v1/timbrar y /api/v1/cancelar de ContaDB."""

from __future__ import annotations

import logging
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Any, TypeVar

import httpx
from pydantic import ValidationError as PydanticValidationError

from ._version import __version__
from .exceptions import (
    APIError,
    ConfigurationError,
    CuentaBloqueadaError,
    InternalError,
    RateLimitError,
    ServerError,
    ValidationError,
    excepcion_para_codigo,
)
from .models import (
    CancelacionResult,
    MotivoCancelacion,
    TimbradoResult,
    _formato_uuid,
)
from .signer import Certificado

DEFAULT_BASE_URL = "https://api.contadb.com"
TIMBRAR_PATH = "/api/v1/timbrar"
CANCELAR_PATH = "/api/v1/cancelar"
USER_AGENT = f"contadb-sdk-python/{__version__}"

logger = logging.getLogger("contadb_sdk")

_R = TypeVar("_R", TimbradoResult, CancelacionResult)


@dataclass(frozen=True)
class RetryPolicy:
    """Política de reintentos para requests transitorios.

    El cliente reintenta automáticamente en errores de red (timeouts, DNS,
    conexiones reseteadas) y en respuestas HTTP 429 y 5xx. No reintenta en
    4xx no transitorios (auth, validación, saldo) — esos errores son del
    request del cliente y reintentarlos solo desperdicia tiempo.

    El espaciado entre reintentos es ``backoff_factor * 2^intento`` segundos
    con ``jitter`` aleatorio uniforme en ``[0, backoff_factor)`` y tope
    ``backoff_max``. Si el servidor envía ``Retry-After``, se respeta su valor
    cuando ``respetar_retry_after=True``.

    Reintentar es seguro porque cada request lleva un ``Idempotency-Key``
    único y el servidor cachea la respuesta para esa clave.
    """

    max_intentos: int = 3
    backoff_factor: float = 0.5
    backoff_max: float = 30.0
    estatus_a_reintentar: tuple[int, ...] = (429, 500, 502, 503, 504)
    respetar_retry_after: bool = True


#: Política por defecto cuando el usuario no configura una explícita.
RETRY_POLICY_DEFAULT = RetryPolicy()


@dataclass(frozen=True)
class _DesactivarRetries:
    """Política sentinela equivalente a 'no reintentar nunca'."""

    max_intentos: int = 1
    backoff_factor: float = 0.0
    backoff_max: float = 0.0
    estatus_a_reintentar: tuple[int, ...] = field(default_factory=tuple)
    respetar_retry_after: bool = False


RETRY_POLICY_NINGUNO = _DesactivarRetries()


class ContaDBClient:
    """Cliente síncrono para el API público de ContaDB.

    Args:
        api_token: token de API generado en el panel de ContaDB
            (formato ``cdb_...``).
        base_url: URL base del API. Si es None, usa la env var
            ``CONTADB_BASE_URL`` o el default ``https://api.contadb.com``.
        timeout: timeout en segundos para cada request HTTP.
        transport: transport httpx personalizado (útil para tests).

    Soporta el protocolo de context manager::

        with ContaDBClient(api_token="cdb_xxx") as client:
            result = client.timbrar(xml)
    """

    def __init__(
        self,
        api_token: str,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        retry_policy: RetryPolicy | _DesactivarRetries | None = None,
    ) -> None:
        if not api_token or not api_token.strip():
            raise ConfigurationError("api_token no puede estar vacío")

        resolved_base_url = (
            base_url or os.environ.get("CONTADB_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")

        if not resolved_base_url.startswith(("http://", "https://")):
            raise ConfigurationError(
                f"base_url inválida: {resolved_base_url!r} — debe iniciar con http:// o https://"
            )

        self._api_token = api_token.strip()
        self._base_url = resolved_base_url
        self._retry_policy: RetryPolicy | _DesactivarRetries = (
            retry_policy if retry_policy is not None else RETRY_POLICY_DEFAULT
        )
        self._http = httpx.Client(
            base_url=resolved_base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {self._api_token}",
                "Accept": "application/json",
            },
        )

    # -- Context manager ---------------------------------------------------

    def __enter__(self) -> ContaDBClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        """Cierra el cliente HTTP subyacente."""
        self._http.close()

    # -- Endpoints ---------------------------------------------------------

    def timbrar(
        self,
        xml: str | bytes,
        *,
        idempotency_key: str | None = None,
    ) -> TimbradoResult:
        """Timbra un CFDI 4.0 firmado contra ContaDB.

        Args:
            xml: XML CFDI 4.0 ya firmado por el emisor (con atributo Sello).
                Acepta str o bytes.
            idempotency_key: clave de idempotencia para el request. Si es
                None, se genera un UUID v4 automáticamente. El servidor
                cachea la respuesta para esta clave durante un período
                corto (resiste reintentos).

        Returns:
            TimbradoResult con UUID, XML timbrado, y saldo restante.

        Raises:
            TokenInvalidoError, TokenRevocadoError, TokenBloqueadoError,
                CuentaBloqueadaError: si la autenticación falla.
            XMLInvalidoError, XMLDemasiadoGrandeError: si el XML es inválido
                o excede 1 MiB.
            SaldoInsuficienteError: si la bolsa no tiene timbres disponibles.
            RateLimitError: si se excede el rate limit (10 req/s por token).
            PACError, InternalError: si el PAC o el servidor fallan.
        """
        if isinstance(xml, str):
            payload = {"xml": xml}
        elif isinstance(xml, bytes):
            payload = {"xml": xml.decode("utf-8")}
        else:
            raise TypeError(f"xml debe ser str o bytes, no {type(xml).__name__}")

        headers = {
            "Idempotency-Key": idempotency_key or str(uuid.uuid4()),
        }

        response = self._post(TIMBRAR_PATH, payload, headers)
        return self._parsear_respuesta(response, TimbradoResult)

    def cancelar(
        self,
        *,
        uuid_cfdi: str,
        motivo: MotivoCancelacion,
        certificado: Certificado,
        folio_sustitucion: str | None = None,
        idempotency_key: str | None = None,
    ) -> CancelacionResult:
        """Cancela un CFDI ya timbrado.

        Args:
            uuid_cfdi: UUID del CFDI a cancelar (devuelto por ``timbrar``).
            motivo: motivo de cancelación según catálogo SAT.
                ``"01"`` (sustitución) requiere ``folio_sustitucion``.
                ``"02"``, ``"03"``, ``"04"`` no admiten ``folio_sustitucion``.
            certificado: CSD del emisor — la cancelación requiere firmar la
                solicitud al SAT con la llave privada del emisor.
            folio_sustitucion: UUID del CFDI que sustituye al cancelado
                (obligatorio y solo para ``motivo="01"``).
            idempotency_key: clave de idempotencia (UUID v4 auto-generado si
                es None). Cancelaciones repetidas con la misma clave devuelven
                el resultado cacheado.

        Returns:
            ``CancelacionResult`` con el acuse del SAT.

        Raises:
            UUIDNoEncontradoError: si el UUID no fue timbrado por este token.
            MotivoInvalidoError: si el motivo o folio_sustitucion son inválidos.
            CertificadoInvalidoError: si el PAC rechazó el CSD enviado.
            ValidationError: si los argumentos locales son inconsistentes.
        """
        _formato_uuid(uuid_cfdi)
        if motivo not in ("01", "02", "03", "04"):
            raise ValidationError("motivo debe ser '01', '02', '03' o '04'")
        if motivo == "01":
            if folio_sustitucion is None:
                raise ValidationError("motivo='01' requiere folio_sustitucion")
            _formato_uuid(folio_sustitucion)
        elif folio_sustitucion is not None:
            raise ValidationError("folio_sustitucion solo aplica para motivo='01'")
        if not isinstance(certificado, Certificado):
            raise ValidationError("certificado debe ser una instancia de Certificado")

        cer_b64, key_b64, password = certificado._material_para_cancelacion()

        payload: dict[str, Any] = {
            "uuid": uuid_cfdi,
            "motivo": motivo,
            "cer": cer_b64,
            "key": key_b64,
            "password": password,
        }
        if folio_sustitucion is not None:
            payload["folio_sustitucion"] = folio_sustitucion

        headers = {
            "Idempotency-Key": idempotency_key or str(uuid.uuid4()),
        }
        response = self._post(CANCELAR_PATH, payload, headers)
        return self._parsear_respuesta(response, CancelacionResult)

    # -- Internos ----------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        """POST con reintentos en errores transitorios (429, 5xx, red).

        Cada intento usa la misma ``Idempotency-Key`` (provista por el caller),
        de forma que el servidor pueda deduplicar.
        """
        policy = self._retry_policy
        max_intentos = max(1, policy.max_intentos)
        intento = 0
        while True:
            intento += 1
            logger.debug(
                "POST %s intento=%d/%d",
                path,
                intento,
                max_intentos,
            )
            try:
                response = self._http.post(path, json=payload, headers=headers)
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                # Error de red — siempre reintenta hasta agotar
                if intento >= max_intentos:
                    logger.warning(
                        "POST %s falló por red tras %d intento(s): %s",
                        path,
                        intento,
                        exc,
                    )
                    raise ServerError(
                        f"Error de red al contactar ContaDB: {exc}",
                        status_code=None,
                    ) from exc
                espera = self._calcular_espera(intento, retry_after_servidor=None)
                logger.info(
                    "POST %s error de red (%s) — reintentando en %.2fs",
                    path,
                    exc,
                    espera,
                )
                time.sleep(espera)
                continue

            # Decidir si reintentamos en base al status
            if response.status_code in policy.estatus_a_reintentar and intento < max_intentos:
                retry_after_hdr = response.headers.get("retry-after")
                espera = self._calcular_espera(
                    intento,
                    retry_after_servidor=retry_after_hdr if policy.respetar_retry_after else None,
                )
                logger.info(
                    "POST %s status=%d — reintentando en %.2fs (intento %d/%d)",
                    path,
                    response.status_code,
                    espera,
                    intento,
                    max_intentos,
                )
                time.sleep(espera)
                continue

            logger.debug("POST %s status=%d", path, response.status_code)
            return response

    def _calcular_espera(self, intento: int, *, retry_after_servidor: str | None) -> float:
        """Calcula segundos de espera entre reintentos.

        Si el servidor envió ``Retry-After`` (segundos o HTTP-date), lo respeta;
        si no, aplica backoff exponencial con jitter.
        """
        policy = self._retry_policy
        if retry_after_servidor:
            parsed = _parsear_retry_after(None, retry_after_servidor)
            if parsed is not None:
                return float(min(parsed, policy.backoff_max))
        backoff: float = policy.backoff_factor * (2 ** (intento - 1))
        jitter: float = (
            random.uniform(0, policy.backoff_factor) if policy.backoff_factor > 0 else 0.0
        )
        total: float = backoff + jitter
        if total > policy.backoff_max:
            return policy.backoff_max
        return total

    def _parsear_respuesta(
        self,
        response: httpx.Response,
        modelo_exitoso: type[_R],
    ) -> _R:
        # Validar Content-Type: si el servidor devolvió HTML/texto plano (típico
        # de errores 502 de un balanceador) lanzamos ServerError antes de
        # intentar parsear JSON, con un mensaje útil para el usuario.
        content_type = (response.headers.get("content-type") or "").lower()
        if content_type and "json" not in content_type:
            extracto = response.text[:200] if response.text else ""
            logger.warning(
                "Respuesta con Content-Type=%r (esperado application/json), status=%d",
                content_type,
                response.status_code,
            )
            raise ServerError(
                f"Content-Type inesperado {content_type!r} (HTTP {response.status_code}): "
                f"{extracto!r}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ServerError(
                f"Respuesta no-JSON del servidor (HTTP {response.status_code})",
                status_code=response.status_code,
            ) from exc

        if not isinstance(data, dict):
            raise ServerError(
                "Respuesta JSON malformada del servidor",
                status_code=response.status_code,
                payload={"raw": data},
            )

        if response.is_success and data.get("success") is True:
            try:
                return modelo_exitoso.model_validate(data)
            except PydanticValidationError as exc:
                raise InternalError(
                    f"Respuesta exitosa con formato inesperado: {exc}",
                    status_code=response.status_code,
                    payload=data,
                ) from exc

        code = str(data.get("code") or "").upper()
        message = str(data.get("error") or data.get("message") or response.reason_phrase)
        exc_cls = excepcion_para_codigo(code) if code else APIError

        kwargs: dict[str, Any] = {
            "code": code or None,
            "status_code": response.status_code,
            "payload": data,
        }
        if exc_cls is RateLimitError:
            kwargs["retry_after"] = _parsear_retry_after(
                data.get("retry_after") or data.get("retry_after_seconds"),
                response.headers.get("retry-after"),
            )
        elif exc_cls is CuentaBloqueadaError:
            blocked_until_raw = data.get("blocked_until") or data.get("fecha_desbloqueo")
            kwargs["blocked_until"] = _parsear_datetime(blocked_until_raw)

        raise exc_cls(message, **kwargs)


def _parsear_datetime(value: object) -> datetime | None:
    if value is None or not isinstance(value, str):
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _parsear_retry_after(payload_value: object, header_value: str | None) -> int | None:
    """Resuelve un Retry-After según RFC 7231: int segundos, float, o HTTP-date."""
    candidates: list[object] = []
    if payload_value is not None:
        candidates.append(payload_value)
    if header_value is not None:
        candidates.append(header_value)
    for raw in candidates:
        if isinstance(raw, int) and raw >= 0:
            return raw
        if isinstance(raw, float) and raw >= 0:
            return int(raw)
        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                return max(0, int(float(stripped)))
            except ValueError:
                pass
            try:
                target = parsedate_to_datetime(stripped)
            except (TypeError, ValueError):
                continue
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            delta = (target - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(delta))
    return None


__all__ = [
    "RETRY_POLICY_DEFAULT",
    "RETRY_POLICY_NINGUNO",
    "ContaDBClient",
    "RetryPolicy",
]
