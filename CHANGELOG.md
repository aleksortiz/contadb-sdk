# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/aosystems/contadb-sdk/releases/tag/v1.0.0
