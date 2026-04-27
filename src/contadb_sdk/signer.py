"""Carga del Certificado de Sello Digital (CSD) del SAT y firma RSA-SHA256.

Los CSD del SAT vienen en dos archivos:

- ``.cer``: certificado X.509 en formato DER (binario).
- ``.key``: llave privada RSA en PKCS#8 cifrada con la contraseña del CSD.

Algunos proveedores también entregan el CSD como un único archivo PKCS#12
(``.pfx``/``.p12``); :meth:`Certificado.cargar_pfx` lo soporta.

Este módulo abstrae la carga de ambos archivos y la firma de la cadena
original del CFDI con RSA + PKCS#1 v1.5 + SHA-256, que es lo que el SAT
exige para el atributo ``Sello`` del comprobante.
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12

from .exceptions import CertificateError

PathLike = str | Path


class Certificado:
    """Certificado de Sello Digital del SAT con su llave privada cargada.

    Use :meth:`cargar` o :meth:`cargar_pfx` para construir desde archivos en disco.
    """

    def __init__(
        self,
        cer_der: bytes,
        private_key: rsa.RSAPrivateKey,
        x509_cert: x509.Certificate,
        *,
        key_der_encrypted: bytes,
        key_password: str,
    ) -> None:
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise CertificateError("La llave privada debe ser RSA")
        self._cer_der = cer_der
        self._private_key = private_key
        self._x509 = x509_cert
        self._key_der_encrypted = key_der_encrypted
        self._key_password = key_password

    # -- Construcción ------------------------------------------------------

    @classmethod
    def cargar(
        cls,
        cer_path: PathLike,
        key_path: PathLike,
        password: str,
    ) -> Certificado:
        """Carga un par .cer + .key desde disco.

        Args:
            cer_path: ruta al archivo ``.cer`` (DER o PEM).
            key_path: ruta al archivo ``.key`` (PKCS#8 cifrado del SAT).
            password: contraseña de la llave privada (la del CSD).

        Raises:
            CertificateError: si los archivos no existen o no son válidos,
                o si la contraseña es incorrecta.
        """
        cer_bytes = Path(cer_path).read_bytes()
        key_bytes = Path(key_path).read_bytes()
        return cls.desde_bytes(cer_bytes, key_bytes, password)

    @classmethod
    def desde_bytes(cls, cer: bytes, key: bytes, password: str) -> Certificado:
        """Construye desde los bytes del .cer y .key (sin tocar disco)."""
        cer_der, x509_cert = _parsear_certificado(cer)
        private_key = _parsear_llave_privada(key, password)
        key_der_encrypted = _serializar_llave_pkcs8(private_key, password)
        cert = cls(
            cer_der,
            private_key,
            x509_cert,
            key_der_encrypted=key_der_encrypted,
            key_password=password,
        )
        cert._verificar_par_de_llaves()
        return cert

    @classmethod
    def cargar_pfx(cls, pfx_path: PathLike, password: str) -> Certificado:
        """Carga un CSD empaquetado como PKCS#12 (``.pfx`` / ``.p12``).

        Args:
            pfx_path: ruta al archivo PKCS#12.
            password: contraseña del PKCS#12 (también se usa para re-cifrar
                la llave privada internamente, manteniendo simetría con el
                flujo de ``.cer + .key``).
        """
        return cls.desde_bytes_pfx(Path(pfx_path).read_bytes(), password)

    @classmethod
    def desde_bytes_pfx(cls, pfx: bytes, password: str) -> Certificado:
        """Construye desde los bytes de un archivo PKCS#12."""
        try:
            private_key, x509_cert, _additional = pkcs12.load_key_and_certificates(
                pfx, password.encode("utf-8") if password else None
            )
        except ValueError as exc:
            raise CertificateError(
                "No se pudo cargar el PKCS#12 — contraseña inválida o archivo corrupto"
            ) from exc
        if private_key is None or x509_cert is None:
            raise CertificateError("El PKCS#12 no contiene certificado o llave privada")
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise CertificateError("La llave privada del PKCS#12 debe ser RSA")
        cer_der = x509_cert.public_bytes(serialization.Encoding.DER)
        key_der_encrypted = _serializar_llave_pkcs8(private_key, password)
        cert = cls(
            cer_der,
            private_key,
            x509_cert,
            key_der_encrypted=key_der_encrypted,
            key_password=password,
        )
        cert._verificar_par_de_llaves()
        return cert

    # -- Atributos derivados ----------------------------------------------

    @property
    def certificado_b64(self) -> str:
        """Base64 del .cer en DER, listo para el atributo ``Certificado`` del CFDI."""
        return base64.b64encode(self._cer_der).decode("ascii")

    @property
    def no_certificado(self) -> str:
        """Número de certificado (NoCertificado) — 20 dígitos del SerialNumber.

        El SAT codifica el SerialNumber del X.509 como bytes ASCII de los
        20 dígitos. Lo decodificamos a string.
        """
        sn_int = self._x509.serial_number
        hex_str = format(sn_int, "x")
        if len(hex_str) % 2:
            hex_str = "0" + hex_str
        try:
            ascii_serial = bytes.fromhex(hex_str).decode("ascii")
        except (UnicodeDecodeError, ValueError):
            return str(sn_int)
        if ascii_serial.isdigit() and len(ascii_serial) == 20:
            return ascii_serial
        return str(sn_int)

    @property
    def rfc(self) -> str | None:
        """RFC asociado al certificado (extraído del subject), o None si no se encuentra."""
        for attr in self._x509.subject:
            if attr.oid.dotted_string == "2.5.4.45":
                value = str(attr.value).strip()
                return value.split("/", 1)[0].strip()
        return None

    # -- Firma -------------------------------------------------------------

    def firmar(self, cadena_original: str) -> str:
        """Firma la cadena original y devuelve el sello en base64.

        El SAT exige RSA-SHA256 con padding PKCS#1 v1.5 sobre los bytes UTF-8
        de la cadena original.
        """
        signature = self._private_key.sign(
            cadena_original.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("ascii")

    # -- Internos ----------------------------------------------------------

    def _material_para_cancelacion(self) -> tuple[str, str, str]:
        """Devuelve (cer_b64, key_b64, password) para el endpoint /cancelar.

        Uso interno del cliente HTTP — el material se manda al PAC que firma
        la solicitud de cancelación al SAT en nombre del emisor.
        """
        cer_b64 = base64.b64encode(self._cer_der).decode("ascii")
        key_b64 = base64.b64encode(self._key_der_encrypted).decode("ascii")
        return cer_b64, key_b64, self._key_password

    def _verificar_par_de_llaves(self) -> None:
        """Verifica que la llave privada corresponda al certificado público."""
        public_key = self._x509.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise CertificateError("El certificado no contiene una llave pública RSA")
        if public_key.public_numbers() != self._private_key.public_key().public_numbers():
            raise CertificateError(
                "La llave privada no corresponde al certificado (.cer y .key no hacen pareja)"
            )
        try:
            sig = self._private_key.sign(
                b"contadb-sdk-keypair-check",
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            public_key.verify(
                sig,
                b"contadb-sdk-keypair-check",
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as exc:  # pragma: no cover — no debería ocurrir
            raise CertificateError("Falló verificación cruzada llave/certificado") from exc


def _parsear_certificado(data: bytes) -> tuple[bytes, x509.Certificate]:
    """Devuelve (DER bytes, certificado parseado). Acepta DER o PEM."""
    try:
        if data.lstrip().startswith(b"-----BEGIN"):
            cert = x509.load_pem_x509_certificate(data)
            der = cert.public_bytes(serialization.Encoding.DER)
            return der, cert
        cert = x509.load_der_x509_certificate(data)
        return data, cert
    except ValueError as exc:
        raise CertificateError(f"No se pudo parsear el certificado: {exc}") from exc


def _parsear_llave_privada(data: bytes, password: str) -> rsa.RSAPrivateKey:
    """Carga la llave privada del SAT (PKCS#8 cifrado)."""
    pwd_bytes = password.encode("utf-8") if password else None
    try:
        if data.lstrip().startswith(b"-----BEGIN"):
            key = serialization.load_pem_private_key(data, password=pwd_bytes)
        else:
            key = serialization.load_der_private_key(data, password=pwd_bytes)
    except ValueError as exc:
        raise CertificateError(
            "No se pudo cargar la llave privada — contraseña inválida o archivo corrupto"
        ) from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise CertificateError("La llave privada debe ser RSA")
    return key


def _serializar_llave_pkcs8(key: rsa.RSAPrivateKey, password: str) -> bytes:
    """Serializa la llave privada como PKCS#8 DER cifrado con la misma password."""
    if not password:
        raise CertificateError("La contraseña del CSD no puede estar vacía")
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )


__all__ = ["Certificado"]
