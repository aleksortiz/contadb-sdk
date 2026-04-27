# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2026-04-27

### Fixed
- URLs de metadatos PyPI corregidas a `github.com/aleksortiz/contadb-sdk` (Documentation, Repository, Issues, Changelog). Antes apuntaban a `aosystems/contadb-sdk` (404).

[1.1.2]: https://github.com/aleksortiz/contadb-sdk/releases/tag/v1.1.2

## [1.1.1] - 2026-04-27

### Fixed
- **URLs corregidas a `contadb.mx`**: el dominio oficial es `.mx`, no `.com`. Afecta:
  - `DEFAULT_BASE_URL` del `ContaDBClient` (ahora `https://api.contadb.mx`).
  - `Homepage` y email de contacto en metadatos PyPI.
  - Referencias en README, docs, ejemplos y tests.

  Si tenías hard-coded `https://api.contadb.com` o la env var `CONTADB_BASE_URL` apuntando a `.com`, actualízala a `.mx`. El default sigue siendo correcto si no la pasaste explícita.

[1.1.1]: https://github.com/aleksortiz/contadb-sdk/releases/tag/v1.1.1

## [1.1.0] - 2026-04-27

### Added
- **`CfdiRelacionados`**: nuevo modelo Pydantic y soporte en `CFDIBuilder` para emitir `<cfdi:CfdiRelacionados>` en el comprobante (catálogo SAT c_TipoRelacion `"01"`–`"07"`). Habilita CFDIs sustituto/nota de crédito/devolución que referencian uno o varios UUIDs previos. Acepta múltiples bloques con distintos `tipo_relacion` por comprobante. API fluida: `builder.agregar_cfdi_relacionado(tipo_relacion=..., uuids=[...])`.
- **Reintentos automáticos**: `ContaDBClient` reintenta en errores transitorios (HTTP 429, 500, 502, 503, 504 y fallos de red) con backoff exponencial + jitter. Configurable vía `RetryPolicy(max_intentos=3, backoff_factor=0.5, backoff_max=30.0, ...)`. Honra `Retry-After` (segundos o HTTP-date). Cada reintento reusa la misma `Idempotency-Key`, así que es seguro. Para deshabilitar usar `RETRY_POLICY_NINGUNO`.
- **Logging estructurado**: el SDK ahora emite eventos vía `logging.getLogger("contadb_sdk")` (request, status, decisiones de reintento). No emite contenido sensible (token, llave privada, contraseña, XML).
- **Validación de Content-Type**: si el servidor responde con un Content-Type que no incluye `json` (típico cuando un balanceador devuelve HTML), el SDK levanta `ServerError` antes de intentar parsear, con un extracto del cuerpo en el mensaje.
- **Validación cruzada `InformacionGlobal` ↔ receptor genérico**: el receptor `XAXX010101000` exige `informacion_global` en CFDI tipo `"I"`, y `informacion_global` solo se acepta cuando el receptor es `XAXX010101000`. Detecta inconsistencias antes de timbrar.
- **Topes SAT en el builder**: rechaza CFDIs con más de 1000 conceptos (`MAX_CONCEPTOS_POR_CFDI`) o con importes que excedan 999,999,999.99 (`MAX_IMPORTE_SAT`).

### Changed
- `ContaDBClient.__init__` ahora acepta `retry_policy: RetryPolicy | None`. Por defecto se aplica `RETRY_POLICY_DEFAULT` (3 intentos, backoff exponencial). Para preservar el comportamiento anterior (sin reintentos), pasar `retry_policy=RETRY_POLICY_NINGUNO`.
- `CLAUDE.md` actualizado para reflejar los nombres reales en español del API público (`Certificado.firmar`, `Certificado.desde_bytes`, `_verificar_par_de_llaves`, `_calcular_impuestos`, `_parsear_respuesta`, `excepcion_para_codigo`, etc.).
- `.gitignore` ahora excluye archivos sueltos en la raíz (`*.xml`, `probar_*.py`, `scratch_*.py`) para evitar que pruebas locales se cuelen al repositorio o al wheel publicado.

### Removed
- Archivos sueltos en la raíz (`probar_watm_raqn.py`, `watm_raqn_firmado.xml`) que eran scratch de pruebas locales y no debían estar en el repo.

[1.1.0]: https://github.com/aleksortiz/contadb-sdk/releases/tag/v1.1.0

## [1.0.0] - 2026-04-27

### Added
- Cliente HTTP síncrono `ContaDBClient` con `timbrar`, `cancelar` y `cerrar` para los endpoints `POST /api/v1/timbrar` y `POST /api/v1/cancelar` de ContaDB.
- `CFDIBuilder` con API fluida en español (`agregar_concepto`, `agregar_conceptos`, `construir_xml`, `construir_y_firmar`) para construir CFDI 4.0 desde modelos Pydantic con cálculo automático de impuestos (IVA, IEPS, retenciones ISR/IVA/IEPS).
- `Certificado` para cargar `.cer` + `.key` del SAT (PKCS#8 cifrado) y firmar con RSA-SHA256 (`Certificado.cargar`, `Certificado.desde_bytes`, `firmar`).
- Soporte para CSDs empaquetados como PKCS#12 (`.pfx` / `.p12`) vía `Certificado.cargar_pfx` y `Certificado.desde_bytes_pfx`.
- Cancelación de CFDI ya timbrados: `ContaDBClient.cancelar(uuid_cfdi, motivo, *, certificado, folio_sustitucion=None)`. Acepta motivos SAT 01/02/03/04 y exige `folio_sustitucion` (UUID) cuando `motivo="01"`.
- Generación de cadena original vía XSLT oficial del SAT (`cadenaoriginal_4_0.xslt` + `utilerias.xslt` bundleados).
- Modelos Pydantic v2 tipados: `Emisor`, `Receptor`, `Concepto`, `InformacionGlobal`, `TimbradoResult`, `CancelacionResult`.
- Alias `MotivoCancelacion` (`Literal["01", "02", "03", "04"]`).
- Catálogos SAT como enums y constantes (`TipoComprobante`, `MetodoPago`, `ObjetoImp`, etc.).
- Jerarquía de excepciones tipadas (`TokenInvalidoError`, `SaldoInsuficienteError`, `RateLimitError`, `CancelacionError`, `UUIDNoEncontradoError`, `MotivoInvalidoError`, `CertificadoInvalidoError`, etc.) mapeadas desde los códigos del API vía `excepcion_para_codigo` (re-exportada en el API público).
- Auto-generación de `Idempotency-Key` (configurable por llamada).
- Validación estricta de invariantes SAT: `forma_pago`/`metodo_pago` obligatorios para `tipo_comprobante` `"I"` y `"E"`; `tipo_cambio` rechazado cuando `moneda="MXN"`; RFC genérico `XAXX010101000` exige `regimen_fiscal_receptor="616"` y `uso_cfdi="S01"`; RFC `XEXX010101000` exige `residencia_fiscal` y `num_reg_id_trib`; `objeto_imp` ∈ {`04`, `05`, `06`, `07`, `08`} con tasas se rechaza explícitamente.
- Emisión correcta del bloque global `cfdi:Impuestos/cfdi:Traslados` incluso cuando todos los conceptos son `Exento`.
- Interpretación de `Retry-After` en tres formatos: enteros, floats y HTTP-date (RFC 7231).
- Validación de UUID con `uuid.UUID` (acepta hex puro o canónico, normaliza a minúsculas con guiones).
- Marcador PEP 561 (`py.typed`) — todos los tipos exportados son verificables con `mypy`.

### Notas
- Solo cliente síncrono. Soporte async planeado para v1.1.
- No incluye generación de PDF — el XML timbrado se obtiene en la respuesta y puede convertirse aparte.
- No expone endpoints de gestión (saldo, historial, tokens) — esos requieren JWT, no API token.
- `construir_xml()` (sin firmar) no emite atributos `Sello`, `NoCertificado`, `Certificado` vacíos.

[1.0.0]: https://github.com/aleksortiz/contadb-sdk/releases/tag/v1.0.0
