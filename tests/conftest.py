"""Fixtures compartidas por los tests.

Genera un par cer/key autofirmado en memoria al inicio de la sesión —
suficiente para validar que el flujo de carga, firma y verificación
funciona, sin depender de archivos del SAT en el repo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    Concepto,
    Emisor,
    Receptor,
)


@pytest.fixture(scope="session")
def cert_password() -> str:
    return "TEST_PASSWORD_12345678"


@pytest.fixture(scope="session")
def keypair_bytes(cert_password: str) -> tuple[bytes, bytes]:
    """Genera un par X.509 + llave privada PKCS#8 cifrado, en formato DER.

    Imita lo que el SAT entrega: .cer en DER y .key en PKCS#8 cifrado.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "MX"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ESCUELA KEMPER URGATE"),
            x509.NameAttribute(NameOID.COMMON_NAME, "ESCUELA KEMPER URGATE"),
            # OID 2.5.4.45 = uniqueIdentifier — el SAT pone aquí "RFC / CURP"
            x509.NameAttribute(x509.ObjectIdentifier("2.5.4.45"), "EKU9003173C9"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(int("30001000000400002434"))
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )

    cer_der = cert.public_bytes(serialization.Encoding.DER)
    key_der = key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(cert_password.encode("utf-8")),
    )
    return cer_der, key_der


@pytest.fixture(scope="session")
def certificate(keypair_bytes: tuple[bytes, bytes], cert_password: str) -> Certificado:
    cer, key = keypair_bytes
    return Certificado.desde_bytes(cer, key, cert_password)


@pytest.fixture
def cert_files(
    tmp_path_factory: pytest.TempPathFactory,
    keypair_bytes: tuple[bytes, bytes],
) -> tuple[str, str]:
    """Escribe el cert/key a archivos temporales y devuelve sus paths."""
    cer, key = keypair_bytes
    tmp = tmp_path_factory.mktemp("certs")
    cer_path = tmp / "test.cer"
    key_path = tmp / "test.key"
    cer_path.write_bytes(cer)
    key_path.write_bytes(key)
    return str(cer_path), str(key_path)


@pytest.fixture
def emisor() -> Emisor:
    return Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )


@pytest.fixture
def receptor() -> Receptor:
    return Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="G03",
        domicilio_fiscal_receptor="65000",
        regimen_fiscal_receptor="601",
    )


@pytest.fixture
def concepto_basico() -> Concepto:
    return Concepto(
        clave_prod_serv="43232408",
        clave_unidad="E48",
        descripcion="Servicios de consultoría en sistemas",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("1000.00"),
        objeto_imp="02",
        tasa_iva=Decimal("0.16"),
    )


@pytest.fixture
def builder(emisor: Emisor, receptor: Receptor, concepto_basico: Concepto) -> CFDIBuilder:
    return CFDIBuilder(
        emisor=emisor,
        receptor=receptor,
        serie="A",
        folio="1",
        fecha=datetime(2026, 4, 26, 12, 0, 0),
        forma_pago="03",
        metodo_pago="PUE",
        lugar_expedicion="64000",
    ).agregar_concepto(concepto_basico)


@pytest.fixture
def signed_xml(builder: CFDIBuilder, certificate: Certificado) -> str:
    return cast(str, builder.construir_y_firmar(certificate))
