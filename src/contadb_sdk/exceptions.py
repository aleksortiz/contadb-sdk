"""Jerarquía de excepciones del SDK.

Todas heredan de :class:`ContaDBError` para captura genérica. Las subclases
permiten manejo granular según el tipo de fallo (autenticación, cuota,
servidor, validación local, etc.).
"""

from __future__ import annotations

from datetime import datetime


class ContaDBError(Exception):
    """Clase base de todas las excepciones del SDK."""


class ConfigurationError(ContaDBError):
    """Configuración inválida del cliente (token vacío, URL inválida, etc.)."""


class BuildError(ContaDBError):
    """Error al construir o firmar el CFDI localmente (antes de enviar)."""


class CertificateError(BuildError):
    """No se pudo cargar el certificado o la llave privada del SAT."""


class ValidationError(BuildError):
    """Datos del CFDI no cumplen las reglas del SAT o del builder."""


class APIError(ContaDBError):
    """Error reportado por el API de ContaDB.

    Atributos:
        code: código de error oficial (ej. ``"SALDO_INSUFICIENTE"``).
        status_code: HTTP status devuelto.
        message: mensaje legible del API.
        payload: respuesta JSON completa (puede contener detalles extras).
    """

    code: str = ""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.status_code = status_code
        self.payload = payload or {}


# --- Auth (401 / 403) -----------------------------------------------------


class AuthError(APIError):
    """Familia de errores de autenticación/autorización."""


class TokenInvalidoError(AuthError):
    code = "TOKEN_INVALIDO"


class TokenRevocadoError(AuthError):
    code = "TOKEN_REVOCADO"


class TokenBloqueadoError(AuthError):
    """Token bloqueado temporalmente por demasiados errores consecutivos."""

    code = "TOKEN_BLOQUEADO"


class CuentaBloqueadaError(AuthError):
    """Cuenta bloqueada permanentemente por exceso de errores acumulados."""

    code = "CUENTA_BLOQUEADA"

    def __init__(
        self,
        message: str,
        *,
        blocked_until: datetime | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.blocked_until = blocked_until


# --- Cliente (4xx) --------------------------------------------------------


class ClientError(APIError):
    """Error en el request del usuario (XML malformado, demasiado grande, etc.)."""


class XMLInvalidoError(ClientError):
    code = "XML_INVALIDO"


class XMLDemasiadoGrandeError(ClientError):
    code = "XML_DEMASIADO_GRANDE"


# --- Cancelación (4xx) ----------------------------------------------------


class CancelacionError(ClientError):
    """Familia de errores específicos del flujo de cancelación."""


class UUIDNoEncontradoError(CancelacionError):
    """El UUID no corresponde a un timbrado realizado por este token/tenant."""

    code = "UUID_NO_ENCONTRADO"


class MotivoInvalidoError(CancelacionError):
    """Motivo de cancelación inválido o falta folio_sustitucion para motivo 01."""

    code = "MOTIVO_INVALIDO"


class CertificadoInvalidoError(CancelacionError):
    """El CSD enviado para cancelación es inválido o la contraseña no coincide."""

    code = "CERTIFICADO_INVALIDO"


# --- Cuota (402 / 429) ----------------------------------------------------


class QuotaError(APIError):
    """Familia de errores de cuota o rate limit."""


class SaldoInsuficienteError(QuotaError):
    code = "SALDO_INSUFICIENTE"


class RateLimitError(QuotaError):
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(
        self,
        message: str,
        *,
        retry_after: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


# --- Servidor (5xx / PAC) -------------------------------------------------


class ServerError(APIError):
    """Familia de errores del servidor o del PAC upstream."""


class PACError(ServerError):
    """El PAC (autoridad certificadora) rechazó o falló al timbrar."""

    code = "PAC_ERROR"


class InternalError(ServerError):
    """Error interno no clasificado del API."""

    code = "INTERNAL_ERROR"


# --- Mapeo código → clase ------------------------------------------------

_CODE_MAP: dict[str, type[APIError]] = {
    TokenInvalidoError.code: TokenInvalidoError,
    TokenRevocadoError.code: TokenRevocadoError,
    TokenBloqueadoError.code: TokenBloqueadoError,
    CuentaBloqueadaError.code: CuentaBloqueadaError,
    XMLInvalidoError.code: XMLInvalidoError,
    XMLDemasiadoGrandeError.code: XMLDemasiadoGrandeError,
    SaldoInsuficienteError.code: SaldoInsuficienteError,
    RateLimitError.code: RateLimitError,
    PACError.code: PACError,
    InternalError.code: InternalError,
    UUIDNoEncontradoError.code: UUIDNoEncontradoError,
    MotivoInvalidoError.code: MotivoInvalidoError,
    CertificadoInvalidoError.code: CertificadoInvalidoError,
}


def excepcion_para_codigo(code: str) -> type[APIError]:
    """Devuelve la clase de excepción más específica para un código de error del API."""
    return _CODE_MAP.get(code, APIError)


__all__ = [
    "APIError",
    "AuthError",
    "BuildError",
    "CancelacionError",
    "CertificadoInvalidoError",
    "CertificateError",
    "ClientError",
    "ConfigurationError",
    "ContaDBError",
    "CuentaBloqueadaError",
    "InternalError",
    "MotivoInvalidoError",
    "PACError",
    "QuotaError",
    "RateLimitError",
    "SaldoInsuficienteError",
    "ServerError",
    "TokenBloqueadoError",
    "TokenInvalidoError",
    "TokenRevocadoError",
    "UUIDNoEncontradoError",
    "ValidationError",
    "XMLDemasiadoGrandeError",
    "XMLInvalidoError",
    "excepcion_para_codigo",
]
