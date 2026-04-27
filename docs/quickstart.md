# Quickstart

Esta guía te lleva del cero a tu primer CFDI 4.0 timbrado en menos de 5 minutos.

## 1. Instala el SDK

```bash
pip install contadb-sdk
```

Requiere Python 3.10+.

## 2. Obtén tus credenciales

Necesitas dos cosas:

### a) API token de ContaDB
1. Crea cuenta en [contadb.mx](https://contadb.mx) y verifica tu email.
2. Compra una bolsa de timbres (mínimo 100 / $200 MXN).
3. En el panel: **Facturación → API Tokens → Generar nuevo token**.
4. Guarda el token (formato `cdb_...`) — solo se muestra una vez.

### b) Certificado de Sello Digital (CSD) del SAT
1. Descarga tu CSD del [portal del SAT](https://www.sat.gob.mx/).
2. Obtendrás dos archivos: `.cer` (certificado) y `.key` (llave privada cifrada).
3. Recuerda la contraseña del CSD (no es la del SAT, es la específica del CSD).

> ⚠️ El CSD es de **sello digital**, no FIEL. La FIEL no funciona para emitir CFDIs.

## 3. Construye y timbra tu primer CFDI

```python
from decimal import Decimal
from contadb_sdk import (
    ContaDBClient, CFDIBuilder, Certificado,
    Emisor, Receptor, Concepto,
)

cert = Certificado.cargar("emisor.cer", "emisor.key", "MI_PASSWORD")

xml = (
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
        folio="1",
        forma_pago="03",
        lugar_expedicion="64000",
    )
    .agregar_concepto(Concepto(
        clave_prod_serv="43232408",
        clave_unidad="E48",
        descripcion="Servicios de consultoría",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("1000.00"),
        tasa_iva=Decimal("0.16"),
    ))
    .construir_y_firmar(cert)
)

with ContaDBClient(api_token="cdb_TU_TOKEN") as client:
    result = client.timbrar(xml)

print(result.uuid)            # UUID asignado por el SAT
print(result.saldo_restante)  # Timbres que te quedan
print(result.xml_timbrado)    # XML completo con el TimbreFiscalDigital
```

## 4. Maneja errores

```python
from contadb_sdk import (
    ContaDBClient,
    SaldoInsuficienteError, RateLimitError,
    TokenInvalidoError, TokenRevocadoError,
    XMLInvalidoError, PACError,
)

try:
    result = client.timbrar(xml)
except SaldoInsuficienteError:
    # Compra más timbres en https://contadb.mx/facturacion
    ...
except RateLimitError as e:
    # El SDK ya reintentó automáticamente; aquí solo llegas si agotó los intentos.
    # e.retry_after trae los segundos sugeridos por el servidor.
    ...
except TokenInvalidoError:
    # El token no existe o tiene formato incorrecto
    ...
except TokenRevocadoError:
    # El token fue revocado — genera uno nuevo
    ...
except XMLInvalidoError:
    # El XML no pasó la validación del PAC
    ...
except PACError as e:
    # Error genérico del PAC — revisa e.message
    ...
```

## 5. Reintentos automáticos

El cliente reintenta solo en errores transitorios (HTTP 429, 5xx y fallos de red) con backoff exponencial. La misma `Idempotency-Key` se reusa entre intentos, así que el servidor deduplica.

```python
from contadb_sdk import ContaDBClient, RetryPolicy, RETRY_POLICY_NINGUNO

# Default: 3 intentos, backoff 0.5s × 2ⁿ con jitter, tope 30s.
client = ContaDBClient(api_token="cdb_xxx")

# Más agresivo:
client = ContaDBClient(
    api_token="cdb_xxx",
    retry_policy=RetryPolicy(max_intentos=5, backoff_factor=1.0, backoff_max=60.0),
)

# Sin reintentos (comportamiento de v1.0):
client = ContaDBClient(api_token="cdb_xxx", retry_policy=RETRY_POLICY_NINGUNO)
```

## 6. CFDI sustituto, nota de crédito, devolución

Cuando emites un CFDI que reemplaza o referencia uno previo, agrega un bloque `cfdi:CfdiRelacionados`:

```python
from contadb_sdk import CFDIBuilder, CfdiRelacionados

builder = CFDIBuilder(...).agregar_cfdi_relacionado(
    tipo_relacion="04",  # 04 = Sustitución (típico tras cancelar con motivo 01)
    uuids=["550e8400-e29b-41d4-a716-446655440000"],
)
```

Catálogo `c_TipoRelacion`: `"01"` nota de crédito · `"02"` nota de débito · `"03"` devolución · `"04"` sustitución · `"05"`–`"07"` traslados/anticipos.

## 7. Logging

El SDK emite eventos vía el logger estándar `contadb_sdk` (request, status, decisiones de reintento). **Nunca** loguea token, llave privada, contraseña ni XML.

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("contadb_sdk").setLevel(logging.DEBUG)
```

## Siguientes pasos

- [Construcción de CFDI](building-cfdi.md) — todos los campos, casos especiales, cálculo de impuestos.
- [API Reference](api-reference.md) — documentación completa de las clases.
- [Catálogos SAT](catalogos-sat.md) — claves comunes (FormaPago, UsoCFDI, etc.).
- [Ejemplos ejecutables](../examples/)
