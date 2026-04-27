# contadb-sdk

[![PyPI version](https://img.shields.io/pypi/v/contadb-sdk.svg)](https://pypi.org/project/contadb-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/contadb-sdk.svg)](https://pypi.org/project/contadb-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SDK oficial de Python para construir, firmar y timbrar CFDI 4.0 contra el API público de **ContaDB**.

Consume timbres de tu **bolsa prepagada** usando un API token. Sin pagos por uso, sin contratos mensuales — solo timbra cuando lo necesites.

---

## Instalación

```bash
pip install contadb-sdk
```

Requiere Python 3.10+.

## Quickstart

```python
from decimal import Decimal
from contadb_sdk import (
    ContaDBClient,
    CFDIBuilder,
    Certificado,
    Emisor,
    Receptor,
    Concepto,
)

# 1. Carga tu CSD (Certificado de Sello Digital del SAT)
cert = Certificado.cargar(
    cer_path="emisor.cer",
    key_path="emisor.key",
    password="MI_PASSWORD",
)

# 2. Construye el CFDI
cfdi_xml = (
    CFDIBuilder(
        emisor=Emisor(
            rfc="EKU9003173C9",
            nombre="ESCUELA KEMPER URGATE",
            regimen_fiscal="601",
        ),
        receptor=Receptor(
            rfc="URE180429TM6",
            nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
            uso_cfdi="G03",
            domicilio_fiscal_receptor="65000",
            regimen_fiscal_receptor="601",
        ),
        serie="A",
        folio="1001",
        forma_pago="03",       # Transferencia electrónica
        metodo_pago="PUE",      # Pago en una sola exhibición
        lugar_expedicion="64000",
    )
    .agregar_concepto(
        Concepto(
            clave_prod_serv="43232408",
            clave_unidad="E48",
            descripcion="Servicios de consultoría en sistemas",
            cantidad=Decimal("1"),
            valor_unitario=Decimal("1000.00"),
            objeto_imp="02",
            tasa_iva=Decimal("0.16"),
        )
    )
    .construir_y_firmar(cert)
)

# 3. Timbra contra ContaDB
with ContaDBClient(api_token="cdb_TU_TOKEN_AQUI") as client:
    resultado = client.timbrar(cfdi_xml)

print(f"UUID:           {resultado.uuid}")
print(f"Saldo restante: {resultado.saldo_restante} timbres")
print(f"XML timbrado:   {len(resultado.xml_timbrado)} chars")
```

## Características

- ✅ **Construcción CFDI 4.0** — Builder con API fluida, validación Pydantic, cálculo automático de impuestos.
- ✅ **Firma RSA-SHA256** — Carga `.cer` + `.key` del SAT, firma cadena original generada con XSLT oficial.
- ✅ **Cliente HTTP tipado** — Errores mapeados a excepciones específicas (`SaldoInsuficienteError`, `TokenRevocadoError`, etc.).
- ✅ **Reintentos automáticos** — Backoff exponencial con jitter en errores 429/5xx/red. Honra `Retry-After`. Idempotency-Key resiste duplicados.
- ✅ **CFDI relacionados** — Emite bloques `cfdi:CfdiRelacionados` (sustitución, nota de crédito, devolución, etc.).
- ✅ **Complementos oficiales** — Recepción de Pagos 2.0 y Carta Porte 3.1.
- ✅ **Cancelación** — `client.cancelar(uuid_cfdi, motivo, certificado, folio_sustitucion=...)` con motivos SAT 01–04.
- ✅ **100% tipado** — Marcador `py.typed` para inferencia perfecta en IDEs y `mypy --strict`.
- ✅ **Cero dependencias mágicas** — Solo `pydantic`, `httpx`, `cryptography`, `lxml`.

## Manejo de errores

```python
from contadb_sdk import (
    ContaDBClient,
    SaldoInsuficienteError,
    RateLimitError,
    TokenRevocadoError,
)

try:
    resultado = client.timbrar(xml)
except SaldoInsuficienteError:
    # Comprar más timbres en https://contadb.com/facturacion
    ...
except RateLimitError as e:
    # El SDK ya reintentó automáticamente; aquí solo llegas si agotó los intentos.
    # e.retry_after trae los segundos sugeridos por el servidor.
    ...
except TokenRevocadoError:
    # Generar un nuevo token
    ...
```

## Reintentos automáticos

El cliente reintenta solo en errores transitorios (HTTP 429, 500, 502, 503, 504 y fallos de red) con backoff exponencial + jitter. Cada reintento reusa el mismo `Idempotency-Key`, así que es seguro.

```python
from contadb_sdk import ContaDBClient, RetryPolicy, RETRY_POLICY_NINGUNO

# Default: 3 intentos, backoff_factor=0.5, backoff_max=30s, honra Retry-After.
client = ContaDBClient(api_token="cdb_xxx")

# Personalizado:
client = ContaDBClient(
    api_token="cdb_xxx",
    retry_policy=RetryPolicy(max_intentos=5, backoff_factor=1.0, backoff_max=60.0),
)

# Sin reintentos (comportamiento de v1.0):
client = ContaDBClient(api_token="cdb_xxx", retry_policy=RETRY_POLICY_NINGUNO)
```

## CFDI sustituto / nota de crédito / devolución

Para emitir un CFDI que referencia uno o varios CFDIs previos (sustitución tras cancelar con motivo 01, nota de crédito, devolución, etc.):

```python
from contadb_sdk import CFDIBuilder, CfdiRelacionados

builder = CFDIBuilder(...).agregar_cfdi_relacionado(
    tipo_relacion="04",                 # 04 = Sustitución de los CFDI previos
    uuids=["550e8400-e29b-41d4-a716-446655440000"],
)
```

Catálogo `c_TipoRelacion` SAT: `"01"` nota de crédito, `"02"` nota de débito, `"03"` devolución, `"04"` sustitución, `"05"`–`"07"` traslados/anticipos.

## Logging

El SDK emite eventos vía el logger estándar `contadb_sdk` (request, status, decisiones de reintento). Nunca loguea token, llave privada, contraseña ni XML.

```python
import logging
logging.getLogger("contadb_sdk").setLevel(logging.INFO)
```

## Configuración

Por defecto el cliente apunta a `https://api.contadb.com`. Puedes cambiarlo:

```python
client = ContaDBClient(
    api_token="cdb_xxx",
    base_url="https://staging.contadb.com",  # o env var CONTADB_BASE_URL
    timeout=60.0,
)
```

## Documentación

- [Quickstart](docs/quickstart.md)
- [Construcción de CFDI](docs/building-cfdi.md)
- [API Reference](docs/api-reference.md)
- [Catálogos SAT comunes](docs/catalogos-sat.md)
- [Ejemplos ejecutables](examples/)

## Cómo obtener un API token

1. Crea cuenta en [contadb.com](https://contadb.com).
2. Ve a **Facturación → API Tokens** y genera uno.
3. Compra una **bolsa de timbres** (desde 100 timbres / $200 MXN).
4. Usa el token con este SDK.

## Licencia

MIT — ver [LICENSE](LICENSE).
