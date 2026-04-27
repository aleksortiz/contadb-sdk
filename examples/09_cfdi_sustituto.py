"""Emitir un CFDI sustituto de uno cancelado con motivo 01.

Flujo SAT cuando un CFDI fue emitido con errores que el receptor sí
detectó:

1. Emitir el **CFDI sustituto** primero (este script). Lleva un bloque
   ``cfdi:CfdiRelacionados`` con ``TipoRelacion="04"`` (Sustitución de los
   CFDI previos) y el UUID del comprobante a cancelar.
2. Cancelar el comprobante anterior con ``motivo="01"`` y
   ``folio_sustitucion=<UUID del sustituto>``. (Ver ``08_cancelar.py``.)

Otros valores de ``tipo_relacion`` útiles:

- ``"01"`` — Nota de crédito de los documentos relacionados.
- ``"02"`` — Nota de débito de los documentos relacionados.
- ``"03"`` — Devolución de mercancía sobre facturas o traslados previos.
- ``"05"`` — Traslados de mercancías facturados previamente.
- ``"06"`` — Factura generada por los traslados previos.
- ``"07"`` — CFDI por aplicación de anticipo.
"""

from __future__ import annotations

from decimal import Decimal

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    CfdiRelacionados,
    Concepto,
    ContaDBClient,
    Emisor,
    Receptor,
)


def main() -> None:
    # --- 1. Cargar el CSD del emisor ---------------------------------------
    cert = Certificado.cargar(
        cer_path="emisor.cer",
        key_path="emisor.key",
        password="MI_PASSWORD",
    )

    # --- 2. UUID del CFDI que estamos sustituyendo -------------------------
    uuid_anterior = "550e8400-e29b-41d4-a716-446655440000"

    # --- 3. Datos del comprobante (idénticos al anterior, corregidos) ------
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )

    receptor = Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="G03",
        domicilio_fiscal_receptor="65000",
        regimen_fiscal_receptor="601",
    )

    concepto = Concepto(
        clave_prod_serv="43232408",
        clave_unidad="E48",
        descripcion="Servicios de consultoría en sistemas (corregido)",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("1000.00"),
        objeto_imp="02",
        tasa_iva=Decimal("0.16"),
    )

    # --- 4. Bloque CfdiRelacionados con tipo_relacion="04" -----------------
    relacionados = CfdiRelacionados(
        tipo_relacion="04",  # Sustitución de los CFDI previos
        uuids=[uuid_anterior],
    )

    # --- 5. Construir el sustituto -----------------------------------------
    builder = CFDIBuilder(
        emisor=emisor,
        receptor=receptor,
        serie="A",
        folio="1002",  # nuevo folio interno
        forma_pago="03",
        metodo_pago="PUE",
        lugar_expedicion="64000",
        cfdi_relacionados=[relacionados],
    )
    builder.agregar_concepto(concepto)
    xml_sustituto = builder.construir_y_firmar(cert)

    # --- 6. Timbrar el sustituto -------------------------------------------
    with ContaDBClient(api_token="cdb_TU_TOKEN_AQUI") as client:
        resultado = client.timbrar(xml_sustituto)

    print(f"UUID del sustituto: {resultado.uuid}")
    print(f"Saldo restante:     {resultado.saldo_restante}")
    print()
    print("Ahora cancela el CFDI anterior con motivo='01' y este UUID como")
    print("folio_sustitucion. Ver examples/08_cancelar.py.")


if __name__ == "__main__":
    main()
