"""contadb-sdk — SDK Python para construir, firmar y timbrar CFDI 4.0 con ContaDB.

Quickstart::

    from decimal import Decimal
    from contadb_sdk import (
        ContaDBClient, CFDIBuilder, Certificado,
        Emisor, Receptor, Concepto,
    )

    cert = Certificado.cargar("emisor.cer", "emisor.key", "MI_PASS")

    xml = (
        CFDIBuilder(
            emisor=Emisor(rfc="EKU9003173C9", nombre="ESCUELA KEMPER URGATE",
                          regimen_fiscal="601"),
            receptor=Receptor(rfc="URE180429TM6", nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
                              uso_cfdi="G03", domicilio_fiscal_receptor="65000",
                              regimen_fiscal_receptor="601"),
            serie="A", folio="1", forma_pago="03", lugar_expedicion="64000",
        )
        .agregar_concepto(Concepto(
            clave_prod_serv="43232408", clave_unidad="E48",
            descripcion="Consultoría", cantidad=Decimal("1"),
            valor_unitario=Decimal("1000"), tasa_iva=Decimal("0.16"),
        ))
        .construir_y_firmar(cert)
    )

    with ContaDBClient(api_token="cdb_xxx") as client:
        result = client.timbrar(xml)
        print(result.uuid, result.saldo_restante)
"""

from ._version import __version__
from .builder import CFDIBuilder
from .cadena import cadena_original
from .catalogs import (
    CFDI_VERSION,
    IMPUESTO_IEPS,
    IMPUESTO_ISR,
    IMPUESTO_IVA,
    MONEDA_MXN,
    NOMBRE_PUBLICO_GENERAL,
    REGIMEN_SIN_OBLIGACIONES,
    RFC_EXTRANJERO,
    RFC_PUBLICO_GENERAL,
    USO_PUBLICO_GENERAL,
    Exportacion,
    FormaPago,
    MetodoPago,
    ObjetoImp,
    Periodicidad,
    TipoComprobante,
)
from .client import ContaDBClient
from .complementos import (
    Autotransporte,
    CartaPorteBuilder,
    Complemento,
    DoctoRelacionado,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Pago,
    PagoBuilder,
    Remolque,
    RetencionDR,
    Seguros,
    TiposFigura,
    TrasladoDR,
    Ubicacion,
)
from .exceptions import (
    APIError,
    AuthError,
    BuildError,
    CancelacionError,
    CertificadoInvalidoError,
    CertificateError,
    ClientError,
    ConfigurationError,
    ContaDBError,
    CuentaBloqueadaError,
    InternalError,
    MotivoInvalidoError,
    PACError,
    QuotaError,
    RateLimitError,
    SaldoInsuficienteError,
    ServerError,
    TokenBloqueadoError,
    TokenInvalidoError,
    TokenRevocadoError,
    UUIDNoEncontradoError,
    ValidationError,
    XMLDemasiadoGrandeError,
    XMLInvalidoError,
    excepcion_para_codigo,
)
from .models import (
    CancelacionResult,
    Concepto,
    Emisor,
    InformacionGlobal,
    MotivoCancelacion,
    Receptor,
    TimbradoResult,
)
from .signer import Certificado

__all__ = [
    "CFDI_VERSION",
    "IMPUESTO_IEPS",
    "IMPUESTO_ISR",
    "IMPUESTO_IVA",
    "MONEDA_MXN",
    "NOMBRE_PUBLICO_GENERAL",
    "REGIMEN_SIN_OBLIGACIONES",
    "RFC_EXTRANJERO",
    "RFC_PUBLICO_GENERAL",
    "USO_PUBLICO_GENERAL",
    "APIError",
    "AuthError",
    "Autotransporte",
    "BuildError",
    "CFDIBuilder",
    "CancelacionError",
    "CancelacionResult",
    "CartaPorteBuilder",
    "Certificado",
    "CertificadoInvalidoError",
    "CertificateError",
    "ClientError",
    "Complemento",
    "Concepto",
    "ConfigurationError",
    "ContaDBClient",
    "ContaDBError",
    "CuentaBloqueadaError",
    "DoctoRelacionado",
    "Domicilio",
    "Emisor",
    "Exportacion",
    "FiguraTransporte",
    "FormaPago",
    "IdentificacionVehicular",
    "InformacionGlobal",
    "InternalError",
    "Mercancia",
    "MetodoPago",
    "MotivoCancelacion",
    "MotivoInvalidoError",
    "ObjetoImp",
    "PACError",
    "Pago",
    "PagoBuilder",
    "Periodicidad",
    "QuotaError",
    "RateLimitError",
    "Receptor",
    "Remolque",
    "RetencionDR",
    "SaldoInsuficienteError",
    "Seguros",
    "ServerError",
    "TimbradoResult",
    "TipoComprobante",
    "TiposFigura",
    "TokenBloqueadoError",
    "TokenInvalidoError",
    "TokenRevocadoError",
    "TrasladoDR",
    "UUIDNoEncontradoError",
    "Ubicacion",
    "ValidationError",
    "XMLDemasiadoGrandeError",
    "XMLInvalidoError",
    "__version__",
    "cadena_original",
    "excepcion_para_codigo",
]
