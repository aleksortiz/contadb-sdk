"""Cancelar un CFDI ya timbrado.

Muestra el flujo completo de cancelación contra ContaDB:

1. Cargar el CSD del emisor (mismo que se usó al timbrar).
2. Llamar a ``client.cancelar`` con el UUID y el motivo.
3. Manejar las excepciones específicas del flujo.

Motivos válidos (catálogo SAT):
    01 — Comprobante emitido con errores con relación (requiere folio_sustitucion).
    02 — Comprobante emitido con errores sin relación.
    03 — No se llevó a cabo la operación.
    04 — Operación nominativa relacionada con factura global.
"""

from __future__ import annotations

from contadb_sdk import (
    Certificado,
    CertificadoInvalidoError,
    ContaDBClient,
    MotivoInvalidoError,
    UUIDNoEncontradoError,
)


def main() -> None:
    cert = Certificado.cargar(
        cer_path="emisor.cer",
        key_path="emisor.key",
        password="MI_PASSWORD",
    )

    uuid_a_cancelar = "550e8400-e29b-41d4-a716-446655440000"

    with ContaDBClient(api_token="cdb_TU_TOKEN_AQUI") as client:
        try:
            resultado = client.cancelar(
                uuid_cfdi=uuid_a_cancelar,
                motivo="02",
                certificado=cert,
            )
        except UUIDNoEncontradoError:
            print("El UUID no fue timbrado por este token.")
            return
        except MotivoInvalidoError as exc:
            print(f"Motivo inválido: {exc.message}")
            return
        except CertificadoInvalidoError as exc:
            print(f"CSD rechazado por el PAC: {exc.message}")
            return

    print(f"Aceptada:     {resultado.aceptada}")
    print(f"EstatusUUID:  {resultado.estatus_uuid}")
    print(f"Mensaje:      {resultado.mensaje}")


def cancelar_con_sustitucion() -> None:
    """Motivo 01 requiere el UUID del CFDI que sustituye al cancelado."""
    cert = Certificado.cargar("emisor.cer", "emisor.key", "MI_PASSWORD")
    uuid_anterior = "550e8400-e29b-41d4-a716-446655440000"
    uuid_sustituto = "660e8400-e29b-41d4-a716-446655440111"

    with ContaDBClient(api_token="cdb_TU_TOKEN_AQUI") as client:
        resultado = client.cancelar(
            uuid_cfdi=uuid_anterior,
            motivo="01",
            folio_sustitucion=uuid_sustituto,
            certificado=cert,
        )
    print(f"Cancelación con sustitución aceptada: {resultado.aceptada}")


if __name__ == "__main__":
    main()
