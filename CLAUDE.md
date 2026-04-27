# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`contadb-sdk` is the official Python SDK for building, signing, and stamping (timbrar) Mexican CFDI 4.0 invoices against the public **ContaDB** API (`https://api.contadb.com`). It is published to PyPI as `contadb-sdk` and is consumed by third-party integrators — not by the AOSystems Invoice Agent backend in the parent directory. Treat this repo as an independent library: it has its own `.git`, its own release cycle, and is published from `dist/`.

The SDK is sync-only (HTTP via `httpx.Client`); async support is planned for a future version. Logging goes through the `contadb_sdk` standard `logging` logger — no sensitive content (token, llave privada, contraseña) is ever emitted; only request paths, status codes, and retry decisions.

## Development Commands

This project uses an editable install with a `[dev]` extra. The local virtualenv lives at `.venv/`.

```bash
# One-time setup
pip install -e ".[dev]"

# Lint + format check (must both pass — CI runs both)
ruff check src tests
ruff format --check src tests
ruff format src tests          # apply formatting

# Strict type check (CI gates on this)
mypy src

# Tests (filterwarnings=error in pyproject — any warning fails the suite)
pytest
pytest --cov=contadb_sdk --cov-report=term-missing
pytest tests/test_builder.py                    # single file
pytest tests/test_builder.py::test_name -v      # single test
pytest -k "cadena and not exempt"               # by expression

# Build the distribution (sdist + wheel) into dist/
python -m build

# Publish (manual; also wired in .github/workflows/publish.yml on tag push)
twine upload dist/*
```

CI matrix: Python 3.10, 3.11, 3.12, 3.13 (`.github/workflows/ci.yml`). The minimum supported version is 3.10 (`requires-python`, `target-version = "py310"`).

## Architecture

### Pipeline: build → cadena → sign → timbrar

The CFDI flow is a strict 4-step pipeline. Each step is a separate module so it can be unit-tested in isolation. Public class and method names are in Spanish — code samples below use the actual identifiers.

1. **`builder.py` → `CFDIBuilder.construir_y_firmar(cert)`** — fluent builder. Internally creates `_ConceptoCalculado` per line, computes `Importe = cantidad * valor_unitario`, base, traslados (IVA/IEPS) and retenciones (ISR/IVA/IEPS) via `_calcular_impuestos()`, then assembles the `cfdi:Comprobante` element with `lxml`. Consolidates `cfdi:Impuestos` grouped by `(Impuesto, TipoFactor, Tasa)` for traslados and by `Impuesto` for retenciones. Also emits `cfdi:CfdiRelacionados` (one block per `TipoRelacion`) before `cfdi:InformacionGlobal`.
2. **`cadena.py` → `cadena_original(xml)`** — runs the **official SAT XSLT** (`_xslt/cadenaoriginal_4_0.xslt` + `utilerias.xslt`, bundled into the wheel via `[tool.hatch.build.targets.wheel.force-include]`) to produce the canonical string. The transform is lazy-loaded and module-level cached. **Never inline the XSLT or hand-build the cadena** — the SAT rejects mismatches.
3. **`signer.py` → `Certificado.firmar(cadena)`** — RSA-SHA256 with **PKCS#1 v1.5 padding** (NOT PSS — SAT requires v1.5). `Certificado.desde_bytes()` (and `Certificado.cargar` / `Certificado.cargar_pfx`) runs `_verificar_par_de_llaves()` to ensure the `.cer` and `.key` form a real pair before any signing. `no_certificado` decodes the X.509 SerialNumber as 20 ASCII digits (the SAT-specific encoding), falling back to the raw int.
4. **`client.py` → `ContaDBClient.timbrar(xml)`** — `POST /api/v1/timbrar` with `Authorization: Bearer cdb_...` and an auto-generated `Idempotency-Key` (UUID v4, override per call). Parses the JSON response in `_parsear_respuesta()`; on success returns `TimbradoResult`, on error dispatches via `excepcion_para_codigo()` to a typed exception. Reintenta automáticamente en errores transitorios (429, 5xx, fallos de red) según la `RetryPolicy` configurada — usar `RETRY_POLICY_NINGUNO` para desactivar.

The public surface is re-exported from `__init__.py` — when adding a public symbol, update both the imports and the `__all__` list there.

### Money and tax conventions

- **All monetary fields and tax rates are `decimal.Decimal`, never `float`.** SAT requires exact precision; `float` arithmetic will silently produce invalid amounts.
- Tax rates are stored as decimals: `Decimal("0.16")` = 16%, `Decimal("0.08")` = 8%. The builder applies `quantize_money()` (2 decimals) for amounts and `fmt_rate()` for tasas — see `xml_utils.py`.
- `objeto_imp="01"` (no objeto) is incompatible with any tasa or `iva_exento=True`; this is enforced by a `model_validator` on `Concepto`. `objeto_imp="02"`/`"03"` is what triggers tax computation in the builder.
- `iva_exento=True` produces `<cfdi:Traslado TipoFactor="Exento">` (no Tasa, no Importe). Don't confuse with rate `0` — they serialize differently.

### Error model

`ContaDBError` is the root. The hierarchy splits into two branches by *origin*:

- **Local errors** (`BuildError`, `CertificateError`, `ValidationError`, `ConfigurationError`) — raised before any HTTP call.
- **API errors** (`APIError` and subclasses: `AuthError`, `ClientError`, `QuotaError`, `ServerError`) — raised from `client._parsear_respuesta()` based on the JSON `code` field. New API error codes go in `_CODE_MAP` in `exceptions.py`; the `code` class attribute on each subclass is the canonical mapping key.
- `RateLimitError.retry_after` and `CuentaBloqueadaError.blocked_until` are extracted from response payload/headers — preserve those constructor signatures when extending.

### Pydantic models

All models in `models.py` inherit from `_StrictModel` which sets `extra="forbid"` and `str_strip_whitespace=True`. Adding an unknown field to a model input raises — this is intentional for catching typos in user code. RFC, CP, and régimen patterns are enforced via `Field(pattern=...)` regex.

The `Concepto` model has the most validation logic; cross-field invariants go in `@model_validator(mode="after")`, not in the builder.

### Tests

`tests/conftest.py` generates a self-signed RSA cert + PKCS#8-encrypted key in-memory at session scope (`keypair_bytes` fixture) so tests don't depend on real SAT CSDs in the repo. Use the existing fixtures (`certificate`, `emisor`, `receptor`, `concepto_basico`, `builder`, `signed_xml`) rather than rebuilding them per test.

`pyproject.toml` sets `filterwarnings = ["error"]` — DeprecationWarnings from upstream libs will fail the suite. If `httpx`/`pydantic`/`cryptography` emits a warning on a new version, fix the call site rather than silencing globally.

`pytest-httpx` is the dependency-of-record for mocking the API; pass a custom `transport` to `ContaDBClient` rather than monkey-patching.

## Release / Versioning

- Version source: `src/contadb_sdk/_version.py` (read by `hatch` via `[tool.hatch.version]`).
- Bump the version there + add a `CHANGELOG.md` section + tag `vX.Y.Z` to trigger `.github/workflows/publish.yml`.
- The `_xslt/*.xslt` and `py.typed` marker are explicitly force-included into the wheel via `pyproject.toml` — if you add new package data, add it there too or it won't ship.

## Conventions

- Public docstrings are in Spanish (matching the user base); internal comments can be either, but match the surrounding file.
- Use `from __future__ import annotations` in all modules — it's already standard across the codebase and required for the `X | Y` syntax on 3.10.
- `lxml._Element` / `_ElementTree` don't support `A | B` at runtime; use `typing.Union` for those (see `cadena.py:19` for the documented exception to PEP 604).
- `mypy --strict` is enforced on `src/` (not on `tests/`, which has `disallow_untyped_defs = false`). Don't add `# type: ignore` without a comment explaining why.
