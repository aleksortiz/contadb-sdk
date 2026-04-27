"""Ejemplo 06 — REP en moneda extranjera (USD) con factura en MXN.

Caso típico: emitiste una factura en MXN al cliente, pero éste paga en
USD desde el extranjero. El CFDI de pago debe reflejar el ``MonedaP``
real (USD) con su ``TipoCambioP``, y el DoctoRelacionado lleva su
``EquivalenciaDR`` para convertir a la moneda del pago.

Convenciones de tipos de cambio en CRP 2.0 (regla de validación SAT:
``ImpPagado_DR * EquivalenciaDR ≈ Pago.Monto``):

- ``EquivalenciaDR`` convierte importes del DR a la moneda del Pago
  *multiplicando*. Es ``MonedaP / MonedaDR`` en términos de unidades.
- ``TipoCambioP`` convierte importes del Pago a MXN *multiplicando*. Es
  cuántos MXN equivalen a 1 unidad de la moneda del pago.

Caso del ejemplo:
- Factura A1500: $20,000 MXN ($17,241.38 + IVA $2,758.62).
- Cliente paga 1,000 USD el 26-abr cuando el tipo de cambio fue 20.00.
- El DR está en MXN, el Pago está en USD.
- EquivalenciaDR = 0.05 (1 MXN = 0.05 USD; verificación: 20,000 * 0.05 = 1,000).
- TipoCambioP = 20.00 (1 USD = 20 MXN; verificación: 1,000 * 20 = 20,000 MXN).
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    ContaDBClient,
    DoctoRelacionado,
    Emisor,
    Pago,
    PagoBuilder,
    Receptor,
    TrasladoDR,
)


def main() -> None:
    # 1. Carga el CSD
    cert = Certificado.cargar("emisor.cer", "emisor.key", os.environ["CSD_PASSWORD"])

    # 2. Traslado de IVA — los importes del DR se expresan en MonedaDR (MXN)
    traslado = TrasladoDR(
        base=Decimal("17241.38"),
        impuesto="002",
        tipo_factor="Tasa",
        tasa_o_cuota=Decimal("0.16"),
        importe=Decimal("2758.62"),
    )

    # 3. DR en MXN — EquivalenciaDR = MonedaP/MonedaDR = USD/MXN = 0.05
    #    (verificación SAT: 20000 MXN * 0.05 = 1000 USD = Pago.Monto)
    dr = DoctoRelacionado(
        id_documento="cccccccc-dddd-eeee-ffff-000000000000",
        serie="A",
        folio="1500",
        moneda_dr="MXN",
        equivalencia_dr=Decimal("0.05"),  # Requerido cuando MonedaDR != MonedaP
        num_parcialidad=1,
        imp_saldo_ant=Decimal("20000.00"),
        imp_pagado=Decimal("20000.00"),
        imp_saldo_insoluto=Decimal("0.00"),
        objeto_imp_dr="02",
        traslados=[traslado],
    )

    # 4. Pago en USD — tipo_cambio convierte USD a MXN para los Totales
    pago = Pago(
        fecha_pago=datetime(2026, 4, 26, 14, 0, 0),
        forma_pago="03",
        moneda="USD",
        tipo_cambio=Decimal("20.00"),  # Requerido cuando moneda != MXN
        monto=Decimal("1000.00"),  # 1,000 USD = 20,000 MXN
        num_operacion="WIRE-78451",
        rfc_emisor_cta_ord="XEXX010101000",
        nom_banco_ord_ext="CHASE BANK USA",
        documentos=[dr],
    )

    pagos = PagoBuilder()
    pagos.agregar_pago(pago)

    # 5. CFDI tipo "P" con receptor extranjero
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )
    receptor = Receptor(
        rfc="XEXX010101000",  # RFC genérico extranjero
        nombre="ACME CORP",
        uso_cfdi="CP01",
        domicilio_fiscal_receptor="64000",
        regimen_fiscal_receptor="616",  # Sin obligaciones fiscales
        residencia_fiscal="USA",
        num_reg_id_trib="123-45-6789",
    )
    cfdi = CFDIBuilder.para_pago(
        emisor=emisor,
        receptor=receptor,
        serie="P",
        folio="2026-003",
        lugar_expedicion="64000",
    )
    cfdi.agregar_complemento(pagos)

    xml = cfdi.construir_y_firmar(cert)

    # Totales en MXN (siempre):
    #   TotalTrasladosBaseIVA16     = 17,241.38 (base del DR convertida vía Equiv * TipoCambio)
    #   TotalTrasladosImpuestoIVA16 =  2,758.62
    #   MontoTotalPagos             = 20,000.00 (1,000 USD * 20 MXN/USD)

    # 6. Timbra
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        result = client.timbrar(xml)

    print(f"✓ REP en USD timbrado — UUID: {result.uuid}")


if __name__ == "__main__":
    main()
