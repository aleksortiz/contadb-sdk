"""Tests del módulo signer (carga de cert/key + firma RSA-SHA256)."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from contadb_sdk import Certificado
from contadb_sdk.exceptions import CertificateError


def test_cargar_from_files(cert_files: tuple[str, str], cert_password: str) -> None:
    cer, key = cert_files
    cert = Certificado.cargar(cer, key, cert_password)
    assert cert.certificado_b64
    assert cert.no_certificado == "30001000000400002434"
    assert cert.rfc == "EKU9003173C9"


def test_password_invalido(
    keypair_bytes: tuple[bytes, bytes],
) -> None:
    cer, key = keypair_bytes
    with pytest.raises(CertificateError, match="contraseña"):
        Certificado.desde_bytes(cer, key, "WRONG_PASSWORD")


def test_certificado_b64_es_der(certificate: Certificado) -> None:
    decoded = base64.b64decode(certificate.certificado_b64)
    # DER de un X.509 empieza con SEQUENCE (0x30) 0x82.
    assert decoded[:2] == b"\x30\x82"


def test_firmar_produce_base64_valido(certificate: Certificado) -> None:
    sello = certificate.firmar("||4.0|A|1|fecha||")
    decoded = base64.b64decode(sello)
    assert len(decoded) == 256  # RSA 2048 → 256 bytes


def test_firmar_es_verificable(
    certificate: Certificado, keypair_bytes: tuple[bytes, bytes]
) -> None:
    """La firma generada debe ser válida usando la pubkey del certificado."""
    from cryptography import x509

    cadena = "||4.0|TEST|1|2026-04-26T12:00:00||"
    sello_b64 = certificate.firmar(cadena)
    sello_bytes = base64.b64decode(sello_b64)

    cer = x509.load_der_x509_certificate(keypair_bytes[0])
    cer.public_key().verify(  # type: ignore[union-attr]
        sello_bytes,
        cadena.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_archivo_corrupto_falla(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad_cer = tmp_path / "bad.cer"
    bad_cer.write_bytes(b"not a real cert")
    bad_key = tmp_path / "bad.key"
    bad_key.write_bytes(b"not a real key")
    with pytest.raises(CertificateError):
        Certificado.cargar(str(bad_cer), str(bad_key), "x")
