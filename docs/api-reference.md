# API Reference

## `ContaDBClient`

Cliente HTTP síncrono para el endpoint `/api/v1/timbrar`.

### Constructor

```python
ContaDBClient(
    api_token: str,
    *,
    base_url: str | None = None,
    timeout: float = 30.0,
    transport: httpx.BaseTransport | None = None,
    retry_policy: RetryPolicy | None = None,
)
```

| Parámetro       | Tipo                       | Default                       | Descripción |
|-----------------|----------------------------|-------------------------------|-------------|
| `api_token`     | `str`                      | —                             | Token API (`cdb_...`) generado en el panel. |
| `base_url`      | `str \| None`              | env `CONTADB_BASE_URL` o `https://api.contadb.mx` | URL base del API. |
| `timeout`       | `float`                    | `30.0`                        | Timeout en segundos por request. |
| `transport`     | `httpx.BaseTransport \| None` | `None`                     | Transport personalizado (útil para tests/proxies). |
| `retry_policy`  | `RetryPolicy \| None`      | `RETRY_POLICY_DEFAULT` (3 intentos) | Política de reintentos en errores transitorios. |

### `timbrar(xml, *, idempotency_key=None) -> TimbradoResult`

Timbra un CFDI 4.0 firmado.

| Parámetro          | Tipo            | Descripción |
|--------------------|-----------------|-------------|
| `xml`              | `str \| bytes`  | XML CFDI 4.0 ya firmado por el emisor. |
| `idempotency_key`  | `str \| None`   | Clave de idempotencia. Auto-genera UUID v4 si es `None`. |

### `cancelar(*, uuid_cfdi, motivo, certificado, folio_sustitucion=None, idempotency_key=None) -> CancelacionResult`

Cancela un CFDI ya timbrado.

| Parámetro            | Tipo            | Descripción |
|----------------------|-----------------|-------------|
| `uuid_cfdi`          | `str`           | UUID del CFDI a cancelar. |
| `motivo`             | `"01"`–`"04"`   | Motivo SAT. `"01"` exige `folio_sustitucion`. |
| `certificado`        | `Certificado`   | CSD del emisor (firma la solicitud al SAT). |
| `folio_sustitucion`  | `str \| None`   | UUID del CFDI sustituto. Solo válido cuando `motivo="01"`. |
| `idempotency_key`    | `str \| None`   | Clave de idempotencia. |

### `cerrar() / context manager`

```python
client = ContaDBClient(api_token="cdb_x")
try:
    ...
finally:
    client.cerrar()

# o equivalente:
with ContaDBClient(api_token="cdb_x") as client:
    ...
```

---

## `RetryPolicy`

Dataclass inmutable que configura los reintentos del cliente.

```python
RetryPolicy(
    max_intentos: int = 3,
    backoff_factor: float = 0.5,
    backoff_max: float = 30.0,
    estatus_a_reintentar: tuple[int, ...] = (429, 500, 502, 503, 504),
    respetar_retry_after: bool = True,
)
```

Espera entre reintentos: `backoff_factor * 2^(intento-1) + jitter`, acotado por `backoff_max`. Si el servidor envía `Retry-After` (segundos o HTTP-date) y `respetar_retry_after=True`, ese valor se usa en su lugar.

Constantes:

- `RETRY_POLICY_DEFAULT` — política por defecto (3 intentos, backoff 0.5s).
- `RETRY_POLICY_NINGUNO` — desactiva reintentos (1 solo intento).

```python
from contadb_sdk import ContaDBClient, RetryPolicy, RETRY_POLICY_NINGUNO

# Política agresiva
client = ContaDBClient(
    api_token="cdb_xxx",
    retry_policy=RetryPolicy(max_intentos=5, backoff_factor=1.0, backoff_max=60.0),
)

# Sin reintentos (comportamiento de v1.0)
client = ContaDBClient(api_token="cdb_xxx", retry_policy=RETRY_POLICY_NINGUNO)
```

---

## `TimbradoResult`

Pydantic model retornado por `timbrar()`.

| Campo               | Tipo              | Descripción |
|---------------------|-------------------|-------------|
| `success`           | `bool`            | Siempre `True` en respuestas exitosas. |
| `xml_timbrado`      | `str`             | XML CFDI 4.0 con el TimbreFiscalDigital integrado. |
| `uuid`              | `str`             | UUID v4 asignado por el SAT (folio fiscal). |
| `saldo_restante`    | `int`             | Timbres restantes en la bolsa. |
| `fecha_vencimiento` | `datetime \| None` | Fecha de vencimiento de la bolsa activa. |

---

## `CFDIBuilder`

Constructor fluido de CFDI 4.0.

### Constructor

```python
CFDIBuilder(
    *,
    emisor: Emisor,
    receptor: Receptor,
    lugar_expedicion: str,                 # CP de 5 dígitos del emisor
    serie: str | None = None,
    folio: str | None = None,
    fecha: datetime | None = None,         # default: ahora
    forma_pago: str | None = None,         # ej. "03"
    metodo_pago: Literal["PUE", "PPD"] = "PUE",
    moneda: str = "MXN",
    tipo_cambio: Decimal | None = None,    # requerido si moneda != MXN
    tipo_comprobante: Literal["I","E","T","P","N"] = "I",
    exportacion: Literal["01","02","03","04"] = "01",
    condiciones_pago: str | None = None,
    informacion_global: InformacionGlobal | None = None,
    cfdi_relacionados: list[CfdiRelacionados] | None = None,
)
```

Validaciones cruzadas:

- `informacion_global` solo se acepta cuando `receptor.rfc == "XAXX010101000"`.
- Receptor `XAXX010101000` exige `informacion_global` en CFDI tipo `"I"`.
- Máx. 1000 conceptos por CFDI; máx. importe por concepto y total: 999,999,999.99.

### Métodos

#### `agregar_concepto(concepto: Concepto) -> Self`
Agrega un concepto al comprobante. Retorna `self` para encadenar.

#### `agregar_conceptos(conceptos: Iterable[Concepto]) -> Self`
Agrega múltiples conceptos.

#### `agregar_cfdi_relacionado(*, tipo_relacion: str, uuids: Iterable[str]) -> Self`
Agrega un bloque `cfdi:CfdiRelacionados`. `tipo_relacion` debe ser una clave del catálogo SAT `c_TipoRelacion` (`"01"`–`"07"`). Acepta uno o más UUIDs por bloque y se pueden agregar varios bloques con distintos `tipo_relacion`.

#### `agregar_complemento(complemento: Complemento) -> Self`
Agrega un complemento (ej. Pagos 2.0, Carta Porte 3.1).

#### `construir_xml() -> bytes`
Construye el XML **sin firmar** (sin `Sello`, sin `NoCertificado`, sin
`Certificado`). Útil para inspección o testing.

#### `construir_y_firmar(cert: Certificado) -> str`
Construye, firma y devuelve el XML completo listo para timbrar.

---

## `Certificado`

Representa un Certificado de Sello Digital (CSD) con su llave privada.

### Constructores

#### `Certificado.cargar(cer_path, key_path, password) -> Certificado`
Carga desde archivos en disco.

#### `Certificado.desde_bytes(cer, key, password) -> Certificado`
Carga desde bytes (sin tocar disco).

### Propiedades

| Propiedad           | Tipo         | Descripción |
|---------------------|--------------|-------------|
| `certificado_b64`   | `str`        | Base64 del .cer DER. |
| `no_certificado`    | `str`        | NoCertificado de 20 dígitos. |
| `rfc`               | `str \| None` | RFC del titular (extraído del subject). |

### `firmar(cadena_original: str) -> str`
Firma la cadena con RSA-SHA256 (PKCS#1 v1.5) y retorna sello en base64.

---

## Modelos

### `Emisor`

| Campo            | Tipo  | Validación |
|------------------|-------|------------|
| `rfc`            | `str` | 12-13 chars, formato RFC mexicano |
| `nombre`         | `str` | 1-300 chars |
| `regimen_fiscal` | `str` | 3 dígitos |

### `Receptor`

| Campo                       | Tipo            | Validación |
|-----------------------------|-----------------|------------|
| `rfc`                       | `str`           | 12-13 chars |
| `nombre`                    | `str`           | 1-300 chars |
| `uso_cfdi`                  | `str`           | letra+2 dígitos (ej "G03") |
| `domicilio_fiscal_receptor` | `str`           | CP de 5 dígitos |
| `regimen_fiscal_receptor`   | `str`           | 3 dígitos |
| `residencia_fiscal`         | `str \| None`   | Código país de 3 chars (extranjeros) |
| `num_reg_id_trib`           | `str \| None`   | Tax ID del extranjero |

### `Concepto`

| Campo                  | Tipo            | Default | Descripción |
|------------------------|-----------------|---------|-------------|
| `clave_prod_serv`      | `str`           | —       | Clave SAT de 8 dígitos |
| `no_identificacion`    | `str \| None`   | None    | Número de serie/SKU |
| `cantidad`             | `Decimal`       | —       | > 0 |
| `clave_unidad`         | `str`           | —       | Clave SAT (ej "E48") |
| `unidad`               | `str \| None`   | None    | Descripción de la unidad |
| `descripcion`          | `str`           | —       | 1-1000 chars |
| `valor_unitario`       | `Decimal`       | —       | ≥ 0 |
| `descuento`            | `Decimal \| None` | None  | ≥ 0 |
| `objeto_imp`           | `"01"\|"02"\|"03"` | `"02"` | Objeto de impuesto |
| `tasa_iva`             | `Decimal \| None` | None  | Decimal (0.16 = 16%) |
| `tasa_ieps`            | `Decimal \| None` | None  | |
| `tasa_retencion_isr`   | `Decimal \| None` | None  | |
| `tasa_retencion_iva`   | `Decimal \| None` | None  | |
| `tasa_retencion_ieps`  | `Decimal \| None` | None  | |
| `iva_exento`           | `bool`          | False   | Genera IVA Exento sin tasa |

### `InformacionGlobal`

Para CFDIs a "Público en general".

| Campo          | Tipo  | Validación |
|----------------|-------|------------|
| `periodicidad` | `str` | "01"-"05" |
| `meses`        | `str` | "01"-"18" |
| `año`          | `int` | 2000-9999 |

### `CfdiRelacionados`

Bloque que referencia uno o más CFDIs previos (sustitución, nota de crédito, devolución, etc.).

| Campo            | Tipo                | Validación |
|------------------|---------------------|------------|
| `tipo_relacion`  | `"01"`–`"07"`       | Catálogo SAT `c_TipoRelacion`. |
| `uuids`          | `list[str]`         | ≥1 UUID, sin duplicados; cada UUID se valida y normaliza. |

Catálogo `c_TipoRelacion`:

| Clave | Significado |
|-------|-------------|
| `"01"` | Nota de crédito de los documentos relacionados |
| `"02"` | Nota de débito de los documentos relacionados |
| `"03"` | Devolución de mercancía sobre facturas o traslados previos |
| `"04"` | Sustitución de los CFDI previos (típico tras cancelar con motivo 01) |
| `"05"` | Traslados de mercancías facturados previamente |
| `"06"` | Factura generada por los traslados previos |
| `"07"` | CFDI por aplicación de anticipo |

---

## Excepciones

Jerarquía completa:

```
ContaDBError
├── ConfigurationError
├── BuildError
│   ├── CertificateError
│   └── ValidationError
└── APIError
    ├── AuthError
    │   ├── TokenInvalidoError
    │   ├── TokenRevocadoError
    │   ├── TokenBloqueadoError
    │   └── CuentaBloqueadaError(blocked_until)
    ├── ClientError
    │   ├── XMLInvalidoError
    │   └── XMLDemasiadoGrandeError
    ├── QuotaError
    │   ├── SaldoInsuficienteError
    │   └── RateLimitError(retry_after)
    └── ServerError
        ├── PACError
        └── InternalError
```

Todas las excepciones de la API exponen los atributos:

| Atributo      | Tipo                 | Descripción |
|---------------|----------------------|-------------|
| `message`     | `str`                | Mensaje legible. |
| `code`        | `str`                | Código del API (`SALDO_INSUFICIENTE`, etc.). |
| `status_code` | `int \| None`        | HTTP status. |
| `payload`     | `dict[str, object]`  | Respuesta JSON completa. |

Adicionalmente:
- `RateLimitError.retry_after: int | None` — segundos a esperar.
- `CuentaBloqueadaError.blocked_until: datetime | None` — fecha de desbloqueo.

---

## Catálogos

Constantes y enums en `contadb_sdk.catalogs` (re-exportados desde el paquete raíz):

```python
from contadb_sdk import (
    TipoComprobante, MetodoPago, Exportacion, ObjetoImp, Periodicidad, FormaPago,
    RFC_PUBLICO_GENERAL, NOMBRE_PUBLICO_GENERAL, USO_PUBLICO_GENERAL,
    REGIMEN_SIN_OBLIGACIONES, RFC_EXTRANJERO,
    IMPUESTO_IVA, IMPUESTO_ISR, IMPUESTO_IEPS,
    MONEDA_MXN, CFDI_VERSION,
)
```

Ver [catalogos-sat.md](catalogos-sat.md) para una tabla de claves comunes.
